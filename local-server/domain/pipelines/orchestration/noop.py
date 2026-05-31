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

from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import LLMProvider


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
        1. Initialize
        2. Call LLM (exercises _call_llm)
        3. Process
        4. Finalize

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

        # Step 2: Call LLM (exercises _call_llm method)
        try:
            llm_response = await self._call_llm(
                system_prompt="You are a helpful assistant.",
                user_prompt="Acknowledge that you received this message.",
                model="test-model",
                temperature=0.0,
            )
            noop_state = replace(
                noop_state,
                steps_completed=(noop_state.steps_completed or []) + ["call_llm"],
            )
        except Exception as e:
            noop_state = replace(
                noop_state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(e), "step": "call_llm"},
            )
            return noop_state

        # Step 3: Process (no-op)
        noop_state = replace(
            noop_state,
            steps_completed=(noop_state.steps_completed or []) + ["process"],
        )

        # Step 4: Finalize
        result = {
            "status": "completed",
            "message": "No-op pipeline completed successfully",
            "input_echo": noop_state.input_data,
            "step_count": 3,
            "steps": noop_state.steps_completed or [],
            "llm_model": llm_response.model if "llm_response" in locals() else None,
            "llm_tokens_in": llm_response.tokens_in if "llm_response" in locals() else 0,
            "llm_tokens_out": llm_response.tokens_out if "llm_response" in locals() else 0,
        }

        noop_state = replace(
            noop_state,
            current_status=PipelineRunStatus.COMPLETED,
            result=result,
            steps_completed=(noop_state.steps_completed or []) + ["finalize"],
        )

        return noop_state
