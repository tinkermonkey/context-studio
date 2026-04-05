"""Integration tests for SQLiteChangeRepository."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from adapters.persistence.sqlite.models import Base, ChangeEvent, Changeset, Proposal, ConflictResolution
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from domain.versioning.value_objects import ChangeOperation
from domain.versioning.exceptions import VersionNotFoundError


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

    def _create_proposal(self, session_factory):
        """Helper method to create a Changeset and Proposal for testing."""
        session = session_factory()
        try:
            changeset_id = str(uuid.uuid4())
            proposal_id = str(uuid.uuid4())

            changeset = Changeset(
                id=changeset_id,
                name="Test Changeset",
                description="Test changeset for conflict resolution",
                state="working"
            )
            session.add(changeset)
            session.flush()

            proposal = Proposal(
                id=proposal_id,
                changeset_id=changeset_id,
                state="open"
            )
            session.add(proposal)
            session.commit()

            return proposal_id
        finally:
            session.close()

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
            changeset_id="changeset-999",
        )

        session = session_factory()
        try:
            record = session.query(ChangeEvent).filter_by(id=change_id).first()
            assert record.previous_state == {"status": "running"}
            assert record.user_id == "user-789"
            assert record.changeset_id == "changeset-999"
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

    def test_save_conflict_resolutions_persists_resolutions(self, change_repo, session_factory):
        """Test that save_conflict_resolutions persists conflict resolution data."""
        proposal_id = self._create_proposal(session_factory)
        resolutions = {
            "entity-1": {
                "field_a": "resolved_value_a",
                "field_b": "resolved_value_b",
            },
            "entity-2": {
                "field_c": "resolved_value_c",
            },
        }

        change_repo.save_conflict_resolutions(proposal_id, resolutions)

        # Verify the resolutions were persisted
        session = session_factory()
        try:
            records = session.query(ConflictResolution).filter_by(
                proposal_id=proposal_id
            ).all()

            assert len(records) == 3

            # Verify all fields are correct
            entity_1_records = [r for r in records if r.entity_id == "entity-1"]
            assert len(entity_1_records) == 2

            entity_2_records = [r for r in records if r.entity_id == "entity-2"]
            assert len(entity_2_records) == 1

            assert entity_2_records[0].field_name == "field_c"
            assert entity_2_records[0].resolved_value == "resolved_value_c"
        finally:
            session.close()

    def test_get_conflict_resolutions_retrieves_resolutions(self, change_repo, session_factory):
        """Test that get_conflict_resolutions retrieves persisted resolutions."""
        proposal_id = self._create_proposal(session_factory)
        resolutions = {
            "entity-1": {
                "field_a": "value_a",
                "field_b": "value_b",
            },
            "entity-2": {
                "field_c": "value_c",
            },
        }

        change_repo.save_conflict_resolutions(proposal_id, resolutions)

        # Retrieve the resolutions
        retrieved = change_repo.get_conflict_resolutions(proposal_id)

        assert retrieved == resolutions
        assert retrieved["entity-1"]["field_a"] == "value_a"
        assert retrieved["entity-1"]["field_b"] == "value_b"
        assert retrieved["entity-2"]["field_c"] == "value_c"

    def test_save_conflict_resolutions_overwrites_existing(self, change_repo, session_factory):
        """Test that save_conflict_resolutions deletes and reinserts (overwrites) existing resolutions."""
        proposal_id = self._create_proposal(session_factory)

        # Save initial resolutions
        initial_resolutions = {
            "entity-1": {"field_a": "initial_value_a"},
            "entity-2": {"field_b": "initial_value_b"},
        }
        change_repo.save_conflict_resolutions(proposal_id, initial_resolutions)

        # Overwrite with new resolutions
        new_resolutions = {
            "entity-1": {"field_a": "new_value_a"},
            "entity-3": {"field_c": "new_value_c"},
        }
        change_repo.save_conflict_resolutions(proposal_id, new_resolutions)

        # Retrieve and verify only new resolutions exist
        retrieved = change_repo.get_conflict_resolutions(proposal_id)

        assert retrieved == new_resolutions
        assert "entity-2" not in retrieved  # Old entity should be gone
        assert retrieved["entity-1"]["field_a"] == "new_value_a"
        assert retrieved["entity-3"]["field_c"] == "new_value_c"

    def test_get_conflict_resolutions_returns_empty_dict_for_nonexistent_proposal(
        self, change_repo
    ):
        """Test that get_conflict_resolutions returns empty dict for nonexistent proposal."""
        retrieved = change_repo.get_conflict_resolutions("nonexistent-proposal")
        assert retrieved == {}
