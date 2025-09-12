"""
Unit Tests for IncrementalSyncEngine

Tests the incremental synchronization functionality including partitioned queries,
parallel processing, and optimization features in Phase 4 implementation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from services.incremental_sync_engine import IncrementalSyncEngine
from services.s3_sync_manager import S3SyncManager


class TestIncrementalSyncEngine:
    """Test suite for IncrementalSyncEngine."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_s3_sync(self):
        """Create mock S3 sync manager."""
        return Mock(spec=S3SyncManager)
    
    @pytest.fixture
    def sync_engine(self, mock_db, mock_s3_sync):
        """Create IncrementalSyncEngine instance with mocked dependencies."""
        return IncrementalSyncEngine(db=mock_db, s3_sync_manager=mock_s3_sync)
    
    @pytest.fixture
    def sample_sync_operation(self):
        """Create sample sync operation for testing."""
        return {
            "id": "sync-123",
            "sync_type": "incremental",
            "started_at": datetime.now(timezone.utc),
            "since_timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "until_timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "entity_types": ["structure_node", "structure_node_link"],
            "synced_changes": 150,
            "new_entities": 25,
            "updated_entities": 125,
            "errors": []
        }
    
    def test_init_sync_engine(self, mock_db, mock_s3_sync):
        """Test IncrementalSyncEngine initialization."""
        engine = IncrementalSyncEngine(db=mock_db, s3_sync_manager=mock_s3_sync)
        
        assert engine.db == mock_db
        assert engine.s3_sync_manager == mock_s3_sync
        assert engine.logger is not None
        assert engine.worker_pool_size >= 1
    
    @patch('services.incremental_sync_engine.uuid.uuid4')
    def test_sync_incremental_success(self, mock_uuid, sync_engine, mock_db, mock_s3_sync):
        """Test successful incremental sync operation."""
        # Setup
        mock_uuid.return_value = MagicMock()
        mock_uuid.return_value.__str__ = Mock(return_value="sync-123")
        
        since_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        until_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        # Mock S3 sync operations
        mock_s3_sync.sync_changes_incremental.return_value = {
            "synced_changes": 100,
            "new_entities": 20,
            "updated_entities": 80,
            "errors": []
        }
        
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.sync_incremental(
            since=since_time,
            until=until_time,
            entity_types=["structure_node"],
            sync_strategy="auto",
            batch_size=1000
        )
        
        # Verify
        assert result["id"] == "sync-123"
        assert result["sync_type"] == "incremental"
        assert result["synced_changes"] == 100
        assert result["new_entities"] == 20
        assert result["updated_entities"] == 80
        
        mock_s3_sync.sync_changes_incremental.assert_called_once()
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()
    
    def test_sync_incremental_invalid_time_range(self, sync_engine):
        """Test incremental sync with invalid time range."""
        # Setup
        since_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
        until_time = datetime(2024, 1, 1, tzinfo=timezone.utc)  # Before since
        
        # Execute & Verify
        with pytest.raises(ValueError, match="'since' timestamp must be before 'until'"):
            sync_engine.sync_incremental(
                since=since_time,
                until=until_time,
                entity_types=["structure_node"]
            )
    
    def test_sync_incremental_parallel_strategy(self, sync_engine, mock_db, mock_s3_sync):
        """Test incremental sync with parallel strategy."""
        # Setup
        since_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        # Mock parallel processing
        mock_s3_sync.sync_changes_parallel.return_value = {
            "synced_changes": 200,
            "new_entities": 50,
            "updated_entities": 150,
            "errors": []
        }
        
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.sync_incremental(
            since=since_time,
            entity_types=["structure_node"],
            sync_strategy="parallel",
            max_parallel_workers=8
        )
        
        # Verify
        assert result["synced_changes"] == 200
        assert result["new_entities"] == 50
        mock_s3_sync.sync_changes_parallel.assert_called_once()
    
    def test_sync_incremental_sequential_strategy(self, sync_engine, mock_db, mock_s3_sync):
        """Test incremental sync with sequential strategy."""
        # Setup
        since_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        # Mock sequential processing
        mock_s3_sync.sync_changes_sequential.return_value = {
            "synced_changes": 75,
            "new_entities": 15,
            "updated_entities": 60,
            "errors": []
        }
        
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.sync_incremental(
            since=since_time,
            entity_types=["structure_node"],
            sync_strategy="sequential",
            batch_size=500
        )
        
        # Verify
        assert result["synced_changes"] == 75
        assert result["new_entities"] == 15
        mock_s3_sync.sync_changes_sequential.assert_called_once()
    
    def test_list_sync_operations(self, sync_engine, mock_db, sample_sync_operation):
        """Test listing sync operations with filtering."""
        # Setup
        mock_db.execute.return_value.fetchall.return_value = [
            (sample_sync_operation["id"], sample_sync_operation["sync_type"],
             sample_sync_operation["started_at"].isoformat(), None,
             sample_sync_operation["since_timestamp"].isoformat(),
             sample_sync_operation["until_timestamp"].isoformat(),
             '["structure_node"]', 150, 25, 125, '[]', '{}')
        ]
        
        # Execute
        result = sync_engine.list_sync_operations(
            sync_type="incremental",
            status="running",
            limit=10
        )
        
        # Verify
        assert len(result) == 1
        assert result[0]["id"] == sample_sync_operation["id"]
        assert result[0]["sync_type"] == sample_sync_operation["sync_type"]
        assert result[0]["synced_changes"] == 150
        
        mock_db.execute.assert_called_once()
    
    def test_get_sync_operation_success(self, sync_engine, mock_db, sample_sync_operation):
        """Test successful sync operation retrieval."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = (
            sample_sync_operation["id"], sample_sync_operation["sync_type"],
            sample_sync_operation["started_at"].isoformat(),
            datetime.now(timezone.utc).isoformat(),  # completed_at
            sample_sync_operation["since_timestamp"].isoformat(),
            sample_sync_operation["until_timestamp"].isoformat(),
            '["structure_node"]', 150, 25, 125, '[]', '{}'
        )
        
        # Execute
        result = sync_engine.get_sync_operation(sample_sync_operation["id"])
        
        # Verify
        assert result["id"] == sample_sync_operation["id"]
        assert result["sync_type"] == sample_sync_operation["sync_type"]
        assert result["synced_changes"] == 150
        assert result["completed_at"] is not None
        
        mock_db.execute.assert_called_once()
    
    def test_get_sync_operation_not_found(self, sync_engine, mock_db):
        """Test sync operation retrieval when operation doesn't exist."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = None
        
        # Execute
        result = sync_engine.get_sync_operation("nonexistent-sync")
        
        # Verify
        assert result is None
        mock_db.execute.assert_called_once()
    
    def test_cancel_sync_operation_success(self, sync_engine, mock_db):
        """Test successful sync operation cancellation."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = ("sync-123", "incremental", None)  # Running
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.cancel_sync_operation("sync-123")
        
        # Verify
        assert result is True
        mock_db.execute.assert_called()
        mock_db.commit.assert_called_once()
    
    def test_cancel_sync_operation_already_completed(self, sync_engine, mock_db):
        """Test cancellation of already completed sync operation."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = (
            "sync-123", "incremental", datetime.now(timezone.utc).isoformat()  # Already completed
        )
        
        # Execute
        result = sync_engine.cancel_sync_operation("sync-123")
        
        # Verify
        assert result is False
    
    def test_get_sync_system_status(self, sync_engine, mock_db):
        """Test sync system status retrieval."""
        # Setup
        mock_db.execute.return_value.fetchone.side_effect = [
            (3,),  # Active operations
            (1,),  # Queued operations
            (25,), # Total operations today
            (datetime.now(timezone.utc).isoformat(),),  # Last successful sync
            (0.75,)  # System load
        ]
        
        # Execute
        result = sync_engine.get_sync_system_status()
        
        # Verify
        assert result["active_operations"] == 3
        assert result["queued_operations"] == 1
        assert result["total_operations_today"] == 25
        assert result["last_successful_sync"] is not None
        assert result["system_load_percent"] == 0.75
        assert "available_workers" in result
        assert "sync_health_score" in result
        
        assert mock_db.execute.call_count >= 5
    
    def test_get_sync_performance_metrics(self, sync_engine, mock_db):
        """Test sync performance metrics retrieval."""
        # Setup
        mock_db.execute.return_value.fetchall.side_effect = [
            [(15.5, 450.0, 0.95, 0.05)],  # Performance stats
            [(9, 14, 16)],  # Peak hours
            [("s3_connection", "slow"), ("batch_size", "optimal")]  # Bottlenecks
        ]
        
        # Execute
        result = sync_engine.get_sync_performance_metrics(days=7)
        
        # Verify
        assert result["avg_sync_time_minutes"] == 15.5
        assert result["throughput_changes_per_minute"] == 450.0
        assert result["success_rate_percent"] == 0.95
        assert result["error_rate_percent"] == 0.05
        assert "bottleneck_analysis" in result
        
        assert mock_db.execute.call_count == 3
    
    def test_get_sync_system_health(self, sync_engine, mock_db, mock_s3_sync):
        """Test sync system health check."""
        # Setup
        mock_s3_sync.test_connection.return_value = True
        mock_db.execute.return_value.fetchone.return_value = (0,)  # No failed operations
        
        # Execute
        result = sync_engine.get_sync_system_health()
        
        # Verify
        assert result["status"] == "healthy"
        assert result["s3_connectivity"] is True
        assert result["database_connectivity"] is True
        assert result["worker_pool_health"] is True
        assert "performance_grade" in result
        assert "recommended_actions" in result
        
        mock_s3_sync.test_connection.assert_called_once()
        mock_db.execute.assert_called()
    
    def test_optimize_sync_configuration(self, sync_engine, mock_db):
        """Test sync configuration optimization."""
        # Setup - Mock performance analysis
        mock_db.execute.return_value.fetchone.side_effect = [
            (300.0,),  # Current throughput
            (2000,),   # Current batch size
            (12.5,)    # Avg processing time
        ]
        
        # Execute
        result = sync_engine.optimize_sync_configuration(
            target_throughput=500.0,
            optimize_for="speed",
            enable_auto_tuning=True
        )
        
        # Verify
        assert "optimized_parameters" in result
        assert "expected_improvement_percent" in result
        assert "recommendation_summary" in result
        assert "applied_changes" in result
        
        # Should recommend improvements
        assert result["expected_improvement_percent"] > 0
        assert len(result["applied_changes"]) > 0
        
        mock_db.execute.assert_called()
    
    def test_get_performance_recommendations(self, sync_engine, mock_db):
        """Test performance recommendations generation."""
        # Setup
        mock_db.execute.return_value.fetchall.side_effect = [
            [(0.85, 1500, 18.5)],  # Performance metrics
            [(5,)],  # Failed operations
            [(3,)]   # Long-running operations
        ]
        
        # Execute
        result = sync_engine.get_performance_recommendations()
        
        # Verify
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check for common recommendations
        recommendations_text = " ".join(result)
        assert any(keyword in recommendations_text.lower() for keyword in 
                  ["batch", "parallel", "performance", "optimize", "memory"])
        
        mock_db.execute.assert_called()
    
    def test_trigger_full_resync(self, sync_engine, mock_db, mock_s3_sync):
        """Test triggering full data resync."""
        # Setup
        mock_db.execute.return_value.fetchone.return_value = None  # No recent full sync
        mock_s3_sync.sync_full_resync.return_value = {
            "operation_id": "full-sync-456",
            "estimated_duration_minutes": 120
        }
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.trigger_full_resync(
            entity_types=["structure_node"],
            force=False
        )
        
        # Verify
        assert result["id"] == "full-sync-456"
        assert "estimated_duration_minutes" in result
        
        mock_s3_sync.sync_full_resync.assert_called_once()
        mock_db.execute.assert_called()
        mock_db.commit.assert_called_once()
    
    def test_trigger_full_resync_force(self, sync_engine, mock_db, mock_s3_sync):
        """Test forcing full resync even with recent sync."""
        # Setup - Recent full sync exists
        mock_db.execute.return_value.fetchone.return_value = (
            datetime.now(timezone.utc).isoformat(),  # Recent sync
        )
        mock_s3_sync.sync_full_resync.return_value = {
            "operation_id": "forced-sync-789"
        }
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.trigger_full_resync(force=True)
        
        # Verify
        assert result["id"] == "forced-sync-789"
        mock_s3_sync.sync_full_resync.assert_called_once()
    
    def test_validate_data_integrity(self, sync_engine, mock_db, mock_s3_sync):
        """Test data integrity validation."""
        # Setup
        local_sample = [{"id": "1", "hash": "abc"}, {"id": "2", "hash": "def"}]
        remote_sample = [{"id": "1", "hash": "abc"}, {"id": "2", "hash": "xyz"}]  # Hash mismatch
        
        mock_db.execute.return_value.fetchall.return_value = [("1", "abc"), ("2", "def")]
        mock_s3_sync.get_remote_sample.return_value = [("1", "abc"), ("2", "xyz")]
        
        # Execute
        result = sync_engine.validate_data_integrity(sample_size=1000)
        
        # Verify
        assert result["status"] in ["healthy", "issues_found"]
        assert "integrity_score" in result
        assert "issues_found" in result
        assert isinstance(result["integrity_score"], float)
        assert 0 <= result["integrity_score"] <= 1
        
        mock_db.execute.assert_called()
        mock_s3_sync.get_remote_sample.assert_called()
    
    def test_get_partition_analytics(self, sync_engine, mock_db):
        """Test partition performance analytics."""
        # Setup
        mock_db.execute.return_value.fetchall.return_value = [
            ("2024-01", 1500, 25.5, 0.95),
            ("2024-02", 1800, 22.0, 0.98),
            ("2024-03", 2100, 18.5, 0.99)
        ]
        
        # Execute
        result = sync_engine.get_partition_analytics(days=90)
        
        # Verify
        assert "partition_performance" in result
        assert "trends" in result
        assert "recommendations" in result
        
        partition_data = result["partition_performance"]
        assert len(partition_data) == 3
        assert partition_data[0]["partition"] == "2024-01"
        assert partition_data[0]["records_processed"] == 1500
        
        mock_db.execute.assert_called_once()
    
    def test_emergency_stop_all_sync(self, sync_engine, mock_db):
        """Test emergency stop of all sync operations."""
        # Setup
        mock_db.execute.return_value.fetchall.return_value = [
            ("sync-1", "running"),
            ("sync-2", "queued"),
            ("sync-3", "running")
        ]
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.emergency_stop_all_sync(reason="System maintenance")
        
        # Verify
        assert result == 3  # Stopped 3 operations
        
        # Should update all running/queued operations
        assert mock_db.execute.call_count >= 2  # Query + updates
        mock_db.commit.assert_called_once()
    
    def test_resume_failed_operations(self, sync_engine, mock_db, mock_s3_sync):
        """Test resuming failed sync operations."""
        # Setup
        failed_ops = [
            ("failed-1", "incremental", "2024-01-01T00:00:00Z", None, '["structure_node"]'),
            ("failed-2", "incremental", "2024-01-02T00:00:00Z", None, '["structure_node_link"]')
        ]
        mock_db.execute.return_value.fetchall.return_value = failed_ops
        mock_s3_sync.retry_sync_operation.return_value = {"status": "restarted"}
        mock_db.commit = Mock()
        
        # Execute
        result = sync_engine.resume_failed_operations(max_retry_count=3)
        
        # Verify
        assert len(result) == 2
        assert "failed-1" in result
        assert "failed-2" in result
        
        assert mock_s3_sync.retry_sync_operation.call_count == 2
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])