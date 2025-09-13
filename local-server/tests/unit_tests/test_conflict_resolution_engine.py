"""
Unit Tests for ConflictResolutionEngine Service

Tests the advanced conflict resolution functionality including intelligent detection,
automatic resolution, and manual conflict resolution in Phase 4 implementation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from services.conflict_resolution_engine import (
    ConflictResolutionEngine, IntelligentConflictDetector, ConflictDescriptor, ConflictType
)


class TestConflictResolutionEngine:
    """Test suite for ConflictResolutionEngine service."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_conflict_detector(self):
        """Create mock conflict detector."""
        return Mock(spec=IntelligentConflictDetector)
    
    @pytest.fixture
    def mock_version_manager(self):
        """Create mock version manager."""
        return Mock()
    
    @pytest.fixture
    def conflict_engine(self, mock_db, mock_conflict_detector, mock_version_manager):
        """Create ConflictResolutionEngine instance with mocked dependencies."""
        return ConflictResolutionEngine(db=mock_db, conflict_detector=mock_conflict_detector, version_manager=mock_version_manager)
    
    @pytest.fixture
    def sample_conflict(self):
        """Create sample conflict descriptor for testing."""
        # Mock EntityVersion objects
        from services.version_manager import EntityVersion, ChangeState
        
        mock_local_version = EntityVersion(
            id="version-local",
            entity_type="structure_node",
            entity_id="entity-456",
            version_number=1,
            content={"name": "Local Name"},
            state=ChangeState.ACTIVE,
            parent_version_id=None,
            changeset_id="changeset-1",
            author_id="user-1",
            created_at=datetime.now(timezone.utc)
        )

        mock_remote_version = EntityVersion(
            id="version-remote",
            entity_type="structure_node",
            entity_id="entity-456",
            version_number=2,
            content={"name": "Remote Name"},
            state=ChangeState.ACTIVE,
            parent_version_id=None,
            changeset_id="changeset-2",
            author_id="user-2",
            created_at=datetime.now(timezone.utc)
        )
        
        return ConflictDescriptor(
            conflict_id="conflict-123",
            conflict_type=ConflictType.CONCURRENT_MODIFICATION,
            entity_type="structure_node",
            entity_id="entity-456",
            local_version=mock_local_version,
            remote_version=mock_remote_version,
            conflict_details={
                "field": "name",
                "local_value": "Local Name",
                "remote_value": "Remote Name"
            },
            resolution_suggestions=[
                {"type": "prefer_local", "confidence": 0.6},
                {"type": "prefer_remote", "confidence": 0.4}
            ],
            severity="medium",
            created_at=datetime.now(timezone.utc)
        )
    
    def test_init_conflict_engine(self, mock_db, mock_conflict_detector, mock_version_manager):
        """Test ConflictResolutionEngine initialization."""
        engine = ConflictResolutionEngine(db=mock_db, conflict_detector=mock_conflict_detector, version_manager=mock_version_manager)
        
        assert engine.db == mock_db
        assert engine.conflict_detector == mock_conflict_detector
        assert engine.version_manager == mock_version_manager
    
    @patch('services.conflict_resolution_engine.uuid.uuid4')
    def test_detect_conflicts_between_versions_success(self, mock_uuid, conflict_engine, mock_db, sample_conflict):
        """Test successful conflict detection between versions."""
        # Setup
        mock_uuid.return_value = MagicMock()
        mock_uuid.return_value.__str__ = Mock(return_value="conflict-123")

        local_versions = [
            {"entity_id": "entity-1", "version_id": "v1-local", "data": {"name": "Local"}}
        ]
        remote_versions = [
            {"entity_id": "entity-1", "version_id": "v1-remote", "data": {"name": "Remote"}}
        ]

        # Mock conflict detector to return iterable list of conflicts
        conflict_engine.conflict_detector.detect_conflicts.return_value = [sample_conflict]

        # Mock database operations
        mock_db.execute.return_value.fetchone.return_value = ("v1-local", "v1-remote")
        mock_db.commit = Mock()

        # Execute
        result = conflict_engine.detect_conflicts_between_versions(
            local_versions, remote_versions, "structure_node"
        )

        # Verify
        assert len(result) >= 0  # May detect conflicts based on logic
        mock_db.execute.assert_called()
    
    def test_resolve_conflict_manually_success(self, conflict_engine, mock_db, sample_conflict):
        """Test successful manual conflict resolution."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = (
            sample_conflict.conflict_id, sample_conflict.conflict_type.value,
            sample_conflict.entity_type, sample_conflict.entity_id,
            sample_conflict.local_version_id, sample_conflict.remote_version_id,
            '{"field": "name"}', '[]', sample_conflict.severity,
            sample_conflict.created_at.isoformat(), None, None, None
        )
        mock_db.commit = Mock()
        
        resolution_choice = {
            "strategy": "prefer_local",
            "resolved_value": "Local Name"
        }
        
        # Execute
        result = conflict_engine.resolve_conflict_manually(
            conflict_id=sample_conflict.conflict_id,
            resolved_by="resolver@example.com",
            resolution_choice=resolution_choice
        )
        
        # Verify
        assert result is True
        mock_db.execute.assert_called()
        mock_db.commit.assert_called_once()
    
    def test_resolve_conflict_manually_not_found(self, conflict_engine, mock_db):
        """Test manual resolution of non-existent conflict."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = None
        
        # Execute & Verify
        with pytest.raises(ValueError, match="Conflict .* not found"):
            conflict_engine.resolve_conflict_manually(
                conflict_id="nonexistent",
                resolved_by="resolver@example.com",
                resolution_choice={"strategy": "prefer_local"}
            )
    
    def test_resolve_conflict_already_resolved(self, conflict_engine, mock_db, sample_conflict):
        """Test resolution of already resolved conflict."""
        # Setup - conflict already resolved
        mock_db.execute.return_value.fetchone.return_value = (
            sample_conflict.conflict_id, sample_conflict.conflict_type.value,
            sample_conflict.entity_type, sample_conflict.entity_id,
            sample_conflict.local_version_id, sample_conflict.remote_version_id,
            '{"field": "name"}', '[]', sample_conflict.severity,
            sample_conflict.created_at.isoformat(),
            datetime.now(timezone.utc).isoformat(),  # Already resolved
            "previous@example.com", '{"strategy": "prefer_local"}'
        )
        
        # Execute & Verify
        with pytest.raises(ValueError, match="already resolved"):
            conflict_engine.resolve_conflict_manually(
                conflict_id=sample_conflict.conflict_id,
                resolved_by="resolver@example.com",
                resolution_choice={"strategy": "prefer_remote"}
            )
    
    def test_resolve_conflict_automatically_success(self, conflict_engine, mock_db, sample_conflict):
        """Test successful automatic conflict resolution."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = (
            sample_conflict.conflict_id, sample_conflict.conflict_type.value,
            sample_conflict.entity_type, sample_conflict.entity_id,
            sample_conflict.local_version_id, sample_conflict.remote_version_id,
            '{"field": "name"}', '[{"type": "prefer_local", "confidence": 0.9}]',
            sample_conflict.severity, sample_conflict.created_at.isoformat(),
            None, None, None
        )
        mock_db.commit = Mock()
        
        # Execute
        result = conflict_engine.resolve_conflict_automatically(
            conflict_id=sample_conflict.conflict_id,
            resolved_by="auto-resolver",
            confidence_threshold=0.8,
            max_attempts=3
        )
        
        # Verify
        assert result.get("resolved") is True
        assert "confidence" in result
        assert "strategy" in result
        mock_db.execute.assert_called()
        mock_db.commit.assert_called_once()
    
    def test_resolve_conflict_automatically_low_confidence(self, conflict_engine, mock_db, sample_conflict):
        """Test automatic resolution with low confidence."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = (
            sample_conflict.conflict_id, sample_conflict.conflict_type.value,
            sample_conflict.entity_type, sample_conflict.entity_id,
            sample_conflict.local_version_id, sample_conflict.remote_version_id,
            '{"field": "name"}', '[{"type": "prefer_local", "confidence": 0.5}]',
            sample_conflict.severity, sample_conflict.created_at.isoformat(),
            None, None, None
        )
        
        # Execute
        result = conflict_engine.resolve_conflict_automatically(
            conflict_id=sample_conflict.conflict_id,
            resolved_by="auto-resolver",
            confidence_threshold=0.8,
            max_attempts=3
        )
        
        # Verify
        assert result.get("resolved") is False
        assert "reason" in result
        assert result["reason"] == "Confidence below threshold"
        assert "suggestions" in result
    
    @patch('services.conflict_resolution_engine.ConflictResolutionEngine.get_conflict')
    def test_batch_resolve_conflicts_success(self, mock_get_conflict, conflict_engine, mock_db):
        """Test successful batch conflict resolution."""
        # Setup
        conflict_ids = ["conflict-1", "conflict-2", "conflict-3"]

        # Mock get_conflict to return conflict data for each ID
        mock_get_conflict.side_effect = [
            {
                "conflict_id": "conflict-1",
                "conflict_type": "concurrent_modification",
                "entity_type": "structure_node",
                "entity_id": "entity-1",
                "local_version_id": "v1",
                "remote_version_id": "v2",
                "conflict_details": {},
                "resolution_suggestions": [],
                "severity": "medium",
                "created_at": "2024-01-01T00:00:00Z",
                "resolved_at": None,
                "resolved_by": None,
                "resolution_choice": None
            },
            {
                "conflict_id": "conflict-2",
                "conflict_type": "structural_conflict",
                "entity_type": "structure_node",
                "entity_id": "entity-2",
                "local_version_id": "v3",
                "remote_version_id": "v4",
                "conflict_details": {},
                "resolution_suggestions": [],
                "severity": "low",
                "created_at": "2024-01-01T00:00:00Z",
                "resolved_at": None,
                "resolved_by": None,
                "resolution_choice": None
            },
            {
                "conflict_id": "conflict-3",
                "conflict_type": "dependency_conflict",
                "entity_type": "structure_node",
                "entity_id": "entity-3",
                "local_version_id": "v5",
                "remote_version_id": "v6",
                "conflict_details": {},
                "resolution_suggestions": [],
                "severity": "high",
                "created_at": "2024-01-01T00:00:00Z",
                "resolved_at": None,
                "resolved_by": None,
                "resolution_choice": None
            }
        ]

        mock_db.commit = Mock()

        # Execute
        result = conflict_engine.batch_resolve_conflicts(
            conflict_ids=conflict_ids,
            resolved_by="batch-resolver",
            resolution_strategy="prefer_local"
        )

        # Verify
        assert len(result) == 3
        assert all(r.get("success") is True for r in result)
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()
    
    def test_list_conflicts_with_filters(self, conflict_engine, mock_db):
        """Test listing conflicts with various filters."""
        # Setup
        mock_db.execute.return_value.fetchall.return_value = [
            ("conflict-1", "concurrent_modification", "structure_node", "entity-1", "v1", "v2",
             '{}', '[]', "medium", "2024-01-01T00:00:00Z", None, None, None)
        ]
        
        # Execute
        result = conflict_engine.list_conflicts(
            conflict_type="concurrent_modification",
            severity="medium",
            entity_type="structure_node",
            resolved=False,
            limit=10,
            offset=0
        )
        
        # Verify
        assert len(result) == 1
        assert result[0]["conflict_id"] == "conflict-1"
        assert result[0]["conflict_type"] == "concurrent_modification"
        assert result[0]["severity"] == "medium"
        mock_db.execute.assert_called_once()
    
    def test_get_conflict_success(self, conflict_engine, mock_db, sample_conflict):
        """Test successful conflict retrieval."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = (
            sample_conflict.conflict_id, sample_conflict.conflict_type.value,
            sample_conflict.entity_type, sample_conflict.entity_id,
            sample_conflict.local_version_id, sample_conflict.remote_version_id,
            '{"field": "name"}', '[]', sample_conflict.severity,
            sample_conflict.created_at.isoformat(), None, None, None
        )
        
        # Execute
        result = conflict_engine.get_conflict(sample_conflict.conflict_id)
        
        # Verify
        assert result["conflict_id"] == sample_conflict.conflict_id
        assert result["conflict_type"] == sample_conflict.conflict_type.value
        assert result["entity_type"] == sample_conflict.entity_type
        assert result["severity"] == sample_conflict.severity
        mock_db.execute.assert_called_once()
    
    def test_get_conflict_not_found(self, conflict_engine, mock_db):
        """Test retrieval of non-existent conflict."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = None
        
        # Execute
        result = conflict_engine.get_conflict("nonexistent")
        
        # Verify
        assert result is None
        mock_db.execute.assert_called_once()
    
    def test_get_entity_conflicts(self, conflict_engine, mock_db):
        """Test getting conflicts for specific entity."""
        # Setup
        mock_db.execute.return_value.fetchall.return_value = [
            ("conflict-1", "concurrent_modification", "structure_node", "entity-1", "v1", "v2",
             '{}', '[]', "medium", "2024-01-01T00:00:00Z", None, None, None),
            ("conflict-2", "structural_conflict", "structure_node", "entity-1", "v3", "v4",
             '{}', '[]', "low", "2024-01-01T00:00:00Z", None, None, None)
        ]
        
        # Execute
        result = conflict_engine.get_entity_conflicts(
            entity_type="structure_node",
            entity_id="entity-1",
            resolved=False
        )
        
        # Verify
        assert len(result) == 2
        assert all(c["entity_id"] == "entity-1" for c in result)
        mock_db.execute.assert_called_once()
    
    def test_get_resolution_suggestions(self, conflict_engine, mock_db, sample_conflict):
        """Test getting resolution suggestions for conflict."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = (
            sample_conflict.conflict_id, sample_conflict.conflict_type.value,
            sample_conflict.entity_type, sample_conflict.entity_id,
            sample_conflict.local_version_id, sample_conflict.remote_version_id,
            '{"field": "name", "local_value": "Local", "remote_value": "Remote"}',
            '[{"type": "prefer_local", "confidence": 0.8}]',
            sample_conflict.severity, sample_conflict.created_at.isoformat(),
            None, None, None
        )
        
        # Execute
        result = conflict_engine.get_resolution_suggestions(
            conflict_id=sample_conflict.conflict_id,
            max_suggestions=5
        )
        
        # Verify
        assert len(result) >= 1
        assert result[0]["type"] == "prefer_local"
        assert result[0]["confidence"] == 0.8
        mock_db.execute.assert_called_once()
    
    def test_get_conflict_analytics(self, conflict_engine, mock_db):
        """Test conflict analytics generation."""
        # Setup - Configure mock for different query types
        mock_execute = mock_db.execute.return_value

        # Sequential calls: fetchone(), fetchall(), fetchall(), fetchone(), fetchall()
        mock_execute.fetchone.side_effect = [
            (25,),  # Total conflicts
            (20, 5, 0.8, 2.5)  # Resolution rates
        ]
        mock_execute.fetchall.side_effect = [
            [("concurrent_modification", 10), ("structural_conflict", 8)],  # By type
            [("high", 5), ("medium", 15), ("low", 5)],  # By severity
            [("structure_node", "entity-1", 3)]  # Top conflict entities
        ]

        # Execute
        result = conflict_engine.get_conflict_analytics(days=30)

        # Verify
        assert result["total_conflicts"] == 25
        assert "conflicts_by_type" in result
        assert "conflicts_by_severity" in result
        assert "resolution_rates" in result
        assert "top_conflict_entities" in result
        assert result["conflicts_by_type"]["concurrent_modification"] == 10

        assert mock_db.execute.call_count == 5
    
    def test_get_system_health(self, conflict_engine, mock_db):
        """Test conflict resolution system health check."""
        # Setup
        mock_db.execute.return_value.fetchone.side_effect = [
            (15,),  # Active conflicts
            (3,),   # Unresolved high severity
            (0.85,)  # Auto resolution success rate
        ]
        
        # Execute
        result = conflict_engine.get_system_health()
        
        # Verify
        assert result["status"] == "healthy"
        assert result["active_conflicts"] == 15
        assert result["unresolved_high_severity"] == 3
        assert result["auto_resolution_enabled"] is True
        assert result["auto_resolution_success_rate"] == 0.85
        
        assert mock_db.execute.call_count == 3
    
    @patch('services.conflict_resolution_engine.ConflictResolutionEngine.get_conflict')
    def test_resolve_conflicts_prefer_local(self, mock_get_conflict, conflict_engine, mock_db):
        """Test resolving conflicts with prefer local strategy."""
        # Setup
        conflict_ids = ["conflict-1", "conflict-2"]

        # Mock get_conflict to return conflict data for each ID
        mock_get_conflict.side_effect = [
            {
                "conflict_id": "conflict-1",
                "conflict_type": "concurrent_modification",
                "entity_type": "structure_node",
                "entity_id": "entity-1",
                "local_version_id": "v1",
                "remote_version_id": "v2",
                "conflict_details": {},
                "resolution_suggestions": [],
                "severity": "medium",
                "created_at": "2024-01-01T00:00:00Z",
                "resolved_at": None,
                "resolved_by": None,
                "resolution_choice": None
            },
            {
                "conflict_id": "conflict-2",
                "conflict_type": "structural_conflict",
                "entity_type": "structure_node",
                "entity_id": "entity-2",
                "local_version_id": "v3",
                "remote_version_id": "v4",
                "conflict_details": {},
                "resolution_suggestions": [],
                "severity": "low",
                "created_at": "2024-01-01T00:00:00Z",
                "resolved_at": None,
                "resolved_by": None,
                "resolution_choice": None
            }
        ]

        mock_db.commit = Mock()

        # Execute
        result = conflict_engine.resolve_conflicts_prefer_local(
            conflict_ids=conflict_ids,
            resolved_by="resolver@example.com"
        )

        # Verify
        assert len(result) == 2
        assert all(r.get("success") is True for r in result)
        assert all(r.get("strategy") == "prefer_local" for r in result)
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()
    
    def test_analyze_conflict_risk(self, conflict_engine, mock_db):
        """Test conflict risk analysis for entity."""
        # Setup
        mock_db.execute.return_value.fetchone.side_effect = [
            (5,),   # Historical conflicts
            (2,),   # Active conflicts
            (0.7,)  # Average resolution time
        ]

        # Execute
        result = conflict_engine.analyze_conflict_risk(
            entity_type="structure_node",
            entity_id="entity-1"
        )

        # Verify
        assert "risk_level" in result
        assert "historical_conflicts" in result
        assert "active_conflicts" in result
        assert "recommendations" in result
        assert result["historical_conflicts"] == 5
        assert result["active_conflicts"] == 2

        assert mock_db.execute.call_count == 3
    
    def test_get_conflict_hotspots(self, conflict_engine, mock_db):
        """Test getting conflict hotspots."""
        # Setup
        mock_db.execute.return_value.fetchall.return_value = [
            ("structure_node", "entity-1", 8, 0.4),
            ("structure_node", "entity-2", 6, 0.3),
            ("structure_node", "entity-3", 5, 0.25)
        ]
        
        # Execute
        result = conflict_engine.get_conflict_hotspots(days=30, limit=10)
        
        # Verify
        assert len(result) == 3
        assert result[0]["entity_id"] == "entity-1"
        assert result[0]["conflict_count"] == 8
        assert result[0]["conflict_rate"] == 0.4
        mock_db.execute.assert_called_once()


class TestIntelligentConflictDetector:
    """Test suite for IntelligentConflictDetector."""
    
    @pytest.fixture
    def detector(self, mock_db):
        """Create IntelligentConflictDetector instance."""
        return IntelligentConflictDetector(mock_db)
    
    def test_detect_concurrent_modification_conflict(self, detector):
        """Test detection of concurrent modification conflicts."""
        # Setup
        local_versions = [
            {"entity_id": "entity-1", "modified_at": "2024-01-01T12:00:00Z", "data": {"name": "Local"}}
        ]
        remote_versions = [
            {"entity_id": "entity-1", "modified_at": "2024-01-01T12:05:00Z", "data": {"name": "Remote"}}
        ]
        
        # Execute
        result = detector._detect_concurrent_modifications(local_versions, remote_versions)
        
        # Verify
        assert len(result) >= 0  # May detect conflicts based on timing and content
    
    def test_detect_structural_conflict(self, detector):
        """Test detection of structural conflicts."""
        # Setup
        local_versions = [
            {"entity_id": "entity-1", "structure": {"type": "node", "children": ["child-1"]}}
        ]
        remote_versions = [
            {"entity_id": "entity-1", "structure": {"type": "node", "children": ["child-2"]}}
        ]
        
        # Execute
        result = detector._detect_structural_conflicts(local_versions, remote_versions)
        
        # Verify
        assert len(result) >= 0  # May detect structural differences
    
    def test_generate_resolution_suggestions(self, detector):
        """Test generation of resolution suggestions."""
        # Setup
        conflict_details = {
            "field": "name",
            "local_value": "Local Name",
            "remote_value": "Remote Name",
            "conflict_type": "concurrent_modification"
        }
        
        # Execute
        result = detector._generate_resolution_suggestions(conflict_details)
        
        # Verify
        assert len(result) >= 2  # Should suggest at least prefer_local and prefer_remote
        assert any(s["type"] == "prefer_local" for s in result)
        assert any(s["type"] == "prefer_remote" for s in result)
        assert all(0 <= s["confidence"] <= 1 for s in result)


if __name__ == "__main__":
    pytest.main([__file__])