"""
Apply service for schema extraction pipeline.

Converts CandidateClass and CandidatePropertyDefinition outputs from a completed
schema extraction run into DRAFT ontology entities (Class, PropertyDefinition, Relationship)
created via OntologyService, so each creation publishes its domain event and is
recorded as a ChangeEvent that the run's revert can undo.

Idempotent: applying the same run twice produces no duplicates. Deduplication is
content-based (title within concept scheme; identifier for property definitions;
source+target+property triple for relationships).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from domain.ontology.exceptions import DuplicateEntityError
from domain.pipelines.apply_result import ApplyResult, SkipReason
from domain.pipelines.apply_selection import check_accepted_ids
from domain.pipelines.candidate_ids import (
    enumerate_schema_candidates,
    enumerate_schema_connections,
)

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.pipelines.entities import PipelineRun


def _slugify(text: str) -> str:
    """Convert a label to a snake_case identifier."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class SchemaExtractionApplyService:
    """
    Materializes schema extraction pipeline output into ontology entities.

    Creates Class, PropertyDefinition, and Relationship entities (DRAFT status) through
    OntologyService with source_run_id set to the originating pipeline run ID. Reads
    used for deduplication go through the OntologyRepository port.

    NOTE: This service performs multiple sequential writes (classes, then property
    definitions, then relationships). If a write fails mid-apply, earlier writes are
    already persisted with no rollback; they are recorded as ChangeEvents, so reverting
    the run removes them.
    """

    def __init__(
        self, ontology_service: "OntologyService", ontology_repo: "OntologyRepository"
    ) -> None:
        self._ontology_service = ontology_service
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        concept_scheme_id: str,
        taxonomy_id: str,
        confidence_threshold: float = 0.0,
        accepted_candidate_ids: "set[str] | list[str] | None" = None,
    ) -> ApplyResult:
        """
        Apply schema extraction results to the ontology.

        Args:
            run: Completed PipelineRun with output_summary containing candidates/connections
            concept_scheme_id: Target concept scheme for Class entities
            taxonomy_id: Parent taxonomy for Class entities; must be the concept
                scheme's taxonomy
            confidence_threshold: Minimum confidence to include a candidate (0.0–1.0).
                Ignored when ``accepted_candidate_ids`` is given.
            accepted_candidate_ids: Explicit reviewer selection of ``class-{i}``,
                ``property-{i}`` and ``connection-{i}`` ids; when given it is the
                full selection — everything else is skipped regardless of
                confidence. An accepted connection whose endpoint class was not
                accepted (and does not already exist) is skipped.

        Returns:
            ApplyResult with counts of created and skipped entities. Selected
            candidates satisfied by an entity that already existed are listed in both
            ``applied_candidate_ids`` and ``existing_candidate_ids``.

        Raises:
            ValueError: If concept_scheme_id or taxonomy_id is empty, the concept
                scheme does not exist, or it does not belong to taxonomy_id
            ApplySelectionError: If an accepted id is not a candidate of this run
        """
        if not concept_scheme_id:
            raise ValueError("concept_scheme_id is required for schema extraction apply")
        if not taxonomy_id:
            raise ValueError("taxonomy_id is required for schema extraction apply")
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
        existing_classes = self._repo.list_classes(concept_scheme_id=concept_scheme_id, limit=None)
        # Lower-cased title -> id, for existing and newly created classes alike
        # (used for dedup and for resolving connection endpoints).
        class_title_to_id: dict[str, str] = {c.title.lower(): c.id for c in existing_classes}

        class_candidates = [(cid, c) for cid, c in candidates if c.get("kind") == "class"]
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
            if label.lower() in class_title_to_id:
                result.classes_skipped += 1
                _already_present(candidate_id)
                continue
            new_class = self._ontology_service.create_class(
                concept_scheme_id=concept_scheme_id,
                title=label,
                description=candidate.get("proposed_definition"),
                source_run_id=run.id,
            )
            class_title_to_id[label.lower()] = new_class.id
            result.classes_created += 1
            result.created_class_ids.append(new_class.id)
            result.applied_candidate_ids.append(candidate_id)

        # --- Property Definitions ---
        prop_candidates = [
            (cid, c) for cid, c in candidates if c.get("kind") == "property_definition"
        ]
        for candidate_id, candidate in prop_candidates:
            label = candidate.get("label", "").strip()
            confidence = candidate.get("confidence", 0.0)
            identifier = _slugify(label)
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
            try:
                new_prop = self._ontology_service.create_property_definition(
                    identifier=identifier,
                    title=label,
                    description=candidate.get("proposed_definition"),
                    source_run_id=run.id,
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

            subject_ref = (connection.get("subject_ref") or "").strip().lower()
            object_ref = (connection.get("object_ref") or "").strip().lower()
            predicate = (connection.get("predicate") or "").strip()

            src_id = class_title_to_id.get(subject_ref)
            tgt_id = class_title_to_id.get(object_ref)
            prop_identifier = _slugify(predicate)
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

            new_rel = self._ontology_service.create_relationship(
                source_id=src_id,
                target_id=tgt_id,
                property_definition_id=prop_def.id,
                source_run_id=run.id,
            )
            result.relationships_created += 1
            result.created_relationship_ids.append(new_rel.id)
            result.applied_candidate_ids.append(candidate_id)

        result.validate()
        return result
