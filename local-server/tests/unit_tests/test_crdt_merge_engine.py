"""
Unit tests for CRDTMergeEngine - Testing CRDT-based conflict-free merging.

Tests merge strategies, conflict resolution, and automatic merging workflows.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from services.crdt_merge_engine import CRDTMergeEngine, MergeStrategy, MergeResult
from services.collaboration_models import Changeset, ChangesetState
from services.changeset_manager import ChangesetManager
from services.working_tree_manager import WorkingTreeManager


class TestCRDTMergeEngine:
    """Test cases for CRDTMergeEngine functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        db.execute.return_value.fetchall.return_value = []
        db.execute.return_value.rowcount = 1
        return db

    @pytest.fixture
    def mock_changeset_manager(self):
        """Mock ChangesetManager."""
        return Mock(spec=ChangesetManager)

    @pytest.fixture
    def mock_working_tree_manager(self):
        """Mock WorkingTreeManager."""
        return Mock(spec=WorkingTreeManager)

    @pytest.fixture
    def crdt_merge_engine(self, mock_db_session, mock_changeset_manager, mock_working_tree_manager):
        """Create CRDTMergeEngine instance for testing."""
        return CRDTMergeEngine(
            db=mock_db_session,
            changeset_manager=mock_changeset_manager,
            working_tree_manager=mock_working_tree_manager
        )

    @pytest.fixture
    def mock_changeset(self):
        """Mock changeset for testing."""
        changeset = Mock(spec=Changeset)
        changeset.id = "changeset123"
        changeset.state = ChangesetState.APPROVED
        changeset.author_id = "user123"
        changeset.created_at = datetime.now(timezone.utc)
        return changeset

    def test_initialization(self, crdt_merge_engine, mock_db_session, mock_changeset_manager, mock_working_tree_manager):
        """Test CRDTMergeEngine initialization."""
        assert crdt_merge_engine.db == mock_db_session
        assert crdt_merge_engine.changeset_manager == mock_changeset_manager
        assert crdt_merge_engine.working_tree == mock_working_tree_manager

    def test_merge_changesets_success(self, crdt_merge_engine, mock_changeset_manager, mock_changeset):
        """Test successful changeset merging."""
        # Mock changesets
        changeset1 = Mock()
        changeset1.id = "changeset1"
        changeset1.state = ChangesetState.APPROVED
        
        changeset2 = Mock()
        changeset2.id = "changeset2"
        changeset2.state = ChangesetState.APPROVED

        mock_changeset_manager.get_changeset.side_effect = [changeset1, changeset2]

        # Mock merge operations
        with patch.object(crdt_merge_engine, '_validate_merge_preconditions'):
            with patch.object(crdt_merge_engine, '_compute_merge_plan', return_value={"operations": []}):
                with patch.object(crdt_merge_engine, '_execute_merge_plan'):
                    with patch.object(crdt_merge_engine, '_record_merge_result'):
                        
                        result = crdt_merge_engine.merge_changesets(
                            ["changeset1", "changeset2"],
                            strategy=MergeStrategy.LAST_WRITER_WINS
                        )

        assert result.success is True
        assert "changeset1" in result.merged_changesets
        assert "changeset2" in result.merged_changesets

    def test_merge_changesets_invalid_changeset(self, crdt_merge_engine, mock_changeset_manager):
        """Test merging with invalid changeset."""
        mock_changeset_manager.get_changeset.return_value = None

        result = crdt_merge_engine.merge_changesets(
            ["nonexistent"],
            strategy=MergeStrategy.LAST_WRITER_WINS
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_merge_changesets_invalid_state(self, crdt_merge_engine, mock_changeset_manager):
        """Test merging changesets in invalid state."""
        mock_changeset = Mock()
        mock_changeset.state = ChangesetState.DRAFT
        mock_changeset_manager.get_changeset.return_value = mock_changeset

        result = crdt_merge_engine.merge_changesets(
            ["changeset1"],
            strategy=MergeStrategy.LAST_WRITER_WINS
        )

        assert result.success is False
        assert "approved" in result.error_message.lower()

    def test_merge_changesets_empty_list(self, crdt_merge_engine):
        """Test merging empty changeset list."""
        result = crdt_merge_engine.merge_changesets(
            [],
            strategy=MergeStrategy.LAST_WRITER_WINS
        )

        assert result.success is False
        assert "at least one changeset" in result.error_message.lower()

    def test_auto_merge_proposal_success(self, crdt_merge_engine, mock_changeset_manager):
        """Test successful auto-merge of proposal."""
        # Mock proposal with approved changeset
        mock_changeset = Mock()
        mock_changeset.id = "changeset123"
        mock_changeset.state = ChangesetState.APPROVED
        mock_changeset_manager.get_changeset.return_value = mock_changeset

        with patch.object(crdt_merge_engine, 'merge_changesets') as mock_merge:
            mock_merge.return_value = MergeResult(
                success=True,
                merge_commit_id="merge123",
                merged_changesets=["changeset123"],
                conflicts=[],
                strategy=MergeStrategy.LAST_WRITER_WINS
            )
            
            result = crdt_merge_engine.auto_merge_proposal("proposal123", "changeset123")

        assert result.success is True
        assert result.merge_commit_id == "merge123"

    def test_auto_merge_proposal_changeset_not_approved(self, crdt_merge_engine, mock_changeset_manager):
        """Test auto-merge when changeset not approved."""
        mock_changeset = Mock()
        mock_changeset.state = ChangesetState.DRAFT
        mock_changeset_manager.get_changeset.return_value = mock_changeset

        result = crdt_merge_engine.auto_merge_proposal("proposal123", "changeset123")

        assert result.success is False
        assert "not in approved state" in result.error_message.lower()

    def test_resolve_conflicts_last_writer_wins(self, crdt_merge_engine):
        """Test conflict resolution with last writer wins strategy."""
        changes = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 1",
                "timestamp": "2023-01-01T00:00:00Z",
                "author_id": "user1"
            },
            {
                "entity_id": "entity1", 
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 2",
                "timestamp": "2023-01-01T01:00:00Z",  # Later timestamp
                "author_id": "user2"
            }
        ]

        resolved = crdt_merge_engine._resolve_conflicts(changes, MergeStrategy.LAST_WRITER_WINS)

        # Should keep the change with later timestamp
        assert len(resolved) == 1
        assert resolved[0]["new_value"] == "Change 2"
        assert resolved[0]["author_id"] == "user2"

    def test_resolve_conflicts_merge_both(self, crdt_merge_engine):
        """Test conflict resolution with merge both strategy."""
        changes = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 1",
                "timestamp": "2023-01-01T00:00:00Z",
                "author_id": "user1"
            },
            {
                "entity_id": "entity1",
                "field": "description", 
                "old_value": "Original desc",
                "new_value": "Change 2 desc",
                "timestamp": "2023-01-01T01:00:00Z",
                "author_id": "user2"
            }
        ]

        resolved = crdt_merge_engine._resolve_conflicts(changes, MergeStrategy.MERGE_BOTH)

        # Should keep both changes as they affect different fields
        assert len(resolved) == 2

    def test_resolve_conflicts_author_priority(self, crdt_merge_engine):
        """Test conflict resolution with author priority strategy."""
        changes = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 1",
                "timestamp": "2023-01-01T01:00:00Z",
                "author_id": "user2"
            },
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original", 
                "new_value": "Change 2",
                "timestamp": "2023-01-01T00:00:00Z",
                "author_id": "user1"  # Higher priority author
            }
        ]

        with patch.object(crdt_merge_engine, '_get_author_priority') as mock_priority:
            mock_priority.side_effect = lambda author: {"user1": 1, "user2": 2}[author]
            
            resolved = crdt_merge_engine._resolve_conflicts(changes, MergeStrategy.AUTHOR_PRIORITY)

        # Should keep change from higher priority author (lower number = higher priority)
        assert len(resolved) == 1
        assert resolved[0]["author_id"] == "user1"

    def test_detect_conflicts_same_field(self, crdt_merge_engine):
        """Test conflict detection for same field changes."""
        changes = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 1"
            },
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 2"
            }
        ]

        conflicts = crdt_merge_engine._detect_conflicts(changes)

        assert len(conflicts) == 1
        assert conflicts[0]["entity_id"] == "entity1"
        assert conflicts[0]["field"] == "title"
        assert len(conflicts[0]["conflicting_changes"]) == 2

    def test_detect_conflicts_different_fields(self, crdt_merge_engine):
        """Test no conflicts for different field changes."""
        changes = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 1"
            },
            {
                "entity_id": "entity1",
                "field": "description",
                "old_value": "Original desc",
                "new_value": "Change 2"
            }
        ]

        conflicts = crdt_merge_engine._detect_conflicts(changes)

        assert len(conflicts) == 0

    def test_detect_conflicts_different_entities(self, crdt_merge_engine):
        """Test no conflicts for different entity changes."""
        changes = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 1"
            },
            {
                "entity_id": "entity2",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change 2"
            }
        ]

        conflicts = crdt_merge_engine._detect_conflicts(changes)

        assert len(conflicts) == 0

    def test_compute_merge_plan(self, crdt_merge_engine, mock_working_tree_manager):
        """Test merge plan computation."""
        mock_working_tree_manager.get_changeset_changes.return_value = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Updated",
                "timestamp": "2023-01-01T00:00:00Z",
                "author_id": "user1"
            }
        ]

        plan = crdt_merge_engine._compute_merge_plan(
            ["changeset1"],
            MergeStrategy.LAST_WRITER_WINS
        )

        assert "operations" in plan
        assert "conflicts" in plan
        assert "resolved_changes" in plan

    def test_execute_merge_plan_success(self, crdt_merge_engine, mock_working_tree_manager):
        """Test successful merge plan execution."""
        plan = {
            "operations": [
                {
                    "type": "update",
                    "entity_id": "entity1",
                    "field": "title",
                    "new_value": "Updated"
                }
            ],
            "conflicts": [],
            "resolved_changes": []
        }

        mock_working_tree_manager.apply_changes.return_value = "commit123"

        commit_id = crdt_merge_engine._execute_merge_plan(plan, ["changeset1"])

        assert commit_id == "commit123"
        mock_working_tree_manager.apply_changes.assert_called_once()

    def test_validate_merge_preconditions_success(self, crdt_merge_engine):
        """Test successful merge precondition validation."""
        changesets = [
            Mock(state=ChangesetState.APPROVED),
            Mock(state=ChangesetState.APPROVED)
        ]

        # Should not raise exception
        crdt_merge_engine._validate_merge_preconditions(changesets)

    def test_validate_merge_preconditions_invalid_state(self, crdt_merge_engine):
        """Test merge precondition validation with invalid state."""
        changesets = [
            Mock(state=ChangesetState.APPROVED),
            Mock(state=ChangesetState.DRAFT)
        ]

        with pytest.raises(ValueError, match="All changesets must be in approved state"):
            crdt_merge_engine._validate_merge_preconditions(changesets)

    def test_record_merge_result(self, crdt_merge_engine, mock_db_session):
        """Test recording merge result in database."""
        result = MergeResult(
            success=True,
            merge_commit_id="commit123",
            merged_changesets=["changeset1", "changeset2"],
            conflicts=[],
            strategy=MergeStrategy.LAST_WRITER_WINS
        )

        crdt_merge_engine._record_merge_result(result, ["changeset1", "changeset2"])

        # Verify database operations were called
        assert mock_db_session.execute.called
        assert mock_db_session.commit.called

    def test_get_author_priority_default(self, crdt_merge_engine):
        """Test default author priority."""
        priority = crdt_merge_engine._get_author_priority("user123")
        assert priority == 999  # Default priority

    def test_merge_strategy_enum_values(self):
        """Test MergeStrategy enum has expected values."""
        assert MergeStrategy.LAST_WRITER_WINS.value == "last_writer_wins"
        assert MergeStrategy.MERGE_BOTH.value == "merge_both"
        assert MergeStrategy.AUTHOR_PRIORITY.value == "author_priority"
        assert MergeStrategy.MANUAL_RESOLUTION.value == "manual_resolution"

    def test_merge_result_dataclass(self):
        """Test MergeResult dataclass structure."""
        result = MergeResult(
            success=True,
            merge_commit_id="commit123",
            merged_changesets=["changeset1"],
            conflicts=[],
            strategy=MergeStrategy.LAST_WRITER_WINS,
            error_message=None
        )

        assert result.success is True
        assert result.merge_commit_id == "commit123"
        assert result.merged_changesets == ["changeset1"]
        assert result.conflicts == []
        assert result.strategy == MergeStrategy.LAST_WRITER_WINS
        assert result.error_message is None

    def test_database_transaction_rollback_on_error(self, crdt_merge_engine, mock_db_session, mock_changeset_manager):
        """Test database rollback on merge error."""
        mock_changeset = Mock()
        mock_changeset.state = ChangesetState.APPROVED
        mock_changeset_manager.get_changeset.return_value = mock_changeset

        with patch.object(crdt_merge_engine, '_compute_merge_plan', side_effect=Exception("Merge error")):
            result = crdt_merge_engine.merge_changesets(
                ["changeset1"],
                strategy=MergeStrategy.LAST_WRITER_WINS
            )

        assert result.success is False
        mock_db_session.rollback.assert_called_once()

    def test_merge_with_complex_conflicts(self, crdt_merge_engine):
        """Test merge with complex conflict scenarios."""
        changes = [
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change A",
                "timestamp": "2023-01-01T00:00:00Z",
                "author_id": "user1"
            },
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change B",
                "timestamp": "2023-01-01T01:00:00Z",
                "author_id": "user2"
            },
            {
                "entity_id": "entity1",
                "field": "title",
                "old_value": "Original",
                "new_value": "Change C",
                "timestamp": "2023-01-01T02:00:00Z",
                "author_id": "user3"
            }
        ]

        resolved = crdt_merge_engine._resolve_conflicts(changes, MergeStrategy.LAST_WRITER_WINS)

        # Should resolve to the latest change
        assert len(resolved) == 1
        assert resolved[0]["new_value"] == "Change C"
        assert resolved[0]["author_id"] == "user3"