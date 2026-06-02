"""
Apply service for schema node connection refinement pipeline.

Applies connection delta proposals from a completed connection refinement run:
- "add" deltas create new Relationship entities
- "remove" deltas delete existing Relationship entities
- "modify" deltas track the operation in relationships_modified counter (accounting only;
  actual relationship mutation is deferred until delta structure includes modification payload)

Idempotent: adding an already-existing relationship is skipped; removing a
non-existent relationship is skipped.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from uuid import uuid4

from domain.ontology.entities import Relationship
from domain.pipelines.apply_result import ApplyResult

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.pipelines.entities import PipelineRun


def _slugify(text: str) -> str:
    """Convert a label to a snake_case identifier."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class SchemaConnectionRefinementApplyService:
    """
    Applies connection delta proposals from a connection refinement run to the ontology.
    """

    def __init__(self, ontology_repo: "OntologyRepository") -> None:
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        confidence_threshold: float = 0.0,
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
            confidence_threshold: Minimum delta confidence to apply

        Returns:
            ApplyResult with relationships_created, relationships_removed,
            relationships_modified, and relationships_skipped counts
        """
        result = ApplyResult()
        deltas = run.output_summary.get("deltas", [])

        # Build title→id lookup from the scope's classes for label-based resolution.
        # Connection refinement deltas use class labels (not IDs) in subject/object fields.
        scope_id = run.output_summary.get("scope_id", "")
        title_to_class_id: dict[str, str] = {}
        if scope_id:
            for cls in self._repo.list_classes(concept_scheme_id=scope_id, limit=None):
                title_to_class_id[cls.title.lower()] = cls.id

        for delta in deltas:
            confidence = delta.get("confidence", 0.0)
            if confidence < confidence_threshold:
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
                if existing:
                    result.relationships_skipped += 1
                    continue
                new_rel = Relationship(
                    id=str(uuid4()),
                    source_id=src_id,
                    target_id=tgt_id,
                    property_definition_id=prop_def.id,
                    source_run_id=run.id,
                )
                self._repo.save_relationship(new_rel)
                result.relationships_created += 1
                result.created_relationship_ids.append(new_rel.id)

            elif operation == "remove":
                if not existing:
                    result.relationships_skipped += 1
                    continue
                self._repo.delete_relationship(existing[0].id)
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

        return result

    def _resolve_class_id(self, ref: str, title_to_class_id: dict[str, str]) -> str | None:
        """Resolve a class reference (ID or label) to an entity ID."""
        if not ref:
            return None
        cls = self._repo.get_class(ref)
        if cls:
            return cls.id
        return title_to_class_id.get(ref.lower())
