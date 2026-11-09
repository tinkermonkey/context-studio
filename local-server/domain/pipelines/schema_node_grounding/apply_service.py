"""
Apply service for schema node grounding pipeline.

Applies grounding candidates from a completed grounding run to an existing ontology
Class by appending ExternalReference entries. The write goes through
OntologyService.update_class, so a ClassUpdated event (and thus a ChangeEvent with the
previous references) is recorded and reverting the run restores the prior list.
Idempotent: groundings already present (matched by URI) are skipped.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from domain.ontology.value_objects import ExternalReference
from domain.pipelines.apply_result import ApplyResult
from domain.pipelines.apply_selection import check_accepted_ids
from domain.pipelines.candidate_ids import enumerate_items

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.pipelines.entities import PipelineRun


class SchemaGroundingApplyService:
    """
    Applies schema node grounding results to an existing Class entity.

    Adds ExternalReference entries sourced from the grounding run output via
    OntologyService; reads go through the OntologyRepository port.
    """

    def __init__(
        self, ontology_service: "OntologyService", ontology_repo: "OntologyRepository"
    ) -> None:
        self._ontology_service = ontology_service
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        node_id: str,
        confidence_threshold: float = 0.0,
        accepted_candidate_ids: "set[str] | list[str] | None" = None,
    ) -> ApplyResult:
        """
        Apply grounding results to the given class node.

        Args:
            run: Completed grounding PipelineRun with output_summary["groundings"]
            node_id: ID of the Class to apply groundings to
            confidence_threshold: Minimum confidence to include a grounding.
                Ignored when ``accepted_candidate_ids`` is given.
            accepted_candidate_ids: Explicit selection of ``grounding-{i}`` ids; when
                given, only these groundings are applied

        Returns:
            ApplyResult with external_references_created and external_references_skipped

        Raises:
            ValueError: If node_id is empty or the class does not exist
            ApplySelectionError: If an accepted id is not a grounding of this run
        """
        if not node_id:
            raise ValueError("node_id is required for grounding apply")

        cls = self._repo.get_class(node_id)
        if cls is None:
            raise ValueError(f"Class {node_id} not found")

        result = ApplyResult()
        groundings = enumerate_items(run.output_summary.get("groundings"), "grounding")
        check_accepted_ids(accepted_candidate_ids, {cid for cid, _ in groundings})
        selected = set(accepted_candidate_ids) if accepted_candidate_ids is not None else None
        existing_uris = {ref.identifier for ref in cls.external_references}
        new_references: list[ExternalReference] = []

        for candidate_id, grounding in groundings:
            uri = (grounding.get("uri") or "").strip()
            if selected is not None:
                wanted = candidate_id in selected
            else:
                wanted = grounding.get("confidence", 0.0) >= confidence_threshold
            if not uri or not wanted:
                result.external_references_skipped += 1
                continue
            if uri in existing_uris:
                result.external_references_skipped += 1
                continue
            ref = ExternalReference(
                source=grounding.get("source", "unknown"),
                identifier=uri,
                uri=uri,
            )
            new_references.append(ref)
            existing_uris.add(uri)
            result.external_references_created += 1
            result.created_external_reference_ids.append(uri)

        if new_references:
            self._ontology_service.update_class(
                node_id, external_references=[*cls.external_references, *new_references]
            )

        result.validate()
        return result
