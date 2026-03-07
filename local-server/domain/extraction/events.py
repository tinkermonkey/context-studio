"""
Domain events for the extraction bounded context.

Events are immutable signals emitted when extraction operations complete.
All events inherit from DomainEvent and use frozen dataclasses for immutability.
No framework or external dependencies - pure Python only.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.ontology.events import DomainEvent


@dataclass(frozen=True)
class ExtractionCompleted(DomainEvent):
    """Emitted when an extraction pipeline run completes successfully."""

    execution_id: str
    entity_count: int
    taxonomy_id: str
