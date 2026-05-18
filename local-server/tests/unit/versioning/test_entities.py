"""
Unit tests for versioning domain entities.

Tests entity invariants and state machine transitions.
"""

import os
import sys
from datetime import datetime, timezone

import pytest

# Add local-server root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.versioning.entities import (
    Changeset,
    Conflict,
    ConflictReport,
    Proposal,
)
from domain.versioning.exceptions import ChangesetStateError, ProposalStateError
from domain.versioning.value_objects import ChangeState, MergeStrategy, ProposalState


class TestChangesetStateTransitions:
    """Test valid and invalid changeset state transitions."""

    def test_working_to_staged_is_valid(self) -> None:
        """Test transition from working to staged."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            _state=ChangeState.WORKING,
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
            _state=ChangeState.STAGED,
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
            _state=ChangeState.PROPOSED,
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
            _state=ChangeState.APPROVED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        changeset.transition_to(ChangeState.MERGED)
        assert changeset.state == ChangeState.MERGED

    def test_staged_back_to_working_is_invalid(self) -> None:
        """Test that transition back from staged to working raises error."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            _state=ChangeState.STAGED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ChangesetStateError):
            changeset.transition_to(ChangeState.WORKING)

    def test_proposed_back_to_working_is_valid(self) -> None:
        """Test transition back from proposed to working."""
        changeset = Changeset(
            id="cs1",
            name="Test changeset",
            _state=ChangeState.PROPOSED,
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
            _state=ChangeState.WORKING,
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
            _state=ChangeState.WORKING,
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
            _state=ChangeState.MERGED,
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
            _state=ChangeState.WORKING,
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
            entity_type="class",
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
            entity_type="class",
            field_name="title",
            base_value="Old",
            incoming_value="New",
        )
        report = ConflictReport(proposal_id="prop1", conflicts=[conflict])
        assert not report.all_resolved

    def test_all_resolved_is_true_with_resolved_conflicts(self) -> None:
        """Test that all_resolved is true when all conflicts are resolved."""
        conflict = Conflict(
            entity_id="entity1",
            entity_type="class",
            field_name="title",
            base_value="Old",
            incoming_value="New",
            resolved_value="Resolved",
            resolution_strategy=MergeStrategy.LAST_WRITE_WINS,
        )
        report = ConflictReport(proposal_id="prop1", conflicts=[conflict])
        assert report.all_resolved

    def test_all_resolved_with_multiple_conflicts(self) -> None:
        """Test all_resolved with multiple conflicts."""
        conflicts = [
            Conflict(
                entity_id="entity1",
                entity_type="class",
                field_name="title",
                base_value="Old",
                incoming_value="New",
                resolved_value="Resolved Title",
                resolution_strategy=MergeStrategy.LAST_WRITE_WINS,
            ),
            Conflict(
                entity_id="entity1",
                entity_type="class",
                field_name="description",
                base_value="Old desc",
                incoming_value="New desc",
                resolved_value="Resolved desc",
                resolution_strategy=MergeStrategy.BASE_VALUE_WINS,
            ),
        ]
        report = ConflictReport(proposal_id="prop1", conflicts=conflicts)
        assert report.all_resolved

    def test_all_resolved_false_with_partially_resolved(self) -> None:
        """Test all_resolved is false with partially resolved conflicts."""
        conflicts = [
            Conflict(
                entity_id="entity1",
                entity_type="class",
                field_name="title",
                base_value="Old",
                incoming_value="New",
                resolved_value="Resolved Title",
                resolution_strategy=MergeStrategy.LAST_WRITE_WINS,
            ),
            Conflict(
                entity_id="entity1",
                entity_type="class",
                field_name="description",
                base_value="Old desc",
                incoming_value="New desc",
            ),
        ]
        report = ConflictReport(proposal_id="prop1", conflicts=conflicts)
        assert not report.all_resolved

    def test_conflict_resolved_to_none_with_strategy(self) -> None:
        """Test that is_resolved is true when resolved_value is None but resolution_strategy is set."""
        conflict = Conflict(
            entity_id="entity1",
            entity_type="class",
            field_name="optional_field",
            base_value=None,
            incoming_value="New Value",
            resolved_value=None,
            resolution_strategy=MergeStrategy.BASE_VALUE_WINS,
        )
        assert conflict.is_resolved is True


class TestProposalStateTransitions:
    """Test valid and invalid proposal state transitions."""

    def test_open_to_approved_is_valid(self) -> None:
        """Test transition from open to approved."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        proposal.transition_to(ProposalState.APPROVED)
        assert proposal.state == ProposalState.APPROVED

    def test_open_to_rejected_is_valid(self) -> None:
        """Test transition from open to rejected."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        proposal.transition_to(ProposalState.REJECTED)
        assert proposal.state == ProposalState.REJECTED

    def test_approved_to_merged_is_valid(self) -> None:
        """Test transition from approved to merged."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.APPROVED,
            submitted_at=datetime.now(timezone.utc),
        )

        proposal.transition_to(ProposalState.MERGED)
        assert proposal.state == ProposalState.MERGED

    def test_approved_to_rejected_is_valid(self) -> None:
        """Test transition from approved to rejected."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.APPROVED,
            submitted_at=datetime.now(timezone.utc),
        )

        proposal.transition_to(ProposalState.REJECTED)
        assert proposal.state == ProposalState.REJECTED

    def test_rejected_to_open_is_valid(self) -> None:
        """Test transition from rejected back to open."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.REJECTED,
            submitted_at=datetime.now(timezone.utc),
        )

        proposal.transition_to(ProposalState.OPEN)
        assert proposal.state == ProposalState.OPEN

    def test_open_to_merged_is_invalid(self) -> None:
        """Test that direct transition from open to merged raises error."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ProposalStateError):
            proposal.transition_to(ProposalState.MERGED)

    def test_merged_cannot_transition(self) -> None:
        """Test that merged proposals cannot transition."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.MERGED,
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ProposalStateError):
            proposal.transition_to(ProposalState.OPEN)

    def test_merged_is_terminal(self) -> None:
        """Test that MERGED is a terminal state."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.MERGED,
            submitted_at=datetime.now(timezone.utc),
        )

        for state in [
            ProposalState.OPEN,
            ProposalState.APPROVED,
            ProposalState.REJECTED,
        ]:
            with pytest.raises(ProposalStateError):
                proposal.transition_to(state)

    def test_rejected_to_approved_is_invalid(self) -> None:
        """Test that transition from rejected to approved raises error."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.REJECTED,
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ProposalStateError):
            proposal.transition_to(ProposalState.APPROVED)

    def test_rejected_to_merged_is_invalid(self) -> None:
        """Test that transition from rejected to merged raises error."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.REJECTED,
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ProposalStateError):
            proposal.transition_to(ProposalState.MERGED)

    def test_transition_raises_descriptive_error(self) -> None:
        """Test that error messages are descriptive."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            _state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ProposalStateError) as exc_info:
            proposal.transition_to(ProposalState.MERGED)

        assert "open" in str(exc_info.value).lower()
        assert "merged" in str(exc_info.value).lower()
