"""
Apply service for schema node connection refinement pipeline.

Applies connection delta proposals from a completed connection refinement run:
- "add" deltas create new Relationship entities
- "remove" deltas delete existing Relationship entities
- "modify" deltas track the operation in relationships_modified counter (accounting only;
  actual relationship mutation is deferred until delta structure includes modification payload)

Writes go through OntologyService, so each add/remove publishes its domain event and
is recorded as a ChangeEvent that the run's revert can undo.

Idempotent: adding an already-existing relationship is skipped; removing a
non-existent relationship is skipped.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from domain.ontology.exceptions import EntityNotFoundError
from domain.pipelines.apply_result import ApplyResult
from domain.pipelines.apply_selection import check_accepted_ids
from domain.pipelines.candidate_ids import enumerate_items

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.pipelines.entities import PipelineRun


def _slugify(text: str) -> str:
    """Convert a label to a snake_case identifier."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class SchemaConnectionRefinementApplyService:
    """
    Applies connection delta proposals from a connection refinement run to the ontology.

    Writes go through OntologyService; reads go through the OntologyRepository port.
    """

    def __init__(
        self, ontology_service: "OntologyService", ontology_repo: "OntologyRepository"
    ) -> None:
        self._ontology_service = ontology_service
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        confidence_threshold: float = 0.0,
        accepted_candidate_ids: "set[str] | list[str] | None" = None,
    ) -> ApplyResult:
        """
        Apply connection deltas to the ontology.

        Deltas are sourced from run.output_summary["deltas"]. Each delta has:
          operation: "add" | "remove" | "modify"
          subject: class label or ID
          predicate: property label or identifier
          object: class label or ID
          confidence: float

        Args:
            run: Completed connection refinement PipelineRun
            confidence_threshold: Minimum delta confidence to apply.
                Ignored when ``accepted_candidate_ids`` is given.
            accepted_candidate_ids: Explicit selection of ``refinement-{i}`` ids; when
                given, only these deltas are applied

        Returns:
            ApplyResult with relationships_created, relationships_removed,
            relationships_modified, and relationships_skipped counts
        """
        result = ApplyResult()
        deltas = enumerate_items(run.output_summary.get("deltas"), "refinement")
        check_accepted_ids(accepted_candidate_ids, {cid for cid, _ in deltas})
        selected = set(accepted_candidate_ids) if accepted_candidate_ids is not None else None
        scope_id = run.output_summary.get("scope_id", "")

        # Build title→id lookup from classes scoped to the refinement's concept scheme.
        # Connection refinement deltas use class labels (not IDs) in subject/object fields.
        # Scoping by concept_scheme_id prevents title collisions across schemes from
        # resolving to incorrect classes.
        title_to_class_id: dict[str, str] = {}
        scheme_id = None
        if scope_id:
            scope_class = self._repo.get_class(scope_id)
            if scope_class:
                scheme_id = scope_class.concept_scheme_id
            else:
                _logger.warning(
                    f"Connection refinement scope_id {scope_id} could not be resolved; "
                    "skipping all deltas to prevent title collisions across "
                    "unrelated concept schemes"
                )
                result.validate()
                return result

        for cls in self._repo.list_classes(concept_scheme_id=scheme_id, limit=None):
            title_to_class_id[cls.title.lower()] = cls.id

        for candidate_id, delta in deltas:
            if selected is not None:
                wanted = candidate_id in selected
            else:
                wanted = delta.get("confidence", 0.0) >= confidence_threshold
            if not wanted:
                result.relationships_skipped += 1
                continue

            operation = delta.get("operation", "").lower()
            subject_ref = delta.get("subject", "")
            predicate_ref = delta.get("predicate", "")
            object_ref = delta.get("object", "")

            src_id = self._resolve_class_id(subject_ref, title_to_class_id)
            tgt_id = self._resolve_class_id(object_ref, title_to_class_id)
            prop_identifier = _slugify(predicate_ref)
            prop_def = (
                self._repo.get_property_definition_by_identifier(prop_identifier)
                if prop_identifier
                else None
            )

            if not src_id or not tgt_id or not prop_def:
                result.relationships_skipped += 1
                continue

            if src_id == tgt_id:
                result.relationships_skipped += 1
                continue

            existing = self._repo.list_relationships(
                source_id=src_id,
                target_id=tgt_id,
                property_id=prop_def.id,
                limit=1,
            )

            if operation == "add":
                # A derived type's relationships are computed by its client.
                if existing or prop_def.derived:
                    result.relationships_skipped += 1
                    continue
                new_rel = self._ontology_service.create_relationship(
                    source_id=src_id,
                    target_id=tgt_id,
                    property_definition_id=prop_def.id,
                    source_run_id=run.id,
                )
                result.relationships_created += 1
                result.created_relationship_ids.append(new_rel.id)

            elif operation == "remove":
                if not existing:
                    result.relationships_skipped += 1
                    continue
                try:
                    self._ontology_service.delete_relationship(existing[0].id)
                except EntityNotFoundError:
                    # Removed concurrently since the lookup above; nothing to do.
                    result.relationships_skipped += 1
                    continue
                result.relationships_removed += 1

            elif operation == "modify":
                if not existing:
                    result.relationships_skipped += 1
                    continue
                _logger.debug(
                    f"Relationship modification tracked but not applied: {src_id} "
                    f"--{prop_identifier}--> {tgt_id} (delta structure does not "
                    f"specify mutation details)"
                )
                result.relationships_modified += 1

            else:
                result.relationships_skipped += 1

        result.validate()
        return result

    def _resolve_class_id(self, ref: str, title_to_class_id: dict[str, str]) -> str | None:
        """Resolve a class reference (ID or label) to an entity ID."""
        if not ref:
            return None
        cls = self._repo.get_class(ref)
        if cls:
            return cls.id
        return title_to_class_id.get(ref.lower())
