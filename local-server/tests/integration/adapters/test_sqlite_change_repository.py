"""Integration tests for SQLiteChangeRepository."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch
import uuid

from adapters.persistence.sqlite.models import Base, ChangeEvent, Changeset, Proposal, ConflictResolution, EntityVersion
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from domain.versioning.value_objects import ChangeOperation, ChangeState, ProposalState, EntityVersionState
from domain.versioning.exceptions import VersionNotFoundError
from domain.versioning.entities import Changeset as DomainChangeset, Proposal as DomainProposal, EntityVersion as DomainEntityVersion
from datetime import datetime, timezone


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

    # New error handling tests

    def test_get_changes_by_ids_happy_path(self, change_repo):
        """Test that get_changes_by_ids retrieves events by their IDs."""
        # Create multiple change events
        id1 = change_repo.record_change(
            entity_id="entity-1",
            entity_type="test_entity",
            operation=ChangeOperation.CREATE,
            new_state={"key": "value1"},
        )
        id3 = change_repo.record_change(
            entity_id="entity-3",
            entity_type="test_entity",
            operation=ChangeOperation.DELETE,
            new_state={},
        )

        # Retrieve by IDs
        retrieved = change_repo.get_changes_by_ids([id1, id3])

        assert len(retrieved) == 2
        assert any(e.id == id1 for e in retrieved)
        assert any(e.id == id3 for e in retrieved)
        assert any(e.entity_id == "entity-1" for e in retrieved)
        assert any(e.entity_id == "entity-3" for e in retrieved)

    def test_get_changes_by_ids_with_empty_list(self, change_repo):
        """Test that get_changes_by_ids returns empty list for empty input."""
        retrieved = change_repo.get_changes_by_ids([])
        assert retrieved == []

    def test_get_changes_by_ids_with_nonexistent_ids(self, change_repo):
        """Test that get_changes_by_ids returns only matching IDs."""
        change_id = change_repo.record_change(
            entity_id="entity-1",
            entity_type="test_entity",
            operation=ChangeOperation.CREATE,
            new_state={"key": "value"},
        )

        # Query with mix of existing and nonexistent IDs
        retrieved = change_repo.get_changes_by_ids([change_id, "nonexistent-id"])

        assert len(retrieved) == 1
        assert retrieved[0].id == change_id

    def test_atomic_update_on_merge_happy_path(self, change_repo, session_factory):
        """Test that atomic_update_on_merge successfully commits all changes."""
        # Create changeset and proposal
        session = session_factory()
        try:
            changeset_id = str(uuid.uuid4())
            proposal_id = str(uuid.uuid4())

            changeset = Changeset(
                id=changeset_id,
                name="Test Changeset",
                state="submitted",
            )
            session.add(changeset)
            session.flush()

            proposal = Proposal(
                id=proposal_id,
                changeset_id=changeset_id,
                state="open",
                submitted_at=datetime.now(timezone.utc),
            )
            session.add(proposal)
            session.commit()
        finally:
            session.close()

        # Create domain entities for merge
        domain_changeset = DomainChangeset(
            id=changeset_id,
            name="Test Changeset",
            _state=ChangeState.MERGED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            event_ids=[],
        )

        domain_proposal = DomainProposal(
            id=proposal_id,
            changeset_id=changeset_id,
            _state=ProposalState.MERGED,
            submitted_at=datetime.now(timezone.utc),
            reviewed_at=datetime.now(timezone.utc),
        )

        domain_version = DomainEntityVersion(
            entity_id="entity-1",
            version=1,
            state=EntityVersionState.ACTIVE,
            snapshot={"data": "snapshot"},
            created_at=datetime.now(timezone.utc),
        )

        # Execute merge
        returned_changeset, returned_proposal = change_repo.atomic_update_on_merge(
            domain_changeset, domain_proposal, [domain_version]
        )

        # Verify returned objects
        assert returned_changeset.state == ChangeState.MERGED
        assert returned_proposal.state == ProposalState.MERGED

        # Verify database state
        session = session_factory()
        try:
            db_changeset = session.query(Changeset).filter_by(id=changeset_id).first()
            assert db_changeset is not None
            assert db_changeset.state == "merged"

            db_proposal = session.query(Proposal).filter_by(id=proposal_id).first()
            assert db_proposal is not None
            assert db_proposal.state == "merged"

            db_version = session.query(EntityVersion).filter_by(
                entity_id="entity-1", version=1
            ).first()
            assert db_version is not None
            assert db_version.snapshot == {"data": "snapshot"}
        finally:
            session.close()

    def test_mark_processed_raises_domain_exception_before_db_exception(self, change_repo):
        """Test that mark_processed raises VersionNotFoundError without catching it."""
        # This test verifies the defensive re-raise is in place
        with pytest.raises(VersionNotFoundError):
            change_repo.mark_processed(["nonexistent-id"])

    def test_atomic_update_on_merge_raises_domain_exception_before_db_exception(
        self, change_repo, session_factory
    ):
        """Test that atomic_update_on_merge raises VersionNotFoundError without catching it."""
        domain_changeset = DomainChangeset(
            id="nonexistent-changeset",
            name="Test",
            _state=ChangeState.MERGED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            event_ids=[],
        )

        domain_proposal = DomainProposal(
            id="nonexistent-proposal",
            changeset_id="nonexistent-changeset",
            _state=ProposalState.MERGED,
            submitted_at=datetime.now(timezone.utc),
            reviewed_at=datetime.now(timezone.utc),
        )

        # Should raise VersionNotFoundError, not RuntimeError
        with pytest.raises(VersionNotFoundError):
            change_repo.atomic_update_on_merge(domain_changeset, domain_proposal, [])

    def test_update_changeset_raises_domain_exception_before_db_exception(
        self, change_repo
    ):
        """Test that update_changeset raises VersionNotFoundError without catching it."""
        domain_changeset = DomainChangeset(
            id="nonexistent-changeset",
            name="Test",
            _state=ChangeState.WORKING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            event_ids=[],
        )

        with pytest.raises(VersionNotFoundError):
            change_repo.update_changeset(domain_changeset)

    def test_update_proposal_raises_domain_exception_before_db_exception(
        self, change_repo
    ):
        """Test that update_proposal raises VersionNotFoundError without catching it."""
        domain_proposal = DomainProposal(
            id="nonexistent-proposal",
            changeset_id="changeset-123",
            _state=ProposalState.MERGED,
            submitted_at=datetime.now(timezone.utc),
            reviewed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(VersionNotFoundError):
            change_repo.update_proposal(domain_proposal)

    def test_update_changeset_and_proposal_on_submit_raises_domain_exception_before_db_exception(
        self, change_repo
    ):
        """Test that update_changeset_and_proposal_on_submit raises VersionNotFoundError."""
        domain_changeset = DomainChangeset(
            id="nonexistent-changeset",
            name="Test",
            _state=ChangeState.PROPOSED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            event_ids=[],
        )

        domain_proposal = DomainProposal(
            id=str(uuid.uuid4()),
            changeset_id="nonexistent-changeset",
            _state=ProposalState.OPEN,
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(VersionNotFoundError):
            change_repo.update_changeset_and_proposal_on_submit(
                domain_changeset, domain_proposal
            )

    def test_atomic_update_changeset_and_proposal_raises_domain_exception_before_db_exception(
        self, change_repo
    ):
        """Test that atomic_update_changeset_and_proposal raises VersionNotFoundError."""
        domain_changeset = DomainChangeset(
            id="nonexistent-changeset",
            name="Test",
            _state=ChangeState.APPROVED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            event_ids=[],
        )

        domain_proposal = DomainProposal(
            id=str(uuid.uuid4()),
            changeset_id="nonexistent-changeset",
            _state=ProposalState.APPROVED,
            submitted_at=datetime.now(timezone.utc),
            reviewed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(VersionNotFoundError):
            change_repo.atomic_update_changeset_and_proposal(
                domain_changeset, domain_proposal
            )
