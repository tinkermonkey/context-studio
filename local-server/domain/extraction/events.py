"""
Extraction domain events.

Domain events published when extraction operations complete.
"""

from dataclasses import dataclass
from typing import ClassVar, Optional

from domain.events import DomainEvent


@dataclass(frozen=True)
class ExtractionCompleted(DomainEvent):
    """
    Event published when text extraction completes successfully.

    Attributes:
        result_id: ID of the ExtractionResult that was produced
        entity_count: Number of unique entities in the result
        duration_ms: Total extraction time in milliseconds
        batch_run_id: The extraction run the change is recorded under, passed
            explicitly rather than read from an ambient context; None records
            it under the run in the correlation context, if any
    """

    _aggregate_id_field: ClassVar[str] = "result_id"
    result_id: str = ""
    entity_count: int = 0
    duration_ms: int = 0
    batch_run_id: Optional[str] = None
