"""
Minimal fake implementation of the SyncTarget protocol for testing.

Useful for testing synchronization logic without external dependencies.
"""

from datetime import datetime, timezone
from typing import Optional, Sequence

from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import SyncResult, SyncStatus


class FakeSyncTarget:
    """
    In-memory implementation of the SyncTarget protocol.

    Provides basic push/pull behavior for testing without external
    synchronization infrastructure.
    """

    def __init__(self, configured: bool = True) -> None:
        """
        Initialize the fake sync target.

        Args:
            configured: Whether this sync target is configured (default True)
        """
        self._configured = configured
        self._pushed_events: list[ChangeEvent] = []
        self._remote_events: list[ChangeEvent] = []

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """
        Push local change events to remote storage.

        Args:
            events: Change events to push

        Returns:
            SyncResult with count of pushed events and their IDs
        """
        now = datetime.now(timezone.utc)
        if not self._configured:
            return SyncResult(
                pushed=0,
                pulled=0,
                errors=("Sync target not configured",),
                pushed_event_ids=(),
                started_at=now,
                completed_at=now,
            )

        self._pushed_events.extend(events)
        pushed_event_ids = tuple(event.id for event in events)
        return SyncResult(
            pushed=len(events),
            pulled=0,
            errors=(),
            pushed_event_ids=pushed_event_ids,
            started_at=now,
            completed_at=now,
        )

    def pull(self, since: Optional[datetime] = None) -> list[ChangeEvent]:
        """
        Pull change events from remote storage.

        Args:
            since: Optional timestamp to fetch changes after

        Returns:
            List of remote change events
        """
        if since:
            return [e for e in self._remote_events if e.timestamp >= since]
        return self._remote_events.copy()

    def is_configured(self) -> bool:
        """
        Check if sync target is configured.

        Returns:
            True if configured, False otherwise
        """
        return self._configured

    def get_sync_status(self) -> SyncStatus:
        """
        Get the status of remote synchronization.

        Returns:
            SyncStatus with sync status information
        """
        last_sync = None
        if self._pushed_events or self._remote_events:
            all_events = self._pushed_events + self._remote_events
            last_sync = max((e.timestamp for e in all_events), default=None)

        return SyncStatus(
            last_pushed_at=last_sync,
            last_pulled_at=last_sync,
            unprocessed_count=len(self._pushed_events),
            is_configured=self._configured,
            is_degraded=False,
        )

    # Test helpers

    def add_remote_events(self, events: list[ChangeEvent]) -> None:
        """
        Add events to remote storage (for testing purposes).

        Args:
            events: Change events to add to remote storage
        """
        self._remote_events.extend(events)

    def get_pushed_events(self) -> list[ChangeEvent]:
        """Get all events that have been pushed."""
        return self._pushed_events.copy()

    def clear(self) -> None:
        """Clear all stored events."""
        self._pushed_events.clear()
        self._remote_events.clear()
