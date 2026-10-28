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
    relationship_identifier,
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
    if plan.get("format") != PLAN_FORMAT:
        raise PlanError([f"{path}: format is {plan.get('format')!r}, expected {PLAN_FORMAT}"])
    return plan


class _Workspace:
    """DR-keyed lookups over the workspace: property definitions and classes by DR id."""

    def __init__(self, repo: OntologyRepository):
        self.repo = repo
        self.properties = {
            ref.identifier: prop
            for prop in repo.list_property_definitions(limit=None)
            for ref in prop.external_references
            if ref.source == DR_SOURCE
        }
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

    def identifier_taken(self, identifier: str, own_id: str | None) -> bool:
        holder = self.repo.get_property_definition_by_identifier(identifier)
        if holder is not None:
            return holder.id != own_id
        return self.repo.get_by_identifier(identifier) is not None


def drafts_for(plan: dict[str, Any], workspace: _Workspace) -> list[OperationDraft]:
    """
    One OperationDraft per plan operation, in Context Studio's vocabulary.

    Raises:
        PlanError: Listing every operation whose target, spec nodes or fields
            don't resolve against the workspace
    """
    drafts: list[OperationDraft] = []
    problems: list[str] = []
    for item in plan.get("operations", []):
        seq = item.get("seq")
        try:
            drafts.append(_draft(item, workspace))
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(f"seq {seq} ({item.get('op')} {item.get('target_id')}): {exc}")
    if problems:
        raise PlanError(problems)
    return drafts


def _draft(item: dict[str, Any], workspace: _Workspace) -> OperationDraft:
    if item.get("kind") != "property":
        raise ValueError(f"kind {item.get('kind')!r} is not supported (only 'property')")
    op = OperationType(item["op"])
    fields = dict(item.get("fields") or {})
    unknown = sorted(set(fields) - _DR_FIELDS)
    if unknown:
        raise ValueError(f"unknown fields {unknown}")
    common: dict[str, Any] = {
        "seq": int(item["seq"]),
        "op": op,
        "kind": OperationKind.PROPERTY,
        "rationale": item.get("rationale"),
        "evidence": list(item.get("evidence") or []),
        "probability": item.get("probability"),
    }
    if op is OperationType.CREATE:
        new = Triple.parse(fields["relationship_id"])
        return OperationDraft(
            **common, ref=item.get("ref"), fields=_create_fields(new, fields, workspace)
        )

    target = workspace.properties.get(item.get("target_id") or "")
    if target is None:
        raise ValueError("no property definition has this DR relationship id")
    if op is OperationType.DELETE:
        return OperationDraft(**common, target_id=target.id)
    if op is not OperationType.UPDATE:
        raise ValueError(f"op {op.value!r} is not supported")
    return OperationDraft(
        **common,
        target_id=target.id,
        fields=_update_fields(item["target_id"], target, fields, workspace),
    )


def _create_fields(new: Triple, fields: dict[str, Any], workspace: _Workspace) -> dict[str, Any]:
    return {
        "identifier": relationship_identifier(
            new.record(), lambda ident: workspace.identifier_taken(ident, None)
        ),
        "title": fields.get("title") or new.record().title,
        "description": fields.get("description"),
        "canonical_predicate": new.predicate,
        "domain_class_id": workspace.class_id(new.source),
        "range_class_id": workspace.class_id(new.destination),
        "external_references": [ExternalReference(source=DR_SOURCE, identifier=new.id).to_dict()],
    }


def _update_fields(
    relationship_id: str, target: Any, fields: dict[str, Any], workspace: _Workspace
) -> dict[str, Any]:
    """Only the changed fields; a new triple also brings a new identifier and DR reference."""
    if not fields:
        raise ValueError("an update needs at least one field")
    current = Triple.parse(relationship_id)
    new = Triple(
        fields.get("source_spec_node_id", current.source),
        fields.get("predicate", current.predicate),
        fields.get("destination_spec_node_id", current.destination),
    )
    mapped: dict[str, Any] = {}
    for name in ("title", "description"):
        if name in fields:
            mapped[name] = fields[name]
    if new.predicate != current.predicate:
        mapped["canonical_predicate"] = new.predicate
    if new.source != current.source:
        mapped["domain_class_id"] = workspace.class_id(new.source)
    if new.destination != current.destination:
        mapped["range_class_id"] = workspace.class_id(new.destination)
    if new != current:
        mapped["identifier"] = relationship_identifier(
            new.record(), lambda ident: workspace.identifier_taken(ident, target.id)
        )
        mapped["external_references"] = [
            (
                ExternalReference(
                    source=ref.source, identifier=new.id, uri=ref.uri, metadata=ref.metadata
                )
                if ref.source == DR_SOURCE and ref.identifier == relationship_id
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
        PlanError: If an operation doesn't resolve against the workspace
        ProposalValidationError: If ProposalService finds the operations invalid
    """
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
