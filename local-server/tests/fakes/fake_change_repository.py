"""
In-memory fake implementation of the ChangeRepository protocol for testing.

Provides a simple dict-based storage for testing domain logic without
database dependencies.
"""

from datetime import datetime, timezone
from typing import Optional

from domain.versioning.entities import ChangeEvent
from domain.versioning.exceptions import VersionNotFoundError
from domain.versioning.value_objects import ChangeHistoryResult, ChangeOperation


class FakeChangeRepository:
    """
    In-memory implementation of the ChangeRepository protocol.

    Uses dictionaries to store entities in memory, useful for unit testing
    domain logic without database dependencies.
    """

    def __init__(self) -> None:
        """Initialize the fake repository with empty storage."""
        self._change_events: dict[str, ChangeEvent] = {}

    # ChangeEvent operations

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: ChangeOperation,
        new_state: dict,
        previous_state: Optional[dict] = None,
        user_id: Optional[str] = None,
        change_reason: Optional[str] = None,
        batch_run_id: Optional[str] = None,
    ) -> str:
        """Record a change event and return its ID."""
        import uuid

        event_id = str(uuid.uuid4())
        event = ChangeEvent(
            id=event_id,
            entity_id=entity_id,
            entity_type=entity_type,
            operation=operation,
            new_state=new_state,
            timestamp=datetime.now(timezone.utc),
            previous_state=previous_state,
            user_id=user_id,
            change_reason=change_reason,
            batch_run_id=batch_run_id,
            processed=False,
        )
        self._change_events[event_id] = event
        return event_id

    def get_changes(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        batch_run_id: Optional[str] = None,
        limit: Optional[int] = 100,
    ) -> ChangeHistoryResult:
        """Retrieve change events with optional filters and return total count."""
        events = list(self._change_events.values())

        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]

        if since:
            events = [e for e in events if e.timestamp >= since]

        if batch_run_id:
            events = [e for e in events if e.batch_run_id == batch_run_id]

        total_count = len(events)
        # Insertion order breaks timestamp ties, like rowid in the SQLite repository.
        position = {event_id: i for i, event_id in enumerate(self._change_events)}
        events.sort(key=lambda e: (e.timestamp, position[e.id]), reverse=True)
        return ChangeHistoryResult(events=tuple(events[:limit]), total=total_count)

    def get_changes_by_ids(self, event_ids: list[str]) -> list[ChangeEvent]:
        """Retrieve change events by their IDs."""
        return [self._change_events[eid] for eid in event_ids if eid in self._change_events]

    def mark_processed(self, event_ids: list[str]) -> None:
        """
        Mark change events as processed.

        Raises:
            VersionNotFoundError: If any event IDs don't exist
        """
        if not event_ids:
            return

        # Check all IDs exist first
        missing_ids = [eid for eid in event_ids if eid not in self._change_events]
        if missing_ids:
            raise VersionNotFoundError(f"Change events not found: {', '.join(sorted(missing_ids))}")

        # Mark all as processed
        for event_id in event_ids:
            self._change_events[event_id].processed = True

    def delete_changes(self, event_ids: list[str]) -> None:
        """
        Delete change events by their IDs (used for rollback on pull failure).

        Raises:
            VersionNotFoundError: If any event IDs don't exist
        """
        if not event_ids:
            return

        # Check all IDs exist first
        missing_ids = [eid for eid in event_ids if eid not in self._change_events]
        if missing_ids:
            raise VersionNotFoundError(f"Change events not found: {', '.join(sorted(missing_ids))}")

        # Delete all
        for event_id in event_ids:
            self._change_events.pop(event_id)

    def get_unprocessed(self, limit: int = 500) -> list[ChangeEvent]:
        """Retrieve unprocessed change events."""
        unprocessed = [e for e in self._change_events.values() if not e.processed]
        unprocessed.sort(key=lambda e: e.timestamp)
        return unprocessed[:limit]

    def count_unprocessed(self) -> int:
        """Count total unprocessed change events without loading them."""
        return sum(1 for e in self._change_events.values() if not e.processed)
