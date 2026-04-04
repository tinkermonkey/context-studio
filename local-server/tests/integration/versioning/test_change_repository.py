"""
Integration tests for SQLiteChangeRepository.

Tests against in-memory SQLite database to verify all persistence operations.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add local-server root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from domain.versioning.entities import (
    EntityVersion,
    Changeset,
    Proposal,
)
from domain.versioning.value_objects import ChangeState, ChangeOperation, ProposalState
from domain.versioning.exceptions import VersionNotFoundError


@pytest.fixture
def session_factory():
    """Create an in-memory SQLite database and session factory."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def repository(session_factory):
    """Create a repository instance with test database."""
    return SQLiteChangeRepository(session_factory)


class TestChangeEventOperations:
    """Test ChangeEvent persistence operations."""

    def test_record_change_returns_id(self, repository) -> None:
        """Test that record_change returns the event ID."""
        event_id = repository.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"title": "Test Class"},
        )

        assert event_id is not None
        assert len(event_id) > 0

    def test_record_change_stores_all_fields(self, repository) -> None:
        """Test that all fields are stored correctly."""
        event_id = repository.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"title": "Updated"},
            previous_state={"title": "Old"},
            user_id="user1",
            change_reason="Fixed typo",
            changeset_id="cs1",
        )

        result = repository.get_changes(entity_id="entity1")
        assert len(result.events) == 1
        assert result.total == 1

        event = result.events[0]
        assert event.id == event_id
        assert event.entity_id == "entity1"
        assert event.entity_type == "class"
        assert event.operation == "update"
        assert event.new_state == {"title": "Updated"}
        assert event.previous_state == {"title": "Old"}
        assert event.user_id == "user1"
        assert event.change_reason == "Fixed typo"
        assert event.changeset_id == "cs1"

    def test_get_changes_by_entity_id(self, repository) -> None:
        """Test filtering changes by entity ID."""
        repository.record_change(
            entity_id="entity1", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )
        repository.record_change(
            entity_id="entity2", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )

        result = repository.get_changes(entity_id="entity1")
        assert len(result.events) == 1
        assert result.total == 1
        assert result.events[0].entity_id == "entity1"

    def test_get_changes_by_timestamp(self, repository) -> None:
        """Test filtering changes by timestamp."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        repository.record_change(
            entity_id="entity1", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )

        recent_result = repository.get_changes(since=past)
        old_result = repository.get_changes(since=future)

        assert len(recent_result.events) == 1
        assert recent_result.total == 1
        assert len(old_result.events) == 0
        assert old_result.total == 0

    def test_get_changes_respects_limit(self, repository) -> None:
        """Test that get_changes respects the limit parameter."""
        for i in range(5):
            repository.record_change(
                entity_id=f"entity{i}",
                entity_type="class",
                operation=ChangeOperation.CREATE,
                new_state={},
            )

        result = repository.get_changes(limit=3)
        assert len(result.events) == 3
        assert result.total == 5

    def test_mark_processed_sets_flag(self, repository) -> None:
        """Test that mark_processed sets the processed flag."""
        event_id = repository.record_change(
            entity_id="entity1", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )

        repository.mark_processed([event_id])

        result = repository.get_changes(entity_id="entity1")
        assert result.events[0].processed is True

    def test_get_unprocessed_returns_unprocessed(self, repository) -> None:
        """Test that get_unprocessed returns only unprocessed events."""
        event1_id = repository.record_change(
            entity_id="entity1", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )
        event2_id = repository.record_change(
            entity_id="entity2", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )

        repository.mark_processed([event1_id])

        unprocessed = repository.get_unprocessed()
        assert len(unprocessed) == 1
        assert unprocessed[0].id == event2_id


class TestEntityVersionOperations:
    """Test EntityVersion persistence operations."""

    def test_save_version_persists(self, repository) -> None:
        """Test that save_version persists the entity version."""
        version = EntityVersion(
            entity_id="entity1",
            version=1,
            state="active",
            snapshot={"title": "Class 1"},
            created_at=datetime.now(timezone.utc),
        )

        repository.save_version(version)

        retrieved = repository.get_version("entity1", 1)
        assert retrieved is not None
        assert retrieved.entity_id == "entity1"
        assert retrieved.version == 1
        assert retrieved.state == "active"

    def test_get_latest_version(self, repository) -> None:
        """Test getting the latest version."""
        v1 = EntityVersion(
            entity_id="entity1",
            version=1,
            state="active",
            snapshot={"title": "V1"},
            created_at=datetime.now(timezone.utc),
        )
        v2 = EntityVersion(
            entity_id="entity1",
            version=2,
            state="active",
            snapshot={"title": "V2"},
            created_at=datetime.now(timezone.utc),
        )

        repository.save_version(v1)
        repository.save_version(v2)

        latest = repository.get_latest_version("entity1")
        assert latest is not None
        assert latest.version == 2

    def test_list_versions_returns_all_in_order(self, repository) -> None:
        """Test that list_versions returns all versions in order."""
        for i in range(1, 4):
            version = EntityVersion(
                entity_id="entity1",
                version=i,
                state="active",
                snapshot={"v": i},
                created_at=datetime.now(timezone.utc),
            )
            repository.save_version(version)

        versions = repository.list_versions("entity1")
        assert len(versions) == 3
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[2].version == 3

    def test_get_version_returns_none_if_not_found(self, repository) -> None:
        """Test that get_version returns None if not found."""
        retrieved = repository.get_version("nonexistent", 1)
        assert retrieved is None

    def test_get_latest_version_returns_none_if_empty(self, repository) -> None:
        """Test that get_latest_version returns None if no versions exist."""
        latest = repository.get_latest_version("nonexistent")
        assert latest is None


class TestChangesetOperations:
    """Test Changeset persistence operations."""

    def test_create_changeset(self, repository) -> None:
        """Test creating a changeset."""
        changeset = Changeset(
            id="cs1",
            name="My Changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            description="Test changeset",
        )

        result = repository.create_changeset(changeset)
        assert result.id == "cs1"
        assert result.name == "My Changeset"

    def test_get_changeset(self, repository) -> None:
        """Test retrieving a changeset."""
        changeset = Changeset(
            id="cs1",
            name="My Changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repository.create_changeset(changeset)
        retrieved = repository.get_changeset("cs1")

        assert retrieved is not None
        assert retrieved.id == "cs1"
        assert retrieved.name == "My Changeset"
        assert retrieved.state == ChangeState.WORKING

    def test_update_changeset(self, repository) -> None:
        """Test updating a changeset."""
        changeset = Changeset(
            id="cs1",
            name="Original",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        repository.create_changeset(changeset)

        changeset.name = "Updated"
        changeset.state = ChangeState.STAGED
        repository.update_changeset(changeset)

        retrieved = repository.get_changeset("cs1")
        assert retrieved is not None
        assert retrieved.name == "Updated"
        assert retrieved.state == ChangeState.STAGED

    def test_get_nonexistent_changeset_returns_none(self, repository) -> None:
        """Test that getting a nonexistent changeset returns None."""
        retrieved = repository.get_changeset("nonexistent")
        assert retrieved is None

    def test_create_changeset_persists_event_ids(self, repository) -> None:
        """Test that create_changeset persists event IDs to junction table."""
        # Create some change events first
        event1_id = repository.record_change(
            entity_id="entity1", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )
        event2_id = repository.record_change(
            entity_id="entity2", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )

        # Create a changeset with these event IDs
        changeset = Changeset(
            id="cs1",
            name="My Changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            event_ids=[event1_id, event2_id],
        )

        repository.create_changeset(changeset)

        # Retrieve the changeset and verify event_ids are persisted
        retrieved = repository.get_changeset("cs1")
        assert retrieved is not None
        assert sorted(retrieved.event_ids) == sorted([event1_id, event2_id])

    def test_update_changeset_raises_if_not_found(self, repository) -> None:
        """Test that update_changeset raises VersionNotFoundError if not found."""
        changeset = Changeset(
            id="nonexistent",
            name="Ghost Changeset",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(VersionNotFoundError):
            repository.update_changeset(changeset)

    def test_update_changeset_persists_event_ids_changes(self, repository) -> None:
        """Verify update_changeset correctly syncs changes to event_ids in junction table."""
        # Create initial events
        event_id_1 = repository.record_change(
            entity_id="entity1", entity_type="TestEntity", operation=ChangeOperation.CREATE, new_state={"name": "test"}
        )
        event_id_2 = repository.record_change(
            entity_id="entity1", entity_type="TestEntity", operation=ChangeOperation.UPDATE, new_state={"name": "updated"}
        )

        # Create changeset with first two events
        changeset = Changeset(
            id="cs1",
            name="Initial Changeset",
            description="Initial description",
            state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            event_ids=[event_id_1, event_id_2],
        )

        repository.create_changeset(changeset)

        # Create additional events
        event_id_3 = repository.record_change(
            entity_id="entity2", entity_type="TestEntity", operation=ChangeOperation.CREATE, new_state={"name": "new"}
        )
        event_id_4 = repository.record_change(
            entity_id="entity2", entity_type="TestEntity", operation=ChangeOperation.UPDATE, new_state={"name": "newer"}
        )

        # Update changeset with new event list (removed event_id_2, added event_id_3 and event_id_4)
        updated_changeset = Changeset(
            id="cs1",
            name="Updated Changeset",
            description="Updated description",
            state=ChangeState.STAGED,
            created_at=changeset.created_at,
            updated_at=datetime.now(timezone.utc),
            event_ids=[event_id_1, event_id_3, event_id_4],
        )

        repository.update_changeset(updated_changeset)

        # Verify the changeset has the updated event_ids
        retrieved = repository.get_changeset("cs1")

        assert retrieved is not None
        assert retrieved.name == "Updated Changeset"
        assert retrieved.description == "Updated description"
        assert retrieved.state == ChangeState.STAGED
        assert set(retrieved.event_ids) == {event_id_1, event_id_3, event_id_4}


class TestProposalOperations:
    """Test Proposal persistence operations."""

    def test_create_proposal(self, repository) -> None:
        """Test creating a proposal."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        result = repository.create_proposal(proposal)
        assert result.id == "prop1"
        assert result.changeset_id == "cs1"
        assert result.state == "open"

    def test_get_proposal(self, repository) -> None:
        """Test retrieving a proposal."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
            reviewer_notes="Looks good",
        )

        repository.create_proposal(proposal)
        retrieved = repository.get_proposal("prop1")

        assert retrieved is not None
        assert retrieved.id == "prop1"
        assert retrieved.reviewer_notes == "Looks good"

    def test_update_proposal(self, repository) -> None:
        """Test updating a proposal."""
        proposal = Proposal(
            id="prop1",
            changeset_id="cs1",
            state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        repository.create_proposal(proposal)

        proposal.state = ProposalState.APPROVED
        proposal.reviewed_at = datetime.now(timezone.utc)
        repository.update_proposal(proposal)

        retrieved = repository.get_proposal("prop1")
        assert retrieved is not None
        assert retrieved.state == "approved"
        assert retrieved.reviewed_at is not None

    def test_get_nonexistent_proposal_returns_none(self, repository) -> None:
        """Test that getting a nonexistent proposal returns None."""
        retrieved = repository.get_proposal("nonexistent")
        assert retrieved is None

    def test_update_proposal_raises_if_not_found(self, repository) -> None:
        """Test that update_proposal raises VersionNotFoundError if not found."""
        proposal = Proposal(
            id="nonexistent",
            changeset_id="cs1",
            state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(VersionNotFoundError):
            repository.update_proposal(proposal)


class TestMarkProcessedOperations:
    """Test mark_processed exception handling."""

    def test_mark_processed_raises_if_event_not_found(self, repository) -> None:
        """Test that mark_processed raises VersionNotFoundError if event ID doesn't exist."""
        with pytest.raises(VersionNotFoundError):
            repository.mark_processed(["nonexistent-event-id"])

    def test_mark_processed_raises_if_any_event_not_found(self, repository) -> None:
        """Test that mark_processed raises if any of multiple event IDs don't exist."""
        # Create one valid event
        event_id = repository.record_change(
            entity_id="entity1", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )

        # Try to mark both valid and invalid IDs
        with pytest.raises(VersionNotFoundError):
            repository.mark_processed([event_id, "nonexistent-id"])

    def test_mark_processed_succeeds_with_all_valid_ids(self, repository) -> None:
        """Test that mark_processed succeeds when all IDs exist."""
        event1_id = repository.record_change(
            entity_id="entity1", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )
        event2_id = repository.record_change(
            entity_id="entity2", entity_type="class", operation=ChangeOperation.CREATE, new_state={}
        )

        # Should not raise
        repository.mark_processed([event1_id, event2_id])

        # Verify both are marked as processed
        unprocessed = repository.get_unprocessed()
        assert len(unprocessed) == 0
