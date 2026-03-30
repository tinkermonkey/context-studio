"""
Domain service for the Version Control & Collaboration bounded context.

Implements change history queries, changeset lifecycle management,
and the proposal approval workflow.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from .entities import ChangeEvent, EntityVersion, Changeset, Proposal, MergeResult, Conflict, ConflictReport
from .exceptions import VersionNotFoundError, ChangesetStateError, ConflictResolutionError
from .ports import ChangeRepository
from .value_objects import ChangeState

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
    ) -> None:
        """
        Initialize the VersioningService.

        Args:
            change_repo: Repository for persisting and retrieving versioning entities
        """
        self._repo = change_repo

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
            state="open",
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

        proposal.state = "approved"
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

        proposal.state = "rejected"
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

    def detect_conflicts(
        self, proposal_id: str, resolutions: Optional[dict[str, dict[str, object]]] = None
    ) -> ConflictReport:
        """
        Detect field-level conflicts in a proposal.

        Compares the previous_state and new_state of change events
        in the changeset to identify conflicts. A conflict occurs when
        a field is modified between two updates to the same entity.

        Optionally accepts a resolutions dict to mark conflicts as resolved.

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
        resolutions: dict[str, dict[str, object]],
    ) -> ConflictReport:
        """
        Manually resolve conflicts in a proposal.

        Detects conflicts, applies the provided resolutions, validates that
        all conflicts are covered, and stores the resolutions in the proposal.

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

        # Persist resolutions to the proposal
        proposal = self._repo.get_proposal(proposal_id)
        if proposal is None:
            raise VersionNotFoundError(f"Proposal {proposal_id} not found")

        proposal.conflict_resolutions = resolutions
        self._repo.update_proposal(proposal)

        _logger.info(
            "Manually resolved conflicts (proposal_id=%s, conflicts_resolved=%d)",
            proposal_id,
            len(report.conflicts),
        )
        return report

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

        if proposal.state != "approved":
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

        proposal.state = "merged"
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
