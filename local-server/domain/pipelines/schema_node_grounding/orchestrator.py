"""
Orchestrator for schema node grounding pipeline.

Grounds schema nodes to external knowledge sources via a single-node
orchestrator that dispatches queries, normalizes results, scores candidates,
and returns ranked groundings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any

from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import LLMProvider
from domain.pipelines.schema_node_grounding.ports import GroundingAdapterPort
from domain.pipelines.schema_node_grounding.scoring import (
    GroundingScorer,
    NodeType,
    ScoredCandidate,
)

_logger = logging.getLogger(__name__)


@dataclass
class SchemaGroundingState(PipelineState):
    """
    State for schema node grounding pipeline execution.

    Extends PipelineState with fields specific to grounding.
    """

    node_label: str = ""
    node_type: NodeType = NodeType.CLASS
    sources: list[str] = field(default_factory=list)
    groundings: list[ScoredCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SchemaGroundingOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for schema node grounding operations.

    Coordinates external source queries, candidate normalization, scoring,
    and ranking to produce external reference candidates for schema nodes.

    Single-node execution flow:
    1. Dispatch queries to active sources (parallel via asyncio)
    2. Normalize source responses to common GroundingCandidate shape
    3. Score candidates using configurable weighted strategy
    4. Rank by confidence and truncate to top N
    5. Return candidates with rationale for human/agent review
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        grounding_adapter: GroundingAdapterPort,
        scorer: GroundingScorer,
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the grounding orchestrator.

        Args:
            llm_provider: LLM provider for semantic scoring (if needed)
            grounding_adapter: Adapter for external source queries
            scorer: GroundingScorer instance for combining scores
            config: Configuration dict (top_n, weights, type preferences, etc.)
        """
        super().__init__(llm_provider)
        self._grounding_adapter = grounding_adapter
        self._scorer = scorer
        self._config = config or {}

    async def execute(self, state: PipelineState) -> PipelineState:
        """
        Execute the schema node grounding pipeline.

        Args:
            state: SchemaGroundingState with:
                - input_data containing node_label, node_type, sources
                - llm_provider (for semantic scoring if configured)

        Returns:
            Updated SchemaGroundingState with groundings populated

        Raises:
            PipelineInputError: If required input fields are missing
            PipelineExecutionError: If pipeline execution fails
        """
        if not isinstance(state, SchemaGroundingState):
            state = SchemaGroundingState(
                run_id=state.run_id,
                pipeline_type=state.pipeline_type,
                input_data=state.input_data,
                current_status=state.current_status,
                llm_provider=state.llm_provider,
                result=state.result,
            )

        node_label = state.input_data.get("node_label", "")
        node_type_str = state.input_data.get("node_type", "Class")
        sources = state.input_data.get("sources", [])

        if not node_label:
            exc = PipelineInputError("node_label is required and cannot be empty")
            state = replace(
                state, current_status=PipelineRunStatus.FAILED, result={"error": str(exc)}
            )
            raise exc

        try:
            node_type = NodeType(node_type_str) if node_type_str else NodeType.CLASS
        except ValueError as exc:
            error_msg = f"Invalid node_type '{node_type_str}'. Must be one of: {', '.join([t.value for t in NodeType])}"
            input_error = PipelineInputError(error_msg)
            state = replace(
                state, current_status=PipelineRunStatus.FAILED, result={"error": error_msg}
            )
            raise input_error from exc

        state = replace(
            state,
            node_label=node_label,
            node_type=node_type,
            sources=sources or ["DBpedia", "ConceptNet"],
            current_status=PipelineRunStatus.RUNNING,
        )

        try:
            candidates = await self._grounding_adapter.query_sources(
                label=node_label,
                sources=state.sources,
            )

            if not candidates:
                return replace(
                    state,
                    groundings=[],
                    current_status=PipelineRunStatus.COMPLETED,
                    result={
                        "groundings": [],
                        "total_candidates_evaluated": 0,
                    },
                )

            scored_candidates = await self._scorer.score_candidates(
                candidates, node_label, state.node_type
            )

            top_n = self._config.get("top_n", 10)
            groundings = scored_candidates[:top_n]

            state = replace(
                state,
                groundings=groundings,
                current_status=PipelineRunStatus.COMPLETED,
                result={
                    "groundings": [
                        {
                            "uri": c.uri,
                            "label": c.label,
                            "description": c.description,
                            "source": c.source,
                            "match_confidence": c.match_confidence,
                            "match_rationale": c.match_rationale,
                        }
                        for c in groundings
                    ],
                    "total_candidates_evaluated": len(scored_candidates),
                },
            )

        except PipelineInputError:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise
        except PipelineExecutionError:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise
        except Exception as exc:
            _logger.error(f"Unexpected error during schema node grounding: {exc}", exc_info=True)
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": "Schema node grounding encountered an unexpected error"},
            )
            raise PipelineExecutionError("Schema node grounding encountered an unexpected error") from exc

        return state
