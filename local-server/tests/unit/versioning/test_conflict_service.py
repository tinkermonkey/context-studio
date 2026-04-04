"""
Unit tests for the ConflictResolutionService domain service.

Tests conflict detection and resolution using FakeChangeRepository.
"""

import sys
import os
from datetime import datetime, timezone

import pytest

# Add local-server root to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.versioning.conflict_service import ConflictResolutionService
from domain.versioning.entities import Changeset, Proposal
from domain.versioning.exceptions import VersionNotFoundError, ConflictResolutionError
from domain.versioning.value_objects import ChangeState, ChangeOperation, ProposalState
from tests.fakes.fake_change_repository import FakeChangeRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def repo() -> FakeChangeRepository:
    """Create a fresh fake repository for each test."""
    return FakeChangeRepository()


@pytest.fixture
def service(repo: FakeChangeRepository) -> ConflictResolutionService:
    """Create a ConflictResolutionService with fake dependencies."""
    return ConflictResolutionService(change_repo=repo)


# ============================================================================
# Conflict Detection Tests
# ============================================================================


class TestConflictDetection:
    """Test conflict detection functionality."""

    def test_detect_conflicts_proposal_not_found(
        self, service: ConflictResolutionService
    ) -> None:
        """Test detect_conflicts raises error when proposal doesn't exist."""
        with pytest.raises(VersionNotFoundError):
            service.detect_conflicts(proposal_id="nonexistent")

    def test_detect_conflicts_changeset_not_found(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test detect_conflicts raises error when changeset doesn't exist."""
        # Create proposal with nonexistent changeset
        proposal = Proposal(
            id="proposal1",
            changeset_id="nonexistent_changeset",
            state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )
        repo._proposals["proposal1"] = proposal

        with pytest.raises(VersionNotFoundError):
            service.detect_conflicts(proposal_id="proposal1")

    def test_detect_conflicts_empty_changeset(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test detect_conflicts with no events in changeset."""
        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id="changeset1",
            name="changeset1",
            event_ids=[],
            state=ChangeState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        repo._changesets["changeset1"] = changeset

        proposal = Proposal(
            id="proposal1",
            changeset_id="changeset1",
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        repo._proposals["proposal1"] = proposal

        report = service.detect_conflicts(proposal_id="proposal1")
        assert report.proposal_id == "proposal1"
        assert len(report.conflicts) == 0

    def test_detect_conflicts_single_event_no_conflicts(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test detect_conflicts with single event produces no conflicts."""
        # Create a single event
        event_id = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )

        # Create changeset with this event
        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id="changeset1",
            name="changeset1",
            event_ids=[event_id],
            state=ChangeState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        repo._changesets["changeset1"] = changeset

        # Create proposal
        proposal = Proposal(
            id="proposal1",
            changeset_id="changeset1",
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        repo._proposals["proposal1"] = proposal

        report = service.detect_conflicts(proposal_id="proposal1")
        assert report.proposal_id == "proposal1"
        assert len(report.conflicts) == 0

    def test_detect_conflicts_sequential_updates_same_entity(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test detect_conflicts identifies conflicts in sequential updates."""
        # Create first event: CREATE entity with name="Old"
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "Old"},
            previous_state={},
        )

        # Create second event: UPDATE name to "New" expecting previous="Old"
        # But previous is actually different, creating a conflict
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "New"},
            previous_state={"name": "Different"},  # Conflict!
        )

        # Create changeset with both events
        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id="changeset1",
            name="changeset1",
            event_ids=[event_id_1, event_id_2],
            state=ChangeState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        repo._changesets["changeset1"] = changeset

        # Create proposal
        proposal = Proposal(
            id="proposal1",
            changeset_id="changeset1",
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        repo._proposals["proposal1"] = proposal

        report = service.detect_conflicts(proposal_id="proposal1")
        assert report.proposal_id == "proposal1"
        assert len(report.conflicts) == 1
        assert report.conflicts[0].entity_id == "entity1"
        assert report.conflicts[0].field_name == "name"

    def test_detect_conflicts_with_resolutions(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test detect_conflicts applies provided resolutions."""
        # Create conflicting events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "Old"},
            previous_state={},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "New"},
            previous_state={"name": "Different"},
        )

        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id="changeset1",
            name="changeset1",
            event_ids=[event_id_1, event_id_2],
            state=ChangeState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        repo._changesets["changeset1"] = changeset

        proposal = Proposal(
            id="proposal1",
            changeset_id="changeset1",
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        repo._proposals["proposal1"] = proposal

        resolutions = {"entity1": {"name": "Resolved"}}
        report = service.detect_conflicts(proposal_id="proposal1", resolutions=resolutions)

        assert len(report.conflicts) == 1
        assert report.conflicts[0].is_resolved is True
        assert report.conflicts[0].resolved_value == "Resolved"


# ============================================================================
# Auto-Resolve Tests
# ============================================================================


class TestAutoResolve:
    """Test automatic conflict resolution."""

    def test_auto_resolve_empty_conflicts(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test auto_resolve with no conflicts."""
        from domain.versioning.entities import ConflictReport

        report = ConflictReport(proposal_id="proposal1", conflicts=[])
        resolved = service.auto_resolve(report)

        assert resolved.proposal_id == "proposal1"
        assert len(resolved.conflicts) == 0

    def test_auto_resolve_applies_last_write_wins(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test auto_resolve marks all conflicts as resolved with incoming value."""
        from domain.versioning.entities import ConflictReport, Conflict

        # Create report with unresolved conflicts
        conflict = Conflict(
            entity_id="entity1",
            field_name="name",
            base_value="Old",
            incoming_value="New",
        )
        report = ConflictReport(proposal_id="proposal1", conflicts=[conflict])

        resolved = service.auto_resolve(report)

        assert len(resolved.conflicts) == 1
        assert resolved.conflicts[0].is_resolved is True
        assert resolved.conflicts[0].resolved_value == "New"


# ============================================================================
# Manual Resolution Tests
# ============================================================================


class TestManualResolution:
    """Test manual conflict resolution."""

    def test_resolve_conflicts_success(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test resolve_conflicts successfully applies resolutions."""
        # Create conflicting events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"status": "draft"},
            previous_state={},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"status": "published"},
            previous_state={"status": "different"},
        )

        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id="changeset1",
            name="changeset1",
            event_ids=[event_id_1, event_id_2],
            state=ChangeState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        repo._changesets["changeset1"] = changeset

        proposal = Proposal(
            id="proposal1",
            changeset_id="changeset1",
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        repo._proposals["proposal1"] = proposal

        resolutions = {"entity1": {"status": "approved"}}
        report = service.resolve_conflicts(proposal_id="proposal1", resolutions=resolutions)

        assert len(report.conflicts) == 1
        assert report.all_resolved is True
        assert report.conflicts[0].resolved_value == "approved"

        # Verify resolutions were persisted
        updated_proposal = repo.get_proposal("proposal1")
        assert updated_proposal is not None
        assert updated_proposal.conflict_resolutions == resolutions

    def test_resolve_conflicts_unresolved_raises_error(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test resolve_conflicts raises error if conflicts remain unresolved."""
        # Create conflicting events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "Old"},
            previous_state={},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "New"},
            previous_state={"name": "Different"},
        )

        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id="changeset1",
            name="changeset1",
            event_ids=[event_id_1, event_id_2],
            state=ChangeState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        repo._changesets["changeset1"] = changeset

        proposal = Proposal(
            id="proposal1",
            changeset_id="changeset1",
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        repo._proposals["proposal1"] = proposal

        # Provide resolutions that don't cover the conflict
        resolutions: dict = {"entity1": {}}

        with pytest.raises(ConflictResolutionError):
            service.resolve_conflicts(proposal_id="proposal1", resolutions=resolutions)

    def test_resolve_conflicts_multiple_conflicts(
        self, service: ConflictResolutionService, repo: FakeChangeRepository
    ) -> None:
        """Test resolve_conflicts handles multiple conflicts."""
        # Create events with multiple conflicts
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "Name1", "status": "draft"},
            previous_state={},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "NameNew", "status": "published"},
            previous_state={"name": "NameOld", "status": "archived"},
        )

        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id="changeset1",
            name="changeset1",
            event_ids=[event_id_1, event_id_2],
            state=ChangeState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        repo._changesets["changeset1"] = changeset

        proposal = Proposal(
            id="proposal1",
            changeset_id="changeset1",
            state=ProposalState.OPEN,
            submitted_at=now,
        )
        repo._proposals["proposal1"] = proposal

        resolutions = {
            "entity1": {"name": "FinalName", "status": "final_status"}
        }
        report = service.resolve_conflicts(proposal_id="proposal1", resolutions=resolutions)

        assert len(report.conflicts) == 2
        assert report.all_resolved is True
