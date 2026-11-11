"""
A schema-extraction run's candidates on a source as proposal operations (#1552).

The same rules as applying a run (`apply_service.py`) decide what is new: a
class candidate whose title (by `class_title_key`) the taxonomy already has,
or a property candidate whose identifier (its label slugified) a relationship
type already has, is skipped.

- A new class is a class create in the taxonomy's first concept scheme (a
  reviewer can edit it before applying), with its proposed definition as its
  description and an identifier slugified from its title (`class_identifier`).
- A new property is a relationship-type create whose predicate is its
  identifier, preceded by a predicate create when the taxonomy's catalog
  lacks it; its domain and range are the classes its proposed domain and range
  name (existing, or "$ref" of a class create), when they name one.

Each create carries the candidate's passages as evidence (its first
MAX_PASSAGES occurrences: a term can occur on every page) and its confidence
as probability. Connections between candidate classes are not proposed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import validate_identifier
from domain.pipelines.schema_extraction.apply_service import (
    class_title_index,
    class_title_key,
    slugify,
    taxonomy_classes,
)
from domain.pipelines.source_operations import (
    OperationPlan,
    PlannedOperation,
    best_probability,
    passage_evidence,
)
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import OperationKind, OperationType

MAX_PASSAGES = 10
MAX_IDENTIFIER_CHARS = 64


def plan_schema_operations(
    candidates: Sequence[dict[str, Any]],
    repo: OntologyRepository,
    taxonomy_id: str,
    source_id: str,
    page_starts: Sequence[int],
) -> OperationPlan:
    """
    Plan a run's class and property candidates as class, predicate and
    relationship-type creates.

    Args:
        candidates: The run's candidates ({kind: class | property_definition, ...})
        repo: The ontology, for existing classes, relationship types and predicates
        taxonomy_id: The taxonomy the run extracted for
        source_id: The source the passages are in
        page_starts: Offset at which each of its pages starts
    """
    plan = OperationPlan()
    schemes = repo.list_concept_schemes(
        taxonomy_id=taxonomy_id, limit=None, sort_by="created_at", sort_order="asc"
    )
    # Title key -> an existing class id, or "$ref" of a class create
    classes: dict[str, str] = {
        key: cls.id for key, cls in class_title_index(taxonomy_classes(repo, taxonomy_id)).items()
    }
    # Identifiers the plan's creates take. Identifiers are unique across classes
    # and relationship types, so the property candidates' identifiers (their
    # slugified labels) are reserved before any class takes one.
    identifiers: set[str] = {
        slugify(str(c.get("label") or "")) for c in candidates if c.get("kind") != "class"
    }

    def add(
        draft_fields: dict[str, Any],
        kind: OperationKind,
        ref: str,
        candidate: dict[str, Any],
        label: str,
        needs: frozenset[str] = frozenset(),
    ) -> None:
        plan.operations.append(
            PlannedOperation(
                draft=OperationDraft(
                    seq=len(plan.operations) + 1,
                    op=OperationType.CREATE,
                    kind=kind,
                    ref=ref,
                    fields=draft_fields,
                    evidence=_evidence(candidate, source_id, page_starts),
                    probability=best_probability(candidate.get("confidence")),
                ),
                label=label,
                needs=needs,
            )
        )

    for candidate in candidates:
        if candidate.get("kind") != "class":
            continue
        label = str(candidate.get("label") or "").strip()
        key = class_title_key(label)
        if not key:
            plan.skip("(no label)", "invalid")
            continue
        if key in classes:
            plan.skip(label, "exists")
            continue
        if not schemes:
            plan.skip(label, "no_scheme")
            continue
        ref = f"c{len(plan.operations) + 1}"
        identifier = class_identifier(label, repo, identifiers)
        identifiers.add(identifier)
        fields: dict[str, Any] = {
            "concept_scheme_id": schemes[0].id,
            "title": label,
            "identifier": identifier,
        }
        if candidate.get("proposed_definition"):
            fields["description"] = str(candidate["proposed_definition"])
        add(fields, OperationKind.CLASS, ref, candidate, label)
        classes[key] = f"${ref}"

    # Predicate identifier -> ref of the predicate create
    predicates: dict[str, str] = {}
    properties: set[str] = set()
    for candidate in candidates:
        if candidate.get("kind") != "property_definition":
            continue
        label = str(candidate.get("label") or "").strip()
        identifier = slugify(label)
        if not identifier or not identifier[0].isalpha():
            plan.skip(label or "(no label)", "invalid")
            continue
        if identifier in properties or repo.get_property_definition_by_identifier(identifier):
            plan.skip(label, "exists")
            continue
        properties.add(identifier)
        if repo.get_predicate_by_identifier(taxonomy_id, identifier) is None:
            predicates[identifier] = f"p{len(plan.operations) + 1}"
            add(
                {"identifier": identifier},
                OperationKind.PREDICATE,
                predicates[identifier],
                candidate,
                f"predicate {identifier}",
            )
        fields = {"identifier": identifier, "title": label, "canonical_predicate": identifier}
        if candidate.get("proposed_definition"):
            fields["description"] = str(candidate["proposed_definition"])
        needs = {predicates[identifier]} if identifier in predicates else set()
        for name, end in (
            ("domain_class_id", "proposed_domain"),
            ("range_class_id", "proposed_range"),
        ):
            class_id = classes.get(class_title_key(candidate.get(end)))
            if class_id:
                fields[name] = class_id
                if class_id.startswith("$"):
                    needs.add(class_id[1:])
        ref = f"r{len(plan.operations) + 1}"
        add(fields, OperationKind.PROPERTY, ref, candidate, label, frozenset(needs))
    return plan


def class_identifier(title: str, repo: OntologyRepository, taken: set[str]) -> str:
    """
    A new class's identifier: its title slugified ("Heating System" ->
    "heating_system"), prefixed "class_" when that isn't a valid identifier
    (a lowercase letter first, 2-64 characters), and suffixed "_2", "_3", ...
    while an existing taxonomy, scheme, class or relationship type, or another
    create of the proposal (`taken`), has it. Identifiers are unique across
    every kind of entity.
    """
    base = slugify(title)[:MAX_IDENTIFIER_CHARS]
    try:
        validate_identifier(base)
    except ValueError:
        base = f"class_{base}".rstrip("_")[:MAX_IDENTIFIER_CHARS]
    identifier, n = base, 1
    while (
        identifier in taken
        or repo.get_by_identifier(identifier) is not None
        or repo.get_property_definition_by_identifier(identifier) is not None
    ):
        n += 1
        suffix = f"_{n}"
        identifier = base[: MAX_IDENTIFIER_CHARS - len(suffix)] + suffix
    return identifier


def _evidence(
    candidate: dict[str, Any], source_id: str, page_starts: Sequence[int]
) -> list[dict[str, Any]]:
    provenance = candidate.get("provenance")
    spans = provenance if isinstance(provenance, list) else [provenance or {}]
    spans = [span for span in spans if isinstance(span, dict)][:MAX_PASSAGES]
    return passage_evidence(spans, source_id, page_starts)
