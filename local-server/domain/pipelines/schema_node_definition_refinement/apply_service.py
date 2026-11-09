"""
Apply service for schema node definition refinement pipeline.

Applies the chosen (or else the highest-confidence) refined definition candidate from
a completed definition refinement run to the class or property definition it refined.
The write goes through OntologyService.update_class or update_property_definition, so
an update event (and thus a ChangeEvent with the previous description) is recorded and
reverting the run restores it.
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
    Applies the best definition candidate from a definition refinement run to its node.
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
        Apply a definition candidate to the target node: the highest-confidence one
        among those selected or, without a selection, among those over the threshold.

        The node_id and node_type come from run.output_summary (set by the orchestrator);
        node_type is "Class" or "PropertyDefinition", and Class when absent.

        Args:
            run: Completed definition refinement PipelineRun
            confidence_threshold: Minimum candidate confidence to consider.
                Ignored when ``accepted_candidate_ids`` is given.
            accepted_candidate_ids: Explicit selection of ``refinement-{i}`` ids

        Returns:
            ApplyResult with classes_updated / classes_skipped for a class, or
            properties_updated / properties_skipped for a property definition

        Raises:
            ValueError: If node_id is missing from output_summary or the node does not exist
            ApplySelectionError: If an accepted id is not a candidate of this run
        """
        result = ApplyResult()
        node_id = run.output_summary.get("node_id", "")
        if not node_id:
            raise ValueError("node_id missing from output_summary — cannot apply definition")

        is_property = run.output_summary.get("node_type") == "PropertyDefinition"
        if is_property:
            if self._repo.get_property_definition(node_id) is None:
                raise ValueError(f"Property definition {node_id} not found")
        elif self._repo.get_class(node_id) is None:
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
            return self._skipped(result, is_property)

        # Pick highest-confidence candidate
        best = max(qualifying, key=lambda c: c.get("confidence", 0.0))
        new_definition = (best.get("definition") or "").strip()
        if not new_definition:
            return self._skipped(result, is_property)

        if is_property:
            self._ontology_service.update_property_definition(node_id, description=new_definition)
            result.properties_updated += 1
        else:
            self._ontology_service.update_class(node_id, description=new_definition)
            result.classes_updated += 1
        result.validate()
        return result

    @staticmethod
    def _skipped(result: ApplyResult, is_property: bool) -> ApplyResult:
        """Record that no candidate was applied."""
        if is_property:
            result.properties_skipped += 1
        else:
            result.classes_skipped += 1
        result.validate()
        return result
