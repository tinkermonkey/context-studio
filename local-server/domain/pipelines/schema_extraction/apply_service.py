"""
Apply service for schema extraction pipeline.

Converts CandidateClass and CandidatePropertyDefinition outputs from a completed
schema extraction run into DRAFT ontology entities (Class, PropertyDefinition, Relationship)
persisted via the OntologyRepository port.

Idempotent: applying the same run twice produces no duplicates. Deduplication is
content-based (title within concept scheme; identifier for property definitions;
source+target+property triple for relationships).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import uuid4

from domain.ontology.entities import Class, PropertyDefinition, Relationship
from domain.ontology.value_objects import Status
from domain.pipelines.apply_result import ApplyResult

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.pipelines.entities import PipelineRun


def _slugify(text: str) -> str:
    """Convert a label to a snake_case identifier."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class SchemaExtractionApplyService:
    """
    Materializes schema extraction pipeline output into ontology entities.

    Creates Class, PropertyDefinition, and Relationship entities with Status.DRAFT
    and source_run_id set to the originating pipeline run ID.
    """

    def __init__(self, ontology_repo: "OntologyRepository") -> None:
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        concept_scheme_id: str,
        taxonomy_id: str,
        confidence_threshold: float = 0.0,
    ) -> ApplyResult:
        """
        Apply schema extraction results to the ontology.

        Args:
            run: Completed PipelineRun with output_summary containing candidates/connections
            concept_scheme_id: Target concept scheme for Class entities
            taxonomy_id: Parent taxonomy for Class entities
            confidence_threshold: Minimum confidence to include a candidate (0.0–1.0)

        Returns:
            ApplyResult with counts of created and skipped entities

        Raises:
            ValueError: If concept_scheme_id or taxonomy_id is empty
        """
        if not concept_scheme_id:
            raise ValueError("concept_scheme_id is required for schema extraction apply")
        if not taxonomy_id:
            raise ValueError("taxonomy_id is required for schema extraction apply")

        result = ApplyResult()
        candidates = run.output_summary.get("candidates", [])
        connections = run.output_summary.get("connections", [])

        # --- Classes ---
        existing_classes = self._repo.list_classes(concept_scheme_id=concept_scheme_id, limit=None)
        existing_titles: dict[str, str] = {c.title.lower(): c.id for c in existing_classes}
        # Also collect newly created classes during this apply for relationship resolution
        all_class_title_to_id: dict[str, str] = dict(existing_titles)

        class_candidates = [c for c in candidates if c.get("kind") == "class"]
        for candidate in class_candidates:
            label = candidate.get("label", "").strip()
            confidence = candidate.get("confidence", 0.0)
            if not label or confidence < confidence_threshold:
                result.classes_skipped += 1
                continue
            if label.lower() in existing_titles:
                result.classes_skipped += 1
                continue
            new_class = Class(
                id=str(uuid4()),
                concept_scheme_id=concept_scheme_id,
                taxonomy_id=taxonomy_id,
                title=label,
                description=candidate.get("proposed_definition"),
                status=Status.DRAFT,
                source_run_id=run.id,
            )
            self._repo.save_class(new_class)
            existing_titles[label.lower()] = new_class.id
            all_class_title_to_id[label.lower()] = new_class.id
            result.classes_created += 1
            result.created_class_ids.append(new_class.id)

        # --- Property Definitions ---
        prop_candidates = [c for c in candidates if c.get("kind") == "property_definition"]
        for candidate in prop_candidates:
            label = candidate.get("label", "").strip()
            confidence = candidate.get("confidence", 0.0)
            if not label or confidence < confidence_threshold:
                result.properties_skipped += 1
                continue
            identifier = _slugify(label)
            if not identifier:
                result.properties_skipped += 1
                continue
            existing_prop = self._repo.get_property_definition_by_identifier(identifier)
            if existing_prop is not None:
                result.properties_skipped += 1
                continue
            new_prop = PropertyDefinition(
                id=str(uuid4()),
                identifier=identifier,
                title=label,
                description=candidate.get("proposed_definition"),
                status=Status.DRAFT,
                source_run_id=run.id,
            )
            self._repo.save_property_definition(new_prop)
            result.properties_created += 1
            result.created_property_definition_ids.append(new_prop.id)

        # --- Relationships ---
        for connection in connections:
            confidence = connection.get("confidence", 0.0)
            if confidence < confidence_threshold:
                result.relationships_skipped += 1
                continue

            subject_ref = (connection.get("subject_ref") or "").strip().lower()
            object_ref = (connection.get("object_ref") or "").strip().lower()
            predicate = (connection.get("predicate") or "").strip()

            src_id = all_class_title_to_id.get(subject_ref)
            tgt_id = all_class_title_to_id.get(object_ref)
            prop_identifier = _slugify(predicate)
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

            existing_rels = self._repo.list_relationships(
                source_id=src_id,
                target_id=tgt_id,
                property_id=prop_def.id,
                limit=1,
            )
            if existing_rels:
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

        return result
