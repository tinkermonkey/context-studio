"""
No-op synchronization adapter for the Version Control & Collaboration bounded context.

Used as a fallback when S3 is not configured. This adapter implements the SyncTarget
port but performs no actual operations, allowing the system to function gracefully
in single-workspace mode without remote synchronization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import SyncResult, SyncStatus


class NoOpSyncTarget:
    """
    No-op implementation of the SyncTarget port.

    Used when remote synchronization is not configured. All operations succeed
    without side effects, allowing the versioning system to function normally
    in single-workspace scenarios.
    """

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """
        No-op push operation.

        Args:
            events: Ignored

        Returns:
            SyncResult indicating no events were pushed
        """
        now = datetime.now(timezone.utc)
        return SyncResult(pushed=0, pulled=0, errors=(), pushed_event_ids=(), started_at=now, completed_at=now)

    def pull(self, since: Optional[datetime] = None) -> list[ChangeEvent]:
        """
        No-op pull operation.

        Args:
            since: Ignored

        Returns:
            Empty list of change events
        """
        return []

    def is_configured(self) -> bool:
        """
        Check if sync target is configured.

        Returns:
            False, as no-op sync is not a real remote target
        """
        return False

    def get_sync_status(self) -> SyncStatus:
        """
        Get the status of remote synchronization.

        Returns:
            SyncStatus indicating no remote connectivity
        """
        return SyncStatus(
            last_pushed_at=None,
            last_pulled_at=None,
            unprocessed_count=0,
            is_configured=False,
            is_degraded=False,
        )
