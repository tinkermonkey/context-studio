"""
Apply service for schema node definition refinement pipeline.

Applies the chosen (or else the highest-confidence) refined definition candidate from
a completed definition refinement run to an existing ontology Class entity. The write goes through
OntologyService.update_class, so a ClassUpdated event (and thus a ChangeEvent with the
previous description) is recorded and reverting the run restores it.
Idempotent: re-applying the same run leaves the description unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from domain.pipelines.apply_result import ApplyResult
from domain.pipelines.apply_selection import check_accepted_ids
from domain.pipelines.candidate_ids import enumerate_items

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.pipelines.entities import PipelineRun


class SchemaDefinitionRefinementApplyService:
    """
    Applies the best definition candidate from a definition refinement run to a Class.
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
        Apply a definition candidate to the target class: the highest-confidence one
        among those selected or, without a selection, among those over the threshold.

        The node_id is sourced from run.output_summary["node_id"] (set by the orchestrator).

        Args:
            run: Completed definition refinement PipelineRun
            confidence_threshold: Minimum candidate confidence to consider.
                Ignored when ``accepted_candidate_ids`` is given.
            accepted_candidate_ids: Explicit selection of ``refinement-{i}`` ids

        Returns:
            ApplyResult (classes_updated=1 if applied, classes_skipped=1 if no candidate qualifies)

        Raises:
            ValueError: If node_id is missing from output_summary or the class does not exist
            ApplySelectionError: If an accepted id is not a candidate of this run
        """
        result = ApplyResult()
        node_id = run.output_summary.get("node_id", "")
        if not node_id:
            raise ValueError("node_id missing from output_summary — cannot apply definition")

        cls = self._repo.get_class(node_id)
        if cls is None:
            raise ValueError(f"Class {node_id} not found")

        candidates = enumerate_items(run.output_summary.get("candidates"), "refinement")
        check_accepted_ids(accepted_candidate_ids, {cid for cid, _ in candidates})
        if accepted_candidate_ids is not None:
            selected = set(accepted_candidate_ids)
            qualifying = [c for cid, c in candidates if cid in selected]
        else:
            qualifying = [
                c for _, c in candidates if c.get("confidence", 0.0) >= confidence_threshold
            ]
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

        self._ontology_service.update_class(node_id, description=new_definition)
        result.classes_updated += 1
        result.validate()
        return result
