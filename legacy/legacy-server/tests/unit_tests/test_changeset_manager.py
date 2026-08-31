"""
Unit tests for ChangesetManager - Testing changeset creation, management, and S3 integration.

Tests changeset lifecycle, state management, version tracking, and error handling.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import uuid
from unittest.mock import Mock, patch

import pytest
from services.changeset_manager import ChangesetManager
from services.collaboration_models import ChangesetState
from services.s3_sync_manager import S3SyncManager
from services.working_tree_manager import WorkingTreeManager


class TestChangesetManager:
    """Test cases for ChangesetManager functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        db.execute.return_value.fetchall.return_value = []
        db.execute.return_value.rowcount = 1
        db.rollback = Mock()
        db.commit = Mock()
        return db

    @pytest.fixture
    def mock_working_tree_manager(self):
        """Mock WorkingTreeManager."""
        return Mock(spec=WorkingTreeManager)

    @pytest.fixture
    def mock_s3_sync_manager(self):
        """Mock S3SyncManager."""
        s3_sync = Mock(spec=S3SyncManager)
        s3_sync.s3_config = {"bucket": "test-bucket"}
        s3_sync.write_metadata_to_s3 = Mock(return_value=True)
        return s3_sync

    @pytest.fixture
    def mock_version_manager(self):
        """Mock VersionManager."""
        from services.version_manager import VersionManager

        return Mock(spec=VersionManager)

    @pytest.fixture
    def changeset_manager(
        self,
        mock_db_session,
        mock_working_tree_manager,
        mock_s3_sync_manager,
        mock_version_manager,
    ):
        """Create ChangesetManager instance for testing."""
        return ChangesetManager(
            db=mock_db_session,
            s3_sync_manager=mock_s3_sync_manager,
            working_tree_manager=mock_working_tree_manager,
            version_manager=mock_version_manager,
        )

    def test_initialization(
        self,
        changeset_manager,
        mock_db_session,
        mock_working_tree_manager,
        mock_s3_sync_manager,
        mock_version_manager,
    ):
        """Test ChangesetManager initialization."""
        assert changeset_manager.db == mock_db_session
        assert changeset_manager.working_tree == mock_working_tree_manager
        assert changeset_manager.s3_sync == mock_s3_sync_manager
        assert changeset_manager.version_manager == mock_version_manager

    def test_create_changeset_success(
        self, changeset_manager, mock_working_tree_manager
    ):
        """Test successful changeset creation."""
        # Mock working tree changes
        mock_working_tree_manager.get_staged_changes.return_value = [
            {"version_id": "v1", "change_type": "create", "entity_type": "node"}
        ]
        mock_working_tree_manager.capture_version_snapshot.return_value = "snapshot123"

        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = uuid.UUID("12345678-1234-5678-9abc-123456789abc")

            changeset = changeset_manager.create_changeset(
                title="Test Changeset",
                description="Test description",
                author_id="user123",
            )

        assert changeset.id == "12345678-1234-5678-9abc-123456789abc"
        assert changeset.title == "Test Changeset"
        assert changeset.description == "Test description"
        assert changeset.author_id == "user123"
        assert changeset.state == ChangesetState.DRAFT
        assert changeset.branch_name is not None

    def test_create_changeset_no_changes(
        self, changeset_manager, mock_working_tree_manager
    ):
        """Test changeset creation with no changes raises ValueError."""
        mock_working_tree_manager.get_staged_changes.return_value = []

        with pytest.raises(ValueError, match="No staged changes found"):
            changeset_manager.create_changeset(
                title="Empty Changeset", description="No changes", author_id="user123"
            )

    def test_create_changeset_invalid_input(self, changeset_manager):
        """Test changeset creation with invalid input."""
        with pytest.raises(ValueError, match="Title and description are required"):
            changeset_manager.create_changeset(
                title="", description="Test", author_id="user123"
            )

        with pytest.raises(ValueError, match="Title and description are required"):
            changeset_manager.create_changeset(
                title="Test", description="", author_id="user123"
            )

        with pytest.raises(ValueError, match="Author ID is required"):
            changeset_manager.create_changeset(
                title="Test", description="Test", author_id=""
            )

    def test_get_changeset_success(self, changeset_manager, mock_db_session):
        """Test successful changeset retrieval."""
        # Mock database response as tuple matching row_to_changeset() expectations
        mock_row = (
            "changeset123",  # id
            "Test Changeset",  # title
            "Test description",  # description
            "DRAFT",  # state
            "changeset-branch-123",  # branch_name
            None,  # parent_changeset_id
            "user123",  # author_id
            "2023-01-01T00:00:00+00:00",  # created_at
            None,  # merged_at
            None,  # metadata
        )

        mock_db_session.execute.return_value.fetchone.return_value = mock_row

        changeset = changeset_manager.get_changeset("changeset123")

        assert changeset is not None
        assert changeset.id == "changeset123"
        assert changeset.title == "Test Changeset"
        assert changeset.state == ChangesetState.DRAFT

    def test_get_changeset_not_found(self, changeset_manager, mock_db_session):
        """Test changeset retrieval when not found."""
        mock_db_session.execute.return_value.fetchone.return_value = None

        changeset = changeset_manager.get_changeset("nonexistent")

        assert changeset is None

    def test_list_changesets_with_filters(self, changeset_manager, mock_db_session):
        """Test listing changesets with filters."""
        # Mock database response as tuple matching row_to_changeset() expectations
        mock_row = (
            "changeset123",  # id
            "Test Changeset",  # title
            "Test description",  # description
            "DRAFT",  # state
            "changeset-branch-123",  # branch_name
            None,  # parent_changeset_id
            "user123",  # author_id
            "2023-01-01T00:00:00+00:00",  # created_at
            None,  # merged_at
            None,  # metadata
        )

        mock_db_session.execute.return_value.fetchall.return_value = [mock_row]

        changesets = changeset_manager.list_changesets(
            author_id="user123", state=ChangesetState.DRAFT, limit=50
        )

        assert len(changesets) == 1
        assert changesets[0].id == "changeset123"
        assert changesets[0].author_id == "user123"

    def test_update_changeset_success(self, changeset_manager, mock_db_session):
        """Test successful changeset update."""
        mock_db_session.execute.return_value.rowcount = 1

        success = changeset_manager.update_changeset(
            changeset_id="changeset123",
            title="Updated Title",
            description="Updated description",
        )

        assert success is True

    def test_update_changeset_not_found(self, changeset_manager, mock_db_session):
        """Test changeset update when changeset not found."""
        mock_db_session.execute.return_value.rowcount = 0

        success = changeset_manager.update_changeset(
            changeset_id="nonexistent", title="Updated Title"
        )

        assert success is False

    def test_delete_changeset_success(self, changeset_manager, mock_db_session):
        """Test successful changeset deletion."""
        # Mock changeset exists and is in valid state
        mock_changeset = Mock()
        mock_changeset.state = ChangesetState.DRAFT

        with patch.object(
            changeset_manager, "get_changeset", return_value=mock_changeset
        ):
            mock_db_session.execute.return_value.rowcount = 1

            success = changeset_manager.delete_changeset("changeset123")

            assert success is True

    def test_delete_changeset_invalid_state(self, changeset_manager):
        """Test changeset deletion in invalid state."""
        # Mock changeset in merged state
        mock_changeset = Mock()
        mock_changeset.state = ChangesetState.MERGED

        with patch.object(
            changeset_manager, "get_changeset", return_value=mock_changeset
        ), pytest.raises(
            ValueError, match="Cannot delete changeset in merged state"
        ):
            changeset_manager.delete_changeset("changeset123")

    def test_delete_changeset_not_found(self, changeset_manager):
        """Test changeset deletion when not found."""
        with patch.object(changeset_manager, "get_changeset", return_value=None):
            success = changeset_manager.delete_changeset("nonexistent")
            assert success is False

    def test_update_changeset_state_success(self, changeset_manager, mock_db_session):
        """Test successful changeset state update."""
        mock_db_session.execute.return_value.rowcount = 1

        success = changeset_manager.update_changeset_state(
            "changeset123", ChangesetState.PROPOSED
        )

        assert success is True

    def test_push_changeset_to_s3_success(
        self, changeset_manager, mock_s3_sync_manager
    ):
        """Test successful S3 push."""
        # Mock changeset exists
        mock_changeset = Mock()
        mock_changeset.id = "changeset123"
        mock_changeset.to_dict.return_value = {"id": "changeset123", "title": "test"}

        with patch.object(
            changeset_manager, "get_changeset", return_value=mock_changeset
        ):
            success = changeset_manager.push_changeset_to_s3("changeset123")

            assert success is True
            mock_s3_sync_manager.write_metadata_to_s3.assert_called_once()

    def test_push_changeset_to_s3_not_found(self, changeset_manager):
        """Test S3 push when changeset not found."""
        with patch.object(changeset_manager, "get_changeset", return_value=None):
            success = changeset_manager.push_changeset_to_s3("nonexistent")
            assert success is False

    def test_push_changeset_to_s3_failure(
        self, changeset_manager, mock_s3_sync_manager
    ):
        """Test S3 push failure handling."""
        # Mock changeset exists
        mock_changeset = Mock()
        mock_changeset.id = "changeset123"
        mock_changeset.to_dict.return_value = {"id": "changeset123", "title": "test"}

        # Mock S3 failure
        mock_s3_sync_manager.write_metadata_to_s3.side_effect = Exception("S3 error")

        with patch.object(
            changeset_manager, "get_changeset", return_value=mock_changeset
        ):
            success = changeset_manager.push_changeset_to_s3("changeset123")

            # Should return False on S3 failure
            assert success is False

    def test_get_changeset_versions(self, changeset_manager, mock_db_session):
        """Test getting changeset versions."""
        # Mock database response for version IDs query
        mock_db_session.execute.return_value.fetchall.return_value = [
            ("v1",),
            ("v2",),
            ("v3",),
        ]

        versions = changeset_manager.get_changeset_versions("changeset123")

        assert versions == ["v1", "v2", "v3"]

    def test_generate_branch_name(self, changeset_manager):
        """Test branch name generation."""
        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = uuid.UUID("12345678-1234-5678-9abc-123456789abc")

            branch_name = changeset_manager._generate_branch_name()

            assert branch_name == "changeset-12345678"

    def test_database_transaction_rollback_on_error(
        self, changeset_manager, mock_db_session, mock_working_tree_manager
    ):
        """Test database rollback on error."""
        mock_working_tree_manager.get_staged_changes.return_value = [
            {"version_id": "v1", "change_type": "create", "entity_type": "node"}
        ]
        mock_working_tree_manager.capture_version_snapshot.side_effect = Exception(
            "Snapshot error"
        )

        with pytest.raises(RuntimeError, match="Failed to create changeset"):
            changeset_manager.create_changeset(
                title="Test Changeset",
                description="Test description",
                author_id="user123",
            )

        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()
