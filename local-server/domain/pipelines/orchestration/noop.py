"""
No-op pipeline implementation for testing the framework end-to-end.

Exercises:
- Pipeline type/implementation registration
- LangGraph state machine construction
- PipelineRun persistence
- change_events linkage
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipeline.ports import LLMProvider


@dataclass
class NoOpPipelineState(PipelineState):
    """Extended state for no-op pipeline with step tracking."""

    step: int = 0
    steps_completed: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize steps tracking."""
        if self.steps_completed is None:
            object.__setattr__(self, "steps_completed", [])


class NoOpPipelineOrchestrator(PipelineOrchestrator):
    """
    Minimal orchestrator that exercises the framework without domain logic.

    State machine:
    1. Initialize — set up state
    2. Process — simulate work (no LLM call)
    3. Finalize — populate result and metrics
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        """Initialize no-op orchestrator."""
        super().__init__(llm_provider)

    def build_graph(self) -> Any:
        """
        Build LangGraph state graph.

        For now, returns None (would be used by execute() in full impl).
        """
        return None

    async def execute(self, state: PipelineState) -> PipelineState:
        """
        Execute the no-op pipeline.

        Steps:
        1. Validate input
        2. Simulate processing
        3. Return populated result

        Args:
            state: PipelineState with input_data

        Returns:
            Updated state with result and metrics
        """
        # Step 1: Initialize
        state = replace(
            state,
            current_status="running",
            steps_completed=["initialize"],
        )

        # Step 2: Process (no-op)
        state = replace(
            state,
            steps_completed=(state.steps_completed or []) + ["process"],
        )

        # Step 3: Finalize
        result = {
            "status": "completed",
            "message": "No-op pipeline completed successfully",
            "input_echo": state.input_data,
            "step_count": 2,
            "steps": state.steps_completed or [],
        }

        state = replace(
            state,
            current_status="completed",
            result=result,
            steps_completed=(state.steps_completed or []) + ["finalize"],
        )

        return state
