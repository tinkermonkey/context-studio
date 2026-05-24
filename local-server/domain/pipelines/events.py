"""
Domain events for the Pipeline Management bounded context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from domain.events import DomainEvent


@dataclass(frozen=True)
class PipelineExecuted(DomainEvent):
    """
    Event emitted when a pipeline execution completes.

    Attributes:
        execution_id: ID of the Execution that completed
        pipeline_id: ID of the PipelineConfiguration that was executed
        status: Completion status ("success" | "error" | "timeout")
    """

    _aggregate_id_field: ClassVar[str] = "execution_id"
    execution_id: str = ""
    pipeline_id: str = ""
    status: str = ""
