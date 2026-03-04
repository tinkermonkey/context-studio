"""
Port interfaces for the Versioning bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
Response dataclasses are defined in this file alongside their corresponding ports.
"""
from dataclasses import dataclass
from typing import Protocol, Optional, Sequence

from domain.versioning.entities import ChangeEvent, ConflictReport, MergeResult


@dataclass
class SyncResult:
    """Result of a sync operation with a remote target."""

    sync_id: str
    pushed_count: int
    pulled_count: int
    conflict_report: Optional[ConflictReport]
    status: str


class SyncStatus(Protocol):
    """Status port for querying sync state."""

    def get_last_sync(self) -> Optional[str]:
        """Get the timestamp of the last sync (ISO datetime string)."""
        ...


class ChangeRepository(Protocol):
    """Repository port for managing change events."""

    def record_change(self, event: ChangeEvent) -> ChangeEvent:
        """Record a change event."""
        ...

    def list_changes(self, since: Optional[str] = None) -> Sequence[ChangeEvent]:
        """List change events, optionally filtered by timestamp (ISO datetime string)."""
        ...

    def get_change(self, event_id: str) -> Optional[ChangeEvent]:
        """Retrieve a change event by ID."""
        ...


class SyncTarget(Protocol):
    """Target port for syncing with remote systems."""

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """Push local change events to remote."""
        ...

    def pull(self, since: Optional[str]) -> Sequence[ChangeEvent]:
        """Pull remote change events since timestamp (ISO datetime string)."""
        ...

    def resolve_conflicts(self, report: ConflictReport) -> MergeResult:
        """Resolve conflicts and return merge result."""
        ...
