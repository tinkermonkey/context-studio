"""
Domain events for the Graph Analysis bounded context.

Events capture state changes affecting the graph analysis system. The primary
event is GraphInvalidated, which signals that cached graph structures need
to be rebuilt due to changes in the underlying ontology.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar
from uuid import uuid4


@dataclass(frozen=True)
class GraphEvent:
    """
    Base class for all domain events in the Graph Analysis context.

    All events have an event ID, timestamp, and an aggregate ID identifying
    the taxonomy or graph entity that was affected.

    Attributes:
        event_id: Unique identifier for this event (typically a UUID string)
        occurred_at: Timestamp of when the event occurred
        aggregate_id: UUID of the aggregate (entity) that triggered the event
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    aggregate_id: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    _aggregate_id_field: ClassVar[str] = ""

    def __post_init__(self) -> None:
        """
        Auto-populate aggregate_id from the specified field and validate string fields.

        For subclasses that set _aggregate_id_field, this method copies the value
        from that field to aggregate_id before validation runs. Then validates that
        required string fields are not empty.

        Raises:
            ValueError: If any string field is empty or contains only whitespace
        """
        # Auto-populate aggregate_id from subclass field if configured
        if self._aggregate_id_field and not self.aggregate_id:
            object.__setattr__(self, "aggregate_id", getattr(self, self._aggregate_id_field))

        # Validate that all string fields (including aggregate_id) are non-empty
        for field_name, _ in self.__dataclass_fields__.items():
            # Skip internal class variable fields
            if field_name.startswith("_"):
                continue
            v = getattr(self, field_name)
            # Only validate string fields; skip datetime and other types
            if isinstance(v, str) and not v.strip():
                raise ValueError(f"Event field '{field_name}' cannot be empty")


@dataclass(frozen=True)
class GraphInvalidated(GraphEvent):
    """
    Event emitted when the graph state is invalidated and needs recomputation.

    This event signals that cached graph structures (in-memory NetworkX graph
    and RDF graph) are stale and should be rebuilt from the ontology repository.

    Attributes:
        taxonomy_id: ID of the affected taxonomy
        reason: Human-readable reason for invalidation
    """

    _aggregate_id_field: ClassVar[str] = "taxonomy_id"
    taxonomy_id: str = ""
    reason: str = ""
