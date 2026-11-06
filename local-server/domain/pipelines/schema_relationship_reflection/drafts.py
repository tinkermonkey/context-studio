"""
Change-plan rows -> proposal operations (one per relationship type).

Follows DR's `proposal-export.ts`: a row whose replacement triple already
exists, or is produced by an earlier operation of the same proposal, deletes
the relationship type and names that twin as its replacement (Context Studio
has no merge); any other row updates the type's predicate, domain and/or
range. Rows of a breaking kind (retarget, compound, conflict) claim breaking
scope, so an approval policy never applies them.

Each operation carries the plan kind and p, the full ranked answers (top 3
with probabilities, plus every probability as JSON) and the evidence pack the
decision model read.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from domain.ontology.entities import PropertyDefinition
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import ChangeScope, OperationKind, OperationType

from .plan import BREAKING_KINDS, CONFLICT, PlannedChange
from .questions import RelationshipCatalog, Triple

# Completes the fields of an update that changes a relationship type's triple
# (e.g. a new identifier and external reference); given the target and the
# changed canonical_predicate / domain_class_id / range_class_id.
TripleFieldCompleter = Callable[[PropertyDefinition, dict[str, Any]], dict[str, Any]]

_LABELS = {
    "rename-predicate": "Rename the predicate",
    "reverse": "Reverse the direction",
    "retarget": "Retarget",
}


@dataclass(frozen=True)
class PlannedDraft:
    """A plan row and the operation proposed for it."""

    row: PlannedChange
    draft: OperationDraft


def plan_drafts(
    plan: Sequence[PlannedChange],
    catalog: RelationshipCatalog,
    complete_fields: TripleFieldCompleter | None = None,
) -> list[PlannedDraft]:
    """
    One operation per plan row, in plan order (seq from 1).

    A row whose replacement is its own triple (a self-loop 'reversed' onto
    itself) changes nothing and gets no operation.
    """
    props = {p.id: p for p in catalog.relationship_types}
    produced: dict[Triple, str] = {}
    out: list[PlannedDraft] = []
    for row in plan:
        target = props[row.property_id]
        replacement = row.replacement
        if replacement == row.current:
            continue
        seq = len(out) + 1
        common: dict[str, Any] = {
            "seq": seq,
            "kind": OperationKind.PROPERTY,
            "target_id": target.id,
            "evidence": _evidence(row, target),
            "probability": round(row.p, 3),
            "claimed_scope": ChangeScope.BREAKING if row.kind in BREAKING_KINDS else None,
        }
        why = f" Plan kind {row.kind}, p {row.p:.2f}.{_conflict_note(row)}"
        twin = catalog.by_triple.get(replacement)
        twin_id = (
            twin.id if twin is not None and twin.id != target.id else produced.get(replacement)
        )
        if twin_id is not None:
            where = (
                "already exists"
                if twin is not None
                else "is produced by an earlier operation in this proposal"
            )
            draft = OperationDraft(
                op=OperationType.DELETE,
                replacement=twin_id,
                rationale=f"Remove {row.current}: {replacement} {where} and expresses it.{why}",
                **common,
            )
        else:
            fields = _triple_fields(target, replacement, catalog)
            if complete_fields is not None:
                fields = complete_fields(target, fields)
            produced[replacement] = target.id
            label = _LABELS.get(row.kind, "Change")
            draft = OperationDraft(
                op=OperationType.UPDATE,
                fields=fields,
                rationale=f"{label} of {row.current} to {replacement}.{why}",
                **common,
            )
        out.append(PlannedDraft(row, draft))
    return out


def _triple_fields(
    target: PropertyDefinition, replacement: Triple, catalog: RelationshipCatalog
) -> dict[str, Any]:
    """The changed predicate, domain and range."""
    fields: dict[str, Any] = {}
    if replacement.predicate != (target.canonical_predicate or target.identifier):
        fields["canonical_predicate"] = replacement.predicate
    domain = catalog.class_id(replacement.source)
    range_ = catalog.class_id(replacement.target)
    if domain != target.domain_class_id:
        fields["domain_class_id"] = domain
    if range_ != target.range_class_id:
        fields["range_class_id"] = range_
    return fields


def _conflict_note(row: PlannedChange) -> str:
    if row.kind != CONFLICT:
        return ""
    return (
        " Another reflection in this run disagrees: the replacement, or this type, is"
        " itself proposed for change."
    )


def _evidence(row: PlannedChange, target: PropertyDefinition) -> list[dict[str, str]]:
    reflection = row.reflection
    item = {
        "quote": reflection.summary(),
        "entity_id": target.id,
        "plan_kind": row.kind,
        "p": f"{row.p:.3f}",
        "alternatives": "; ".join(row.alternatives),
        "replacement": str(row.replacement),
        "probabilities": json.dumps(
            {q: dict(a.probabilities) for q, a in reflection.answers.items()},
            sort_keys=True,
        ),
    }
    for question, answer in reflection.answers.items():
        item[question] = answer.top3()
    items = [item]
    if reflection.evidence:
        items.append(
            {"quote": reflection.evidence, "entity_id": target.id, "label": "Evidence pack"}
        )
    return items
