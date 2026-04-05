"""
Domain service for the Version Control & Collaboration bounded context.

Implements change history queries, changeset lifecycle management,
conflict detection and resolution, and the proposal approval workflow.

Per the architecture specification, VersioningService is a single service that
coordinates all versioning operations. It does not delegate to separate services.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from .entities import (
    EntityVersion,
    Changeset,
    Proposal,
    MergeResult,
    ConflictReport,
    Conflict,
    ChangeEvent,
)
from .exceptions import (
    VersionNotFoundError,
    ChangesetStateError,
    ConflictResolutionError,
    SyncError,
)
from .ports import ChangeRepository, SyncTarget
from .value_objects import SyncStatus, SyncResult, ChangeHistoryResult, SyncDirection, ChangeState, ProposalState
from .events import ChangesetMerged, SyncCompleted
from domain.ports import EventPublisher

_logger = logging.getLogger(__name__)


class VersioningService:
    """
    Single unified domain service for all versioning operations.

    Coordinates change history queries, changeset lifecycle management,
    conflict detection and resolution, and the proposal workflow.
    """

    def __init__(
        self,
        change_repo: ChangeRepository,
        sync_target: SyncTarget,
        event_publisher: EventPublisher,
    ) -> None:
        """
        Initialize the VersioningService.

        Args:
            change_repo: Repository for persisting and retrieving versioning entities
            sync_target: Adapter for remote synchronization (S3, etc.)
            event_publisher: Publisher for domain events
        """
        self._repo = change_repo
        self._sync = sync_target
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

        A changeset is a named collection of change events that can be
        reviewed and merged as a unit. Changesets progress through states:
        WORKING → STAGED → PROPOSED → APPROVED → MERGED

        Args:
            name: Name of the changeset
            description: Optional detailed description of the changeset
            event_ids: Optional list of existing change event IDs to include

        Returns:
            The persisted Changeset entity in WORKING state
        """
        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id=str(uuid.uuid4()),
            name=name,
            _state=ChangeState.WORKING,
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
            VersionNotFoundError: If the changeset does not exist
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
            VersionNotFoundError: If the changeset does not exist
        """
        changeset = self._repo.get_changeset(changeset_id)
        if changeset is None:
            raise VersionNotFoundError(f"Changeset {changeset_id} not found")

        now = datetime.now(timezone.utc)
        changeset.transition_to(ChangeState.PROPOSED)
        changeset.updated_at = now

        proposal = Proposal(
            id=str(uuid.uuid4()),
            changeset_id=changeset_id,
            _state=ProposalState.OPEN,
            submitted_at=now,
        )

        # Atomically update changeset and create proposal to prevent inconsistent state
        updated_changeset, persisted_proposal = self._repo.update_changeset_and_proposal_on_submit(
            changeset, proposal
        )
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

        proposal.transition_to(ProposalState.APPROVED)
        proposal.reviewed_at = now

        # Atomically update both entities to prevent inconsistent state
        updated_changeset, updated_proposal = self._repo.atomic_update_changeset_and_proposal(
            changeset, proposal
        )
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

        proposal.transition_to(ProposalState.REJECTED)
        proposal.reviewed_at = now
        proposal.reviewer_notes = reason

        # Atomically update both entities to prevent inconsistent state
        updated_changeset, updated_proposal = self._repo.atomic_update_changeset_and_proposal(
            changeset, proposal
        )
        _logger.info(
            "Proposal rejected (proposal_id=%s, changeset_id=%s, state=%s, reason=%s)",
            updated_proposal.id,
            proposal.changeset_id,
            updated_proposal.state,
            reason,
        )
        return updated_proposal

    def detect_conflicts(
        self, proposal_id: str, resolutions: Optional[dict[str, dict[str, str]]] = None
    ) -> ConflictReport:
        """
        Detect field-level conflicts in a proposal.

        Compares the previous_state and new_state of change events
        in the changeset to identify conflicts. A conflict occurs when
        a field is modified between two updates to the same entity.

        Algorithm:
        - Get all change events in the changeset
        - Group events by entity_id
        - For each entity with multiple events:
          - Sort events by timestamp
          - For each pair of consecutive events, compare:
            - previous_state of later event vs new_state of earlier event
          - Any field mismatch indicates a conflict
        - Apply resolutions if provided

        Args:
            proposal_id: ID of the proposal to check for conflicts
            resolutions: Optional dict mapping entity_id -> {field_name: resolved_value}

        Returns:
            ConflictReport with detected conflicts (may be empty)

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

        report = ConflictReport(proposal_id=proposal_id, conflicts=[])

        # If no events in changeset, no conflicts possible
        if not changeset.event_ids:
            return report

        # Get events in this changeset using the changeset's event_ids
        changeset_events = self._repo.get_changes_by_ids(changeset.event_ids)

        # Group events by entity_id and sort by timestamp
        events_by_entity: dict[str, list[ChangeEvent]] = {}
        for event in changeset_events:
            if event.entity_id not in events_by_entity:
                events_by_entity[event.entity_id] = []
            events_by_entity[event.entity_id].append(event)

        # Sort events by timestamp within each entity
        for entity_id in events_by_entity:
            events_by_entity[entity_id].sort(key=lambda e: e.timestamp)

        # Detect conflicts: compare consecutive events for same entity
        for entity_id, entity_events in events_by_entity.items():
            for i in range(1, len(entity_events)):
                earlier = entity_events[i - 1]
                later = entity_events[i]

                # Compare previous_state of later event to new_state of earlier event
                earlier_new = earlier.new_state or {}
                later_prev = later.previous_state or {}

                for field_name, later_prev_value in later_prev.items():
                    earlier_new_value = earlier_new.get(field_name)
                    if earlier_new_value != later_prev_value:
                        conflict = Conflict(
                            entity_id=entity_id,
                            field_name=field_name,
                            base_value=earlier_new_value,
                            incoming_value=later.new_state.get(field_name),
                        )
                        report.conflicts.append(conflict)

        # Apply resolutions if provided
        if resolutions:
            for conflict in report.conflicts:
                entity_resolutions = resolutions.get(conflict.entity_id, {})
                if conflict.field_name in entity_resolutions:
                    conflict.resolved_value = entity_resolutions[conflict.field_name]
                    conflict.is_resolved = True

        _logger.info(
            "Conflict detection complete (proposal_id=%s, conflicts_found=%d, resolved=%d)",
            proposal_id,
            len(report.conflicts),
            sum(1 for c in report.conflicts if c.is_resolved),
        )
        return report

    def auto_resolve(self, conflict_report: ConflictReport) -> ConflictReport:
        """
        Automatically resolve all conflicts using last-write-wins strategy.

        Sets is_resolved=True and resolved_value=incoming_value for all conflicts.

        Args:
            conflict_report: ConflictReport with unresolved conflicts

        Returns:
            The same ConflictReport with all conflicts marked as resolved
        """
        for conflict in conflict_report.conflicts:
            conflict.resolved_value = conflict.incoming_value
            conflict.is_resolved = True

        _logger.info(
            "Auto-resolved conflicts (proposal_id=%s, conflicts_resolved=%d)",
            conflict_report.proposal_id,
            len(conflict_report.conflicts),
        )
        return conflict_report

    def resolve_conflicts(
        self,
        proposal_id: str,
        resolutions: dict[str, dict[str, str]],
    ) -> ConflictReport:
        """
        Manually resolve conflicts in a proposal.

        Detects conflicts, applies the provided resolutions, validates that
        all conflicts are covered, and persists the resolutions for later use.

        Args:
            proposal_id: ID of the proposal to resolve conflicts for
            resolutions: Dict mapping entity_id -> {field_name: resolved_value}

        Returns:
            ConflictReport with all conflicts marked as resolved

        Raises:
            ConflictResolutionError: If any conflicts remain unresolved
            VersionNotFoundError: If the proposal or changeset does not exist
        """
        report = self.detect_conflicts(proposal_id, resolutions)

        if not report.all_resolved:
            unresolved = [
                f"{c.entity_id}.{c.field_name}"
                for c in report.conflicts if not c.is_resolved
            ]
            error_msg = f"Unresolved conflicts: {unresolved}"
            _logger.error(error_msg)
            raise ConflictResolutionError(error_msg)

        # Persist the resolutions so merge_proposal can retrieve them
        self._repo.save_conflict_resolutions(proposal_id, resolutions)

        _logger.info(
            "Manually resolved conflicts (proposal_id=%s, conflicts_resolved=%d)",
            proposal_id,
            len(report.conflicts),
        )
        return report

    def merge_proposal(self, proposal_id: str) -> MergeResult:
        """
        Merge an approved proposal.

        Detects conflicts and blocks the merge if unresolved conflicts exist.
        Transitions the changeset from APPROVED to MERGED and updates the
        proposal state to 'merged'. Publishes ChangesetMerged event upon
        successful completion.

        Args:
            proposal_id: ID of the proposal to merge

        Returns:
            MergeResult with details of the merge operation

        Raises:
            VersionNotFoundError: If the proposal or changeset does not exist
            ChangesetStateError: If the proposal is not in 'approved' state
            ConflictResolutionError: If unresolved conflicts exist

        Publishes:
            ChangesetMerged event after successful merge
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

        # Detect conflicts, using any previously persisted resolutions
        stored_resolutions = self._repo.get_conflict_resolutions(proposal_id)
        report = self.detect_conflicts(proposal_id, stored_resolutions)
        if report.has_conflicts and not report.all_resolved:
            error_msg = (
                f"Proposal {proposal_id} has {len(report.conflicts)} unresolved conflicts"
            )
            _logger.error(error_msg)
            raise ConflictResolutionError(error_msg)

        now = datetime.now(timezone.utc)
        changeset.transition_to(ChangeState.MERGED)
        changeset.updated_at = now

        proposal.transition_to(ProposalState.MERGED)

        # Atomically update both entities to prevent inconsistent state
        updated_changeset, updated_proposal = self._repo.atomic_update_changeset_and_proposal(
            changeset, proposal
        )

        result = MergeResult(
            proposal_id=proposal_id,
            changeset_id=proposal.changeset_id,
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

        Raises:
            SyncError: If the sync target fails to push changes
        """
        events = self._repo.get_unprocessed(limit=500)
        sent_event_ids = {change_event.id for change_event in events}

        try:
            result = self._sync.push(events)
        except RuntimeError as e:
            # Wrap infrastructure-level error from adapter into domain exception
            raise SyncError(str(e)) from e

        # Track validated IDs that were actually marked as processed
        processed_ids: tuple[str, ...] = ()

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
                processed_ids = tuple(sorted(valid_ids))
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
            direction=SyncDirection.PUSH,
            events_count=result.pushed,
            completed_at=datetime.now(timezone.utc),
        )
        failures = self._event_publisher.publish(event)
        _logger.debug(
            "Published SyncCompleted event (direction=push, events_count=%d)",
            result.pushed,
        )
        if failures:
            _logger.warning(
                "Handler failures while publishing SyncCompleted event: %s", failures
            )

        # Return SyncResult with validated event IDs to surface any discrepancies to API consumer
        return SyncResult(
            pushed=result.pushed,
            pulled=result.pulled,
            errors=result.errors,
            pushed_event_ids=processed_ids if processed_ids else None,
        )

    def pull_changes(self) -> SyncResult:
        """
        Pull remote changes from the sync target and record them locally.

        Fetches changes from the sync target (e.g., S3) and records each change
        in the local repository using stop-on-first-error semantics with rollback.

        Processing stops immediately on the first failure. All previously recorded
        changes are rolled back to prevent partial success and duplicates on re-pull.
        If rollback itself fails, the rollback error is logged but does not prevent
        method completion; instead, both the original error and rollback error are
        returned in the SyncResult. Publishes SyncCompleted event with direction 'pull'
        after completion.

        Returns:
            SyncResult with count of pulled events and any errors

        Publishes:
            SyncCompleted event after completion with direction='pull'

        Raises:
            SyncError: If the sync target fails to pull changes
        """
        try:
            events = self._sync.pull()
        except RuntimeError as e:
            # Wrap infrastructure-level error from adapter into domain exception
            raise SyncError(str(e)) from e
        recorded_events = []
        errors = []

        # Record each pulled event, rolling back on first failure
        for change_event in events:
            try:
                event_id = self._repo.record_change(
                    entity_id=change_event.entity_id,
                    entity_type=change_event.entity_type,
                    operation=change_event.operation,
                    new_state=change_event.new_state,
                    previous_state=change_event.previous_state,
                    user_id=change_event.user_id,
                    change_reason=change_event.change_reason,
                )
                recorded_events.append(event_id)
            except Exception as e:
                error_msg = f"Failed to record change for entity {change_event.entity_id}: {str(e)}"
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
            pushed=0,
            pulled=len(recorded_events),
            errors=tuple(errors),
            pushed_event_ids=(),
        )
        _logger.info(
            "Pull completed (pulled=%d, errors=%d)",
            result.pulled,
            len(result.errors),
        )

        # Publish completion event
        event = SyncCompleted(
            direction=SyncDirection.PULL,
            events_count=result.pulled,
            completed_at=datetime.now(timezone.utc),
        )
        failures = self._event_publisher.publish(event)
        _logger.debug(
            "Published SyncCompleted event (direction=pull, events_count=%d)",
            result.pulled,
        )
        if failures:
            _logger.warning(
                "Handler failures while publishing SyncCompleted event: %s", failures
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
