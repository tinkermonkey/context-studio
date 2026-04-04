"""Port protocols for versioning domain."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence

from domain.versioning.entities import ChangeEvent, Changeset, EntityVersion, Proposal
from domain.versioning.value_objects import SyncResult


class ChangeRepository(Protocol):
    """Port for persisting changes and versions."""

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: str,
        new_state: dict,
        previous_state: Optional[dict] = None,
        user_id: Optional[str] = None,
        change_reason: Optional[str] = None,
        changeset_id: Optional[str] = None,
    ) -> str:
        """Record a change event and return its ID."""
        ...

    def get_changes(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[ChangeEvent]:
        """Get change events with optional filters."""
        ...

    def get_changes_by_ids(self, event_ids: list[str]) -> list[ChangeEvent]:
        """Retrieve change events by their IDs."""
        ...

    def mark_processed(self, event_ids: list[str]) -> None:
        """Mark events as processed."""
        ...

    def get_unprocessed(self, limit: int = 500) -> list[ChangeEvent]:
        """Get unprocessed change events."""
        ...

    def save_version(self, version: EntityVersion) -> None:
        """Save an entity version snapshot."""
        ...

    def get_version(
        self, entity_id: str, version: int
    ) -> Optional[EntityVersion]:
        """Get a specific entity version."""
        ...

    def get_latest_version(self, entity_id: str) -> Optional[EntityVersion]:
        """Get the latest version of an entity."""
        ...

    def list_versions(self, entity_id: str) -> list[EntityVersion]:
        """List all versions of an entity."""
        ...

    def create_changeset(self, changeset: Changeset) -> Changeset:
        """Create a new changeset."""
        ...

    def get_changeset(self, changeset_id: str) -> Optional[Changeset]:
        """Get a changeset by ID."""
        ...

    def update_changeset(self, changeset: Changeset) -> Changeset:
        """Update an existing changeset."""
        ...

    def create_proposal(self, proposal: Proposal) -> Proposal:
        """Create a new proposal."""
        ...

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a proposal by ID."""
        ...

    def update_proposal(self, proposal: Proposal) -> Proposal:
        """Update an existing proposal."""
        ...


class SyncTarget(Protocol):
    """Port for remote synchronization."""

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """Push change events to remote."""
        ...

    def pull(self, since: Optional[datetime] = None) -> list[ChangeEvent]:
        """Pull change events from remote."""
        ...

    def is_configured(self) -> bool:
        """Check if sync is configured."""
        ...
