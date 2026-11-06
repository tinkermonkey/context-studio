"""Port protocols for versioning domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, Sequence

from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.entities import ChangeEvent
from domain.versioning.gold import DecisionFilter, ProposalDecision
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
    """Port for persisting and querying change events."""

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: ChangeOperation,
        new_state: dict,
        previous_state: Optional[dict] = None,
        user_id: Optional[str] = None,
        change_reason: Optional[str] = None,
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

    def delete_changes(self, event_ids: list[str]) -> None:
        """
        Delete change events by their IDs (used for rollback on pull failure).

        Args:
            event_ids: List of event IDs to delete

        Raises:
            VersionNotFoundError: If any event IDs don't exist
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
    """Port for storing change proposals and the outcome of each operation."""

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

    def save_operations(
        self,
        proposal_id: str,
        operations: Sequence[ProposedOperation],
        decisions: Sequence[ProposalDecision] = (),
    ) -> None:
        """Persist the status, result, reason, scope, base and applied fields of these operations.

        The decisions taken on them are recorded with them, in the same commit.

        Raises ValueError for an unknown proposal or operation.
        """
        ...

    def supersede_decisions(self, proposal_id: str, superseded_at: datetime, by: str) -> int:
        """Mark the proposal's decisions not yet superseded as superseded; return how many."""
        ...

    def list_decisions(
        self, filters: DecisionFilter, limit: Optional[int] = None, offset: int = 0
    ) -> list[ProposalDecision]:
        """Decisions matching the filters, oldest first (limit None: all of them)."""
        ...

    def count_decisions(self, filters: DecisionFilter) -> int:
        """Count decisions matching the filters."""
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
    an identifier). Unedited creates and updates they govern are checked too,
    as they apply: what was valid when proposed may not be any more.
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

    def check(self, operation: ProposedOperation, fields: dict[str, Any]) -> None:
        """
        Refuse an unedited create or update the rules forbid as it applies now.

        Args:
            operation: A property-definition create or update, applied as proposed
            fields: Its fields, with "$ref" values resolved

        Raises:
            ValueError: With the reason, when it is refused
        """
        ...
