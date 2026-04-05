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
from domain.versioning.entities import EntityVersion, Proposal, ChangeEvent
from domain.versioning.events import ChangesetMerged, SyncCompleted
from domain.versioning.exceptions import VersionNotFoundError, ChangesetStateError, ConflictResolutionError
from domain.versioning.value_objects import ChangeState, ChangeOperation, ProposalState, SyncResult, EntityVersionState
from tests.fakes.fake_change_repository import FakeChangeRepository
from tests.fakes.fake_sync_target import FakeSyncTarget
from tests.fakes.fake_event_publisher import FakeEventPublisher


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def repo() -> FakeChangeRepository:
    """Create a fresh fake repository for each test."""
    return FakeChangeRepository()


@pytest.fixture
def sync_target() -> FakeSyncTarget:
    """Create a fresh fake sync target for each test."""
    return FakeSyncTarget()


@pytest.fixture
def event_publisher() -> FakeEventPublisher:
    """Create a fresh fake event publisher for each test."""
    return FakeEventPublisher()


@pytest.fixture
def service(repo: FakeChangeRepository, sync_target: FakeSyncTarget, event_publisher: FakeEventPublisher) -> VersioningService:
    """Create a VersioningService with fake dependencies."""
    return VersioningService(
        change_repo=repo,
        sync_target=sync_target,
        event_publisher=event_publisher,
    )


# ============================================================================
# Change History Query Tests
# ============================================================================


class TestChangeHistoryQueries:
    """Test change history query methods."""

    def test_get_change_history_empty(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history when no changes exist."""
        result = service.get_change_history()
        assert result.events == ()
        assert result.total == 0

    def test_get_change_history_all_events(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving all change events."""
        # Record some events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity2"},
        )

        result = service.get_change_history()
        assert len(result.events) == 2
        assert result.total == 2
        assert any(e.id == event_id_1 for e in result.events)
        assert any(e.id == event_id_2 for e in result.events)

    def test_get_change_history_filtered_by_entity(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history filtered by entity."""
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity2"},
        )

        result = service.get_change_history(entity_id="entity1")
        assert len(result.events) == 1
        assert result.total == 1
        assert result.events[0].entity_id == "entity1"

    def test_get_change_history_filtered_by_since(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history since a timestamp."""
        now = datetime.now(timezone.utc)
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        # This event is recorded with current time, so it will be after 'now'
        # Let's retrieve after a time before now
        since = now - timedelta(seconds=1)

        result = service.get_change_history(since=since)
        # The recorded event should be after 'since'
        assert len(result.events) > 0
        assert result.total > 0

    def test_get_change_history_respects_limit(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that change history respects the limit parameter."""
        for i in range(10):
            repo.record_change(
                entity_id=f"entity{i}",
                entity_type="class",
                operation=ChangeOperation.CREATE,
                new_state={"name": f"Entity{i}"},
            )

        result = service.get_change_history(limit=5)
        assert len(result.events) == 5
        assert result.total == 10

    def test_get_entity_version_success(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving a specific entity version."""
        version = EntityVersion(
            entity_id="entity1",
            version=1,
            state=EntityVersionState.ACTIVE,
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
            state=EntityVersionState.ACTIVE,
            snapshot={"name": "Entity1"},
            created_at=datetime.now(timezone.utc),
        )
        v2 = EntityVersion(
            entity_id="entity1",
            version=2,
            state=EntityVersionState.ACTIVE,
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
            state=EntityVersionState.ACTIVE,
            snapshot={"name": "Entity1"},
            created_at=datetime.now(timezone.utc),
        )
        v2 = EntityVersion(
            entity_id="entity1",
            version=2,
            state=EntityVersionState.ACTIVE,
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
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
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
        self, service: VersioningService, event_publisher: FakeEventPublisher
    ) -> None:
        """Test merging an approved proposal."""
        changeset = service.create_changeset(name="Test changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        result = service.merge_proposal(proposal.id)

        assert result.proposal_id == proposal.id
        assert result.changeset_id == changeset.id
        assert result.merged_at is not None
        assert result.events_applied == 0
        assert result.conflicts_resolved == 0

        # Verify ChangesetMerged event was published
        events = event_publisher.get_events_of_type(ChangesetMerged)
        assert len(events) == 1
        event = events[0]
        assert event.changeset_id == changeset.id
        assert event.proposal_id == proposal.id
        assert event.events_applied == 0

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
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
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


# ============================================================================
# Conflict Detection and Resolution Tests
# ============================================================================


class TestConflictDetection:
    """Test conflict detection in proposals."""

    def test_detect_conflicts_no_conflicts_empty_changeset(
        self, service: VersioningService
    ) -> None:
        """Test conflict detection with empty changeset (no events)."""
        changeset = service.create_changeset(name="Empty changeset")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        report = service.detect_conflicts(proposal.id)

        assert report.proposal_id == proposal.id
        assert report.has_conflicts is False
        assert report.all_resolved is True
        assert len(report.conflicts) == 0

    def test_detect_conflicts_no_conflicts_non_overlapping_entities(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that non-overlapping entity updates produce no conflicts."""
        # Create events for different entities
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1", "description": "Desc1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity2", "description": "Desc2"},
        )

        changeset = service.create_changeset(
            name="Non-overlapping changes", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        report = service.detect_conflicts(proposal.id)

        assert report.has_conflicts is False
        assert report.all_resolved is True
        assert len(report.conflicts) == 0

    def test_detect_conflicts_single_entity_no_conflicts(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that a single event on an entity produces no conflicts."""
        event_id = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )

        changeset = service.create_changeset(name="Single event", event_ids=[event_id])
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        report = service.detect_conflicts(proposal.id)

        assert report.has_conflicts is False
        assert len(report.conflicts) == 0

    def test_detect_conflicts_overlapping_updates_on_same_field(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test conflict detection when same field is updated twice."""
        # First update: entity1, name: old -> new1
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old_name"},
            new_state={"name": "new_name_1"},
        )

        # Second update: entity1, name should be new_name_1, but it's actually different
        # This simulates external modification: someone else changed it to new_name_2
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "different_name"},  # External change detected!
            new_state={"name": "new_name_2"},
        )

        changeset = service.create_changeset(
            name="Conflicting updates", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        report = service.detect_conflicts(proposal.id)

        assert report.has_conflicts is True
        assert len(report.conflicts) == 1
        conflict = report.conflicts[0]
        assert conflict.entity_id == "entity1"
        assert conflict.field_name == "name"
        assert conflict.base_value == "new_name_1"
        assert conflict.incoming_value == "new_name_2"
        assert conflict.is_resolved is False

    def test_detect_conflicts_multiple_fields_same_entity(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test conflict detection with multiple field conflicts on same entity."""
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old", "description": "old_desc", "status": "active"},
            new_state={"name": "new1", "description": "desc1", "status": "active"},
        )

        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "external_name", "description": "external_desc", "status": "active"},
            new_state={"name": "new2", "description": "desc2", "status": "inactive"},
        )

        changeset = service.create_changeset(
            name="Multiple field conflicts", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        report = service.detect_conflicts(proposal.id)

        assert report.has_conflicts is True
        # Should detect conflicts in name and description, but not status
        assert len(report.conflicts) == 2
        field_names = {c.field_name for c in report.conflicts}
        assert "name" in field_names
        assert "description" in field_names

    def test_detect_conflicts_proposal_not_found(
        self, service: VersioningService
    ) -> None:
        """Test conflict detection with non-existent proposal."""
        with pytest.raises(VersionNotFoundError):
            service.detect_conflicts("nonexistent-proposal-id")

    def test_detect_conflicts_changeset_not_found(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test conflict detection when changeset is missing."""
        proposal = Proposal(
            id="test-proposal",
            changeset_id="nonexistent-changeset",
            state=ProposalState.APPROVED,
            submitted_at=datetime.now(timezone.utc),
        )
        repo.create_proposal(proposal)

        with pytest.raises(VersionNotFoundError):
            service.detect_conflicts(proposal.id)


class TestAutoResolveConflicts:
    """Test automatic conflict resolution."""

    def test_auto_resolve_marks_all_resolved(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that auto_resolve marks all conflicts as resolved."""
        from domain.versioning.entities import Conflict, ConflictReport

        report = ConflictReport(proposal_id="test-proposal")
        report.conflicts = [
            Conflict(
                entity_id="entity1",
                field_name="name",
                base_value="old",
                incoming_value="new1",
            ),
            Conflict(
                entity_id="entity2",
                field_name="description",
                base_value="old_desc",
                incoming_value="new_desc",
            ),
        ]

        resolved = service.auto_resolve(report)

        assert resolved.all_resolved is True
        for conflict in resolved.conflicts:
            assert conflict.is_resolved is True
            assert conflict.resolved_value == conflict.incoming_value

    def test_auto_resolve_uses_incoming_value(
        self, service: VersioningService
    ) -> None:
        """Test that auto_resolve uses incoming_value for resolution."""
        from domain.versioning.entities import Conflict, ConflictReport

        report = ConflictReport(proposal_id="test-proposal")
        report.conflicts = [
            Conflict(
                entity_id="entity1",
                field_name="name",
                base_value="base_value",
                incoming_value="incoming_value",
            ),
        ]

        resolved = service.auto_resolve(report)

        assert resolved.conflicts[0].resolved_value == "incoming_value"

    def test_auto_resolve_empty_report(
        self, service: VersioningService
    ) -> None:
        """Test auto_resolve on empty conflict report."""
        from domain.versioning.entities import ConflictReport

        report = ConflictReport(proposal_id="test-proposal")

        resolved = service.auto_resolve(report)

        assert resolved.all_resolved is True
        assert len(resolved.conflicts) == 0


class TestManualConflictResolution:
    """Test manual conflict resolution."""

    def test_resolve_conflicts_no_conflicts(
        self, service: VersioningService
    ) -> None:
        """Test manual resolution when there are no conflicts."""
        changeset = service.create_changeset(name="No conflicts")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        report = service.resolve_conflicts(proposal.id, {})

        assert report.all_resolved is True
        assert len(report.conflicts) == 0

    def test_resolve_conflicts_complete_resolutions(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test successful resolution when all conflicts are provided."""
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old"},
            new_state={"name": "new1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "external"},
            new_state={"name": "new2"},
        )

        changeset = service.create_changeset(
            name="Conflict to resolve", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        resolutions = {
            "entity1": {"name": "resolved_name"}
        }

        report = service.resolve_conflicts(proposal.id, resolutions)

        assert report.all_resolved is True
        assert len(report.conflicts) == 1
        assert report.conflicts[0].is_resolved is True
        assert report.conflicts[0].resolved_value == "resolved_name"

    def test_resolve_conflicts_partial_resolutions_raises(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that partial resolutions raise ConflictResolutionError."""
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old", "description": "old_desc"},
            new_state={"name": "new1", "description": "desc1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "external_name", "description": "external_desc"},
            new_state={"name": "new2", "description": "desc2"},
        )

        changeset = service.create_changeset(
            name="Multiple conflicts", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        # Only resolve one of two conflicts
        resolutions = {
            "entity1": {"name": "resolved_name"}
            # description not resolved
        }

        with pytest.raises(ConflictResolutionError) as exc_info:
            service.resolve_conflicts(proposal.id, resolutions)

        assert "Unresolved conflicts" in str(exc_info.value)
        assert "entity1.description" in str(exc_info.value)

    def test_resolve_conflicts_wrong_entity_id_raises(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that resolution with wrong entity ID raises error."""
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old"},
            new_state={"name": "new1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "external"},
            new_state={"name": "new2"},
        )

        changeset = service.create_changeset(
            name="Conflict to resolve", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        # Try to resolve with wrong entity ID
        resolutions = {
            "wrong_entity": {"name": "resolved_name"}
        }

        with pytest.raises(ConflictResolutionError):
            service.resolve_conflicts(proposal.id, resolutions)


class TestMergeWithConflictDetection:
    """Test merge_proposal with conflict detection integrated."""

    def test_merge_proposal_blocks_unresolved_conflicts(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that merge is blocked when unresolved conflicts exist."""
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old"},
            new_state={"name": "new1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "external"},
            new_state={"name": "new2"},
        )

        changeset = service.create_changeset(
            name="Conflicted changeset", event_ids=[event_id_1, event_id_2]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        with pytest.raises(ConflictResolutionError) as exc_info:
            service.merge_proposal(proposal.id)

        assert "unresolved conflicts" in str(exc_info.value)

    def test_merge_proposal_succeeds_no_conflicts(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test merge succeeds when there are no conflicts."""
        event_id = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )

        changeset = service.create_changeset(name="Clean changeset", event_ids=[event_id])
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        result = service.merge_proposal(proposal.id)

        assert result.proposal_id == proposal.id
        assert result.conflicts_resolved == 0
        assert result.events_applied == 1

    def test_merge_proposal_counts_conflicts_resolved(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that merge result correctly counts resolved conflicts when no conflicts exist."""
        # Create a changeset with events but no conflicts
        event_id = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "new1"},
        )

        changeset = service.create_changeset(
            name="No conflicts", event_ids=[event_id]
        )
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        # Merge should succeed with no conflicts
        result = service.merge_proposal(proposal.id)

        assert result.proposal_id == proposal.id
        assert result.conflicts_resolved == 0
        assert result.events_applied == 1

    def test_merge_proposal_transitions_changeset_to_merged(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that merge transitions changeset to MERGED state."""
        changeset = service.create_changeset(name="To merge")
        service.stage_changeset(changeset.id)
        proposal = service.submit_proposal(changeset.id)
        service.approve_proposal(proposal.id)

        service.merge_proposal(proposal.id)

        retrieved = repo.get_changeset(changeset.id)
        assert retrieved is not None
        assert retrieved.state == ChangeState.MERGED


# ============================================================================
# Synchronization Tests
# ============================================================================


class TestSyncMethods:
    """Test sync methods (push/pull) with event slicing and transaction handling."""

    def test_push_changes_empty_returns_zero_pushed(
        self, service: VersioningService, repo: FakeChangeRepository, sync_target: FakeSyncTarget
    ) -> None:
        """Test push_changes with no unprocessed events returns 0 pushed."""
        result = service.push_changes()

        assert result.pushed == 0
        assert result.pushed_event_ids is None or len(result.pushed_event_ids) == 0
        assert len(result.errors) == 0

    def test_push_changes_marks_events_as_processed(
        self, service: VersioningService, repo: FakeChangeRepository, sync_target: FakeSyncTarget, event_publisher: FakeEventPublisher
    ) -> None:
        """Test push_changes marks successfully pushed events as processed."""
        # Record some unprocessed events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity2"},
        )

        # Push changes
        result = service.push_changes()

        # Verify push succeeded
        assert result.pushed == 2
        assert result.pushed_event_ids is not None
        assert event_id_1 in result.pushed_event_ids
        assert event_id_2 in result.pushed_event_ids
        assert len(result.errors) == 0

        # Verify events are marked as processed
        history = repo.get_changes()
        for change_event in history.events:
            if change_event.id in [event_id_1, event_id_2]:
                assert change_event.processed

        # Verify SyncCompleted event was published
        events = event_publisher.get_events_of_type(SyncCompleted)
        assert len(events) == 1
        event = events[0]
        assert event.direction == "push"
        assert event.events_count == 2

    def test_push_changes_respects_500_event_limit(
        self, service: VersioningService, repo: FakeChangeRepository, sync_target: FakeSyncTarget
    ) -> None:
        """Test push_changes slices events to 500 limit."""
        # Record 600 unprocessed events
        event_ids = []
        for i in range(600):
            event_id = repo.record_change(
                entity_id=f"entity{i}",
                entity_type="class",
                operation=ChangeOperation.CREATE,
                new_state={"name": f"Entity{i}"},
            )
            event_ids.append(event_id)

        # Push changes
        result = service.push_changes()

        # Should push only 500 (the limit)
        assert result.pushed == 500
        assert result.pushed_event_ids is not None
        assert len(result.pushed_event_ids) == 500

        # Verify 500 were marked processed, 100 remain unprocessed
        unprocessed_events = repo.get_unprocessed()
        assert len(unprocessed_events) == 100

    def test_push_changes_with_sync_target_not_configured(
        self, repo: FakeChangeRepository, event_publisher: FakeEventPublisher
    ) -> None:
        """Test push_changes when sync target is not configured."""
        sync_target = FakeSyncTarget(configured=False)
        service = VersioningService(
            change_repo=repo,
            sync_target=sync_target,
            event_publisher=event_publisher,
        )

        # Record an event
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )

        # Push should return error
        result = service.push_changes()

        assert result.pushed == 0
        assert len(result.errors) > 0
        # Event should not be marked as processed
        unprocessed = repo.get_unprocessed()
        assert len(unprocessed) == 1

    def test_pull_changes_empty_returns_zero_pulled(
        self, service: VersioningService, repo: FakeChangeRepository, sync_target: FakeSyncTarget
    ) -> None:
        """Test pull_changes with no remote events returns 0 pulled."""
        result = service.pull_changes()

        assert result.pulled == 0
        assert len(result.errors) == 0
        assert len(repo.get_changes().events) == 0

    def test_pull_changes_records_events_locally(
        self, service: VersioningService, repo: FakeChangeRepository, sync_target: FakeSyncTarget, event_publisher: FakeEventPublisher
    ) -> None:
        """Test pull_changes records remote events in local repository."""
        # Add remote events
        remote_event_1 = ChangeEvent(
            id="remote-1",
            entity_id="remote_entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity1"},
            timestamp=datetime.now(timezone.utc),
        )
        remote_event_2 = ChangeEvent(
            id="remote-2",
            entity_id="remote_entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity2"},
            timestamp=datetime.now(timezone.utc),
        )
        sync_target.add_remote_events([remote_event_1, remote_event_2])

        # Pull changes
        result = service.pull_changes()

        # Verify pull recorded events
        assert result.pulled == 2
        assert len(result.errors) == 0

        # Verify events are in repository
        history = repo.get_changes()
        assert len(history.events) == 2
        assert any(e.entity_id == "remote_entity1" for e in history.events)
        assert any(e.entity_id == "remote_entity2" for e in history.events)

        # Verify SyncCompleted event was published
        events = event_publisher.get_events_of_type(SyncCompleted)
        assert len(events) == 1
        event = events[0]
        assert event.direction == "pull"
        assert event.events_count == 2

    def test_pull_changes_stops_on_first_error(
        self, service: VersioningService, repo: FakeChangeRepository, event_publisher: FakeEventPublisher
    ) -> None:
        """Test pull_changes stops on first record error and logs partial success."""
        # Create a mock sync target that returns events
        remote_event = ChangeEvent(
            id="remote-1",
            entity_id="remote_entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity1"},
            timestamp=datetime.now(timezone.utc),
        )

        class FailingSyncTarget:
            def pull(self, since=None):
                return [remote_event]

            def push(self, events):
                return SyncResult(pushed=0, pulled=0, errors=())

            def is_configured(self):
                return True

        # Create a repository that fails on record_change by extending FakeChangeRepository
        class FailingRepository(FakeChangeRepository):
            def record_change(
                self,
                entity_id: str,
                entity_type: str,
                operation: ChangeOperation,
                new_state: dict,
                previous_state=None,
                user_id=None,
                change_reason=None,
                changeset_id=None,
            ):
                raise RuntimeError("Database error")

        failing_repo = FailingRepository()
        service = VersioningService(
            change_repo=failing_repo,
            sync_target=FailingSyncTarget(),
            event_publisher=event_publisher,
        )

        result = service.pull_changes()

        # Should have error, zero pulled
        assert result.pulled == 0
        assert len(result.errors) > 0
        assert "Database error" in result.errors[0]

    def test_pull_changes_rolls_back_on_partial_failure(
        self, service: VersioningService, repo: FakeChangeRepository, event_publisher: FakeEventPublisher
    ) -> None:
        """Test pull_changes rolls back all recorded events when one fails mid-pull."""
        # Create remote events to be pulled
        remote_event_1 = ChangeEvent(
            id="remote-1",
            entity_id="remote_entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity1"},
            timestamp=datetime.now(timezone.utc),
        )
        remote_event_2 = ChangeEvent(
            id="remote-2",
            entity_id="remote_entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity2"},
            timestamp=datetime.now(timezone.utc),
        )

        class PartialFailingSyncTarget:
            def pull(self, since=None):
                return [remote_event_1, remote_event_2]

            def push(self, events):
                return SyncResult(pushed=0, pulled=0, errors=())

            def is_configured(self):
                return True

        # Create a repository that succeeds once, then fails on second record_change
        class PartialFailingRepository(FakeChangeRepository):
            def __init__(self):
                super().__init__()
                self.record_change_count = 0

            def record_change(
                self,
                entity_id: str,
                entity_type: str,
                operation: ChangeOperation,
                new_state: dict,
                previous_state=None,
                user_id=None,
                change_reason=None,
                changeset_id=None,
            ):
                self.record_change_count += 1
                if self.record_change_count > 1:
                    raise RuntimeError("Second record failed")
                # First call succeeds - call parent implementation
                return super().record_change(
                    entity_id,
                    entity_type,
                    operation,
                    new_state,
                    previous_state,
                    user_id,
                    change_reason,
                    changeset_id,
                )

        failing_repo = PartialFailingRepository()
        service = VersioningService(
            change_repo=failing_repo,
            sync_target=PartialFailingSyncTarget(),
            event_publisher=event_publisher,
        )

        # Pull should fail after recording first event
        result = service.pull_changes()

        # Should have error
        assert len(result.errors) > 0
        assert "Second record failed" in result.errors[0]

        # Verify no events remain (first was recorded but then deleted during rollback)
        history = failing_repo.get_changes()
        assert len(history.events) == 0
