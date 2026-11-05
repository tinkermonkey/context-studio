"""
Domain service for the Version Control & Collaboration bounded context.

Implements change history queries and remote synchronization of change events.
Reviewing and applying changes lives in ProposalService (proposal_service.py).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from domain.ports import EventPublisher

from .events import SyncCompleted
from .exceptions import SyncError
from .ports import ChangeRepository, SyncTarget
from .value_objects import (
    ChangeHistoryResult,
    SyncDirection,
    SyncResult,
    SyncStatus,
)

_logger = logging.getLogger(__name__)


class VersioningService:
    """
    Single unified domain service for all versioning operations.

    Coordinates change history queries and remote synchronization.
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
        limit: Optional[int] = 100,
        batch_run_id: Optional[str] = None,
    ) -> ChangeHistoryResult:
        """
        Retrieve change events with optional filters.

        Args:
            entity_id: Optional filter to changes for a specific entity
            since: Optional filter to changes after a specific timestamp
            limit: Maximum number of results to return
            batch_run_id: Optional filter to changes from a specific pipeline run

        Returns:
            ChangeHistoryResult with paginated events and total count without limit
        """
        return self._repo.get_changes(
            entity_id=entity_id, since=since, limit=limit, batch_run_id=batch_run_id
        )

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
        started_at = datetime.now(timezone.utc)
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

        completed_at = datetime.now(timezone.utc)
        _logger.info(
            "Push completed (pushed=%d, errors=%d)",
            result.pushed,
            len(result.errors),
        )

        # Publish completion event
        event = SyncCompleted(
            direction=SyncDirection.PUSH,
            events_count=result.pushed,
            completed_at=completed_at,
        )
        failures = self._event_publisher.publish(event)
        _logger.debug(
            "Published SyncCompleted event (direction=push, events_count=%d)",
            result.pushed,
        )
        if failures:
            _logger.warning("Handler failures while publishing SyncCompleted event: %s", failures)

        # Return SyncResult with validated event IDs to surface any discrepancies to API consumer
        return SyncResult(
            pushed=result.pushed,
            pulled=result.pulled,
            errors=result.errors,
            pushed_event_ids=processed_ids if processed_ids else None,
            started_at=started_at,
            completed_at=completed_at,
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
        started_at = datetime.now(timezone.utc)
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
            except (RuntimeError, OSError, ValueError) as e:
                error_msg = (
                    f"Failed to record change for entity {change_event.entity_id}:" f" {str(e)}"
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
                    except (RuntimeError, OSError, ValueError) as rollback_error:
                        _logger.error(
                            "Failed to rollback recorded events: %s",
                            str(rollback_error),
                        )
                        errors.append(f"Rollback failed: {str(rollback_error)}")
                    recorded_events = []

                # Stop attempting to record more events after first failure
                break

        completed_at = datetime.now(timezone.utc)
        result = SyncResult(
            pushed=0,
            pulled=len(recorded_events),
            errors=tuple(errors),
            pushed_event_ids=(),
            started_at=started_at,
            completed_at=completed_at,
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
            completed_at=completed_at,
        )
        failures = self._event_publisher.publish(event)
        _logger.debug(
            "Published SyncCompleted event (direction=pull, events_count=%d)",
            result.pulled,
        )
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
        count = 0
        is_configured = False
        is_degraded = False

        try:
            count = self._repo.count_unprocessed()
        except (RuntimeError, OSError) as e:
            _logger.warning("Failed to count unprocessed changes in sync status: %s", str(e))
            is_degraded = True

        try:
            is_configured = self._sync.is_configured()
        except (RuntimeError, OSError) as e:
            _logger.warning("Failed to check sync configuration status: %s", str(e))
            is_degraded = True

        status = SyncStatus(
            last_pushed_at=None,
            last_pulled_at=None,
            unprocessed_count=count,
            is_configured=is_configured,
            is_degraded=is_degraded,
        )
        _logger.debug(
            "Sync status: unprocessed=%d, configured=%s, degraded=%s",
            count,
            is_configured,
            is_degraded,
        )
        return status

    # ============================================================================
    # Event Handlers (for subscribing to own events)
    # ============================================================================

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
