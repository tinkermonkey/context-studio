"""Port protocols for versioning domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, Sequence

from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.entities import ChangeEvent, Changeset, EntityVersion, Proposal
from domain.versioning.proposals import (
    ChangeProposal,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)
from domain.versioning.value_objects import (
    ChangeHistoryResult,
    ChangeOperation,
    SyncResult,
    SyncStatus,
)


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
        batch_run_id: Optional[str] = None,
    ) -> str:
        """Record a change event and return its ID."""
        ...

    def get_changes(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        batch_run_id: Optional[str] = None,
        limit: Optional[int] = 100,
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

    def get_version(self, entity_id: str, version: int) -> Optional[EntityVersion]:
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

    def list_changesets(self, limit: int = 100) -> list[Changeset]:
        """List all changesets."""
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
        Atomically create proposal and update changeset on submit.

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

    def atomic_update_changeset_and_proposal(
        self, changeset: Changeset, proposal: Proposal
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset and proposal on approve, reject, or merge.

        Ensures both operations succeed or both fail together. This atomic operation
        prevents leaving the system in an inconsistent state where one entity is
        updated but the other is not.

        Args:
            changeset: The Changeset domain entity with transitioned state
            proposal: The Proposal domain entity with transitioned state

        Returns:
            Tuple of (updated Changeset, updated Proposal)

        Raises:
            VersionNotFoundError: If the changeset or proposal does not exist
        """
        ...

    def atomic_update_on_merge(
        self,
        changeset: Changeset,
        proposal: Proposal,
        versions: list[EntityVersion],
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset, proposal, and save entity versions on merge.

        The changeset and proposal state transition, along with all entity version
        snapshots, are persisted within a single transaction. If any operation fails,
        all changes are rolled back to maintain consistency between the merge state
        and version snapshots.

        Args:
            changeset: The Changeset domain entity with transitioned state
            proposal: The Proposal domain entity with transitioned state
            versions: List of EntityVersion snapshots to persist for merged entities

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
        self, proposal_id: str, resolutions: dict[str, dict[str, object]]
    ) -> None:
        """
        Persist conflict resolutions for a proposal.

        Args:
            proposal_id: ID of the proposal
            resolutions: Dict mapping entity_id -> {field_name: resolved_value}
        """
        ...

    def get_conflict_resolutions(self, proposal_id: str) -> dict[str, dict[str, object]]:
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

    def get_sync_status(self) -> SyncStatus:
        """Get the status of remote synchronization."""
        ...


class ChangeProposalRepository(Protocol):
    """
    Port for storing change proposals and the outcome of each operation.

    Not to be confused with ``entities.Proposal``, the request to merge a
    changeset handled by the changeset methods above.
    """

    def create(self, proposal: ChangeProposal) -> ChangeProposal:
        """Store a new proposal with its operations; its id becomes a batch run id.

        Raises ValueError if a batch run with that id already exists.
        """
        ...

    def get(self, proposal_id: str) -> Optional[ChangeProposal]:
        """Return the proposal with its operations in seq order, or None."""
        ...

    def list_proposals(
        self,
        taxonomy_id: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        source: Optional[ProposalSource] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChangeProposal]:
        """Return proposals, newest first, optionally filtered."""
        ...

    def count_proposals(
        self,
        taxonomy_id: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        source: Optional[ProposalSource] = None,
    ) -> int:
        """Count proposals matching the filters."""
        ...

    def save_operations(self, proposal_id: str, operations: Sequence[ProposedOperation]) -> None:
        """Persist the status, result, reason, scope and applied fields of these operations.

        Raises ValueError for an unknown proposal or operation.
        """
        ...

    def set_status(self, proposal_id: str, status: ProposalStatus) -> None:
        """Persist the proposal's status."""
        ...


class ApprovalPolicyRepository(Protocol):
    """Port for each taxonomy's approval policy (at most one per taxonomy)."""

    def get(self, taxonomy_id: str) -> Optional[ApprovalPolicy]:
        """Return the taxonomy's policy, or None if none is set."""
        ...

    def save(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        """Create or replace the policy of policy.taxonomy_id."""
        ...


class ProposalApplyRules(Protocol):
    """
    Rules that some property definitions are under (e.g. the DR spec's
    relationship types), whichever proposal changes them: property definitions
    are global, so the target decides, not the proposal's taxonomy.

    ProposalService checks a reviewer's edit like any proposed update, then
    asks the rules that govern the operation just before it applies (inside
    the proposal's lock, after earlier operations of the same apply have run).
    The rules may refuse the edit or complete it with fields they derive (e.g.
    an identifier).
    """

    def governs(self, operation: ProposedOperation, fields: dict[str, Any]) -> bool:
        """
        Whether these rules govern the operation: its target, or what its
        fields point it at.

        Args:
            operation: A property-definition operation
            fields: The fields it is about to apply (proposed or edited)
        """
        ...

    def prepare(
        self,
        proposal: ChangeProposal,
        operation: ProposedOperation,
        fields: dict[str, Any],
        other_edits: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """
        The fields to apply as an update of the operation's target.

        Args:
            proposal: The proposal, with the outcomes of operations applied so far
            operation: The edited operation (an update or delete of its target)
            fields: The reviewer's fields, in the JSON encoding of snapshots
            other_edits: The other edits of the same apply, by operation id

        Raises:
            ValueError: With the reason, when the edit is refused
        """
        ...
