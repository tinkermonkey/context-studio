"""
Domain events for the pipeline bounded context.

Events are immutable signals emitted when pipeline operations complete.
All events inherit from DomainEvent and use frozen dataclasses for immutability.
No framework or external dependencies - pure Python only.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.ontology.events import DomainEvent


@dataclass(frozen=True)
class PipelineExecuted(DomainEvent):
    """Emitted when a pipeline execution completes."""

    execution_id: str
    pipeline_id: str
    status: str
