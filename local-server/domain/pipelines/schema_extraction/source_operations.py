"""
A schema-extraction run's candidates on a source as proposal operations (#1552).

The same rules as applying a run (`apply_service.py`) decide what is new: a
class candidate whose title (by `class_title_key`) the taxonomy already has,
or a property candidate whose identifier (its label slugified) a relationship
type already has, is skipped; so is a property candidate whose identifier a
class, scheme or taxonomy has ("identifier_taken": identifiers are unique
across kinds, and a type is matched to its candidate by that slug).

- A new class is a class create in the taxonomy's first concept scheme (a
  reviewer can edit it before applying), with its proposed definition as its
  description and an identifier slugified from its title (`class_identifier`).
  Its `proposed_parent` (#1570) becomes its `parent_class_id`: an existing
  class in that scheme, or "$ref" of an earlier class create (parents are
  planned before their children). A parent in another scheme, or one that is
  neither a class nor a class create, leaves it top-level, with a note saying so.
- An attribute candidate (#1570) is an attribute create on the class it
  describes (existing, or "$ref" of a class create), with its value type as
  datatype and its definition and unit as description. One whose class is
  neither is skipped ("no_class"); one its class already has is skipped
  ("exists").
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
from domain.pipelines.schema_extraction.apply_service import (
    attribute_datatype,
    attribute_description,
    attribute_identifier,
    class_identifier,
    class_title_index,
    class_title_key,
    ordered_parents_first,
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


def plan_schema_operations(
    candidates: Sequence[dict[str, Any]],
    repo: OntologyRepository,
    taxonomy_id: str,
    source_id: str,
    page_starts: Sequence[int],
) -> OperationPlan:
    """
    Plan a run's class, attribute and property candidates as class, attribute,
    predicate and relationship-type creates.

    Args:
        candidates: The run's candidates ({kind: class | attribute | property_definition, ...})
        repo: The ontology, for existing classes, attributes, relationship types and predicates
        taxonomy_id: The taxonomy the run extracted for
        source_id: The source the passages are in
        page_starts: Offset at which each of its pages starts
    """
    plan = OperationPlan()
    schemes = repo.list_concept_schemes(
        taxonomy_id=taxonomy_id, limit=None, sort_by="created_at", sort_order="asc"
    )
    existing = taxonomy_classes(repo, taxonomy_id)
    scheme_of = {cls.id: cls.concept_scheme_id for cls in existing}
    # Title key -> an existing class id, or "$ref" of a class create
    classes: dict[str, str] = {key: cls.id for key, cls in class_title_index(existing).items()}
    # Identifiers the plan's creates take. Identifiers are unique across classes
    # and relationship types, so the property candidates' identifiers (their
    # slugified labels) are reserved before any class takes one.
    identifiers: set[str] = {
        slugify(str(c.get("label") or ""))
        for c in candidates
        if c.get("kind") == "property_definition"
    }

    def add(
        draft_fields: dict[str, Any],
        kind: OperationKind,
        ref: str,
        candidate: dict[str, Any],
        label: str,
        needs: frozenset[str] = frozenset(),
        notes: str | None = None,
    ) -> None:
        plan.operations.append(
            PlannedOperation(
                draft=OperationDraft(
                    seq=len(plan.operations) + 1,
                    op=OperationType.CREATE,
                    kind=kind,
                    ref=ref,
                    fields=draft_fields,
                    notes=notes,
                    evidence=_evidence(candidate, source_id, page_starts),
                    probability=best_probability(candidate.get("confidence")),
                ),
                label=label,
                needs=needs,
            )
        )

    class_candidates = [c for c in candidates if c.get("kind") == "class"]
    for candidate in ordered_parents_first(class_candidates):
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
        needs: frozenset[str] = frozenset()
        notes = None
        parent = str(candidate.get("proposed_parent") or "").strip()
        parent_id = classes.get(class_title_key(parent)) if parent else None
        if parent and parent_id is None:
            notes = f"Proposed parent {parent} is neither a class nor a class create: top-level."
        elif parent_id and parent_id.startswith("$"):
            fields["parent_class_id"] = parent_id
            needs = frozenset({parent_id[1:]})
        elif parent_id and scheme_of.get(parent_id) == schemes[0].id:
            fields["parent_class_id"] = parent_id
        elif parent_id:
            notes = f"Proposed parent {parent} is in another concept scheme: top-level."
        add(fields, OperationKind.CLASS, ref, candidate, label, needs, notes)
        classes[key] = f"${ref}"

    # (class id or "$ref", identifier) of the attributes planned
    planned_attributes: set[tuple[str, str]] = set()
    for candidate in candidates:
        if candidate.get("kind") != "attribute":
            continue
        label = str(candidate.get("label") or "").strip()
        identifier = attribute_identifier(label)
        if not identifier:
            plan.skip(label or "(no label)", "invalid")
            continue
        class_id = classes.get(class_title_key(candidate.get("of")))
        if not class_id:
            plan.skip(label, "no_class")
            continue
        if (class_id, identifier) in planned_attributes or _has_attribute(
            repo, class_id, identifier
        ):
            plan.skip(label, "exists")
            continue
        planned_attributes.add((class_id, identifier))
        fields = {
            "class_id": class_id,
            "identifier": identifier,
            "title": label,
            "datatype": attribute_datatype(candidate),
        }
        description = attribute_description(candidate)
        if description:
            fields["description"] = description
        add(
            fields,
            OperationKind.ATTRIBUTE,
            f"a{len(plan.operations) + 1}",
            candidate,
            f"{label} of {candidate.get('of')}",
            frozenset({class_id[1:]}) if class_id.startswith("$") else frozenset(),
        )

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
        if repo.get_by_identifier(identifier) is not None:
            # A class, scheme or taxonomy has it (identifiers are unique across
            # kinds); the type keeps its slug, so it isn't proposed. The plan's
            # own class creates never take it: property identifiers are reserved.
            plan.skip(label, "identifier_taken")
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
        type_needs = {predicates[identifier]} if identifier in predicates else set()
        for name, end in (
            ("domain_class_id", "proposed_domain"),
            ("range_class_id", "proposed_range"),
        ):
            class_id = classes.get(class_title_key(candidate.get(end)))
            if class_id:
                fields[name] = class_id
                if class_id.startswith("$"):
                    type_needs.add(class_id[1:])
        ref = f"r{len(plan.operations) + 1}"
        add(fields, OperationKind.PROPERTY, ref, candidate, label, frozenset(type_needs))
    return plan


def _has_attribute(repo: OntologyRepository, class_id: str, identifier: str) -> bool:
    """Whether an existing class (not a "$ref") already has an attribute with this identifier."""
    if class_id.startswith("$"):
        return False
    return any(
        a.identifier == identifier
        for a in repo.list_attribute_definitions(class_id=class_id, limit=None)
    )


def _evidence(
    candidate: dict[str, Any], source_id: str, page_starts: Sequence[int]
) -> list[dict[str, Any]]:
    provenance = candidate.get("provenance")
    spans = provenance if isinstance(provenance, list) else [provenance or {}]
    spans = [span for span in spans if isinstance(span, dict)][:MAX_PASSAGES]
    return passage_evidence(spans, source_id, page_starts)
