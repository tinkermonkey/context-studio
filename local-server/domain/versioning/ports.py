"""Port protocols for versioning domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, Sequence

from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.claims import Claim, ClaimFilter, ClaimTriage, ClaimVerdict
from domain.versioning.entities import ChangeEvent
from domain.versioning.gold import DecisionFilter, ProposalDecision
from domain.versioning.proposals import (
    ChangeProposal,
    Landing,
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
        landed: Optional[bool] = None,
    ) -> list[ChangeProposal]:
        """Return proposals, newest first, optionally filtered (landed: landed or not)."""
        ...

    def count_proposals(
        self,
        taxonomy_id: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        source: Optional[ProposalSource] = None,
        landed: Optional[bool] = None,
    ) -> int:
        """Count proposals matching the filters."""
        ...

    def set_landed(self, proposal_id: str, landed: Optional[Landing]) -> None:
        """Record where the proposal landed, or clear it (None)."""
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
        """
        Mark the proposal's applied decisions (applied, applied_with_edits) not yet
        superseded as superseded; rejections still stand. Return how many.
        """
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


class ClaimRepository(Protocol):
    """Port for a taxonomy's claims (see domain/versioning/claims.py)."""

    def upsert(self, claims: Sequence[Claim]) -> list[Claim]:
        """
        Add claims, or replace the ones whose (taxonomy_id, key) already exists.

        A replaced claim keeps its id and created_at, and keeps its triage and
        verdict only if its text is unchanged. Returns the stored claims, in order.
        """
        ...

    def delete_for_note(
        self, taxonomy_id: str, note_ref: str, keep_keys: Sequence[str] = ()
    ) -> int:
        """Delete a note's claims, except those with keep_keys; returns how many."""
        ...

    def get(self, claim_id: str) -> Optional[Claim]:
        """A claim by id, or None."""
        ...

    def list_claims(
        self, filters: ClaimFilter, limit: Optional[int] = None, offset: int = 0
    ) -> list[Claim]:
        """Matching claims, oldest first (then by key)."""
        ...

    def count_claims(self, filters: ClaimFilter) -> int:
        """How many claims match."""
        ...

    def save_triage(self, claim_id: str, triage: ClaimTriage) -> None:
        """Set a claim's triage, replacing any earlier one."""
        ...

    def set_verdict(self, claim_id: str, verdict: Optional[ClaimVerdict]) -> None:
        """Set or clear a claim's verdict."""
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
    Rules that some property definitions or predicates are under (e.g. the DR
    spec's relationship types and predicate catalog), whichever proposal changes
    them: property definitions are global, so the target decides, not the
    proposal's taxonomy.

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
            operation: A property-definition or predicate operation
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
            operation: A property-definition or predicate create or update, applied as
                proposed
            fields: Its fields, with "$ref" values resolved

        Raises:
            ValueError: With the reason, when it is refused
        """
        ...
