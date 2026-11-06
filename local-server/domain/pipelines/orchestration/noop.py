"""
No-op pipeline implementation for testing the framework end-to-end.

Exercises:
- Pipeline type/implementation registration
- Pipeline execution framework
- PipelineRun persistence
- change_events linkage
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Any, cast

from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.orchestration.base import (
    PipelineOrchestrator,
    PipelineState,
)
from domain.pipelines.ports import LLMProvider, PipelineRunStatusWriter


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

    The input may ask for a long run: `items` work items of `item_seconds`
    each, reporting progress after every item (for testing background runs).
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
    ) -> None:
        """Initialize no-op orchestrator."""
        super().__init__(llm_provider, run_id, status_writer)

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
        self._write_running_status()

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
            raise

        # Step 3: Process (no-op), item by item when the input asks for items
        items = _non_negative(noop_state.input_data.get("items"), int)
        item_seconds = _non_negative(noop_state.input_data.get("item_seconds"), float)
        if items:
            self._report_progress(0, items)
        for done in range(1, items + 1):
            await asyncio.sleep(item_seconds)
            self._report_progress(done, items)
        noop_state = replace(
            noop_state,
            steps_completed=(noop_state.steps_completed or []) + ["process"],
        )

        # Step 4: Finalize
        steps_with_finalize = (noop_state.steps_completed or []) + ["finalize"]
        result = {
            "status": "completed",
            "message": "No-op pipeline completed successfully",
            "input_echo": noop_state.input_data,
            "step_count": len(steps_with_finalize),
            "steps": steps_with_finalize,
            "llm_model": llm_response.model,
            "llm_tokens_in": llm_response.tokens_in,
            "llm_tokens_out": llm_response.tokens_out,
        }

        noop_state = replace(
            noop_state,
            current_status=PipelineRunStatus.COMPLETED,
            result=result,
            steps_completed=steps_with_finalize,
        )

        return noop_state


def _non_negative(value: Any, kind: type) -> Any:
    """The value as a non-negative int or float, or 0 when it is not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return kind(0)
    return kind(max(0, value))
