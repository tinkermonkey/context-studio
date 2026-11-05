"""
Domain events for the Version Control & Collaboration bounded context.

These events capture significant synchronization operations.
They are published by the VersioningService and subscribed to by domain event handlers
for audit trails, notifications, and other cross-context concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.events import DomainEvent
from domain.versioning.value_objects import SyncDirection


@dataclass(frozen=True)
class SyncCompleted(DomainEvent):
    """
    Event published when a synchronization operation (push or pull) completes.

    This event indicates that the workspace has successfully synchronized changes
    with a remote workspace via the configured sync target (e.g., S3).

    Attributes:
        direction: Direction of the sync ('push' to send local changes, 'pull' to receive remote)
        events_count: Number of events pushed or pulled in this operation
        completed_at: Timestamp of when the sync operation completed
    """

    direction: SyncDirection = None  # type: ignore
    events_count: int = 0
    completed_at: datetime = None  # type: ignore

    def __post_init__(self) -> None:
        """Validate required fields and sync direction."""
        # Set aggregate_id to a fixed value since sync operations are system-wide
        if not self.aggregate_id:
            object.__setattr__(self, "aggregate_id", "sync")

        super().__post_init__()
        if not isinstance(self.direction, SyncDirection):
            raise ValueError("SyncCompleted event requires direction to be a valid SyncDirection")
        if self.completed_at is None:
            raise ValueError("SyncCompleted event requires completed_at timestamp")
