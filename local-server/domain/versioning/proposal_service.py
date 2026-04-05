"""
Domain service for proposal workflow management in the versioning context.

Encapsulates proposal submission, approval, rejection, and merging logic.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .entities import Proposal, MergeResult
from .exceptions import VersionNotFoundError, ChangesetStateError, ConflictResolutionError
from .ports import ChangeRepository
from .value_objects import ProposalState, ChangeState

if TYPE_CHECKING:
    from .conflict_service import ConflictResolutionService

_logger = logging.getLogger(__name__)


class ProposalWorkflowService:
    """
    Domain service for proposal workflow management.

    Coordinates proposal submission, approval, rejection, and merging operations.
    """

    def __init__(
        self,
        change_repo: ChangeRepository,
        conflict_service: ConflictResolutionService,
    ) -> None:
        """
        Initialize the ProposalWorkflowService.

        Args:
            change_repo: Repository for persisting proposal and changeset entities
            conflict_service: Service for detecting and resolving conflicts
        """
        self._repo = change_repo
        self._conflict_service = conflict_service

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
            VersionNotFoundError: If the changeset does not exist
        """
        changeset = self._repo.get_changeset(changeset_id)
        if changeset is None:
            raise VersionNotFoundError(f"Changeset {changeset_id} not found")

        now = datetime.now(timezone.utc)
        changeset.transition_to(ChangeState.PROPOSED)
        changeset.updated_at = now
        self._repo.update_changeset(changeset)

        proposal = Proposal(
            id=str(uuid.uuid4()),
            changeset_id=changeset_id,
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        persisted_proposal = self._repo.create_proposal(proposal)
        _logger.info(
            "Proposal submitted (proposal_id=%s, changeset_id=%s, state=%s)",
            persisted_proposal.id,
            changeset_id,
            persisted_proposal.state,
        )
        return persisted_proposal

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
            VersionNotFoundError: If the proposal or changeset does not exist
        """
        proposal = self._repo.get_proposal(proposal_id)
        if proposal is None:
            raise VersionNotFoundError(f"Proposal {proposal_id} not found")

        changeset = self._repo.get_changeset(proposal.changeset_id)
        if changeset is None:
            raise VersionNotFoundError(
                f"Changeset {proposal.changeset_id} for proposal {proposal_id} not found"
            )

        now = datetime.now(timezone.utc)
        changeset.transition_to(ChangeState.APPROVED)
        changeset.updated_at = now
        self._repo.update_changeset(changeset)

        proposal.transition_to(ProposalState.APPROVED)
        proposal.reviewed_at = now
        updated_proposal = self._repo.update_proposal(proposal)
        _logger.info(
            "Proposal approved (proposal_id=%s, changeset_id=%s, state=%s)",
            updated_proposal.id,
            proposal.changeset_id,
            updated_proposal.state,
        )
        return updated_proposal

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
            VersionNotFoundError: If the proposal or changeset does not exist
        """
        proposal = self._repo.get_proposal(proposal_id)
        if proposal is None:
            raise VersionNotFoundError(f"Proposal {proposal_id} not found")

        changeset = self._repo.get_changeset(proposal.changeset_id)
        if changeset is None:
            raise VersionNotFoundError(
                f"Changeset {proposal.changeset_id} for proposal {proposal_id} not found"
            )

        now = datetime.now(timezone.utc)
        changeset.transition_to(ChangeState.WORKING)
        changeset.updated_at = now
        self._repo.update_changeset(changeset)

        proposal.transition_to(ProposalState.REJECTED)
        proposal.reviewed_at = now
        proposal.reviewer_notes = reason
        updated_proposal = self._repo.update_proposal(proposal)
        _logger.info(
            "Proposal rejected (proposal_id=%s, changeset_id=%s, state=%s, reason=%s)",
            updated_proposal.id,
            proposal.changeset_id,
            updated_proposal.state,
            reason,
        )
        return updated_proposal

    def merge_proposal(self, proposal_id: str) -> MergeResult:
        """
        Merge an approved proposal.

        Detects conflicts using any stored resolutions, and blocks the merge
        if unresolved conflicts exist. Transitions the changeset from APPROVED
        to MERGED and updates the proposal state to 'merged'.

        Args:
            proposal_id: ID of the proposal to merge

        Returns:
            MergeResult with details of the merge operation

        Raises:
            VersionNotFoundError: If the proposal or changeset does not exist
            ChangesetStateError: If the proposal is not in 'approved' state
            ConflictResolutionError: If unresolved conflicts exist
        """
        proposal = self._repo.get_proposal(proposal_id)
        if proposal is None:
            raise VersionNotFoundError(f"Proposal {proposal_id} not found")

        if proposal.state != ProposalState.APPROVED:
            error_msg = (
                f"Cannot merge proposal {proposal_id} in state '{proposal.state}': "
                "proposal must be in 'approved' state"
            )
            _logger.error(error_msg)
            raise ChangesetStateError(error_msg)

        changeset = self._repo.get_changeset(proposal.changeset_id)
        if changeset is None:
            raise VersionNotFoundError(
                f"Changeset {proposal.changeset_id} for proposal {proposal_id} not found"
            )

        # Detect conflicts using any stored resolutions
        report = self._conflict_service.detect_conflicts(proposal_id, proposal.conflict_resolutions)
        if report.has_conflicts and not report.all_resolved:
            error_msg = (
                f"Proposal {proposal_id} has {len(report.conflicts)} unresolved conflicts"
            )
            _logger.error(error_msg)
            raise ConflictResolutionError(error_msg)

        now = datetime.now(timezone.utc)
        changeset.transition_to(ChangeState.MERGED)
        changeset.updated_at = now
        self._repo.update_changeset(changeset)

        proposal.transition_to(ProposalState.MERGED)
        self._repo.update_proposal(proposal)

        result = MergeResult(
            proposal_id=proposal_id,
            merged_at=now,
            events_applied=len(changeset.event_ids),
            conflicts_resolved=len(report.conflicts),
        )
        _logger.info(
            "Proposal merged (proposal_id=%s, changeset_id=%s, events_applied=%d, conflicts_resolved=%d)",
            proposal_id,
            proposal.changeset_id,
            result.events_applied,
            result.conflicts_resolved,
        )
        return result
