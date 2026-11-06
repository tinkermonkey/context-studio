"""
Change-plan rows -> proposal operations (one per relationship type).

Follows DR's `proposal-export.ts`: a row whose replacement triple already
exists, or is produced by an earlier operation of the same proposal, deletes
the relationship type and names that twin as its replacement (Context Studio
has no merge); any other row updates the type's predicate, domain and/or
range. Rows of a breaking kind (retarget, compound, conflict) claim breaking
scope, so an approval policy never applies them.

Each operation carries the plan kind and p, the full ranked answers (top 3
with probabilities, plus every probability as JSON), the current triple, the
plan's pick per question, the class id of each class option, and the evidence
pack the decision model read. `reflection_view` reads them back for a reviewer.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from domain.decision.value_objects import NONE_OPTION
from domain.ontology.entities import PropertyDefinition
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import ChangeScope, OperationKind, OperationType

from .plan import BREAKING_KINDS, CONFLICT, PlannedChange
from .questions import (
    PREDICATE_FOR,
    QUESTION_NAMES,
    SOURCE_FOR,
    TARGET_FOR,
    RelationshipCatalog,
    Triple,
)

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
            "evidence": _evidence(row, target, catalog),
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


def _evidence(
    row: PlannedChange, target: PropertyDefinition, catalog: RelationshipCatalog
) -> list[dict[str, str]]:
    reflection = row.reflection
    current = row.current
    labels = {
        option
        for question in (SOURCE_FOR, TARGET_FOR)
        if question in reflection.answers
        for option in reflection.answers[question].probabilities
    } | {current.source, current.target}
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
        "current": json.dumps(
            {"source": current.source, "predicate": current.predicate, "target": current.target}
        ),
        "picks": json.dumps(_picks(row), sort_keys=True),
        "class_ids": json.dumps(
            {label: catalog.class_id(label) for label in sorted(labels) if catalog.class_id(label)},
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


def _current_answers(current: Triple) -> dict[str, str]:
    return {
        SOURCE_FOR: current.source,
        TARGET_FOR: current.target,
        PREDICATE_FOR: current.predicate,
    }


def _picks(row: PlannedChange) -> dict[str, str]:
    """The plan's answer per question: the alternative that won, else the current one."""
    return {**_current_answers(row.current), **_alternative_picks(row.alternatives)}


# ------------------------------------------------------------------ reading back


@dataclass(frozen=True)
class AnswerOption:
    """One option of a sorting question as a reviewer sees it."""

    option: str
    probability: float
    # The class the option names (source and target questions); None for a
    # predicate, 'none', or a proposal recorded before class ids were kept
    class_id: str | None
    current: bool
    plan: bool


@dataclass(frozen=True)
class ReflectionView:
    """What a reflection operation's evidence says, for review."""

    plan_kind: str
    p: float | None
    current: Triple | None
    replacement: str | None
    answers: dict[str, list[AnswerOption]]
    # The evidence pack's blocks (design intent, attributes, the pair's types, ...)
    evidence_pack: list[str]


def reflection_view(evidence: Sequence[Mapping[str, Any]]) -> ReflectionView | None:
    """
    Read back the plan row `plan_drafts` stored on an operation.

    Every option of each question, likeliest first, marked current and plan
    (a current or plan answer under 1% is listed last, at 0).
    Operations recorded before the current triple, picks and class ids were
    kept read their picks from the alternatives and have no current marks.

    Returns:
        None when the evidence is not a reflection plan row's
    """
    item = next((e for e in evidence if isinstance(e, Mapping) and "plan_kind" in e), None)
    if item is None:
        return None
    probabilities = _json(item.get("probabilities"))
    current_json = _json(item.get("current"))
    current = (
        Triple(current_json["source"], current_json["predicate"], current_json["target"])
        if {"source", "predicate", "target"} <= current_json.keys()
        else None
    )
    picks = {k: v for k, v in _json(item.get("picks")).items() if isinstance(v, str)}
    if not picks:
        picks = _alternative_picks(str(item.get("alternatives") or "").split("; "))
    if current is not None:
        picks = {**_current_answers(current), **picks}
    class_ids = _json(item.get("class_ids"))
    currents = _current_answers(current) if current is not None else {}
    answers: dict[str, list[AnswerOption]] = {}
    for question in QUESTION_NAMES:
        options = probabilities.get(question)
        if not isinstance(options, Mapping):
            continue
        ranked = sorted(
            ((str(k), float(v)) for k, v in options.items()), key=lambda kv: (-kv[1], kv[0])
        )
        listed = {option for option, _ in ranked}
        for marked in dict.fromkeys((currents.get(question), picks.get(question))):
            if marked and marked not in listed:
                ranked.append((marked, 0.0))
        answers[question] = [
            AnswerOption(
                option=option,
                probability=probability,
                class_id=(
                    class_ids.get(option)
                    if question != PREDICATE_FOR and option != NONE_OPTION
                    else None
                ),
                current=currents.get(question) == option,
                plan=picks.get(question) == option,
            )
            for option, probability in ranked
        ]
    pack = next(
        (
            e.get("quote")
            for e in evidence
            if isinstance(e, Mapping) and e.get("label") == "Evidence pack"
        ),
        None,
    )
    return ReflectionView(
        plan_kind=str(item["plan_kind"]),
        p=_number(item.get("p")),
        current=current,
        replacement=item.get("replacement") if isinstance(item.get("replacement"), str) else None,
        answers=answers,
        evidence_pack=(
            [block.strip() for block in pack.split("\n\n") if block.strip()]
            if isinstance(pack, str)
            else []
        ),
    )


def _json(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _alternative_picks(alternatives: Sequence[str]) -> dict[str, str]:
    """['source=x|0.81', 'predicate=reverse:p|0.70'] -> {source_for: x, predicate_for: ...}."""
    picks = {}
    for alternative in filter(None, (a.strip() for a in alternatives)):
        name, _, rest = alternative.partition("=")
        picks[f"{name}_for"] = rest.rpartition("|")[0] or rest
    return picks
