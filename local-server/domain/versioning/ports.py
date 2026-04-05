"""Port protocols for versioning domain."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence

from domain.versioning.entities import ChangeEvent, Changeset, EntityVersion, Proposal
from domain.versioning.value_objects import SyncResult, ChangeOperation, ChangeHistoryResult


class ChangeRepository(Protocol):
    """Port for persisting changes and versions."""

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: ChangeOperation,
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
    ) -> ChangeHistoryResult:
        """Get change events with optional filters, returning paginated results with total count."""
        ...

    def get_changes_by_ids(self, event_ids: list[str]) -> list[ChangeEvent]:
        """Retrieve change events by their IDs."""
        ...

    def mark_processed(self, event_ids: list[str]) -> None:
        """
        Mark events as processed.

        Args:
            event_ids: List of event IDs to mark as processed

        Raises:
            VersionNotFoundError: If any event IDs don't exist
        """
        ...

    def get_unprocessed(self, limit: int = 500) -> list[ChangeEvent]:
        """Get unprocessed change events."""
        ...

    def count_unprocessed(self) -> int:
        """Count total unprocessed change events without loading them."""
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
        """
        Update an existing changeset.

        Args:
            changeset: The Changeset domain entity with updated fields

        Returns:
            The updated Changeset domain entity

        Raises:
            VersionNotFoundError: If the changeset does not exist
        """
        ...

    def create_proposal(self, proposal: Proposal) -> Proposal:
        """Create a new proposal."""
        ...

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a proposal by ID."""
        ...

    def update_proposal(self, proposal: Proposal) -> Proposal:
        """
        Update an existing proposal.

        Args:
            proposal: The Proposal domain entity with updated fields

        Returns:
            The updated Proposal domain entity

        Raises:
            VersionNotFoundError: If the proposal does not exist
        """
        ...

    def update_changeset_and_proposal_on_submit(
        self, changeset: Changeset, proposal: Proposal
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset and create proposal on submit.

        Ensures both operations succeed or both fail together. This atomic operation
        prevents leaving the system in an inconsistent state where the changeset is
        PROPOSED but no proposal exists, or vice versa.

        Args:
            changeset: The Changeset domain entity with updated state
            proposal: The new Proposal domain entity to create

        Returns:
            Tuple of (updated Changeset, created Proposal)

        Raises:
            VersionNotFoundError: If the changeset does not exist
        """
        ...

    def update_changeset_and_proposal_on_approve(
        self, changeset: Changeset, proposal: Proposal
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset and proposal on approve.

        Ensures both operations succeed or both fail together. This atomic operation
        prevents leaving the system in an inconsistent state where the changeset is
        APPROVED but the proposal is still OPEN, or vice versa.

        Args:
            changeset: The Changeset domain entity with state transitioned to APPROVED
            proposal: The Proposal domain entity with state transitioned to APPROVED

        Returns:
            Tuple of (updated Changeset, updated Proposal)

        Raises:
            VersionNotFoundError: If the changeset or proposal does not exist
        """
        ...

    def update_changeset_and_proposal_on_reject(
        self, changeset: Changeset, proposal: Proposal
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset and proposal on reject.

        Ensures both operations succeed or both fail together. This atomic operation
        prevents leaving the system in an inconsistent state where the changeset is
        WORKING but the proposal is still OPEN, or vice versa.

        Args:
            changeset: The Changeset domain entity with state transitioned to WORKING
            proposal: The Proposal domain entity with state transitioned to REJECTED

        Returns:
            Tuple of (updated Changeset, updated Proposal)

        Raises:
            VersionNotFoundError: If the changeset or proposal does not exist
        """
        ...

    def update_changeset_and_proposal_on_merge(
        self, changeset: Changeset, proposal: Proposal
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset and proposal on merge.

        Ensures both operations succeed or both fail together. This atomic operation
        prevents leaving the system in an inconsistent state where the changeset is
        MERGED but the proposal is still APPROVED, or vice versa.

        Args:
            changeset: The Changeset domain entity with state transitioned to MERGED
            proposal: The Proposal domain entity with state transitioned to MERGED

        Returns:
            Tuple of (updated Changeset, updated Proposal)

        Raises:
            VersionNotFoundError: If the changeset or proposal does not exist
        """
        ...

    def delete_changes(self, event_ids: list[str]) -> None:
        """
        Delete change events by their IDs (used for rollback on pull failure).

        Args:
            event_ids: List of event IDs to delete

        Raises:
            VersionNotFoundError: If any event IDs don't exist
        """
        ...

    def save_conflict_resolutions(
        self, proposal_id: str, resolutions: dict[str, dict[str, str]]
    ) -> None:
        """
        Persist conflict resolutions for a proposal.

        Args:
            proposal_id: ID of the proposal
            resolutions: Dict mapping entity_id -> {field_name: resolved_value}
        """
        ...

    def get_conflict_resolutions(
        self, proposal_id: str
    ) -> dict[str, dict[str, str]]:
        """
        Retrieve persisted conflict resolutions for a proposal.

        Args:
            proposal_id: ID of the proposal

        Returns:
            Dict mapping entity_id -> {field_name: resolved_value}
        """
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
