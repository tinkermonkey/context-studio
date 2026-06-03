"""
Apply service for individual extraction pipeline.

Converts RDF triple output from a completed individual extraction run into DRAFT
Individual and Relationship entities persisted via the OntologyRepository port.

Idempotent: applying the same run twice produces no duplicates. Deduplication is
content-based (title within the first class_id for individuals; source+target+property
for relationships).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from domain.ontology.entities import Individual, Relationship
from domain.ontology.value_objects import Status
from domain.pipelines.apply_result import ApplyResult

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.pipelines.entities import PipelineRun


class IndividualExtractionApplyService:
    """
    Materializes individual extraction pipeline output into ontology entities.

    Creates Individual and Relationship entities with Status.DRAFT and source_run_id
    set to the originating pipeline run ID.
    """

    def __init__(self, ontology_repo: "OntologyRepository") -> None:
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        confidence_threshold: float = 0.0,
    ) -> ApplyResult:
        """
        Apply individual extraction results to the ontology.

        Args:
            run: Completed PipelineRun with output_summary containing triples
            confidence_threshold: Minimum confidence to include a triple (0.0–1.0)

        Returns:
            ApplyResult with counts of created and skipped entities
        """
        result = ApplyResult()
        triples = run.output_summary.get("triples", [])

        # Track individuals created in this apply pass: (title_lower, class_id) → entity_id
        individual_key_to_id: dict[tuple[str, str], str] = {}

        for triple in triples:
            subject = triple.get("subject", {})
            predicate = triple.get("predicate", {})
            obj = triple.get("object", {})
            confidence = triple.get("confidence", 0.0)

            if confidence < confidence_threshold:
                result.individuals_skipped += 1
                continue

            if subject.get("kind") != "individual":
                continue

            subject_label = (subject.get("label") or "").strip()
            subject_id = subject.get("id", "")

            # Resolve class IDs for this individual from the triple object or subject context
            class_ids: list[str] = subject.get("class_ids") or []

            # Attempt to resolve subject individual: prefer explicit ID, then label+class lookup
            resolved_id = self._resolve_individual_id(
                subject_id, subject_label, class_ids, individual_key_to_id
            )

            if resolved_id is None:
                # Create new individual
                if not subject_label or not class_ids:
                    result.individuals_skipped += 1
                    continue

                # Verify all class_ids exist
                valid_class_ids = [
                    cid for cid in class_ids if self._repo.get_class(cid) is not None
                ]
                if not valid_class_ids:
                    result.individuals_skipped += 1
                    continue

                new_individual = Individual(
                    id=str(uuid4()),
                    class_ids=valid_class_ids,
                    title=subject_label,
                    status=Status.DRAFT,
                    source_run_id=run.id,
                )
                self._repo.save_individual(new_individual)
                resolved_id = new_individual.id
                result.individuals_created += 1
                result.created_individual_ids.append(resolved_id)

                # Cache for dedup within this apply pass
                for cid in valid_class_ids:
                    key = (subject_label.lower(), cid)
                    individual_key_to_id[key] = resolved_id

            # Create relationship if predicate + object are present
            property_definition_id = predicate.get("property_definition_id", "")
            obj_kind = obj.get("kind", "")
            obj_id = obj.get("id", "")

            if property_definition_id and obj_kind in ("individual", "class") and obj_id:
                self._apply_relationship(
                    source_id=resolved_id,
                    target_id=obj_id,
                    property_definition_id=property_definition_id,
                    source_run_id=run.id,
                    result=result,
                )

        result.validate()
        return result

    def _resolve_individual_id(
        self,
        subject_id: str,
        subject_label: str,
        class_ids: list[str],
        local_cache: dict[tuple[str, str], str],
    ) -> str | None:
        """Return existing individual ID if found, else None."""
        # Check local cache first (individuals created earlier in this apply pass)
        for cid in class_ids:
            cached = local_cache.get((subject_label.lower(), cid))
            if cached:
                return cached

        # Try lookup by explicit ID
        if subject_id:
            existing = self._repo.get_individual(subject_id)
            if existing:
                return existing.id

        # Try lookup by label within each class
        for cid in class_ids:
            candidates = self._repo.list_individuals(class_id=cid, limit=None)
            for ind in candidates:
                if ind.title.lower() == subject_label.lower():
                    return ind.id

        return None

    def _apply_relationship(
        self,
        source_id: str,
        target_id: str,
        property_definition_id: str,
        source_run_id: str,
        result: ApplyResult,
    ) -> None:
        """Create a relationship if it does not already exist."""
        if source_id == target_id:
            result.relationships_skipped += 1
            return

        existing = self._repo.list_relationships(
            source_id=source_id,
            target_id=target_id,
            property_id=property_definition_id,
            limit=1,
        )
        if existing:
            result.relationships_skipped += 1
            return

        new_rel = Relationship(
            id=str(uuid4()),
            source_id=source_id,
            target_id=target_id,
            property_definition_id=property_definition_id,
            source_run_id=source_run_id,
        )
        self._repo.save_relationship(new_rel)
        result.relationships_created += 1
        result.created_relationship_ids.append(new_rel.id)
