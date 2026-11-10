"""
The DR spec's predicate catalog rules (#1481).

A DR predicate (a predicate with a `documentation_robotics` reference) keeps
DR's own fields in that reference's metadata: inverse, category,
archimate_alignment and semantics ({directionality, transitivity, symmetry,
reflexivity}). Context Studio doesn't reason over them, but DR's landing
checks them against `spec/schemas/base/predicate-catalog.schema.json`, so a
proposal is checked against the same enums as it applies, and a create must
give everything DR's catalog requires.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from adapters.interchange.dr_relationships import DR_PREDICATE_KEYS, DR_SOURCE
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import ExternalReference
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationType,
    ProposedOperation,
)

# The enums of DR's predicate-catalog.schema.json
DR_PREDICATE_CATEGORIES = frozenset(
    {
        "motivation",
        "business",
        "security",
        "application",
        "technology",
        "api",
        "data",
        "data-store",
        "ux",
        "navigation",
        "apm",
        "testing",
        "structural",
        "behavioral",
        "dependency",
        "traceability",
        "governance",
    }
)
DR_ARCHIMATE_ALIGNMENTS = frozenset(
    {
        "Composition",
        "Aggregation",
        "Assignment",
        "Realization",
        "Serving",
        "Access",
        "Influence",
        "Triggering",
        "Flow",
        "Specialization",
        "Association",
    }
)
DR_DIRECTIONALITIES = frozenset({"unidirectional", "bidirectional"})
DR_SEMANTIC_FLAGS = ("transitivity", "symmetry", "reflexivity")
DR_SEMANTICS_KEYS = ("directionality", *DR_SEMANTIC_FLAGS)


def dr_predicate_reference(predicate_id: str, entry: Mapping[str, Any]) -> ExternalReference:
    """A spec catalog entry's DR reference for its predicate, carrying its DR-only fields."""
    metadata = {key: entry[key] for key in DR_PREDICATE_KEYS if key in entry}
    return ExternalReference(
        source=DR_SOURCE, identifier=predicate_id, metadata=MappingProxyType(metadata)
    )


def dr_predicate_metadata(references: Any) -> dict[str, Any] | None:
    """The metadata of the DR reference among references (dicts or objects); None if none."""
    for ref in references or []:
        source = ref.get("source") if isinstance(ref, dict) else getattr(ref, "source", None)
        if source == DR_SOURCE:
            metadata = ref.get("metadata") if isinstance(ref, dict) else ref.metadata
            return dict(metadata or {})
    return None


def dr_predicate_problems(metadata: Mapping[str, Any], creating: bool) -> list[str]:
    """
    How a DR predicate's metadata breaks DR's catalog schema. With `creating`
    (a create, or an update that sets the DR reference: Context Studio keeps
    the whole entry, and the export sends only what changed) inverse, category
    and all four semantics are required; otherwise only the given fields are
    checked.
    """
    problems: list[str] = []
    unknown = sorted(set(metadata) - set(DR_PREDICATE_KEYS))
    if unknown:
        problems.append(f"unknown DR predicate fields {unknown}")
    if creating:
        missing = [key for key in ("inverse", "category", "semantics") if key not in metadata]
        if missing:
            problems.append(f"a DR predicate needs {', '.join(missing)}")
    inverse = metadata.get("inverse", "")
    if "inverse" in metadata and (not isinstance(inverse, str) or not inverse.strip()):
        problems.append("inverse must be a predicate name")
    if "category" in metadata and metadata["category"] not in DR_PREDICATE_CATEGORIES:
        problems.append(
            f"category {metadata['category']!r} isn't one of {sorted(DR_PREDICATE_CATEGORIES)}"
        )
    alignment = metadata.get("archimate_alignment")
    if alignment is not None and alignment not in DR_ARCHIMATE_ALIGNMENTS:
        problems.append(
            f"archimate_alignment {alignment!r} isn't one of"
            f" {sorted(DR_ARCHIMATE_ALIGNMENTS)} or null"
        )
    if "semantics" in metadata:
        problems += _semantics_problems(metadata["semantics"], creating)
    return problems


def _semantics_problems(semantics: Any, creating: bool) -> list[str]:
    if not isinstance(semantics, dict):
        return ["semantics must be an object"]
    problems: list[str] = []
    unknown = sorted(set(semantics) - set(DR_SEMANTICS_KEYS))
    if unknown:
        problems.append(f"unknown semantics fields {unknown}")
    missing = [key for key in DR_SEMANTICS_KEYS if key not in semantics]
    if creating and missing:
        problems.append(f"semantics needs {', '.join(missing)}")
    if "directionality" in semantics and semantics["directionality"] not in DR_DIRECTIONALITIES:
        problems.append(
            f"directionality {semantics['directionality']!r} isn't one of"
            f" {sorted(DR_DIRECTIONALITIES)}"
        )
    for flag in DR_SEMANTIC_FLAGS:
        if flag in semantics and not isinstance(semantics[flag], bool):
            problems.append(f"{flag} must be true or false")
    return problems


class DrPredicateRules:
    """
    ProposalApplyRules for DR predicates: a predicate create or update whose
    references carry a DR reference, or an update of a predicate that has one,
    is checked against DR's catalog schema as it applies. The DR reference it
    sets holds the whole entry (inverse, category, semantics; archimate_alignment
    optional), and its description, which DR's catalog requires, can't be empty.
    """

    def __init__(self, repo: OntologyRepository) -> None:
        self._repo = repo

    def governs(self, operation: ProposedOperation, fields: dict[str, Any]) -> bool:
        if operation.kind is not OperationKind.PREDICATE or operation.op not in (
            OperationType.CREATE,
            OperationType.UPDATE,
        ):
            return False
        if dr_predicate_metadata(fields.get("external_references")) is not None:
            return True
        target = self._repo.get_predicate(operation.target_id) if operation.target_id else None
        return target is not None and dr_predicate_metadata(target.external_references) is not None

    def prepare(
        self,
        proposal: ChangeProposal,
        operation: ProposedOperation,
        fields: dict[str, Any],
        other_edits: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        return fields  # reviewers edit relationship types only

    def check(self, operation: ProposedOperation, fields: dict[str, Any]) -> None:
        creating = operation.op is OperationType.CREATE
        problems: list[str] = []
        if "external_references" in fields or creating:
            metadata = dr_predicate_metadata(fields.get("external_references"))
            if metadata is None:
                problems.append("a DR predicate keeps its DR reference")
            else:
                problems += dr_predicate_problems(metadata, creating=True)
        if (creating or "description" in fields) and not (fields.get("description") or "").strip():
            problems.insert(0, "a DR predicate needs a description")
        if problems:
            raise ValueError("; ".join(problems))
