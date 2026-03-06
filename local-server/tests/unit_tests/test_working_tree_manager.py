"""
Unit tests for WorkingTreeManager - Testing working tree state management functionality.  # noqa: E501

Tests staging operations, working tree status, and commit operations.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: E501
)

import pytest  # noqa: E402

from services.version_manager import VersionManager, ChangeState  # noqa: E402
from services.working_tree_manager import (  # noqa: E402
    WorkingTreeManager,
)


class TestWorkingTreeManager:
    """Test cases for WorkingTreeManager functionality."""

    @pytest.fixture
    def managers(self, db_session):
        """Create VersionManager and WorkingTreeManager instances."""
        version_manager = VersionManager(db_session)
        working_tree_manager = WorkingTreeManager(db_session, version_manager)
        return version_manager, working_tree_manager

    @pytest.fixture
    def sample_content(self):
        """Sample content for testing."""
        return {
            "id": "test-entity-123",
            "title": "Test Entity",
            "description": "A test entity for working tree management",
        }

    def test_initialize_entity_in_working_tree(self, managers, sample_content):
        """Test initializing an entity in the working tree."""
        version_manager, working_tree_manager = managers

        # Create a version first
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        # Initialize in working tree
        entry = working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version.id
        )

        assert entry.entity_type == "structure_node"
        assert entry.entity_id == "test-123"
        assert entry.current_version_id == version.id
        assert entry.canonical_version_id == version.id
        assert entry.staged is False
        assert not entry.has_changes()  # Initially no changes

    def test_initialize_entity_invalid_entity_type(self, managers):
        """Test initializing entity with invalid entity type."""
        version_manager, working_tree_manager = managers

        with pytest.raises(ValueError, match="Invalid entity_type"):
            working_tree_manager.initialize_entity_in_working_tree(
                "invalid_type", "test-123", "version-id"
            )

    def test_initialize_entity_missing_parameters(self, managers):
        """Test initializing entity with missing parameters."""
        version_manager, working_tree_manager = managers

        with pytest.raises(
            ValueError, match="entity_id and initial_version_id are required"
        ):
            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", "", "version-id"
            )

        with pytest.raises(
            ValueError, match="entity_id and initial_version_id are required"
        ):
            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", "test-123", ""
            )

    def test_initialize_entity_duplicate(self, managers, sample_content):
        """Test initializing an entity that already exists in working tree."""
        version_manager, working_tree_manager = managers

        # Create version and initialize in working tree
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        entry1 = working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version.id
        )

        # Try to initialize again
        entry2 = working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version.id
        )

        # Should return existing entry
        assert entry1.entity_id == entry2.entity_id

    def test_initialize_entity_nonexistent_version(self, managers):
        """Test initializing entity with non-existent version."""
        version_manager, working_tree_manager = managers

        with pytest.raises(ValueError, match="Version .* does not exist"):
            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", "test-123", "non-existent-version-id"
            )

    def test_update_current_version(self, managers, sample_content):
        """Test updating the current working version."""
        version_manager, working_tree_manager = managers

        # Create initial version and working tree entry
        version1 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version1.id
        )

        # Create second version
        modified_content = sample_content.copy()
        modified_content["title"] = "Modified Title"

        version2 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=modified_content,
            author_id="test-user",
        )

        # Update current version
        entry = working_tree_manager.update_current_version(
            "structure_node", "test-123", version2.id
        )

        assert entry.current_version_id == version2.id
        assert entry.canonical_version_id == version1.id  # Unchanged
        assert entry.staged is False  # Reset on version update
        assert entry.has_changes()  # Now has changes

    def test_update_current_version_not_in_working_tree(self, managers):
        """Test updating current version for entity not in working tree."""
        version_manager, working_tree_manager = managers

        with pytest.raises(ValueError, match="not found in working tree"):
            working_tree_manager.update_current_version(
                "structure_node", "non-existent", "version-id"
            )

    def test_update_current_version_nonexistent_version(self, managers, sample_content):  # noqa: E501
        """Test updating current version with non-existent version."""
        version_manager, working_tree_manager = managers

        # Create initial setup
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version.id
        )

        # Try to update with non-existent version
        with pytest.raises(ValueError, match="Version .* does not exist"):
            working_tree_manager.update_current_version(
                "structure_node", "test-123", "non-existent-version-id"
            )

    def test_stage_entity(self, managers, sample_content):
        """Test staging an entity for commit."""
        version_manager, working_tree_manager = managers

        # Create initial version and working tree entry
        version1 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version1.id
        )

        # Create modified version and update working tree
        modified_content = sample_content.copy()
        modified_content["title"] = "Modified Title"

        version2 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=modified_content,
            author_id="test-user",
        )

        working_tree_manager.update_current_version(
            "structure_node", "test-123", version2.id
        )

        # Stage the entity
        success = working_tree_manager.stage_entity("structure_node", "test-123")  # noqa: E501
        assert success is True

        # Verify staged status
        entry = working_tree_manager.get_working_tree_entry(
            "structure_node", "test-123"
        )
        assert entry.staged is True

    def test_stage_entity_no_changes(self, managers, sample_content):
        """Test staging an entity with no changes."""
        version_manager, working_tree_manager = managers

        # Create version and working tree entry
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version.id
        )

        # Try to stage without changes
        success = working_tree_manager.stage_entity("structure_node", "test-123")  # noqa: E501
        assert success is False  # No changes to stage

    def test_stage_entity_not_in_working_tree(self, managers):
        """Test staging entity not in working tree."""
        version_manager, working_tree_manager = managers

        with pytest.raises(ValueError, match="not found in working tree"):
            working_tree_manager.stage_entity("structure_node", "non-existent")

    def test_unstage_entity(self, managers, sample_content):
        """Test unstaging an entity."""
        version_manager, working_tree_manager = managers

        # Setup staged entity
        version1 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version1.id
        )

        # Create changes and stage
        modified_content = sample_content.copy()
        modified_content["title"] = "Modified Title"

        version2 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=modified_content,
            author_id="test-user",
        )

        working_tree_manager.update_current_version(
            "structure_node", "test-123", version2.id
        )
        working_tree_manager.stage_entity("structure_node", "test-123")

        # Unstage
        success = working_tree_manager.unstage_entity("structure_node", "test-123")  # noqa: E501
        assert success is True

        # Verify unstaged status
        entry = working_tree_manager.get_working_tree_entry(
            "structure_node", "test-123"
        )
        assert entry.staged is False
        assert entry.has_changes()  # Still has changes, just not staged

    def test_unstage_entity_not_staged(self, managers, sample_content):
        """Test unstaging entity that's not staged."""
        version_manager, working_tree_manager = managers

        # Create version and working tree entry (not staged)
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version.id
        )

        # Try to unstage
        success = working_tree_manager.unstage_entity("structure_node", "test-123")  # noqa: E501
        assert success is True  # Should succeed even if not staged

    def test_get_working_tree_entry(self, managers, sample_content):
        """Test retrieving a working tree entry."""
        version_manager, working_tree_manager = managers

        # Create version and working tree entry
        version = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content,
            author_id="test-user",
        )

        created_entry = working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version.id
        )

        # Retrieve entry
        retrieved_entry = working_tree_manager.get_working_tree_entry(
            "structure_node", "test-123"
        )

        assert retrieved_entry is not None
        assert retrieved_entry.entity_type == created_entry.entity_type
        assert retrieved_entry.entity_id == created_entry.entity_id
        assert retrieved_entry.current_version_id == created_entry.current_version_id  # noqa: E501

    def test_get_working_tree_entry_not_found(self, managers):
        """Test retrieving non-existent working tree entry."""
        version_manager, working_tree_manager = managers

        entry = working_tree_manager.get_working_tree_entry(
            "structure_node", "non-existent"
        )
        assert entry is None

    def test_get_working_changes(self, managers, sample_content):
        """Test retrieving all entities with working changes."""
        version_manager, working_tree_manager = managers

        # Create multiple entities with changes
        for i in range(3):
            entity_id = f"test-{i}"
            content = sample_content.copy()
            content["id"] = entity_id

            # Create initial version
            version1 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=content,
                author_id="test-user",
            )

            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", entity_id, version1.id
            )

            # Create modified version for first two entities
            if i < 2:
                modified_content = content.copy()
                modified_content["title"] = f"Modified {i}"

                version2 = version_manager.create_version(
                    entity_type="structure_node",
                    entity_id=entity_id,
                    content=modified_content,
                    author_id="test-user",
                )

                working_tree_manager.update_current_version(
                    "structure_node", entity_id, version2.id
                )

        # Get working changes
        changes = working_tree_manager.get_working_changes()

        # Should only return entities with changes (first two)
        assert len(changes) == 2
        assert all(entry.has_changes() for entry in changes)

    def test_get_staged_entities(self, managers, sample_content):
        """Test retrieving all staged entities."""
        version_manager, working_tree_manager = managers

        # Create multiple entities, stage some of them
        for i in range(3):
            entity_id = f"test-{i}"
            content = sample_content.copy()
            content["id"] = entity_id

            # Create versions and working tree entries
            version1 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=content,
                author_id="test-user",
            )

            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", entity_id, version1.id
            )

            # Create changes and stage first two entities
            if i < 2:
                modified_content = content.copy()
                modified_content["title"] = f"Modified {i}"

                version2 = version_manager.create_version(
                    entity_type="structure_node",
                    entity_id=entity_id,
                    content=modified_content,
                    author_id="test-user",
                )

                working_tree_manager.update_current_version(
                    "structure_node", entity_id, version2.id
                )

                working_tree_manager.stage_entity("structure_node", entity_id)

        # Get staged entities
        staged = working_tree_manager.get_staged_entities()

        assert len(staged) == 2
        assert all(entry.staged for entry in staged)

    def test_get_working_tree_status(self, managers, sample_content):
        """Test retrieving working tree status."""
        version_manager, working_tree_manager = managers

        # Create multiple entities in different states
        for i in range(4):
            entity_id = f"test-{i}"
            content = sample_content.copy()
            content["id"] = entity_id

            # Create initial version and working tree entry
            version1 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=content,
                author_id="test-user",
            )

            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", entity_id, version1.id
            )

            # Create different states:
            # 0: no changes
            # 1: unstaged changes
            # 2: staged changes
            # 3: staged changes
            if i >= 1:
                modified_content = content.copy()
                modified_content["title"] = f"Modified {i}"

                version2 = version_manager.create_version(
                    entity_type="structure_node",
                    entity_id=entity_id,
                    content=modified_content,
                    author_id="test-user",
                )

                working_tree_manager.update_current_version(
                    "structure_node", entity_id, version2.id
                )

                # Stage entities 2 and 3
                if i >= 2:
                    working_tree_manager.stage_entity("structure_node", entity_id)  # noqa: E501

        # Get working tree status
        status = working_tree_manager.get_working_tree_status()

        assert status.total_entities == 4
        assert status.modified_entities == 3  # Entities 1, 2, 3 have changes
        assert status.staged_entities == 2  # Entities 2, 3 are staged
        assert status.unstaged_entities == 1  # Entity 1 has unstaged changes
        assert len(status.entries) == 4

    def test_commit_staged_changes(self, managers, sample_content):
        """Test committing staged changes."""
        version_manager, working_tree_manager = managers

        # Create staged entities
        staged_entities = []
        for i in range(2):
            entity_id = f"test-{i}"
            content = sample_content.copy()
            content["id"] = entity_id

            # Create initial version
            version1 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=content,
                author_id="test-user",
            )

            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", entity_id, version1.id
            )

            # Create changes and stage
            modified_content = content.copy()
            modified_content["title"] = f"Modified {i}"

            version2 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=modified_content,
                author_id="test-user",
            )

            working_tree_manager.update_current_version(
                "structure_node", entity_id, version2.id
            )
            working_tree_manager.stage_entity("structure_node", entity_id)
            staged_entities.append((entity_id, version2.id))

        # Commit staged changes
        committed_versions = working_tree_manager.commit_staged_changes("commit-user")  # noqa: E501

        assert len(committed_versions) == 2

        # Verify entities are no longer staged and canonical versions updated
        for entity_id, expected_version_id in staged_entities:
            entry = working_tree_manager.get_working_tree_entry(
                "structure_node", entity_id
            )
            assert entry.staged is False
            assert entry.canonical_version_id == expected_version_id
            assert not entry.has_changes()  # Should be clean after commit

        # Verify versions are marked as MERGED
        for version in committed_versions:
            assert version.state == ChangeState.MERGED

    def test_commit_no_staged_changes(self, managers):
        """Test committing when no changes are staged."""
        version_manager, working_tree_manager = managers

        committed_versions = working_tree_manager.commit_staged_changes("commit-user")  # noqa: E501
        assert len(committed_versions) == 0
