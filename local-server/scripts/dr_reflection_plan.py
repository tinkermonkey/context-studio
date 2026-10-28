"""
DR reflection plans -> change proposals, and decisions back to DR.

Documentation Robotics (DR) exports a layer's spec-refinement plan as a
`dr-reflection-plan/1` file (`cli/scripts/spec-enrich/proposal-export.ts` in
the DR repo, whose header holds the contract). Each operation creates, updates
or deletes one relationship schema, which Context Studio holds as a property
definition keyed back to DR by an external reference (source
"documentation_robotics", identifier "{source}.{predicate}.{destination}"; see
`dr_ontology_loader.py`).

`import_reflection_plan` resolves every operation against the workspace and
proposes them, through ProposalService, as one change proposal on the
`dr_spec` taxonomy. DR's fields are mapped onto Context Studio's: predicate ->
canonical_predicate, source/destination spec node -> domain/range class, and a
new triple -> a new identifier and DR reference. DR's `base` and `dr`
bookkeeping are ignored; Context Studio captures its own base. Each
operation keeps DR's seq, the join key for the decisions coming back.

`decisions_for` writes the decisions file DR's `proposal-import.ts
--decisions` reads: one `{seq, op_id, status, reason, result_entity_id}` per
operation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain.ontology.entities import PropertyDefinition
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import ExternalReference
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
from scripts.dr_ontology_loader import (
    DR_SOURCE,
    DR_TAXONOMY_IDENTIFIER,
    RelationshipSchemaRecord,
    assign_relationship_identifiers,
    dr_property_definitions,
)

PLAN_FORMAT = "dr-reflection-plan/1"
_DR_FIELDS = frozenset(
    {
        "predicate",
        "source_spec_node_id",
        "destination_spec_node_id",
        "title",
        "description",
        "relationship_id",
    }
)


class PlanError(ValueError):
    """The plan can't be proposed; `problems` lists each one, by seq."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class Triple:
    """A DR relationship id split into its parts."""

    source: str
    predicate: str
    destination: str

    @classmethod
    def parse(cls, relationship_id: str) -> "Triple":
        """'api.operation.delivers.api.response' -> (api.operation, delivers, api.response)."""
        parts = relationship_id.split(".")
        if len(parts) != 5 or not all(parts):
            raise ValueError(
                f"'{relationship_id}' is not a {{source}}.{{predicate}}.{{destination}} id"
            )
        return cls(f"{parts[0]}.{parts[1]}", parts[2], f"{parts[3]}.{parts[4]}")

    @property
    def id(self) -> str:
        return f"{self.source}.{self.predicate}.{self.destination}"

    def record(self) -> RelationshipSchemaRecord:
        return RelationshipSchemaRecord(
            source_spec_node_id=self.source,
            source_layer=self.source.split(".")[0],
            destination_spec_node_id=self.destination,
            destination_layer=self.destination.split(".")[0],
            predicate=self.predicate,
            title=f"{self.source} {self.predicate} {self.destination}",
            description=None,
        )


def read_plan(path: Path) -> dict[str, Any]:
    """Read a dr-reflection-plan/1 file."""
    plan = json.loads(Path(path).read_text())
    _check_shape(plan, str(path))
    return plan


def _check_shape(plan: Any, label: str = "plan") -> None:
    if not isinstance(plan, dict):
        raise PlanError([f"{label}: not a JSON object"])
    if plan.get("format") != PLAN_FORMAT:
        raise PlanError([f"{label}: format is {plan.get('format')!r}, expected {PLAN_FORMAT}"])
    if not isinstance(plan.get("operations"), list):
        raise PlanError([f"{label}: operations is not a list"])


class _Workspace:
    """DR-keyed lookups over the workspace: property definitions and classes by DR id."""

    def __init__(self, repo: OntologyRepository):
        self.repo = repo
        self.properties = dr_property_definitions(repo)
        taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
        if taxonomy is None:
            raise PlanError([f"No '{DR_TAXONOMY_IDENTIFIER}' taxonomy; import the DR spec first"])
        self.taxonomy_id = taxonomy.id
        self.classes = {
            ref.identifier: cls.id
            for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None)
            for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None)
            for ref in cls.external_references
            if ref.source == DR_SOURCE
        }

    def class_id(self, spec_node_id: str) -> str:
        found = self.classes.get(spec_node_id)
        if found is None:
            raise ValueError(f"no class for spec node {spec_node_id}")
        return found


@dataclass
class _Planned:
    """One plan operation resolved against the workspace."""

    item: dict[str, Any]
    op: OperationType
    target: PropertyDefinition | None  # update, delete
    current: Triple | None  # update, delete: the target's DR id
    new: Triple | None  # create, and an update that changes the triple

    @property
    def seq(self) -> int:
        return int(self.item["seq"])

    @property
    def label(self) -> str:
        return f"seq {self.seq} ({self.op.value} {self.item.get('target_id')})"


def drafts_for(plan: dict[str, Any], workspace: _Workspace) -> list[OperationDraft]:
    """
    One OperationDraft per plan operation, in Context Studio's vocabulary.

    Raises:
        PlanError: Listing every operation that can't be proposed: its target,
            spec nodes or fields don't resolve; it renames onto a relationship
            type that already exists; or it shares a target or a new triple with
            another operation
    """
    _check_shape(plan)
    planned: list[_Planned] = []
    problems: list[str] = []
    for index, item in enumerate(plan["operations"], start=1):
        if not isinstance(item, dict):
            problems.append(f"operation {index}: not an object")
            continue
        try:
            planned.append(_resolve(item, workspace))
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(
                f"seq {item.get('seq')} ({item.get('op')} {item.get('target_id')}): {exc}"
            )
    if not problems:
        problems = _clashes(planned, workspace)
    if problems:
        raise PlanError(problems)

    try:
        identifiers = _identifiers_after(planned, workspace)
    except ValueError as exc:
        raise PlanError([str(exc)]) from exc
    return [_draft(p, workspace, identifiers) for p in planned]


def _resolve(item: dict[str, Any], workspace: _Workspace) -> _Planned:
    if item.get("kind") != "property":
        raise ValueError(f"kind {item.get('kind')!r} is not supported (only 'property')")
    int(item["seq"])
    op = OperationType(item["op"])
    fields = item.get("fields") or {}
    if not isinstance(fields, dict):
        raise ValueError("fields is not an object")
    unknown = sorted(set(fields) - _DR_FIELDS)
    if unknown:
        raise ValueError(f"unknown fields {unknown}")
    if op is OperationType.CREATE:
        return _Planned(item, op, None, None, Triple.parse(fields["relationship_id"]))
    if op not in (OperationType.UPDATE, OperationType.DELETE):
        raise ValueError(f"op {op.value!r} is not supported")
    target = workspace.properties.get(item.get("target_id") or "")
    if target is None:
        raise ValueError("no property definition has this DR relationship id")
    current = Triple.parse(item["target_id"])
    if op is OperationType.DELETE:
        return _Planned(item, op, target, current, None)
    if not fields:
        raise ValueError("an update needs at least one field")
    new = Triple(
        fields.get("source_spec_node_id", current.source),
        fields.get("predicate", current.predicate),
        fields.get("destination_spec_node_id", current.destination),
    )
    for node in (new.source, new.destination):
        workspace.class_id(node)
    return _Planned(item, op, target, current, new if new != current else None)


def _clashes(planned: list[_Planned], workspace: _Workspace) -> list[str]:
    """Operations that could only fail: onto an existing triple, or sharing one."""
    problems = [
        f"{p.label}: {p.new.id} already exists"
        for p in planned
        if p.new is not None and p.new.id in workspace.properties
    ]
    for kind, key in (("target", "current"), ("produce", "new")):
        seqs: dict[str, list[int]] = {}
        for p in planned:
            triple = getattr(p, key)
            if triple is not None:
                seqs.setdefault(triple.id, []).append(p.seq)
        for triple_id, found in seqs.items():
            if len(found) > 1:
                listed = ", ".join(str(s) for s in found[:-1]) + f" and {found[-1]}"
                problems.append(f"seqs {listed} both {kind} {triple_id}")
    return problems


def _identifiers_after(planned: list[_Planned], workspace: _Workspace) -> dict[str, str]:
    """
    Each relationship type's identifier in the spec the plan produces, as a
    re-import of that spec computes it (see assign_relationship_identifiers).
    """
    owners: dict[str, str | None] = {}
    for relationship_id, prop in workspace.properties.items():
        try:
            Triple.parse(relationship_id)
        except ValueError:
            continue
        owners[relationship_id] = prop.id
    for p in planned:
        if p.current is not None and (p.op is OperationType.DELETE or p.new is not None):
            owners.pop(p.current.id, None)
        if p.new is not None:
            owners[p.new.id] = p.target.id if p.target is not None else None
    records = [Triple.parse(relationship_id).record() for relationship_id in owners]
    return assign_relationship_identifiers(records, workspace.repo, owners)


def _draft(p: _Planned, workspace: _Workspace, identifiers: dict[str, str]) -> OperationDraft:
    item = p.item
    common: dict[str, Any] = {
        "seq": p.seq,
        "op": p.op,
        "kind": OperationKind.PROPERTY,
        "rationale": item.get("rationale"),
        "evidence": list(item.get("evidence") or []),
        "probability": item.get("probability"),
    }
    fields = item.get("fields") or {}
    if p.op is OperationType.CREATE:
        new = p.new
        assert new is not None
        return OperationDraft(
            **common,
            ref=item.get("ref"),
            fields={
                "identifier": identifiers[new.id],
                "title": fields.get("title") or new.record().title,
                "description": fields.get("description"),
                "canonical_predicate": new.predicate,
                "domain_class_id": workspace.class_id(new.source),
                "range_class_id": workspace.class_id(new.destination),
                "external_references": [
                    ExternalReference(source=DR_SOURCE, identifier=new.id).to_dict()
                ],
            },
        )
    assert p.target is not None and p.current is not None
    if p.op is OperationType.DELETE:
        return OperationDraft(**common, target_id=p.target.id)
    return OperationDraft(
        **common, target_id=p.target.id, fields=_update_fields(p, fields, workspace, identifiers)
    )


def _update_fields(
    p: _Planned, fields: dict[str, Any], workspace: _Workspace, identifiers: dict[str, str]
) -> dict[str, Any]:
    """Only the changed fields; a new triple also brings a new identifier and DR reference."""
    current, new, target = p.current, p.new, p.target
    assert current is not None and target is not None
    mapped: dict[str, Any] = {
        name: fields[name] for name in ("title", "description") if name in fields
    }
    if new is None:
        return mapped
    if new.predicate != current.predicate:
        mapped["canonical_predicate"] = new.predicate
    if new.source != current.source:
        mapped["domain_class_id"] = workspace.class_id(new.source)
    if new.destination != current.destination:
        mapped["range_class_id"] = workspace.class_id(new.destination)
    mapped["identifier"] = identifiers[new.id]
    mapped["external_references"] = [
        (
            ExternalReference(
                source=ref.source, identifier=new.id, uri=ref.uri, metadata=ref.metadata
            )
            if ref.source == DR_SOURCE and ref.identifier == current.id
            else ref
        ).to_dict()
        for ref in target.external_references
    ]
    return mapped


def import_reflection_plan(
    plan: dict[str, Any], proposal_service: ProposalService, repo: OntologyRepository
) -> ChangeProposal:
    """
    Propose a reflection plan as one change proposal on the dr_spec taxonomy.

    Raises:
        PlanError: If the plan is malformed or an operation can't be proposed
        ProposalValidationError: If ProposalService finds the operations invalid
    """
    _check_shape(plan)
    workspace = _Workspace(repo)
    drafts = drafts_for(plan, workspace)
    return proposal_service.propose(
        taxonomy_id=workspace.taxonomy_id,
        title=plan.get("title") or f"DR reflection plan: {plan.get('layer')} layer",
        operations=drafts,
        source=ProposalSource.PIPELINE,
        rationale=plan.get("rationale"),
        source_detail=plan.get("source_detail"),
    )


def decisions_for(proposal: ChangeProposal) -> list[dict[str, Any]]:
    """
    The decisions file for DR's `proposal-import.ts --decisions`, joined by seq.

    Pending operations are included with status "pending", which DR skips.

    Raises:
        ValueError: If the proposal was reverted, so none of it stands
    """
    if proposal.status is ProposalStatus.REVERTED:
        raise ValueError(
            f"Change proposal {proposal.id} was reverted; its decisions no longer hold"
        )
    return [
        {
            "seq": operation.seq,
            "op_id": operation.id,
            "status": operation.status.value,
            "reason": operation.reason,
            "result_entity_id": operation.result_entity_id,
        }
        for operation in proposal.operations
    ]
