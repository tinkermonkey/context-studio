"""
Apply service for schema node definition refinement pipeline.

Applies the highest-confidence refined definition candidate from a completed
definition refinement run to an existing ontology Class entity.
Idempotent: re-applying the same run overwrites the description with the same value.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from domain.pipelines.apply_result import ApplyResult

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.pipelines.entities import PipelineRun


class SchemaDefinitionRefinementApplyService:
    """
    Applies the best definition candidate from a definition refinement run to a Class.
    """

    def __init__(self, ontology_repo: "OntologyRepository") -> None:
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        confidence_threshold: float = 0.0,
    ) -> ApplyResult:
        """
        Apply the top definition candidate to the target class.

        The node_id is sourced from run.output_summary["node_id"] (set by the orchestrator).

        Args:
            run: Completed definition refinement PipelineRun
            confidence_threshold: Minimum candidate confidence to consider

        Returns:
            ApplyResult (classes_updated=1 if applied, classes_skipped=1 if no candidate qualifies)

        Raises:
            ValueError: If node_id is missing from output_summary or the class does not exist
        """
        result = ApplyResult()
        node_id = run.output_summary.get("node_id", "")
        if not node_id:
            raise ValueError("node_id missing from output_summary — cannot apply definition")

        cls = self._repo.get_class(node_id)
        if cls is None:
            raise ValueError(f"Class {node_id} not found")

        candidates = run.output_summary.get("candidates", [])
        qualifying = [c for c in candidates if c.get("confidence", 0.0) >= confidence_threshold]
        if not qualifying:
            result.classes_skipped += 1
            result.validate()
            return result

        # Pick highest-confidence candidate
        best = max(qualifying, key=lambda c: c.get("confidence", 0.0))
        new_definition = (best.get("definition") or "").strip()
        if not new_definition:
            result.classes_skipped += 1
            result.validate()
            return result

        cls.description = new_definition
        try:
            self._repo.save_class(cls)
        except Exception as e:
            _logger.error(f"Failed to save class with updated definition: {e}")
            raise
        result.classes_updated += 1
        result.validate()
        return result
