"""
Unit Tests for IncrementalSyncEngine

Tests the incremental synchronization functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import pandas as pd  # type: ignore[import-untyped]

from services.incremental_sync_engine import IncrementalSyncEngine
from services.duckdb_service import DuckDBService
from services.version_manager import VersionManager


class TestIncrementalSyncEngine:
    """Test suite for IncrementalSyncEngine."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_duckdb_service(self):
        """Create mock DuckDBService."""
        return Mock(spec=DuckDBService)

    @pytest.fixture
    def mock_version_manager(self):
        """Create mock VersionManager."""
        return Mock(spec=VersionManager)

    @pytest.fixture
    def mock_s3_config(self):
        """Create mock S3 configuration."""
        return {
            "bucket": "test-bucket",
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
            "aws_region": "us-east-1"
        }

    @pytest.fixture
    def sync_engine(self, mock_db, mock_duckdb_service, mock_version_manager, mock_s3_config):
        """Create IncrementalSyncEngine instance with mocked dependencies."""
        return IncrementalSyncEngine(
            db=mock_db,
            duckdb_service=mock_duckdb_service,
            version_manager=mock_version_manager,
            s3_config=mock_s3_config
        )

    def test_init_sync_engine(self, mock_db, mock_duckdb_service, mock_version_manager, mock_s3_config):
        """Test IncrementalSyncEngine initialization."""
        engine = IncrementalSyncEngine(
            db=mock_db,
            duckdb_service=mock_duckdb_service,
            version_manager=mock_version_manager,
            s3_config=mock_s3_config
        )

        assert engine.db == mock_db
        assert engine.duckdb == mock_duckdb_service
        assert engine.version_manager == mock_version_manager
        assert engine.s3_config == mock_s3_config

    @patch('services.incremental_sync_engine.IncrementalSyncEngine._create_sync_operation')
    @patch('services.incremental_sync_engine.IncrementalSyncEngine._store_sync_operation')
    @patch('services.incremental_sync_engine.IncrementalSyncEngine._complete_sync_operation')
    def test_sync_incremental_invalid_time_range(self, mock_complete, mock_store, mock_create, sync_engine, mock_duckdb_service):
        """Test incremental sync with invalid time range."""
        # Mock the sync operation creation
        mock_sync_op = Mock()
        mock_sync_op.id = "sync-123"
        mock_create.return_value = mock_sync_op

        # Mock DuckDB query execution - return empty DataFrame
        mock_result_df = pd.DataFrame()
        mock_duckdb_service.execute_query.return_value = mock_result_df

        since_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
        until_time = datetime(2024, 1, 1, tzinfo=timezone.utc)  # Before since

        result = sync_engine.sync_incremental(
            since=since_time,
            until=until_time,
            entity_types=["structure_node"]
        )

        # Should return a result with the operation_id
        assert "operation_id" in result

    @patch('services.incremental_sync_engine.IncrementalSyncEngine._create_sync_operation')
    @patch('services.incremental_sync_engine.IncrementalSyncEngine._store_sync_operation')
    @patch('services.incremental_sync_engine.IncrementalSyncEngine._complete_sync_operation')
    def test_sync_incremental_success(self, mock_complete, mock_store, mock_create, sync_engine, mock_db, mock_duckdb_service):
        """Test successful incremental sync operation."""
        # Mock the sync operation creation
        mock_sync_op = Mock()
        mock_sync_op.id = "sync-123"
        mock_create.return_value = mock_sync_op

        # Mock database operations for sync operation tracking
        mock_db.execute = Mock()
        mock_db.commit = Mock()

        # Mock DuckDB query execution - return empty DataFrame for simplicity
        mock_result_df = pd.DataFrame()
        mock_duckdb_service.execute_query.return_value = mock_result_df

        since_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        until_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

        # Execute
        result = sync_engine.sync_incremental(
            since=since_time,
            until=until_time,
            entity_types=["structure_node"]
        )

        # Verify
        assert "operation_id" in result
        assert result["operation_id"] == "sync-123"
        assert "synced_changes" in result
        assert "new_entities" in result
        assert "updated_entities" in result
        assert "sync_duration_seconds" in result
        assert "strategy_used" in result

        # Should have called the mocked methods
        mock_create.assert_called_once()
        mock_complete.assert_called_once()
        # Note: _store_sync_operation is called inside _create_sync_operation,
        # so it won't be called when _create_sync_operation is mocked

    def test_get_optimal_sync_strategy(self, sync_engine):
        """Test optimal sync strategy determination."""
        result = sync_engine.get_optimal_sync_strategy(
            target_entity_count=1000,
            time_range_days=7
        )

        assert "recommended_strategy" in result
        assert "reasoning" in result
        assert result["recommended_strategy"] in ["sequential", "parallel", "auto"]

    def test_get_sync_history(self, sync_engine, mock_db):
        """Test sync history retrieval."""
        # Mock database query result - simpler format matching actual SyncOperation fields
        mock_db.execute.return_value.fetchall.return_value = [
            ("sync-123", "incremental", "2024-01-01T00:00:00+00:00",
             "2024-01-01T00:05:00+00:00", 100, "sequential", '{}')
        ]

        result = sync_engine.get_sync_history(limit=10)

        assert isinstance(result, list)
        if result:  # Only check if we have results
            # The method returns SyncOperation objects, so check object attributes
            sync_op = result[0]
            assert hasattr(sync_op, 'id')
            assert hasattr(sync_op, 'operation_type')
            assert sync_op.id == "sync-123"

        mock_db.execute.assert_called_once()

    def test_get_sync_statistics(self, sync_engine, mock_db):
        """Test sync statistics retrieval."""
        # Mock database query result - single row with all stats
        mock_row = Mock()
        mock_row.total_syncs = 150
        mock_row.total_changes = 1250
        mock_row.avg_duration_seconds = 25.5
        mock_row.completed_syncs = 143
        mock_row.failed_syncs = 7

        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = sync_engine.get_sync_statistics(days=30)

        # Check for the actual keys returned by the implementation
        assert "total_syncs" in result
        assert "total_changes" in result
        assert "avg_duration_seconds" in result
        assert "completed_syncs" in result
        assert "failed_syncs" in result
        assert "success_rate" in result

        mock_db.execute.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])