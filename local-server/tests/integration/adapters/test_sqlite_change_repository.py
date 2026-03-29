"""Integration tests for SQLiteChangeRepository."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base, ChangeEvent
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def change_repo(db_session):
    """Create a SQLiteChangeRepository with test session."""
    return SQLiteChangeRepository(db_session)


class TestSQLiteChangeRepository:
    """Tests for SQLiteChangeRepository."""

    def test_record_change_creates_record(self, change_repo, db_session):
        """Test that record_change persists a change event."""
        change_id = change_repo.record_change(
            entity_id="entity-123",
            entity_type="extraction_result",
            operation="create",
            new_state={"result_id": "entity-123", "count": 42},
            change_reason="Test creation",
        )

        assert change_id is not None

        # Verify the record was persisted
        record = db_session.query(ChangeEvent).filter_by(id=change_id).first()
        assert record is not None
        assert record.entity_id == "entity-123"
        assert record.entity_type == "extraction_result"
        assert record.operation == "create"
        assert record.new_state == {"result_id": "entity-123", "count": 42}
        assert record.change_reason == "Test creation"

    def test_record_change_with_all_fields(self, change_repo, db_session):
        """Test that record_change captures all optional fields."""
        change_id = change_repo.record_change(
            entity_id="entity-456",
            entity_type="pipeline_execution",
            operation="update",
            new_state={"status": "complete"},
            previous_state={"status": "running"},
            user_id="user-789",
            change_reason="Status updated",
            changeset_id="changeset-999",
        )

        record = db_session.query(ChangeEvent).filter_by(id=change_id).first()
        assert record.previous_state == {"status": "running"}
        assert record.user_id == "user-789"
        assert record.changeset_id == "changeset-999"

    def test_record_change_returns_unique_ids(self, change_repo):
        """Test that multiple calls return unique change IDs."""
        id1 = change_repo.record_change(
            entity_id="entity-1",
            entity_type="extraction_result",
            operation="create",
            new_state={},
        )
        id2 = change_repo.record_change(
            entity_id="entity-2",
            entity_type="extraction_result",
            operation="create",
            new_state={},
        )

        assert id1 != id2
