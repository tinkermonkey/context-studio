"""
Integration tests for SQLiteChangeRepository.

Tests against in-memory SQLite database to verify all persistence operations.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base
from domain.versioning.exceptions import VersionNotFoundError
from domain.versioning.value_objects import ChangeOperation


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

    def test_get_changes_by_entity_id(self, repository) -> None:
        """Test filtering changes by entity ID."""
        repository.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
        )
        repository.record_change(
            entity_id="entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
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
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
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
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
        )

        repository.mark_processed([event_id])

        result = repository.get_changes(entity_id="entity1")
        assert result.events[0].processed is True

    def test_get_unprocessed_returns_unprocessed(self, repository) -> None:
        """Test that get_unprocessed returns only unprocessed events."""
        event1_id = repository.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
        )
        event2_id = repository.record_change(
            entity_id="entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
        )

        repository.mark_processed([event1_id])

        unprocessed = repository.get_unprocessed()
        assert len(unprocessed) == 1
        assert unprocessed[0].id == event2_id


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
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
        )

        # Try to mark both valid and invalid IDs
        with pytest.raises(VersionNotFoundError):
            repository.mark_processed([event_id, "nonexistent-id"])

    def test_mark_processed_succeeds_with_all_valid_ids(self, repository) -> None:
        """Test that mark_processed succeeds when all IDs exist."""
        event1_id = repository.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
        )
        event2_id = repository.record_change(
            entity_id="entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={},
        )

        # Should not raise
        repository.mark_processed([event1_id, event2_id])

        # Verify both are marked as processed
        unprocessed = repository.get_unprocessed()
        assert len(unprocessed) == 0
