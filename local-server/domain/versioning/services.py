"""
Domain service for the Version Control & Collaboration bounded context.

Implements change history queries, changeset lifecycle management,
and the proposal approval workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from .entities import ChangeEvent, EntityVersion, Changeset, Proposal, MergeResult
from .exceptions import VersionNotFoundError, ChangesetStateError
from .ports import ChangeRepository, SyncTarget
from .value_objects import ChangeState


class VersioningService:
    """
    Domain service for versioning operations.

    Coordinates change history queries, changeset lifecycle management,
    and the proposal workflow without mutating state directly.
    """

    def __init__(
        self,
        change_repo: ChangeRepository,
        sync_target: SyncTarget,
    ) -> None:
        """
        Initialize the VersioningService.

        Args:
            change_repo: Repository for persisting and retrieving versioning entities
            sync_target: Adapter for synchronizing changes with remote
        """
        self._repo = change_repo
        self._sync = sync_target

    # ============================================================================
    # Change History Query Methods
    # ============================================================================

    def get_change_history(
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
        return self._repo.get_changes(entity_id=entity_id, since=since, limit=limit)

    def get_entity_version(self, entity_id: str, version: int) -> EntityVersion:
        """
        Retrieve a specific version of an entity.

        Args:
            entity_id: ID of the entity
            version: Version number

        Returns:
            The EntityVersion object

        Raises:
            VersionNotFoundError: If the version does not exist
        """
        entity_version = self._repo.get_version(entity_id, version)
        if entity_version is None:
            raise VersionNotFoundError(
                f"Version {version} of entity {entity_id} not found"
            )
        return entity_version

    def get_latest_version(self, entity_id: str) -> Optional[EntityVersion]:
        """
        Retrieve the most recent version of an entity.

        Args:
            entity_id: ID of the entity

        Returns:
            The latest EntityVersion if found, None otherwise
        """
        return self._repo.get_latest_version(entity_id)

    def list_versions(self, entity_id: str) -> list[EntityVersion]:
        """
        Retrieve all versions of an entity in order.

        Args:
            entity_id: ID of the entity

        Returns:
            List of EntityVersion objects in version order
        """
        return self._repo.list_versions(entity_id)

    # ============================================================================
    # Changeset Lifecycle Methods
    # ============================================================================

    def create_changeset(
        self,
        name: str,
        description: Optional[str] = None,
        event_ids: Optional[list[str]] = None,
    ) -> Changeset:
        """
        Create a new changeset in WORKING state.

        Args:
            name: Human-readable name for the changeset
            description: Optional detailed description
            event_ids: Optional list of change event IDs to include

        Returns:
            The persisted Changeset entity in WORKING state
        """
        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id=str(uuid.uuid4()),
            name=name,
            state=ChangeState.WORKING,
            created_at=now,
            updated_at=now,
            description=description,
            event_ids=event_ids or [],
        )
        return self._repo.create_changeset(changeset)

    def stage_changeset(self, changeset_id: str) -> Changeset:
        """
        Transition a changeset from WORKING to STAGED.

        Args:
            changeset_id: ID of the changeset to stage

        Returns:
            The updated Changeset entity in STAGED state

        Raises:
            ChangesetStateError: If the changeset cannot transition to STAGED
        """
        changeset = self._repo.get_changeset(changeset_id)
        if changeset is None:
            raise VersionNotFoundError(f"Changeset {changeset_id} not found")

        changeset.transition_to(ChangeState.STAGED)
        changeset.updated_at = datetime.now(timezone.utc)
        return self._repo.update_changeset(changeset)

    def submit_proposal(self, changeset_id: str) -> Proposal:
        """
        Submit a changeset as a proposal for review.

        Transitions the changeset from STAGED to PROPOSED and creates
        a Proposal in 'open' state.

        Args:
            changeset_id: ID of the changeset to propose

        Returns:
            The created Proposal entity

        Raises:
            ChangesetStateError: If the changeset is not in STAGED state
        """
        changeset = self._repo.get_changeset(changeset_id)
        if changeset is None:
            raise VersionNotFoundError(f"Changeset {changeset_id} not found")

        changeset.transition_to(ChangeState.PROPOSED)
        changeset.updated_at = datetime.now(timezone.utc)
        self._repo.update_changeset(changeset)

        now = datetime.now(timezone.utc)
        proposal = Proposal(
            id=str(uuid.uuid4()),
            changeset_id=changeset_id,
            state="open",
            submitted_at=now,
        )
        return self._repo.create_proposal(proposal)

    # ============================================================================
    # Proposal Workflow Methods
    # ============================================================================

    def approve_proposal(self, proposal_id: str) -> Proposal:
        """
        Approve a proposal.

        Transitions the linked changeset from PROPOSED to APPROVED
        and updates the proposal state to 'approved'.

        Args:
            proposal_id: ID of the proposal to approve

        Returns:
            The updated Proposal entity

        Raises:
            VersionNotFoundError: If the proposal does not exist
        """
        proposal = self._repo.get_proposal(proposal_id)
        if proposal is None:
            raise VersionNotFoundError(f"Proposal {proposal_id} not found")

        changeset = self._repo.get_changeset(proposal.changeset_id)
        if changeset is None:
            raise VersionNotFoundError(
                f"Changeset {proposal.changeset_id} for proposal {proposal_id} not found"
            )

        changeset.transition_to(ChangeState.APPROVED)
        changeset.updated_at = datetime.now(timezone.utc)
        self._repo.update_changeset(changeset)

        now = datetime.now(timezone.utc)
        proposal.state = "approved"
        proposal.reviewed_at = now
        return self._repo.update_proposal(proposal)

    def reject_proposal(self, proposal_id: str, reason: str) -> Proposal:
        """
        Reject a proposal.

        Transitions the linked changeset back to WORKING state,
        records the rejection reason, and updates the proposal state to 'rejected'.

        Args:
            proposal_id: ID of the proposal to reject
            reason: Explanation for the rejection

        Returns:
            The updated Proposal entity

        Raises:
            VersionNotFoundError: If the proposal does not exist
        """
        proposal = self._repo.get_proposal(proposal_id)
        if proposal is None:
            raise VersionNotFoundError(f"Proposal {proposal_id} not found")

        changeset = self._repo.get_changeset(proposal.changeset_id)
        if changeset is None:
            raise VersionNotFoundError(
                f"Changeset {proposal.changeset_id} for proposal {proposal_id} not found"
            )

        changeset.transition_to(ChangeState.WORKING)
        changeset.updated_at = datetime.now(timezone.utc)
        self._repo.update_changeset(changeset)

        now = datetime.now(timezone.utc)
        proposal.state = "rejected"
        proposal.reviewed_at = now
        proposal.reviewer_notes = reason
        return self._repo.update_proposal(proposal)

    def merge_proposal(self, proposal_id: str) -> MergeResult:
        """
        Merge an approved proposal.

        In this phase, implements the happy path only: proposal must be
        in 'approved' state. Conflict detection and resolution will be
        implemented in Phase 4.4c.

        Transitions the changeset from APPROVED to MERGED and updates
        the proposal state to 'merged'.

        Args:
            proposal_id: ID of the proposal to merge

        Returns:
            MergeResult with details of the merge operation

        Raises:
            VersionNotFoundError: If the proposal does not exist
            ChangesetStateError: If the proposal is not in 'approved' state
        """
        proposal = self._repo.get_proposal(proposal_id)
        if proposal is None:
            raise VersionNotFoundError(f"Proposal {proposal_id} not found")

        if proposal.state != "approved":
            raise ChangesetStateError(
                f"Cannot merge proposal {proposal_id} in state '{proposal.state}': "
                "proposal must be in 'approved' state"
            )

        changeset = self._repo.get_changeset(proposal.changeset_id)
        if changeset is None:
            raise VersionNotFoundError(
                f"Changeset {proposal.changeset_id} for proposal {proposal_id} not found"
            )

        changeset.transition_to(ChangeState.MERGED)
        changeset.updated_at = datetime.now(timezone.utc)
        self._repo.update_changeset(changeset)

        now = datetime.now(timezone.utc)
        proposal.state = "merged"
        self._repo.update_proposal(proposal)

        return MergeResult(
            proposal_id=proposal_id,
            merged_at=now,
            events_applied=len(changeset.event_ids),
            conflicts_resolved=0,
        )
