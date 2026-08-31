"""
Unit tests for VersionManager - Testing entity version management functionality.

Tests version creation, retrieval, rollback, and state management operations.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from datetime import datetime, timezone

import pytest
from services.version_manager import ChangeState, VersionManager


class TestVersionManager:
    """Test cases for VersionManager functionality."""

    @pytest.fixture
    def version_manager(self, db_session):
        """Create a VersionManager instance with test database."""
        manager = VersionManager(db_session)
        return manager

    @pytest.fixture
    def sample_content(self):
        """Sample content for version testing."""
        return {
            "id": "test-entity-123",
            "title": "Test Entity",
            "description": "A test entity for version management",
            "properties": {"category": "test", "priority": "high"},
        }

    def test_version_manager_initialization(self, version_manager):
        """Test VersionManager initialization."""
        assert version_manager.db is not None
        assert hasattr(version_manager, "db")

    def test_create_version_success(self, version_manager, sample_content):
        """Test successful version creation."""
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
            state=ChangeState.WORKING,
        )

        assert version.id is not None
        assert version.entity_type == "structure_node"
        assert version.entity_id == "test-123"
        assert version.version_number == 1
        assert version.content == sample_content
        assert version.state == ChangeState.WORKING
        assert version.author_id == "test-user"
        assert isinstance(version.created_at, datetime)

    def test_create_version_invalid_entity_type(self, version_manager, sample_content):
        """Test version creation with invalid entity type."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            version_manager.create_version(
                entity_type="invalid_type",
                entity_id="test-123",
                content=sample_content,
                author_id="test-user",
            )

    def test_create_version_missing_required_fields(
        self, version_manager, sample_content
    ):
        """Test version creation with missing required fields."""
        with pytest.raises(ValueError, match="entity_id and author_id are required"):
            version_manager.create_version(
                entity_type="structure_node",
                entity_id="",
                content=sample_content,
                author_id="test-user",
            )

        with pytest.raises(ValueError, match="entity_id and author_id are required"):
            version_manager.create_version(
                entity_type="structure_node",
                entity_id="test-123",
                content=sample_content,
                author_id="",
            )

    def test_create_version_empty_content(self, version_manager):
        """Test version creation with empty content."""
        with pytest.raises(ValueError, match="content cannot be empty"):
            version_manager.create_version(
                entity_type="structure_node",
                entity_id="test-123",
                content={},
                author_id="test-user",
            )

    def test_create_multiple_versions(self, version_manager, sample_content):
        """Test creating multiple versions for the same entity."""
        # Create first version
        version1 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        # Create second version with modified content
        modified_content = sample_content.copy()
        modified_content["title"] = "Modified Test Entity"

        version2 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=modified_content,
            author_id="test-user",
        )

        assert version1.version_number == 1
        assert version2.version_number == 2
        assert version1.content["title"] == "Test Entity"
        assert version2.content["title"] == "Modified Test Entity"

    def test_get_entity_versions(self, version_manager, sample_content):
        """Test retrieving all versions of an entity."""
        # Create multiple versions
        for i in range(3):
            content = sample_content.copy()
            content["version"] = i + 1
            version_manager.create_version(
                entity_type="structure_node",
                entity_id="test-123",
                content=content,
                author_id="test-user",
            )

        # Retrieve all versions
        versions = version_manager.get_entity_versions("structure_node", "test-123")

        assert len(versions) == 3
        assert versions[0].version_number == 1
        assert versions[1].version_number == 2
        assert versions[2].version_number == 3

        # Verify content is correct
        assert versions[0].content["version"] == 1
        assert versions[1].content["version"] == 2
        assert versions[2].content["version"] == 3

    def test_get_version_by_number(self, version_manager, sample_content):
        """Test retrieving a specific version by number."""
        # Create a version
        created_version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        # Retrieve by version number
        retrieved_version = version_manager.get_version_by_number(
            "structure_node", "test-123", 1
        )

        assert retrieved_version is not None
        assert retrieved_version.id == created_version.id
        assert retrieved_version.version_number == 1
        assert retrieved_version.content == sample_content

    def test_get_version_by_number_not_found(self, version_manager):
        """Test retrieving a non-existent version."""
        version = version_manager.get_version_by_number(
            "structure_node", "non-existent", 1
        )
        assert version is None

    def test_get_current_version(self, version_manager, sample_content):
        """Test retrieving the current (latest) version."""
        # Create multiple versions
        for i in range(3):
            content = sample_content.copy()
            content["version"] = i + 1
            version_manager.create_version(
                entity_type="structure_node",
                entity_id="test-123",
                content=content,
                author_id="test-user",
            )

        # Get current version
        current_version = version_manager.get_current_version(
            "structure_node", "test-123"
        )

        assert current_version is not None
        assert current_version.version_number == 3
        assert current_version.content["version"] == 3

    def test_get_current_version_no_versions(self, version_manager):
        """Test getting current version when no versions exist."""
        current_version = version_manager.get_current_version(
            "structure_node", "non-existent"
        )
        assert current_version is None

    def test_rollback_to_version(self, version_manager, sample_content):
        """Test rollback to a previous version."""
        # Create multiple versions
        versions = []
        for i in range(3):
            content = sample_content.copy()
            content["version"] = i + 1
            version = version_manager.create_version(
                entity_type="structure_node",
                entity_id="test-123",
                content=content,
                author_id="test-user",
            )
            versions.append(version)

        # Rollback to version 2
        rollback_version = version_manager.rollback_to_version(
            "structure_node", "test-123", 2, "test-user"
        )

        assert rollback_version.version_number == 4  # New version created
        assert rollback_version.content["version"] == 2  # Content from version 2
        assert rollback_version.parent_version_id == versions[1].id
        assert rollback_version.metadata["operation"] == "rollback"
        assert rollback_version.metadata["target_version"] == 2

    def test_rollback_to_nonexistent_version(self, version_manager, sample_content):
        """Test rollback to a non-existent version."""
        # Create one version
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        # Try to rollback to non-existent version
        with pytest.raises(ValueError, match="Target version 5 does not exist"):
            version_manager.rollback_to_version(
                "structure_node", "test-123", 5, "test-user"
            )

    def test_update_version_state(self, version_manager, sample_content):
        """Test updating version state."""
        # Create a version
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
            state=ChangeState.WORKING,
        )

        # Update state to STAGED
        success = version_manager.update_version_state(
            version.id, ChangeState.STAGED, "test-user"
        )

        assert success is True

        # Verify state was updated
        updated_version = version_manager.get_version_by_number(
            "structure_node", "test-123", 1
        )
        assert updated_version.state == ChangeState.STAGED

    def test_update_version_state_not_found(self, version_manager):
        """Test updating state of non-existent version."""
        success = version_manager.update_version_state(
            "non-existent-id", ChangeState.STAGED, "test-user"
        )
        assert success is False

    def test_get_versions_by_state(self, version_manager, sample_content):
        """Test retrieving versions by state."""
        # Create versions with different states
        version1 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
            state=ChangeState.WORKING,
        )

        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-456",
            content=sample_content,
            author_id="test-user",
            state=ChangeState.STAGED,
        )

        # Update first version to STAGED
        version_manager.update_version_state(
            version1.id, ChangeState.STAGED, "test-user"
        )

        # Get all STAGED versions
        staged_versions = version_manager.get_versions_by_state(ChangeState.STAGED)

        assert len(staged_versions) == 2
        assert all(v.state == ChangeState.STAGED for v in staged_versions)

    def test_version_with_parent(self, version_manager, sample_content):
        """Test creating version with parent reference."""
        # Create parent version
        parent_version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        # Create child version with parent reference
        child_content = sample_content.copy()
        child_content["title"] = "Child Version"

        child_version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=child_content,
            author_id="test-user",
            parent_version_id=parent_version.id,
        )

        assert child_version.parent_version_id == parent_version.id

    def test_version_with_invalid_parent(self, version_manager, sample_content):
        """Test creating version with non-existent parent."""
        with pytest.raises(ValueError, match="Parent version .* does not exist"):
            version_manager.create_version(
                entity_type="structure_node",
                entity_id="test-123",
                content=sample_content,
                author_id="test-user",
                parent_version_id="non-existent-id",
            )

    def test_version_with_metadata(self, version_manager, sample_content):
        """Test creating version with metadata."""
        metadata = {
            "operation": "test",
            "source": "unit_test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
            metadata=metadata,
        )

        assert version.metadata == metadata
