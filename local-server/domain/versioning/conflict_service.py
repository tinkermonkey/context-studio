"""
Conflict resolution service for merge proposals.

Handles detection and resolution of field-level conflicts during proposal merging.
"""

import logging
from typing import Optional

from .entities import Conflict, ConflictReport, ChangeEvent
from .exceptions import ConflictResolutionError, VersionNotFoundError
from .ports import ChangeRepository

_logger = logging.getLogger(__name__)


class ConflictResolutionService:
    """
    Domain service for detecting and resolving merge conflicts.

    Analyzes proposals for field-level conflicts and applies manual or automatic resolutions.
    """

    def __init__(self, change_repo: ChangeRepository) -> None:
        """
        Initialize the ConflictResolutionService.

        Args:
            change_repo: Repository for retrieving change events and proposals
        """
        self._repo = change_repo

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
