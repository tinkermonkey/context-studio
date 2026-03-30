"""
Unit tests for versioning domain entities.

Tests entity invariants and state machine transitions.
"""

import sys
import os
from datetime import datetime, timezone

import pytest

# Add local-server root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.versioning.entities import (
    Changeset,
    ConflictReport,
    Conflict,
)
from domain.versioning.exceptions import ChangesetStateError
from domain.versioning.value_objects import ChangeState


class TestChangesetStateTransitions:
    """Test valid and invalid changeset state transitions."""

    def test_working_to_staged_is_valid(self) -> None:
        """Test transition from working to staged."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        changeset.transition_to(ChangeState.STAGED)
        assert changeset.state == ChangeState.STAGED

    def test_staged_to_proposed_is_valid(self) -> None:
        """Test transition from staged to proposed."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.STAGED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        changeset.transition_to(ChangeState.PROPOSED)
        assert changeset.state == ChangeState.PROPOSED

    def test_proposed_to_approved_is_valid(self) -> None:
        """Test transition from proposed to approved."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.PROPOSED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        changeset.transition_to(ChangeState.APPROVED)
        assert changeset.state == ChangeState.APPROVED

    def test_approved_to_merged_is_valid(self) -> None:
        """Test transition from approved to merged."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.APPROVED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        changeset.transition_to(ChangeState.MERGED)
        assert changeset.state == ChangeState.MERGED

    def test_staged_back_to_working_is_valid(self) -> None:
        """Test transition back from staged to working."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.STAGED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        changeset.transition_to(ChangeState.WORKING)
        assert changeset.state == ChangeState.WORKING

    def test_proposed_back_to_working_is_valid(self) -> None:
        """Test transition back from proposed to working."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.PROPOSED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        changeset.transition_to(ChangeState.WORKING)
        assert changeset.state == ChangeState.WORKING

    def test_working_to_proposed_is_invalid(self) -> None:
        """Test that direct transition from working to proposed raises error."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ChangesetStateError):
            changeset.transition_to(ChangeState.PROPOSED)

    def test_working_to_approved_is_invalid(self) -> None:
        """Test that direct transition from working to approved raises error."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ChangesetStateError):
            changeset.transition_to(ChangeState.APPROVED)

    def test_merged_cannot_transition(self) -> None:
        """Test that merged changesets cannot transition."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.MERGED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ChangesetStateError):
            changeset.transition_to(ChangeState.WORKING)

    def test_transition_raises_descriptive_error(self) -> None:
        """Test that error messages are descriptive."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ChangesetStateError) as exc_info:
            changeset.transition_to(ChangeState.MERGED)

        assert "working" in str(exc_info.value).lower()
        assert "merged" in str(exc_info.value).lower()


class TestConflictReport:
    """Test ConflictReport properties."""

    def test_empty_report_has_no_conflicts(self) -> None:
        """Test that empty report has no conflicts."""
        report = ConflictReport(proposal_id="prop1")
        assert not report.has_conflicts

    def test_report_with_conflicts_has_conflicts(self) -> None:
        """Test that report with conflicts reports has_conflicts."""
        conflict = Conflict(
            entity_id="entity1",
            field_name="title",
            base_value="Old",
            incoming_value="New",
        )
        report = ConflictReport(proposal_id="prop1", conflicts=[conflict])
        assert report.has_conflicts

    def test_all_resolved_is_false_with_unresolved_conflicts(self) -> None:
        """Test that all_resolved is false when conflicts are unresolved."""
        conflict = Conflict(
            entity_id="entity1",
            field_name="title",
            base_value="Old",
            incoming_value="New",
            is_resolved=False,
        )
        report = ConflictReport(proposal_id="prop1", conflicts=[conflict])
        assert not report.all_resolved

    def test_all_resolved_is_true_with_resolved_conflicts(self) -> None:
        """Test that all_resolved is true when all conflicts are resolved."""
        conflict = Conflict(
            entity_id="entity1",
            field_name="title",
            base_value="Old",
            incoming_value="New",
            resolved_value="Resolved",
            is_resolved=True,
        )
        report = ConflictReport(proposal_id="prop1", conflicts=[conflict])
        assert report.all_resolved

    def test_all_resolved_with_multiple_conflicts(self) -> None:
        """Test all_resolved with multiple conflicts."""
        conflicts = [
            Conflict(
                entity_id="entity1",
                field_name="title",
                base_value="Old",
                incoming_value="New",
                is_resolved=True,
            ),
            Conflict(
                entity_id="entity1",
                field_name="description",
                base_value="Old desc",
                incoming_value="New desc",
                is_resolved=True,
            ),
        ]
        report = ConflictReport(proposal_id="prop1", conflicts=conflicts)
        assert report.all_resolved

    def test_all_resolved_false_with_partially_resolved(self) -> None:
        """Test all_resolved is false with partially resolved conflicts."""
        conflicts = [
            Conflict(
                entity_id="entity1",
                field_name="title",
                base_value="Old",
                incoming_value="New",
                is_resolved=True,
            ),
            Conflict(
                entity_id="entity1",
                field_name="description",
                base_value="Old desc",
                incoming_value="New desc",
                is_resolved=False,
            ),
        ]
        report = ConflictReport(proposal_id="prop1", conflicts=conflicts)
        assert not report.all_resolved
