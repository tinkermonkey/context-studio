"""
Apply service for schema extraction pipeline.

Converts CandidateClass, CandidateAttribute and CandidatePropertyDefinition outputs
from a completed schema extraction run into DRAFT ontology entities (Class,
AttributeDefinition, PropertyDefinition, Relationship) created via OntologyService, so
each creation publishes its domain event and is recorded as a ChangeEvent that the
run's revert can undo.

A new class takes its ``proposed_parent`` (#1570) as parent when that class exists or
is created by the same apply (parents are created first) and is in the new class's
scheme; otherwise it is top-level. An attribute candidate becomes an attribute of the
class it describes (``of``), existing or created by the same apply; without one it is
skipped (``no_class``).

Idempotent: applying the same run twice produces no duplicates. Deduplication is
content-based (class title anywhere in the taxonomy, compared by ``class_title_key``;
identifier for attributes within their class and for property definitions;
source+target+property triple for relationships). A property candidate whose identifier
a class, scheme or taxonomy already has is skipped (``identifier_taken``): identifiers
are unique across every kind of entity.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from domain.ontology.exceptions import DomainRangeMismatchError, DuplicateEntityError
from domain.ontology.value_objects import DataType, validate_identifier
from domain.pipelines.apply_result import ApplyResult, SkipReason
from domain.pipelines.apply_selection import check_accepted_ids
from domain.pipelines.candidate_ids import (
    enumerate_schema_candidates,
    enumerate_schema_connections,
)

_logger = logging.getLogger(__name__)

MAX_IDENTIFIER_CHARS = 64
# The datatypes an attribute candidate may have (a class attribute holding one value)
ATTRIBUTE_DATATYPES: tuple[str, ...] = tuple(
    t.value for t in DataType if t not in (DataType.ARRAY, DataType.OBJECT)
)

if TYPE_CHECKING:
    from domain.ontology.entities import Class
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.pipelines.entities import PipelineRun


def slugify(text: str) -> str:
    """Convert a label to a snake_case identifier."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def class_title_key(title: str | None) -> str:
    """
    Dedup key for a class title within a taxonomy.

    Case, whitespace, hyphens and underscores are ignored, so a proposed
    "Data Object" resolves to an existing "DataObject" (the DR spec's CamelCase
    titles) instead of creating a near-duplicate class.
    """
    return re.sub(r"[\s_-]+", "", (title or "").lower())


def class_identifier(title: str, repo: "OntologyRepository", taken: set[str]) -> str:
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


def attribute_identifier(label: str) -> str | None:
    """
    An attribute candidate's identifier: its label slugified ("Indoor Humidity"
    -> "indoor_humidity"), prefixed "attr_" when that isn't a valid identifier;
    None for a label with nothing to slugify. Attribute identifiers are unique
    only within their class.
    """
    base = slugify(label)[:MAX_IDENTIFIER_CHARS]
    if not base:
        return None
    try:
        return validate_identifier(base)
    except ValueError:
        return f"attr_{base}"[:MAX_IDENTIFIER_CHARS]


def attribute_datatype(candidate: dict) -> str:
    """An attribute candidate's value_type as a datatype; "string" when unknown."""
    value_type = str(candidate.get("value_type") or "")
    return value_type if value_type in ATTRIBUTE_DATATYPES else DataType.STRING.value


def attribute_description(candidate: dict) -> str | None:
    """An attribute candidate's definition, with its unit when it has one."""
    definition = str(candidate.get("proposed_definition") or "").strip()
    unit = str(candidate.get("unit") or "").strip()
    if unit:
        definition = f"{definition} Unit: {unit}.".strip()
    return definition or None


def ordered_parents_first(candidates: "list[dict]") -> "list[dict]":
    """
    Class candidates reordered so a candidate named as another's
    ``proposed_parent`` comes before it; otherwise in their order. A cycle is
    broken where it closes (that child comes first and its parent can't be
    resolved when it is created).
    """
    by_key: dict[str, dict] = {}
    for candidate in candidates:
        by_key.setdefault(class_title_key(candidate.get("label")), candidate)
    ordered: list[dict] = []
    placed: set[int] = set()
    visiting: set[int] = set()

    def visit(candidate: dict) -> None:
        if id(candidate) in placed or id(candidate) in visiting:
            return
        visiting.add(id(candidate))
        parent = by_key.get(class_title_key(candidate.get("proposed_parent")))
        if parent is not None:
            visit(parent)
        visiting.discard(id(candidate))
        placed.add(id(candidate))
        ordered.append(candidate)

    for candidate in candidates:
        visit(candidate)
    return ordered


def taxonomy_classes(repo: "OntologyRepository", taxonomy_id: str) -> "list[Class]":
    """
    Every class in a taxonomy, scheme by scheme, oldest scheme first.

    Recognition preview and apply both read classes through this, so a class
    the preview reports as existing is the one apply reuses.
    """
    classes: list[Class] = []
    for scheme in repo.list_concept_schemes(
        taxonomy_id=taxonomy_id, limit=None, sort_by="created_at", sort_order="asc"
    ):
        classes.extend(repo.list_classes(concept_scheme_id=scheme.id, limit=None))
    return classes


def class_title_index(classes: "list[Class]") -> "dict[str, Class]":
    """
    Title key -> class. Titles are unique per scheme, not per taxonomy; when two
    schemes share one, the first class (oldest scheme) wins.
    """
    index: dict[str, Class] = {}
    for cls in classes:
        index.setdefault(class_title_key(cls.title), cls)
    return index


class SchemaExtractionApplyService:
    """
    Materializes schema extraction pipeline output into ontology entities.

    Creates Class, AttributeDefinition, PropertyDefinition and Relationship entities
    (DRAFT status) through OntologyService with source_run_id set to the originating
    pipeline run ID. Reads used for deduplication go through the OntologyRepository port.

    NOTE: This service performs multiple sequential writes (classes, then attributes,
    then property definitions, then relationships). If a write fails mid-apply, earlier
    writes are already persisted with no rollback; they are recorded as ChangeEvents,
    so reverting the run removes them.
    """

    def __init__(
        self, ontology_service: "OntologyService", ontology_repo: "OntologyRepository"
    ) -> None:
        self._ontology_service = ontology_service
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        taxonomy_id: str,
        concept_scheme_id: str | None = None,
        confidence_threshold: float = 0.0,
        accepted_candidate_ids: "set[str] | list[str] | None" = None,
    ) -> ApplyResult:
        """
        Apply schema extraction results to the ontology.

        Args:
            run: Completed PipelineRun with output_summary containing candidates/connections
            taxonomy_id: The taxonomy to apply to. A selected class whose title
                already exists anywhere in it is reused, never duplicated, and
                connections resolve their endpoints across the whole taxonomy.
            concept_scheme_id: Where new classes go; must belong to taxonomy_id.
                Only needed when the selection creates a class.
            confidence_threshold: Minimum confidence to include a candidate (0.0–1.0).
                Ignored when ``accepted_candidate_ids`` is given.
            accepted_candidate_ids: Explicit reviewer selection of ``class-{i}``,
                ``property-{i}``, ``attribute-{i}`` and ``connection-{i}`` ids; when
                given it is the full selection — everything else is skipped
                regardless of confidence. An accepted connection whose endpoint
                class was not accepted (and does not already exist) is skipped, as
                is an accepted attribute whose class was not.

        Returns:
            ApplyResult with counts of created and skipped entities. Selected
            candidates satisfied by an entity that already existed are listed in both
            ``applied_candidate_ids`` and ``existing_candidate_ids``.

        Raises:
            ValueError: If taxonomy_id is empty; the concept scheme does not exist
                or does not belong to taxonomy_id; or the selection creates a class
                and no concept scheme was given (checked before anything is written)
            ApplySelectionError: If an accepted id is not a candidate of this run
        """
        if not taxonomy_id:
            raise ValueError("taxonomy_id is required for schema extraction apply")
        if concept_scheme_id:
            scheme = self._repo.get_concept_scheme(concept_scheme_id)
            if scheme is None:
                raise ValueError(f"Concept scheme {concept_scheme_id} not found")
            if scheme.taxonomy_id != taxonomy_id:
                raise ValueError(
                    f"Concept scheme {concept_scheme_id} does not belong to taxonomy {taxonomy_id}"
                )

        result = ApplyResult()
        candidates = enumerate_schema_candidates(run.output_summary)
        connections = enumerate_schema_connections(run.output_summary)
        check_accepted_ids(accepted_candidate_ids, {cid for cid, _ in candidates + connections})
        selected = set(accepted_candidate_ids) if accepted_candidate_ids is not None else None

        def _is_selected(candidate_id: str, confidence: float) -> bool:
            if selected is not None:
                return candidate_id in selected
            return confidence >= confidence_threshold

        # Reason for a candidate that was never selected.
        unselected_reason: SkipReason = (
            "not_selected" if selected is not None else "below_threshold"
        )

        def _already_present(candidate_id: str) -> None:
            result.applied_candidate_ids.append(candidate_id)
            result.existing_candidate_ids.append(candidate_id)

        # --- Classes ---
        # Title key -> id across the taxonomy, for existing and newly created
        # classes alike (used for dedup and for resolving connection endpoints).
        existing_classes = taxonomy_classes(self._repo, taxonomy_id)
        class_title_to_id: dict[str, str] = {
            key: c.id for key, c in class_title_index(existing_classes).items()
        }
        # Class id -> its scheme: a new class takes a parent only in its own scheme
        class_scheme: dict[str, str] = {c.id: c.concept_scheme_id for c in existing_classes}

        # Identifiers are unique across classes and relationship types, so the
        # selected property candidates' slugs are reserved before any class
        # takes one (the source planner does the same).
        taken: set[str] = {
            slugify(c.get("label", ""))
            for cid, c in candidates
            if c.get("kind") == "property_definition"
            and _is_selected(cid, c.get("confidence", 0.0))
        }

        # Parents before their children, so a parent created here is found
        class_candidates = [(cid, c) for cid, c in candidates if c.get("kind") == "class"]
        order = {
            id(c): n for n, c in enumerate(ordered_parents_first([c for _, c in class_candidates]))
        }
        class_candidates.sort(key=lambda pair: order[id(pair[1])])
        for candidate_id, candidate in class_candidates:
            label = candidate.get("label", "").strip()
            confidence = candidate.get("confidence", 0.0)
            if not _is_selected(candidate_id, confidence):
                result.classes_skipped += 1
                result.skip(candidate_id, unselected_reason)
                continue
            if not label:
                result.classes_skipped += 1
                result.skip(candidate_id, "invalid")
                continue
            if class_title_key(label) in class_title_to_id:
                result.classes_skipped += 1
                _already_present(candidate_id)
                continue
            if not concept_scheme_id:
                # Classes are written first and earlier ones were only reused,
                # so nothing has been written yet.
                raise ValueError("Choose a concept scheme for the new classes")
            identifier = class_identifier(label, self._repo, taken)
            taken.add(identifier)
            parent_id = class_title_to_id.get(class_title_key(candidate.get("proposed_parent")))
            if parent_id and class_scheme.get(parent_id) != concept_scheme_id:
                _logger.info(
                    "Class candidate %r stays top-level: its parent %r is in another scheme",
                    label,
                    candidate.get("proposed_parent"),
                )
                parent_id = None
            new_class = self._ontology_service.create_class(
                concept_scheme_id=concept_scheme_id,
                title=label,
                description=candidate.get("proposed_definition"),
                source_run_id=run.id,
                identifier=identifier,
                parent_class_id=parent_id,
            )
            class_title_to_id[class_title_key(label)] = new_class.id
            class_scheme[new_class.id] = concept_scheme_id
            result.classes_created += 1
            result.created_class_ids.append(new_class.id)
            result.applied_candidate_ids.append(candidate_id)

        # --- Attributes ---
        # On the class each describes: one that existed or was just created
        for candidate_id, candidate in candidates:
            if candidate.get("kind") != "attribute":
                continue
            label = (candidate.get("label") or "").strip()
            identifier = attribute_identifier(label)
            if not _is_selected(candidate_id, candidate.get("confidence", 0.0)):
                result.attributes_skipped += 1
                result.skip(candidate_id, unselected_reason)
                continue
            if not identifier:
                result.attributes_skipped += 1
                result.skip(candidate_id, "invalid")
                continue
            class_id = class_title_to_id.get(class_title_key(candidate.get("of")))
            if not class_id:
                result.attributes_skipped += 1
                result.skip(candidate_id, "no_class")
                continue
            if any(
                a.identifier == identifier
                for a in self._repo.list_attribute_definitions(class_id=class_id, limit=None)
            ):
                result.attributes_skipped += 1
                _already_present(candidate_id)
                continue
            new_attribute = self._ontology_service.create_attribute_definition(
                class_id=class_id,
                identifier=identifier,
                title=label,
                datatype=attribute_datatype(candidate),
                description=attribute_description(candidate),
                source_run_id=run.id,
            )
            result.attributes_created += 1
            result.created_attribute_definition_ids.append(new_attribute.id)
            result.applied_candidate_ids.append(candidate_id)

        # --- Property Definitions ---
        prop_candidates = [
            (cid, c) for cid, c in candidates if c.get("kind") == "property_definition"
        ]
        for candidate_id, candidate in prop_candidates:
            label = candidate.get("label", "").strip()
            confidence = candidate.get("confidence", 0.0)
            identifier = slugify(label)
            if not _is_selected(candidate_id, confidence):
                result.properties_skipped += 1
                result.skip(candidate_id, unselected_reason)
                continue
            if not identifier:
                result.properties_skipped += 1
                result.skip(candidate_id, "invalid")
                continue
            if self._repo.get_property_definition_by_identifier(identifier) is not None:
                result.properties_skipped += 1
                _already_present(candidate_id)
                continue
            if self._repo.get_by_identifier(identifier) is not None:
                # A class, scheme or taxonomy has it (identifiers are unique across
                # kinds). Connections naming this type skip as unresolved_predicate.
                result.properties_skipped += 1
                result.skip(candidate_id, "identifier_taken")
                continue
            try:
                # Its predicate is its identifier, added to the taxonomy's catalog
                # when the catalog lacks it (extraction is one of CS's own editors).
                new_prop = self._ontology_service.create_property_definition(
                    identifier=identifier,
                    title=label,
                    description=candidate.get("proposed_definition"),
                    source_run_id=run.id,
                    canonical_predicate=identifier,
                    taxonomy_id=taxonomy_id,
                    create_missing_predicate=True,
                )
            except DuplicateEntityError:
                # A property with this title exists under a different identifier;
                # connections resolve properties by identifier, so it cannot be reused.
                _logger.warning(
                    "Skipping property candidate %r: title conflicts with an existing "
                    "property definition",
                    label,
                )
                result.properties_skipped += 1
                result.skip(candidate_id, "title_conflict")
                continue
            result.properties_created += 1
            result.created_property_definition_ids.append(new_prop.id)
            result.applied_candidate_ids.append(candidate_id)

        # --- Relationships ---
        for candidate_id, connection in connections:
            confidence = connection.get("confidence", 0.0)
            if not _is_selected(candidate_id, confidence):
                result.relationships_skipped += 1
                result.skip(candidate_id, unselected_reason)
                continue

            subject_ref = class_title_key(connection.get("subject_ref"))
            object_ref = class_title_key(connection.get("object_ref"))
            predicate = (connection.get("predicate") or "").strip()

            src_id = class_title_to_id.get(subject_ref)
            tgt_id = class_title_to_id.get(object_ref)
            prop_identifier = slugify(predicate)
            prop_def = (
                self._repo.get_property_definition_by_identifier(prop_identifier)
                if prop_identifier
                else None
            )

            unresolved: SkipReason | None = None
            if not src_id or not tgt_id:
                unresolved = "unresolved_endpoint"
            elif not prop_def:
                unresolved = "unresolved_predicate"
            elif prop_def.derived:
                unresolved = "derived_type"
            elif src_id == tgt_id:
                unresolved = "self_loop"
            if unresolved is not None:
                result.relationships_skipped += 1
                result.skip(candidate_id, unresolved)
                continue

            existing_rels = self._repo.list_relationships(
                source_id=src_id,
                target_id=tgt_id,
                property_id=prop_def.id,
                limit=1,
            )
            if existing_rels:
                result.relationships_skipped += 1
                _already_present(candidate_id)
                continue

            try:
                new_rel = self._ontology_service.create_relationship(
                    source_id=src_id,
                    target_id=tgt_id,
                    property_definition_id=prop_def.id,
                    source_run_id=run.id,
                )
            except DomainRangeMismatchError as exc:
                _logger.info("Skipping connection %s: %s", candidate_id, exc)
                result.relationships_skipped += 1
                result.skip(candidate_id, "domain_range_mismatch")
                continue
            result.relationships_created += 1
            result.created_relationship_ids.append(new_rel.id)
            result.applied_candidate_ids.append(candidate_id)

        result.validate()
        return result
