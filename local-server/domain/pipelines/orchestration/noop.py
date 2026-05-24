"""
No-op pipeline implementation for testing the framework end-to-end.

Exercises:
- Pipeline type/implementation registration
- Pipeline execution framework
- PipelineRun persistence
- change_events linkage
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from domain.pipelines.ports import LLMProvider
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState


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

    Execution flow:
    1. Initialize — set up state
    2. Process — simulate work (no LLM call)
    3. Finalize — populate result and metrics
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        """Initialize no-op orchestrator."""
        super().__init__(llm_provider)

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
        noop_state = cast(NoOpPipelineState, state)
        # Step 1: Initialize
        noop_state = replace(
            noop_state,
            current_status=PipelineRunStatus.RUNNING,
            steps_completed=["initialize"],
        )

        # Step 2: Process (no-op)
        noop_state = replace(
            noop_state,
            steps_completed=(noop_state.steps_completed or []) + ["process"],
        )

        # Step 3: Finalize
        result = {
            "status": "completed",
            "message": "No-op pipeline completed successfully",
            "input_echo": noop_state.input_data,
            "step_count": 2,
            "steps": noop_state.steps_completed or [],
        }

        noop_state = replace(
            noop_state,
            current_status=PipelineRunStatus.COMPLETED,
            result=result,
            steps_completed=(noop_state.steps_completed or []) + ["finalize"],
        )

        return noop_state
