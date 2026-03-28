"""
Domain events for the LLM Pipeline Management bounded context.

PipelineExecuted captures the completion of an LLM pipeline execution,
including the execution status and outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from domain.events import DomainEvent


@dataclass(frozen=True)
class PipelineExecuted(DomainEvent):
    """
    Event emitted when a pipeline execution completes.

    This event is published for every LLM pipeline execution, whether it
    succeeds, times out, or encounters an error. It enables downstream
    systems to track execution history, monitor performance, and trigger
    workflows based on execution outcomes.

    Attributes:
        execution_id: ID of the Execution that completed
        pipeline_id: ID of the PipelineConfiguration that was executed
        status: Completion status ("success" | "error" | "timeout")
    """

    _aggregate_id_field: ClassVar[str] = "execution_id"
    execution_id: str = ""
    pipeline_id: str = ""
    status: str = ""
