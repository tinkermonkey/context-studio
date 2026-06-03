"""
Domain events for the Version Control & Collaboration bounded context.

These events capture significant state changes in changesets and synchronization operations.
They are published by the VersioningService and subscribed to by domain event handlers
for audit trails, notifications, and other cross-context concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from domain.events import DomainEvent
from domain.versioning.value_objects import SyncDirection


@dataclass(frozen=True)
class ChangesetMerged(DomainEvent):
    """
    Event published when a changeset proposal is successfully merged.

    This event indicates that all conflict resolutions are complete and the changes
    have been applied to the workspace, transitioning the changeset to MERGED state.

    Attributes:
        changeset_id: ID of the changeset that was merged
        proposal_id: ID of the proposal that was merged
        merged_at: Timestamp of when the merge occurred
        events_applied: Number of change events included in the changeset
    """

    _aggregate_id_field: ClassVar[str] = "changeset_id"

    changeset_id: str = ""
    proposal_id: str = ""
    merged_at: datetime = None  # type: ignore
    events_applied: int = 0

    def __post_init__(self) -> None:
        """Auto-populate aggregate_id and validate required fields."""
        super().__post_init__()
        if self.merged_at is None:
            raise ValueError("ChangesetMerged event requires merged_at timestamp")


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
            raise ValueError(
                "SyncCompleted event requires direction to be a valid SyncDirection"
            )
        if self.completed_at is None:
            raise ValueError("SyncCompleted event requires completed_at timestamp")
