"""Integration tests for SQLiteChangeRepository."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base, ChangeEvent
from domain.versioning.exceptions import VersionNotFoundError
from domain.versioning.value_objects import ChangeOperation
from tests.utils.parent_rows import create_batch_run_row


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    """Create a session factory for testing."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def change_repo(session_factory):
    """Create a SQLiteChangeRepository with test session factory."""
    return SQLiteChangeRepository(session_factory)


class TestSQLiteChangeRepository:
    """Tests for SQLiteChangeRepository."""

    def test_record_change_creates_record(self, change_repo, session_factory):
        """Test that record_change persists a change event."""
        change_id = change_repo.record_change(
            entity_id="entity-123",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"result_id": "entity-123", "count": 42},
            change_reason="Test creation",
        )

        assert change_id is not None

        # Verify the record was persisted
        session = session_factory()
        try:
            record = session.query(ChangeEvent).filter_by(id=change_id).first()
            assert record is not None
            assert record.entity_id == "entity-123"
            assert record.entity_type == "extraction_result"
            assert record.operation == "create"
            assert record.new_state == {"result_id": "entity-123", "count": 42}
            assert record.change_reason == "Test creation"
        finally:
            session.close()

    def test_record_change_with_all_fields(self, change_repo, session_factory):
        """Test that record_change captures all optional fields."""
        change_id = change_repo.record_change(
            entity_id="entity-456",
            entity_type="pipeline_execution",
            operation=ChangeOperation.UPDATE,
            new_state={"status": "complete"},
            previous_state={"status": "running"},
            user_id="user-789",
            change_reason="Status updated",
        )

        session = session_factory()
        try:
            record = session.query(ChangeEvent).filter_by(id=change_id).first()
            assert record.previous_state == {"status": "running"}
            assert record.user_id == "user-789"
        finally:
            session.close()

    def test_record_change_returns_unique_ids(self, change_repo):
        """Test that multiple calls return unique change IDs."""
        id1 = change_repo.record_change(
            entity_id="entity-1",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={},
        )
        id2 = change_repo.record_change(
            entity_id="entity-2",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={},
        )

        assert id1 != id2

    def test_mark_processed_updates_flag(self, change_repo, session_factory):
        """Test that mark_processed updates the processed flag."""
        change_id = change_repo.record_change(
            entity_id="entity-123",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-123"},
        )

        assert change_id is not None

        # Mark as processed
        change_repo.mark_processed([change_id])

        # Verify the flag was updated
        session = session_factory()
        try:
            record = session.query(ChangeEvent).filter_by(id=change_id).first()
            assert record is not None
            assert record.processed is True
        finally:
            session.close()

    def test_mark_processed_raises_on_missing_ids(self, change_repo):
        """Test that mark_processed raises VersionNotFoundError for non-existent IDs."""
        with pytest.raises(VersionNotFoundError):
            change_repo.mark_processed(["non-existent-id"])

    def test_mark_processed_raises_if_any_id_missing(self, change_repo):
        """Test that mark_processed raises if any ID in a batch doesn't exist."""
        change_id = change_repo.record_change(
            entity_id="entity-123",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-123"},
        )

        with pytest.raises(VersionNotFoundError) as exc_info:
            change_repo.mark_processed([change_id, "non-existent-id"])

        assert "non-existent-id" in str(exc_info.value)

    def test_delete_changes_removes_records(self, change_repo, session_factory):
        """Test that delete_changes removes change events."""
        change_id = change_repo.record_change(
            entity_id="entity-123",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-123"},
        )

        assert change_id is not None

        # Delete the change
        change_repo.delete_changes([change_id])

        # Verify it was deleted
        session = session_factory()
        try:
            record = session.query(ChangeEvent).filter_by(id=change_id).first()
            assert record is None
        finally:
            session.close()

    def test_delete_changes_raises_on_missing_ids(self, change_repo):
        """Test that delete_changes raises VersionNotFoundError for non-existent IDs."""
        with pytest.raises(VersionNotFoundError):
            change_repo.delete_changes(["non-existent-id"])

    def test_delete_changes_raises_if_any_id_missing(self, change_repo):
        """Test that delete_changes raises if any ID in a batch doesn't exist."""
        change_id = change_repo.record_change(
            entity_id="entity-123",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-123"},
        )

        with pytest.raises(VersionNotFoundError) as exc_info:
            change_repo.delete_changes([change_id, "non-existent-id"])

        assert "non-existent-id" in str(exc_info.value)

    def test_count_unprocessed_counts_only_unprocessed(self, change_repo):
        """Test that count_unprocessed counts only unprocessed changes."""
        # Create 3 unprocessed changes
        id1 = change_repo.record_change(
            entity_id="entity-1",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-1"},
        )
        change_repo.record_change(
            entity_id="entity-2",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-2"},
        )
        change_repo.record_change(
            entity_id="entity-3",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-3"},
        )

        # Mark one as processed
        change_repo.mark_processed([id1])

        # Count should be 2 (id2 and id3)
        count = change_repo.count_unprocessed()
        assert count == 2

    def test_count_unprocessed_with_no_changes(self, change_repo):
        """Test that count_unprocessed returns 0 with no changes."""
        count = change_repo.count_unprocessed()
        assert count == 0

    def test_count_unprocessed_with_all_processed(self, change_repo):
        """Test that count_unprocessed returns 0 when all changes are processed."""
        change_id = change_repo.record_change(
            entity_id="entity-123",
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-123"},
        )

        change_repo.mark_processed([change_id])

        count = change_repo.count_unprocessed()
        assert count == 0

    # New error handling tests

    def test_mark_processed_raises_domain_exception_before_db_exception(self, change_repo):
        """Test that mark_processed raises VersionNotFoundError without catching it."""
        # This test verifies the defensive re-raise is in place
        with pytest.raises(VersionNotFoundError):
            change_repo.mark_processed(["nonexistent-id"])

    def test_get_changes_breaks_timestamp_ties_newest_inserted_first(
        self, change_repo, session_factory
    ):
        """Events with the same timestamp come back in reverse insertion order."""
        same_time = datetime.now(timezone.utc)
        with session_factory() as session:
            for event_id in ("zzz-first", "aaa-second"):  # ids sort opposite to insertion
                session.add(
                    ChangeEvent(
                        id=event_id,
                        entity_id="entity-1",
                        entity_type="class",
                        operation="update",
                        new_state={},
                        timestamp=same_time,
                    )
                )
                session.flush()
            session.commit()

        result = change_repo.get_changes(entity_id="entity-1", limit=None)

        assert [e.id for e in result.events] == ["aaa-second", "zzz-first"]

    def test_get_changes_filters_by_batch_run_id(self, change_repo, session_factory):
        """Test that get_changes correctly filters by batch_run_id."""
        for run_id in ("batch-1", "batch-2"):
            create_batch_run_row(session_factory, run_id)
        # Record changes for different batch runs
        change_repo.record_change(
            entity_id="entity-1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-1"},
            batch_run_id="batch-1",
        )
        change_repo.record_change(
            entity_id="entity-2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-2"},
            batch_run_id="batch-1",
        )
        change_repo.record_change(
            entity_id="entity-3",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-3"},
            batch_run_id="batch-2",
        )

        # Get changes for batch-1
        result = change_repo.get_changes(batch_run_id="batch-1", limit=None)
        assert len(result.events) == 2
        assert all(e.batch_run_id == "batch-1" for e in result.events)
        entity_ids = {e.entity_id for e in result.events}
        assert entity_ids == {"entity-1", "entity-2"}

        # Get changes for batch-2
        result = change_repo.get_changes(batch_run_id="batch-2", limit=None)
        assert len(result.events) == 1
        assert result.events[0].batch_run_id == "batch-2"
        assert result.events[0].entity_id == "entity-3"

        # Get changes for non-existent batch
        result = change_repo.get_changes(batch_run_id="batch-nonexistent", limit=None)
        assert len(result.events) == 0

    def test_get_changes_combines_multiple_filters(self, change_repo, session_factory):
        """Test that get_changes correctly applies multiple filters together."""
        for run_id in ("batch-1", "batch-2"):
            create_batch_run_row(session_factory, run_id)
        # Record changes with different combinations of attributes
        change_repo.record_change(
            entity_id="entity-1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-1"},
            batch_run_id="batch-1",
        )
        change_repo.record_change(
            entity_id="entity-1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={},
            new_state={"id": "entity-1", "updated": True},
            batch_run_id="batch-1",
        )
        change_repo.record_change(
            entity_id="entity-2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"id": "entity-2"},
            batch_run_id="batch-2",
        )

        # Filter by batch_run_id and entity_id
        result = change_repo.get_changes(batch_run_id="batch-1", entity_id="entity-1", limit=None)
        assert len(result.events) == 2
        assert all(e.entity_id == "entity-1" and e.batch_run_id == "batch-1" for e in result.events)

        # Filter by batch_run_id only
        result = change_repo.get_changes(batch_run_id="batch-1", limit=None)
        assert len(result.events) == 2
