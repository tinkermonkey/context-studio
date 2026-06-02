"""Apply service for NoOp pipeline.

Creates a sentinel ontology entity to prove the apply path works and emits change events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domain.pipelines.apply_result import ApplyResult

if TYPE_CHECKING:
    from domain.ontology.services import OntologyService
    from domain.pipelines.entities import PipelineRun


class NoOpApplyService:
    """Apply service that creates a sentinel entity for NoOp pipeline."""

    def __init__(self, ontology_service: "OntologyService") -> None:
        self._service = ontology_service

    def apply(self, run: "PipelineRun") -> ApplyResult:
        """
        Apply NoOp results to the ontology.

        Creates a sentinel taxonomy to prove the apply path works and produces change events.

        Args:
            run: Completed NoOp PipelineRun

        Returns:
            ApplyResult with sentinel entity tracking
        """
        result = ApplyResult()

        # Create a sentinel taxonomy that represents the NoOp execution
        # Using the service ensures domain events are emitted and change events are recorded
        sentinel_taxonomy = self._service.create_taxonomy(
            title=f"NoOp Execution {run.id[:8]}",
            description="Sentinel entity created by NoOp pipeline apply",
        )

        # Track the created taxonomy ID
        result.created_taxonomy_ids.append(sentinel_taxonomy.id)

        return result
