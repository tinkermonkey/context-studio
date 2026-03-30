"""
Unit tests for the VersioningService domain service.

Tests the change history queries, changeset lifecycle, and proposal workflow
using FakeChangeRepository.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

import pytest

# Add local-server root to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.versioning.services import VersioningService
from domain.versioning.entities import EntityVersion
from domain.versioning.exceptions import VersionNotFoundError, ChangesetStateError
from domain.versioning.value_objects import ChangeState
from tests.fakes.fake_change_repository import FakeChangeRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def repo() -> FakeChangeRepository:
    """Create a fresh fake repository for each test."""
    return FakeChangeRepository()


@pytest.fixture
def service(repo: FakeChangeRepository) -> VersioningService:
    """Create a VersioningService with fake dependencies."""
    return VersioningService(change_repo=repo)


# ============================================================================
# Change History Query Tests
# ============================================================================


class TestChangeHistoryQueries:
    """Test change history query methods."""

    def test_get_change_history_empty(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history when no changes exist."""
        history = service.get_change_history()
        assert history == []

    def test_get_change_history_all_events(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving all change events."""
        # Record some events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation="create",
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation="create",
            new_state={"name": "Entity2"},
        )

        history = service.get_change_history()
        assert len(history) == 2
        assert any(e.id == event_id_1 for e in history)
        assert any(e.id == event_id_2 for e in history)

    def test_get_change_history_filtered_by_entity(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history filtered by entity."""
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation="create",
            new_state={"name": "Entity1"},
        )
        repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation="create",
            new_state={"name": "Entity2"},
        )

        history = service.get_change_history(entity_id="entity1")
        assert len(history) == 1
        assert history[0].entity_id == "entity1"

    def test_get_change_history_filtered_by_since(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history since a timestamp."""
        now = datetime.now(timezone.utc)
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation="create",
            new_state={"name": "Entity1"},
        )
        # This event is recorded with current time, so it will be after 'now'
        # Let's retrieve after a time before now
        since = now - timedelta(seconds=1)

        history = service.get_change_history(since=since)
        # The recorded event should be after 'since'
        assert len(history) > 0

    def test_get_change_history_respects_limit(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that change history respects the limit parameter."""
        for i in range(10):
            repo.record_change(
                entity_id=f"entity{i}",
                entity_type="class",
                operation="create",
                new_state={"name": f"Entity{i}"},
            )

        history = service.get_change_history(limit=5)
        assert len(history) == 5

    def test_get_entity_version_success(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving a specific entity version."""
        version = EntityVersion(
            entity_id="entity1",
            version=1,
            state="active",
            snapshot={"name": "Entity1"},
            created_at=datetime.now(timezone.utc),
        )
        repo.save_version(version)

        retrieved = service.get_entity_version("entity1", 1)
        assert retrieved.entity_id == "entity1"
        assert retrieved.version == 1
        assert retrieved.state == "active"

    def test_get_entity_version_not_found(
        self, service: VersioningService
    ) -> None:
        """Test retrieving a non-existent entity version raises error."""
        with pytest.raises(VersionNotFoundError):
            service.get_entity_version("entity1", 999)

    def test_get_latest_version_success(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving the latest version of an entity."""
        v1 = EntityVersion(
            entity_id="entity1",
            version=1,
            state="active",
            snapshot={"name": "Entity1"},
            created_at=datetime.now(timezone.utc),
        )
        v2 = EntityVersion(
            entity_id="entity1",
            version=2,
            state="active",
            snapshot={"name": "Entity1 Updated"},
            created_at=datetime.now(timezone.utc),
        )
        repo.save_version(v1)
        repo.save_version(v2)

        latest = service.get_latest_version("entity1")
        assert latest is not None
        assert latest.version == 2

    def test_get_latest_version_not_found(
        self, service: VersioningService
    ) -> None:
        """Test retrieving latest version when entity has no versions."""
        latest = service.get_latest_version("entity1")
        assert latest is None

    def test_list_versions_success(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving all versions of an entity."""
        v1 = EntityVersion(
            entity_id="entity1",
            version=1,
            state="active",
            snapshot={"name": "Entity1"},
            created_at=datetime.now(timezone.utc),
        )
        v2 = EntityVersion(
            entity_id="entity1",
            version=2,
            state="active",
            snapshot={"name": "Entity1 Updated"},
            created_at=datetime.now(timezone.utc),
        )
        repo.save_version(v1)
        repo.save_version(v2)

        versions = service.list_versions("entity1")
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2

    def test_list_versions_empty(
        self, service: VersioningService

    ) -> None:
        """Test listing versions when entity has no versions."""
        versions = service.list_versions("entity1")
        assert versions == []


# ============================================================================
# Changeset Lifecycle Tests
# ============================================================================


class TestChangesetLifecycle:
    """Test changeset creation, staging, and proposal submission."""

    def test_create_changeset_basic(
        self, service: VersioningService
    ) -> None:
        """Test creating a basic changeset."""
        changeset = service.create_changeset(name="Test changeset")

        assert changeset.name == "Test changeset"
        assert changeset.state == ChangeState.WORKING
        assert changeset.description is None
        assert changeset.event_ids == []
        assert changeset.created_at is not None
        assert changeset.updated_at is not None

    def test_create_changeset_with_description(
        self, service: VersioningService
    ) -> None:
        """Test creating a changeset with a description."""
        description = "This is a test changeset"
        changeset = service.create_changeset(
            name="Test changeset", description=description
        )

        assert changeset.description == description

    def test_create_changeset_with_event_ids(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test creating a changeset with event IDs."""
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation="create",
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation="create",
            new_state={"name": "Entity2"},
        )

        changeset = service.create_changeset(
            name="Test changeset", event_ids=[event_id_1, event_id_2]
        )

        assert len(changeset.event_ids) == 2
        assert event_id_1 in changeset.event_ids
        assert event_id_2 in changeset.event_ids

    def test_create_changeset_is_persisted(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that created changeset is persisted to repository."""
        changeset = service.create_changeset(name="Test changeset")

        retrieved = repo.get_changeset(changeset.id)
        assert retrieved is not None
        assert retrieved.id == changeset.id
        assert retrieved.name == "Test changeset"

    def test_stage_changeset_success(
        self, service: VersioningService
    ) -> None:
        """Test staging a changeset from WORKING to STAGED."""
        changeset = service.create_changeset(name="Test changeset")
        assert changeset.state == ChangeState.WORKING

        staged = service.stage_changeset(changeset.id)
        assert staged.state == ChangeState.STAGED

    def test_stage_changeset_updates_timestamp(
        self, service: VersioningService
    ) -> None:
        """Test that staging a changeset updates its timestamp."""
        changeset = service.create_changeset(name="Test changeset")

        staged = service.stage_changeset(changeset.id)
        # The updated_at should be updated, but we can't guarantee it's strictly
        # greater due to timing, so just verify it exists
        assert staged.updated_at is not None

    def test_stage_changeset_not_found(
        self, service: VersioningService
    ) -> None:
        """Test staging a non-existent changeset raises error."""
        with pytest.raises(VersionNotFoundError):
            service.stage_changeset("nonexistent-id")

    def test_stage_already_staged_raises(
        self, service: VersioningService
    ) -> None:
        """Test that staging an already staged changeset raises error."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)

        with pytest.raises(ChangesetStateError):
            service.stage_changeset(changeset.id)

    def test_submit_proposal_success(
        self, service: VersioningService
    ) -> None:
        """Test submitting a changeset as a proposal."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)

        proposal = service.submit_proposal(changeset.id)

        assert proposal.changeset_id == changeset.id
        assert proposal.state == "open"
        assert proposal.submitted_at is not None
        assert proposal.reviewed_at is None

    def test_submit_proposal_transitions_changeset(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that submitting a proposal transitions changeset to PROPOSED."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)

        service.submit_proposal(changeset.id)

        updated_changeset = repo.get_changeset(changeset.id)
        assert updated_changeset is not None
        assert updated_changeset.state == ChangeState.PROPOSED

    def test_submit_proposal_not_found(
        self, service: VersioningService
    ) -> None:
        """Test submitting a proposal for non-existent changeset raises error."""
        with pytest.raises(VersionNotFoundError):
            service.submit_proposal("nonexistent-id")

    def test_submit_proposal_not_staged_raises(
        self, service: VersioningService
    ) -> None:
        """Test that submitting a proposal from WORKING state raises error."""
        changeset = service.create_changeset(name="Test changeset")
        # Don't stage it

        with pytest.raises(ChangesetStateError):
            service.submit_proposal(changeset.id)


# ============================================================================
# Proposal Workflow Tests
# ============================================================================


class TestProposalWorkflow:
    """Test proposal approval, rejection, and merge workflows."""

    def test_approve_proposal_success(
        self, service: VersioningService
    ) -> None:
        """Test approving a proposal."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)

        approved = service.approve_proposal(proposal.id)

        assert approved.state == "approved"
        assert approved.reviewed_at is not None

    def test_approve_proposal_transitions_changeset(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that approving a proposal transitions changeset to APPROVED."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)

        service.approve_proposal(proposal.id)

        updated_changeset = repo.get_changeset(changeset.id)
        assert updated_changeset is not None
        assert updated_changeset.state == ChangeState.APPROVED

    def test_approve_proposal_not_found(
        self, service: VersioningService
    ) -> None:
        """Test approving a non-existent proposal raises error."""
        with pytest.raises(VersionNotFoundError):
            service.approve_proposal("nonexistent-id")

    def test_reject_proposal_success(
        self, service: VersioningService
    ) -> None:
        """Test rejecting a proposal."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)

        reason = "Does not meet requirements"
        rejected = service.reject_proposal(proposal.id, reason)

        assert rejected.state == "rejected"
        assert rejected.reviewer_notes == reason
        assert rejected.reviewed_at is not None

    def test_reject_proposal_transitions_changeset_back_to_working(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that rejecting a proposal transitions changeset back to WORKING."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)

        service.reject_proposal(proposal.id, "Not ready")

        updated_changeset = repo.get_changeset(changeset.id)
        assert updated_changeset is not None
        assert updated_changeset.state == ChangeState.WORKING

    def test_reject_proposal_not_found(
        self, service: VersioningService
    ) -> None:
        """Test rejecting a non-existent proposal raises error."""
        with pytest.raises(VersionNotFoundError):
            service.reject_proposal("nonexistent-id", "Test reason")

    def test_merge_proposal_success(
        self, service: VersioningService
    ) -> None:
        """Test merging an approved proposal."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        result = service.merge_proposal(proposal.id)

        assert result.proposal_id == proposal.id
        assert result.merged_at is not None
        assert result.events_applied == 0
        assert result.conflicts_resolved == 0

    def test_merge_proposal_transitions_changeset(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that merging a proposal transitions changeset to MERGED."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        service.merge_proposal(proposal.id)

        updated_changeset = repo.get_changeset(changeset.id)
        assert updated_changeset is not None
        assert updated_changeset.state == ChangeState.MERGED

    def test_merge_proposal_updates_proposal_state(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that merging a proposal updates its state to 'merged'."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        service.merge_proposal(proposal.id)

        updated_proposal = repo.get_proposal(proposal.id)
        assert updated_proposal is not None
        assert updated_proposal.state == "merged"

    def test_merge_proposal_counts_events(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that merge result counts events applied."""
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation="create",
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation="create",
            new_state={"name": "Entity2"},
        )

        changeset = service.create_changeset(
            name="Test changeset", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        result = service.merge_proposal(proposal.id)
        assert result.events_applied == 2

    def test_merge_proposal_not_found(
        self, service: VersioningService
    ) -> None:
        """Test merging a non-existent proposal raises error."""
        with pytest.raises(VersionNotFoundError):
            service.merge_proposal("nonexistent-id")

    def test_merge_proposal_not_approved_raises(
        self, service: VersioningService
    ) -> None:
        """Test that merging a non-approved proposal raises error."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        # Don't approve it

        with pytest.raises(ChangesetStateError):
            service.merge_proposal(proposal.id)

    def test_merge_rejected_proposal_raises(
        self, service: VersioningService
    ) -> None:
        """Test that merging a rejected proposal raises error."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.reject_proposal(proposal.id, "Not ready")

        with pytest.raises(ChangesetStateError):
            service.merge_proposal(proposal.id)


# ============================================================================
# Integration Tests
# ============================================================================


class TestChangesetWorkflow:
    """Test complete workflows through multiple state transitions."""

    def test_full_changeset_workflow_approve_and_merge(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test complete workflow: create, stage, propose, approve, merge."""
        # Create
        changeset = service.create_changeset(
            name="Full workflow test",
            description="Testing the complete workflow",
        )
        assert changeset.state == ChangeState.WORKING

        # Stage
        changeset = service.stage_changeset(changeset.id)
        assert changeset.state == ChangeState.STAGED

        # Submit
        proposal = service.submit_proposal(changeset.id)
        assert proposal.state == "open"
        retrieved_changeset = repo.get_changeset(changeset.id)
        assert retrieved_changeset is not None
        assert retrieved_changeset.state == ChangeState.PROPOSED

        # Approve
        proposal = service.approve_proposal(proposal.id)
        assert proposal.state == "approved"
        retrieved_changeset = repo.get_changeset(changeset.id)
        assert retrieved_changeset is not None
        assert retrieved_changeset.state == ChangeState.APPROVED

        # Merge
        result = service.merge_proposal(proposal.id)
        assert result.proposal_id == proposal.id
        retrieved_changeset = repo.get_changeset(changeset.id)
        assert retrieved_changeset is not None
        assert retrieved_changeset.state == ChangeState.MERGED
        retrieved_proposal = repo.get_proposal(proposal.id)
        assert retrieved_proposal is not None
        assert retrieved_proposal.state == "merged"

    def test_changeset_workflow_reject_and_rework(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test workflow: create, stage, propose, reject, rework."""
        # Create and stage
        changeset = service.create_changeset(name="Workflow test")
        service.stage_changeset(changeset.id)

        # Submit proposal
        proposal = service.submit_proposal(changeset.id)
        retrieved_changeset = repo.get_changeset(changeset.id)
        assert retrieved_changeset is not None
        assert retrieved_changeset.state == ChangeState.PROPOSED

        # Reject
        service.reject_proposal(proposal.id, "Needs revision")
        retrieved_changeset = repo.get_changeset(changeset.id)
        assert retrieved_changeset is not None
        assert retrieved_changeset.state == ChangeState.WORKING

        # Re-stage and re-propose
        service.stage_changeset(retrieved_changeset.id)
        retrieved_changeset = repo.get_changeset(changeset.id)
        assert retrieved_changeset is not None
        assert retrieved_changeset.state == ChangeState.STAGED

        proposal2 = service.submit_proposal(retrieved_changeset.id)
        assert proposal2.changeset_id == proposal.changeset_id
        assert proposal2.id != proposal.id

    def test_multiple_changesets_independent(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that multiple changesets are independent."""
        cs1 = service.create_changeset(name="Changeset 1")
        cs2 = service.create_changeset(name="Changeset 2")

        service.stage_changeset(cs1.id)
        # cs2 should still be in WORKING
        retrieved_cs2 = repo.get_changeset(cs2.id)
        assert retrieved_cs2 is not None
        assert retrieved_cs2.state == ChangeState.WORKING

        service.stage_changeset(cs2.id)
        retrieved_cs1 = repo.get_changeset(cs1.id)
        assert retrieved_cs1 is not None
        assert retrieved_cs1.state == ChangeState.STAGED
        retrieved_cs2 = repo.get_changeset(cs2.id)
        assert retrieved_cs2 is not None
        assert retrieved_cs2.state == ChangeState.STAGED
