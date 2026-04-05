"""
Domain service for the Version Control & Collaboration bounded context.

Implements change history queries, changeset lifecycle management,
and the proposal approval workflow.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from .entities import EntityVersion, Changeset, Proposal, MergeResult, ConflictReport
from .exceptions import VersionNotFoundError
from .ports import ChangeRepository, SyncTarget
from .value_objects import SyncStatus, SyncResult, ChangeHistoryResult
from .events import ChangesetMerged, SyncCompleted
from .proposal_service import ProposalWorkflowService
from .changeset_service import ChangesetManagementService
from domain.ports import EventPublisher

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
        proposal_service: ProposalWorkflowService,
        changeset_service: ChangesetManagementService,
        event_publisher: EventPublisher,
    ) -> None:
        """
        Initialize the VersioningService.

        Args:
            change_repo: Repository for persisting and retrieving versioning entities
            sync_target: Adapter for remote synchronization (S3, etc.)
            conflict_service: Service for detecting and resolving conflicts
            proposal_service: Service for proposal workflow management
            changeset_service: Service for changeset management
            event_publisher: Publisher for domain events
        """
        self._repo = change_repo
        self._sync = sync_target
        self._conflict_service = conflict_service
        self._proposal_service = proposal_service
        self._changeset_service = changeset_service
        self._event_publisher = event_publisher

    # ============================================================================
    # Change History Query Methods
    # ============================================================================

    def get_change_history(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> ChangeHistoryResult:
        """
        Retrieve change events with optional filters.

        Args:
            entity_id: Optional filter to changes for a specific entity
            since: Optional filter to changes after a specific timestamp
            limit: Maximum number of results to return

        Returns:
            ChangeHistoryResult with paginated events and total count without limit
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

        Delegates to ChangesetManagementService.

        Args:
            changeset_id: ID of the changeset to retrieve

        Returns:
            The Changeset entity
        """
        return self._changeset_service.get_changeset(changeset_id)

    def create_changeset(
        self,
        name: str,
        description: Optional[str] = None,
        event_ids: Optional[list[str]] = None,
    ) -> Changeset:
        """
        Create a new changeset in WORKING state.

        Delegates to ChangesetManagementService.

        Args:
            name: Human-readable name for the changeset
            description: Optional detailed description
            event_ids: Optional list of change event IDs to include

        Returns:
            The persisted Changeset entity in WORKING state
        """
        return self._changeset_service.create_changeset(name, description, event_ids)

    def stage_changeset(self, changeset_id: str) -> Changeset:
        """
        Transition a changeset from WORKING to STAGED.

        Delegates to ChangesetManagementService.

        Args:
            changeset_id: ID of the changeset to stage

        Returns:
            The updated Changeset entity in STAGED state
        """
        return self._changeset_service.stage_changeset(changeset_id)

    def submit_proposal(self, changeset_id: str) -> Proposal:
        """
        Submit a changeset as a proposal for review.

        Delegates to ProposalWorkflowService.

        Args:
            changeset_id: ID of the changeset to propose

        Returns:
            The created Proposal entity
        """
        return self._proposal_service.submit_proposal(changeset_id)

    def approve_proposal(self, proposal_id: str) -> Proposal:
        """
        Approve a proposal.

        Delegates to ProposalWorkflowService.

        Args:
            proposal_id: ID of the proposal to approve

        Returns:
            The updated Proposal entity
        """
        return self._proposal_service.approve_proposal(proposal_id)

    def reject_proposal(self, proposal_id: str, reason: str) -> Proposal:
        """
        Reject a proposal.

        Delegates to ProposalWorkflowService.

        Args:
            proposal_id: ID of the proposal to reject
            reason: Explanation for the rejection

        Returns:
            The updated Proposal entity
        """
        return self._proposal_service.reject_proposal(proposal_id, reason)

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

        Delegates to ProposalWorkflowService and publishes ChangesetMerged event
        upon successful completion.

        Args:
            proposal_id: ID of the proposal to merge

        Returns:
            MergeResult with details of the merge operation

        Publishes:
            ChangesetMerged event after successful merge
        """
        result = self._proposal_service.merge_proposal(proposal_id)

        # Publish event after successful merge
        event = ChangesetMerged(
            changeset_id=result.changeset_id,
            proposal_id=proposal_id,
            merged_at=result.merged_at,
            events_applied=result.events_applied,
        )
        failures = self._event_publisher.publish(event)
        _logger.debug(
            "Published ChangesetMerged event (changeset_id=%s, proposal_id=%s)",
            result.changeset_id,
            proposal_id,
        )
        if failures:
            _logger.warning(
                "Handler failures while publishing ChangesetMerged event: %s",
                failures,
            )

        return result

    # ============================================================================
    # Synchronization Methods
    # ============================================================================

    def push_changes(self) -> SyncResult:
        """
        Push unprocessed local changes to the remote sync target.

        Retrieves unprocessed change events, pushes them to the sync target (e.g., S3),
        and marks them as processed upon successful push. Publishes SyncCompleted event
        with direction 'push' after completion.

        Returns:
            SyncResult with count of pushed events and any errors

        Publishes:
            SyncCompleted event after completion with direction='push'
        """
        events = self._repo.get_unprocessed(limit=500)
        sent_event_ids = {event.id for event in events}
        result = self._sync.push(events)

        # Validate that pushed_event_ids correspond to actually sent events
        if result.pushed > 0 and result.pushed_event_ids:
            # Ensure returned IDs are a subset of sent IDs to prevent marking wrong events
            returned_ids = set(result.pushed_event_ids)
            valid_ids = returned_ids & sent_event_ids

            if len(valid_ids) != len(returned_ids):
                _logger.warning(
                    "Adapter returned %d IDs that were not sent (sent=%d, returned=%d)",
                    len(returned_ids - sent_event_ids),
                    len(sent_event_ids),
                    len(returned_ids),
                )

            if valid_ids:
                self._repo.mark_processed(list(valid_ids))
                _logger.info(
                    "Marked %d change events as processed after push",
                    len(valid_ids),
                )

        _logger.info(
            "Push completed (pushed=%d, errors=%d)",
            result.pushed,
            len(result.errors),
        )

        # Publish completion event
        event = SyncCompleted(
            direction="push",
            events_count=result.pushed,
            completed_at=datetime.now(timezone.utc),
        )
        failures = self._event_publisher.publish(event)
        _logger.debug("Published SyncCompleted event (direction=push, events_count=%d)", result.pushed)
        if failures:
            _logger.warning("Handler failures while publishing SyncCompleted event: %s", failures)

        return result

    def pull_changes(self) -> SyncResult:
        """
        Pull remote changes from the sync target and record them locally.

        Fetches changes from the sync target (e.g., S3) and records each change
        in the local repository atomically (all events or none).

        If any change fails to record, all previously recorded changes are rolled back
        to ensure all-or-nothing semantics. This prevents partial success and
        duplicates on re-pull. Publishes SyncCompleted event with direction 'pull'
        after completion.

        Returns:
            SyncResult with count of pulled events and any errors

        Publishes:
            SyncCompleted event after completion with direction='pull'
        """
        events = self._sync.pull()
        recorded_events = []
        errors = []

        # Record each pulled event, rolling back on first failure
        for event in events:
            try:
                event_id = self._repo.record_change(
                    entity_id=event.entity_id,
                    entity_type=event.entity_type,
                    operation=event.operation,
                    new_state=event.new_state,
                    previous_state=event.previous_state,
                    user_id=event.user_id,
                    change_reason=event.change_reason,
                )
                recorded_events.append(event_id)
            except Exception as e:
                error_msg = (
                    f"Failed to record change for entity {event.entity_id}: {str(e)}"
                )
                errors.append(error_msg)
                _logger.error(error_msg)

                # Rollback all previously recorded events to maintain atomicity
                if recorded_events:
                    try:
                        self._repo.delete_changes(recorded_events)
                        _logger.info(
                            "Rolled back %d recorded events due to failure",
                            len(recorded_events),
                        )
                    except Exception as rollback_error:
                        _logger.error(
                            "Failed to rollback recorded events: %s",
                            str(rollback_error),
                        )
                        errors.append(f"Rollback failed: {str(rollback_error)}")
                    recorded_events = []

                # Stop attempting to record more events after first failure
                break

        result = SyncResult(
            pushed=0, pulled=len(recorded_events), errors=tuple(errors), pushed_event_ids=()
        )
        _logger.info(
            "Pull completed (pulled=%d, errors=%d)",
            result.pulled,
            len(result.errors),
        )

        # Publish completion event
        event = SyncCompleted(
            direction="pull",
            events_count=result.pulled,
            completed_at=datetime.now(timezone.utc),
        )
        failures = self._event_publisher.publish(event)
        _logger.debug("Published SyncCompleted event (direction=pull, events_count=%d)", result.pulled)
        if failures:
            _logger.warning("Handler failures while publishing SyncCompleted event: %s", failures)

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
