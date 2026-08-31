"""
Unit tests for DiffGenerator - Testing diff generation functionality.

Tests diff generation between versions, working diffs, and diff formatting.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from services.diff_generator import (
    DiffGenerator,
    DiffSummary,
    EntityDiff,
)
from services.version_manager import VersionManager
from services.working_tree_manager import WorkingTreeManager


class TestDiffGenerator:
    """Test cases for DiffGenerator functionality."""

    @pytest.fixture
    def managers(self, db_session):
        """Create all manager instances."""
        version_manager = VersionManager(db_session)
        working_tree_manager = WorkingTreeManager(db_session, version_manager)
        diff_generator = DiffGenerator(version_manager, working_tree_manager)
        return version_manager, working_tree_manager, diff_generator

    @pytest.fixture
    def sample_content_v1(self):
        """Sample content for version 1."""
        return {
            "id": "test-entity-123",
            "title": "Test Entity",
            "description": "A test entity",
            "properties": {
                "category": "test",
                "priority": "high",
                "tags": ["tag1", "tag2"],
            },
            "metadata": {"created_by": "user1", "version": 1},
        }

    @pytest.fixture
    def sample_content_v2(self):
        """Sample content for version 2 with modifications."""
        return {
            "id": "test-entity-123",
            "title": "Updated Test Entity",  # Modified
            "description": "A test entity with updates",  # Modified
            "properties": {
                "category": "updated",  # Modified
                "priority": "high",
                "tags": ["tag1", "tag3"],  # Modified (tag2 -> tag3)
                "new_field": "added",  # Added
            },
            "metadata": {
                "created_by": "user1",
                "version": 2,  # Modified
                "updated_by": "user2",  # Added
            },
        }

    def test_generate_diff_basic(self, managers, sample_content_v1, sample_content_v2):
        """Test basic diff generation between two contents."""
        _version_manager, _working_tree_manager, diff_generator = managers

        diff = diff_generator.generate_diff(sample_content_v1, sample_content_v2)

        # Should contain changes
        assert isinstance(diff, dict)
        assert len(diff) > 0

        # Check for expected change types
        if "values_changed" in diff:
            # DeepDiff format includes changed values
            assert isinstance(diff["values_changed"], dict)

    def test_generate_diff_no_changes(self, managers, sample_content_v1):
        """Test diff generation with identical content."""
        _version_manager, _working_tree_manager, diff_generator = managers

        diff = diff_generator.generate_diff(sample_content_v1, sample_content_v1)

        # Should be empty or minimal
        assert isinstance(diff, dict)
        # Empty diff might still have some metadata, so we check if it's effectively empty
        assert len([k for k, v in diff.items() if v]) == 0

    def test_generate_diff_with_ignore_keys(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test diff generation with ignored keys."""
        _version_manager, _working_tree_manager, diff_generator = managers

        # Ignore the 'version' field changes
        diff = diff_generator.generate_diff(
            sample_content_v1, sample_content_v2, ignore_keys=["version"]
        )

        assert isinstance(diff, dict)
        # The diff should still show other changes even with ignored keys

    def test_generate_version_diff(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test generating diff between two specific versions."""
        version_manager, _working_tree_manager, diff_generator = managers

        # Create two versions
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v2,
            author_id="test-user",
        )

        # Generate diff between versions
        diff = diff_generator.generate_version_diff("structure_node", "test-123", 1, 2)

        assert isinstance(diff, EntityDiff)
        assert diff.entity_type == "structure_node"
        assert diff.entity_id == "test-123"
        assert diff.before_version.version_number == 1
        assert diff.after_version.version_number == 2
        assert diff.has_changes()
        assert isinstance(diff.changes, dict)
        assert isinstance(diff.summary, dict)

    def test_generate_version_diff_creation(self, managers, sample_content_v1):
        """Test generating diff for entity creation (no before version)."""
        version_manager, _working_tree_manager, diff_generator = managers

        # Create one version
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        # Generate diff with no before version
        diff = diff_generator.generate_version_diff(
            "structure_node", "test-123", None, 1
        )

        assert isinstance(diff, EntityDiff)
        assert diff.before_version is None
        assert diff.after_version.version_number == 1
        assert diff.has_changes()  # Creation always has changes

    def test_generate_version_diff_nonexistent_version(
        self, managers, sample_content_v1
    ):
        """Test generating diff with non-existent version."""
        version_manager, _working_tree_manager, diff_generator = managers

        # Create one version
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        # Try to generate diff with non-existent after version
        with pytest.raises(ValueError, match="After version 2 not found"):
            diff_generator.generate_version_diff("structure_node", "test-123", 1, 2)

        # Try to generate diff with non-existent before version
        with pytest.raises(ValueError, match="Before version 5 not found"):
            diff_generator.generate_version_diff("structure_node", "test-123", 5, 1)

    def test_generate_working_diff(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test generating diff between working and canonical versions."""
        version_manager, working_tree_manager, diff_generator = managers

        # Create initial version and working tree entry
        version1 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version1.id
        )

        # Create modified version and update working tree
        version2 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v2,
            author_id="test-user",
        )

        working_tree_manager.update_current_version(
            "structure_node", "test-123", version2.id
        )

        # Generate working diff
        diff = diff_generator.generate_working_diff("structure_node", "test-123")

        assert isinstance(diff, EntityDiff)
        assert diff.entity_type == "structure_node"
        assert diff.entity_id == "test-123"
        assert diff.before_version.version_number == 1  # Canonical
        assert diff.after_version.version_number == 2  # Working
        assert diff.has_changes()

    def test_generate_working_diff_no_working_tree(self, managers):
        """Test generating working diff for entity not in working tree."""
        _version_manager, _working_tree_manager, diff_generator = managers

        with pytest.raises(ValueError, match="not found in working tree"):
            diff_generator.generate_working_diff("structure_node", "non-existent")

    def test_generate_all_working_diffs(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test generating diffs for all entities with working changes."""
        version_manager, working_tree_manager, diff_generator = managers

        # Create multiple entities with changes
        for i in range(3):
            entity_id = f"test-{i}"
            content_v1 = sample_content_v1.copy()
            content_v1["id"] = entity_id

            # Create initial version
            version1 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=content_v1,
                author_id="test-user",
            )

            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", entity_id, version1.id
            )

            # Create changes for first two entities only
            if i < 2:
                content_v2 = sample_content_v2.copy()
                content_v2["id"] = entity_id

                version2 = version_manager.create_version(
                    entity_type="structure_node",
                    entity_id=entity_id,
                    content=content_v2,
                    author_id="test-user",
                )

                working_tree_manager.update_current_version(
                    "structure_node", entity_id, version2.id
                )

        # Generate all working diffs
        diffs = diff_generator.generate_all_working_diffs()

        # Should only return diffs for entities with changes
        assert len(diffs) == 2
        assert all(diff.has_changes() for diff in diffs)
        assert all(isinstance(diff, EntityDiff) for diff in diffs)

    def test_generate_commit_preview(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test generating commit preview for staged changes."""
        version_manager, working_tree_manager, diff_generator = managers

        # Create staged entities
        for i in range(2):
            entity_id = f"test-{i}"
            content_v1 = sample_content_v1.copy()
            content_v1["id"] = entity_id

            # Create initial version and working tree
            version1 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=content_v1,
                author_id="test-user",
            )

            working_tree_manager.initialize_entity_in_working_tree(
                "structure_node", entity_id, version1.id
            )

            # Create changes and stage
            content_v2 = sample_content_v2.copy()
            content_v2["id"] = entity_id

            version2 = version_manager.create_version(
                entity_type="structure_node",
                entity_id=entity_id,
                content=content_v2,
                author_id="test-user",
            )

            working_tree_manager.update_current_version(
                "structure_node", entity_id, version2.id
            )
            working_tree_manager.stage_entity("structure_node", entity_id)

        # Generate commit preview
        preview_diffs = diff_generator.generate_commit_preview()

        assert len(preview_diffs) == 2
        assert all(diff.has_changes() for diff in preview_diffs)
        assert all(isinstance(diff, EntityDiff) for diff in preview_diffs)

    def test_get_change_summary(self, managers, sample_content_v1, sample_content_v2):
        """Test getting change summary for an entity."""
        version_manager, working_tree_manager, diff_generator = managers

        # Setup entity with changes
        version1 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        working_tree_manager.initialize_entity_in_working_tree(
            "structure_node", "test-123", version1.id
        )

        version2 = version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v2,
            author_id="test-user",
        )

        working_tree_manager.update_current_version(
            "structure_node", "test-123", version2.id
        )

        # Get change summary
        summary = diff_generator.get_change_summary("structure_node", "test-123")

        assert isinstance(summary, DiffSummary)
        assert summary.total_changes > 0
        assert summary.added_items >= 0
        assert summary.removed_items >= 0
        assert summary.modified_items >= 0

    def test_format_diff_for_display_summary(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test formatting diff for summary display."""
        version_manager, _working_tree_manager, diff_generator = managers

        # Create versions and diff
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v2,
            author_id="test-user",
        )

        diff = diff_generator.generate_version_diff("structure_node", "test-123", 1, 2)

        # Format as summary
        formatted = diff_generator.format_diff_for_display(diff, "summary")

        assert isinstance(formatted, dict)
        assert "entity" in formatted
        assert "versions" in formatted
        assert "summary" in formatted
        assert "has_changes" in formatted
        assert formatted["entity"] == "structure_node:test-123"
        assert formatted["has_changes"] is True

    def test_format_diff_for_display_detailed(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test formatting diff for detailed display."""
        version_manager, _working_tree_manager, diff_generator = managers

        # Create versions and diff
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v2,
            author_id="test-user",
        )

        diff = diff_generator.generate_version_diff("structure_node", "test-123", 1, 2)

        # Format as detailed
        formatted = diff_generator.format_diff_for_display(diff, "detailed")

        assert isinstance(formatted, dict)
        assert "entity" in formatted
        assert "versions" in formatted
        assert "summary" in formatted
        assert "changes" in formatted  # Detailed includes full changes
        assert "has_changes" in formatted

    def test_format_diff_for_display_json(
        self, managers, sample_content_v1, sample_content_v2
    ):
        """Test formatting diff for JSON display."""
        version_manager, _working_tree_manager, diff_generator = managers

        # Create versions and diff
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v2,
            author_id="test-user",
        )

        diff = diff_generator.generate_version_diff("structure_node", "test-123", 1, 2)

        # Format as JSON
        formatted = diff_generator.format_diff_for_display(diff, "json")

        assert isinstance(formatted, dict)
        assert "entity_type" in formatted
        assert "entity_id" in formatted
        assert "before_version" in formatted
        assert "after_version" in formatted
        assert "changes" in formatted
        assert "summary" in formatted
        assert "generated_at" in formatted

    def test_format_diff_for_display_invalid_format(self, managers, sample_content_v1):
        """Test formatting diff with invalid format type."""
        version_manager, _working_tree_manager, diff_generator = managers

        # Create version and diff
        version_manager.create_version(
            entity_type="structure_node",
            entity_id="test-123",
            content=sample_content_v1,
            author_id="test-user",
        )

        diff = diff_generator.generate_version_diff(
            "structure_node", "test-123", None, 1
        )

        # Try invalid format
        with pytest.raises(ValueError, match="Unsupported format type"):
            diff_generator.format_diff_for_display(diff, "invalid_format")
