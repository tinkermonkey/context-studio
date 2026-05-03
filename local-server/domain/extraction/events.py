"""
Extraction domain events.

Domain events published when extraction operations complete.
"""

from dataclasses import dataclass
from typing import ClassVar

from domain.events import DomainEvent


@dataclass(frozen=True)
class ExtractionCompleted(DomainEvent):
    """
    Event published when text extraction completes successfully.

    Attributes:
        result_id: ID of the ExtractionResult that was produced
        entity_count: Number of unique entities in the result
        duration_ms: Total extraction time in milliseconds
    """

    _aggregate_id_field: ClassVar[str] = "result_id"
    result_id: str = ""
    entity_count: int = 0
    duration_ms: int = 0
