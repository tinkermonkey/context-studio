"""
Port interfaces (protocols) for the Version Control & Collaboration bounded context.

Ports define contracts for external adapters (persistence, synchronization, etc.).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence

from .entities import ChangeEvent, EntityVersion, Changeset, Proposal
from .value_objects import SyncResult


class ChangeRepository(Protocol):
    """
    Port for persisting and retrieving change events and related entities.

    Handles all CRUD operations on change events, entity versions,
    changesets, and proposals.
    """

    # ChangeEvent operations
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
        """
        Record a new change event.

        Args:
            entity_id: ID of the entity that changed
            entity_type: Type of entity
            operation: Type of operation ('create', 'update', 'delete')
            new_state: JSON snapshot of entity after change
            previous_state: JSON snapshot of entity before change (optional)
            user_id: Optional ID of user who made the change
            change_reason: Optional explanation of the change
            changeset_id: Optional ID of changeset this belongs to

        Returns:
            The ID of the recorded change event
        """
        ...

    def get_changes(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[ChangeEvent]:
        """
        Retrieve change events with optional filters.

        Args:
            entity_id: Optional filter to changes for a specific entity
            since: Optional filter to changes after a specific timestamp
            limit: Maximum number of results to return

        Returns:
            List of matching ChangeEvent objects
        """
        ...

    def get_changes_by_ids(self, event_ids: list[str]) -> list[ChangeEvent]:
        """
        Retrieve change events by their IDs.

        Args:
            event_ids: List of change event IDs to retrieve

        Returns:
            List of matching ChangeEvent objects
        """
        ...

    def mark_processed(self, event_ids: list[str]) -> None:
        """
        Mark change events as processed (synchronized to remote).

        Args:
            event_ids: List of change event IDs to mark as processed
        """
        ...

    def get_unprocessed(self, limit: int = 500) -> list[ChangeEvent]:
        """
        Retrieve change events not yet synchronized to remote.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of unprocessed ChangeEvent objects
        """
        ...

    # EntityVersion operations
    def save_version(self, version: EntityVersion) -> None:
        """
        Persist an entity version snapshot.

        Args:
            version: The EntityVersion to save
        """
        ...

    def get_version(self, entity_id: str, version: int) -> Optional[EntityVersion]:
        """
        Retrieve a specific version of an entity.

        Args:
            entity_id: ID of the entity
            version: Version number

        Returns:
            The EntityVersion if found, None otherwise
        """
        ...

    def get_latest_version(self, entity_id: str) -> Optional[EntityVersion]:
        """
        Retrieve the most recent version of an entity.

        Args:
            entity_id: ID of the entity

        Returns:
            The latest EntityVersion if found, None otherwise
        """
        ...

    def list_versions(self, entity_id: str) -> list[EntityVersion]:
        """
        Retrieve all versions of an entity in order.

        Args:
            entity_id: ID of the entity

        Returns:
            List of EntityVersion objects in version order
        """
        ...

    # Changeset operations
    def create_changeset(self, changeset: Changeset) -> Changeset:
        """
        Create a new changeset.

        Args:
            changeset: The Changeset entity to create

        Returns:
            The persisted Changeset entity
        """
        ...

    def get_changeset(self, changeset_id: str) -> Optional[Changeset]:
        """
        Retrieve a changeset by ID.

        Args:
            changeset_id: ID of the changeset

        Returns:
            The Changeset if found, None otherwise
        """
        ...

    def update_changeset(self, changeset: Changeset) -> Changeset:
        """
        Update an existing changeset.

        Args:
            changeset: The Changeset entity to update

        Returns:
            The updated Changeset entity
        """
        ...

    # Proposal operations
    def create_proposal(self, proposal: Proposal) -> Proposal:
        """
        Create a new proposal.

        Args:
            proposal: The Proposal entity to create

        Returns:
            The persisted Proposal entity
        """
        ...

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """
        Retrieve a proposal by ID.

        Args:
            proposal_id: ID of the proposal

        Returns:
            The Proposal if found, None otherwise
        """
        ...

    def update_proposal(self, proposal: Proposal) -> Proposal:
        """
        Update an existing proposal.

        Args:
            proposal: The Proposal entity to update

        Returns:
            The updated Proposal entity
        """
        ...


class SyncTarget(Protocol):
    """
    Port for synchronizing changes with a remote workspace.

    Handles pushing local changes and pulling remote changes.
    """

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """
        Push local change events to remote.

        Args:
            events: Change events to push

        Returns:
            SyncResult with count of pushed events and any errors
        """
        ...

    def pull(self, since: Optional[datetime] = None) -> list[ChangeEvent]:
        """
        Pull change events from remote.

        Args:
            since: Optional timestamp to fetch changes after

        Returns:
            List of remote ChangeEvent objects
        """
        ...

    def is_configured(self) -> bool:
        """
        Check if remote sync target is configured.

        Returns:
            True if sync target is configured, False otherwise
        """
        ...
