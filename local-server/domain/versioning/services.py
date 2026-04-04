"""
Domain service for the Version Control & Collaboration bounded context.

Implements change history queries, changeset lifecycle management,
and the proposal approval workflow.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .entities import ChangeEvent, EntityVersion, Changeset, Proposal, MergeResult, ConflictReport
from .exceptions import VersionNotFoundError, ChangesetStateError, ConflictResolutionError
from .ports import ChangeRepository, SyncTarget
from .value_objects import ChangeState, ProposalState, SyncStatus, SyncResult
from .events import ChangesetMerged, SyncCompleted

if TYPE_CHECKING:
    from .conflict_service import ConflictResolutionService

_logger = logging.getLogger(__name__)


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
        conflict_service: ConflictResolutionService,
    ) -> None:
        """
        Initialize the VersioningService.

        Args:
            change_repo: Repository for persisting and retrieving versioning entities
            sync_target: Adapter for remote synchronization (S3, etc.)
            conflict_service: Service for detecting and resolving conflicts
        """
        self._repo = change_repo
        self._sync = sync_target
        self._conflict_service = conflict_service

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

    def get_changeset(self, changeset_id: str) -> Changeset:
        """
        Retrieve a changeset by ID.

        Args:
            changeset_id: ID of the changeset to retrieve

        Returns:
            The Changeset entity

        Raises:
            VersionNotFoundError: If the changeset does not exist
        """
        changeset = self._repo.get_changeset(changeset_id)
        if changeset is None:
            raise VersionNotFoundError(f"Changeset {changeset_id} not found")
        return changeset

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
        persisted = self._repo.create_changeset(changeset)
        _logger.info(
            "Changeset created (changeset_id=%s, name=%s, state=%s)",
            persisted.id,
            persisted.name,
            persisted.state,
        )
        return persisted

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
        updated = self._repo.update_changeset(changeset)
        _logger.info(
            "Changeset staged (changeset_id=%s, state=%s)",
            updated.id,
            updated.state,
        )
        return updated

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


    # ============================================================================
    # Conflict Resolution Methods (delegated to ConflictResolutionService)
    # ============================================================================

    def detect_conflicts(
        self, proposal_id: str, resolutions: Optional[dict[str, dict[str, str]]] = None
    ) -> ConflictReport:
        """
        Detect field-level conflicts in a proposal.

        Args:
            proposal_id: ID of the proposal to check for conflicts
            resolutions: Optional dict mapping entity_id -> {field_name: resolved_value}

        Returns:
            ConflictReport with detected conflicts (may be empty)

        Raises:
            VersionNotFoundError: If the proposal or changeset does not exist
        """
        return self._conflict_service.detect_conflicts(proposal_id, resolutions)

    def auto_resolve(self, conflict_report: ConflictReport) -> ConflictReport:
        """
        Automatically resolve all conflicts using last-write-wins strategy.

        Args:
            conflict_report: ConflictReport with unresolved conflicts

        Returns:
            The same ConflictReport with all conflicts marked as resolved
        """
        return self._conflict_service.auto_resolve(conflict_report)

    def resolve_conflicts(
        self,
        proposal_id: str,
        resolutions: dict[str, dict[str, str]],
    ) -> ConflictReport:
        """
        Manually resolve conflicts in a proposal.

        Args:
            proposal_id: ID of the proposal to resolve conflicts for
            resolutions: Dict mapping entity_id -> {field_name: resolved_value}

        Returns:
            ConflictReport with all conflicts marked as resolved

        Raises:
            ConflictResolutionError: If any conflicts remain unresolved
            VersionNotFoundError: If the proposal or changeset does not exist
        """
        return self._conflict_service.resolve_conflicts(proposal_id, resolutions)

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
            VersionNotFoundError: If the proposal does not exist
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
        report = self.detect_conflicts(proposal_id, proposal.conflict_resolutions)
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

    # ============================================================================
    # Synchronization Methods
    # ============================================================================

    def push_changes(self) -> SyncResult:
        """
        Push unprocessed local changes to the remote sync target.

        Retrieves unprocessed change events, pushes them to the sync target (e.g., S3),
        and marks them as processed upon successful push.

        Returns:
            SyncResult with count of pushed events and any errors

        Publishes:
            SyncCompleted event after completion
        """
        events = self._repo.get_unprocessed(limit=500)
        result = self._sync.push(events)

        # Mark as processed only the events that were actually pushed
        if result.pushed > 0 and result.pushed_event_ids:
            self._repo.mark_processed(result.pushed_event_ids)
            _logger.info(
                "Marked %d change events as processed after push",
                result.pushed,
            )

        _logger.info(
            "Push completed (pushed=%d, errors=%d)",
            result.pushed,
            len(result.errors),
        )
        return result

    def pull_changes(self) -> SyncResult:
        """
        Pull remote changes from the sync target and record them locally.

        Fetches changes from the sync target (e.g., S3) and records each change
        in the local repository atomically (all events or none).

        NOTE: The repository implementation MUST ensure that all record_change
        calls within this method execute in a single transaction. If one call
        fails, no events should be persisted to prevent partial success and
        duplicates on re-pull.

        Returns:
            SyncResult with count of pulled events and any errors

        Publishes:
            SyncCompleted event after completion
        """
        events = self._sync.pull()
        recorded_events = []
        errors = []

        # Record each pulled event - repository must handle transactional atomicity
        for event in events:
            try:
                self._repo.record_change(
                    entity_id=event.entity_id,
                    entity_type=event.entity_type,
                    operation=event.operation,
                    new_state=event.new_state,
                    previous_state=event.previous_state,
                    user_id=event.user_id,
                    change_reason=event.change_reason,
                )
                recorded_events.append(event.id)
            except Exception as e:
                error_msg = (
                    f"Failed to record change for entity {event.entity_id}: {str(e)}"
                )
                errors.append(error_msg)
                _logger.error(error_msg)
                # If any record fails, log which events were recorded before failure
                if recorded_events:
                    _logger.warning(
                        "Partial pull recorded %d events before failure. "
                        "Repository must handle transaction rollback to prevent duplicates.",
                        len(recorded_events),
                    )
                # Stop attempting to record more events after first failure
                break

        result = SyncResult(
            pushed=0, pulled=len(recorded_events), errors=errors, pushed_event_ids=[]
        )
        _logger.info(
            "Pull completed (pulled=%d, errors=%d)",
            result.pulled,
            len(result.errors),
        )
        return result

    def get_sync_status(self) -> SyncStatus:
        """
        Get the current synchronization status.

        Returns information about unprocessed changes awaiting push and whether
        the remote sync target is configured.

        Returns:
            SyncStatus with unprocessed count and configuration status
        """
        count = self._repo.count_unprocessed()

        status = SyncStatus(
            last_pushed_at=None,
            last_pulled_at=None,
            unprocessed_count=count,
            is_configured=self._sync.is_configured(),
        )
        _logger.debug(
            "Sync status: unprocessed=%d, configured=%s",
            count,
            self._sync.is_configured(),
        )
        return status

    # ============================================================================
    # Event Handlers (for subscribing to own events)
    # ============================================================================

    def on_changeset_merged(self, event: ChangesetMerged) -> None:
        """
        Handle ChangesetMerged event.

        This handler is subscribed during app startup. It can be used for
        audit logging, notifications, or other cross-context concerns.

        Args:
            event: The ChangesetMerged event
        """
        _logger.info(
            "ChangesetMerged event handled (changeset_id=%s, proposal_id=%s, events_applied=%d)",
            event.changeset_id,
            event.proposal_id,
            event.events_applied,
        )

    def on_sync_completed(self, event: SyncCompleted) -> None:
        """
        Handle SyncCompleted event.

        This handler is subscribed during app startup. It can be used for
        audit logging, notifications, or other cross-context concerns.

        Args:
            event: The SyncCompleted event
        """
        _logger.info(
            "SyncCompleted event handled (direction=%s, events_count=%d)",
            event.direction,
            event.events_count,
        )
