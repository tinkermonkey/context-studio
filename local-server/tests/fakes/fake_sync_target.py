"""
Minimal fake implementation of the SyncTarget protocol for testing.

Useful for testing synchronization logic without external dependencies.
"""

from datetime import datetime
from typing import Optional, Sequence

from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import SyncResult


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
            SyncResult with count of pushed events
        """
        if not self._configured:
            return SyncResult(pushed=0, pulled=0, errors=["Sync target not configured"])

        self._pushed_events.extend(events)
        return SyncResult(pushed=len(events), pulled=0, errors=[])

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
