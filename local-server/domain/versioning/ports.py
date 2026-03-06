"""
Port interfaces for the Versioning bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
Response dataclasses are defined in this file alongside their corresponding ports.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Optional, Sequence

from domain.versioning.entities import ChangeEvent


@dataclass
class EntityVersion:
    """Version snapshot of an entity."""

    entity_id: str
    version: int
    state: dict
    created_at: datetime


@dataclass
class SyncResult:
    """Result of a sync operation with a remote target."""

    success: bool
    changes_pushed: int
    remote_version: Optional[str]
    errors: list[str] = field(default_factory=list)


@dataclass
class SyncStatus:
    """Status of sync operations."""

    last_sync: Optional[datetime]
    pending_changes: int
    remote_reachable: bool


class ChangeRepository(Protocol):
    """Repository for change events and entity version history."""

    def record_change(self, event: ChangeEvent) -> ChangeEvent:
        """Record a change event."""
        ...

    def get_changes(
        self,
        record_type: Optional[str] = None,
        record_id: Optional[str] = None,
        since: Optional[datetime] = None,
        processed: Optional[bool] = None,
        limit: int = 100,
    ) -> Sequence[ChangeEvent]:
        """Query change events with optional filtering."""
        ...

    def mark_processed(self, event_ids: Sequence[int]) -> int:
        """Mark events as processed and return count updated."""
        ...

    def save_version(self, version: EntityVersion) -> EntityVersion:
        """Save an entity version snapshot."""
        ...

    def get_version(self, entity_id: str, version: int) -> Optional[EntityVersion]:
        """Retrieve a specific version of an entity."""
        ...

    def get_latest_version(self, entity_id: str) -> Optional[EntityVersion]:
        """Retrieve the latest version of an entity."""
        ...

    def list_versions(self, entity_id: str) -> Sequence[EntityVersion]:
        """List all versions of an entity."""
        ...


class SyncTarget(Protocol):
    """Target for remote synchronization of changes."""

    def push_changes(self, changes: Sequence[ChangeEvent], metadata: dict) -> SyncResult:
        """Push local change events to remote."""
        ...

    def pull_changes(self, since: datetime) -> Sequence[ChangeEvent]:
        """Pull remote change events since timestamp."""
        ...

    def get_sync_status(self) -> SyncStatus:
        """Get current sync status."""
        ...
