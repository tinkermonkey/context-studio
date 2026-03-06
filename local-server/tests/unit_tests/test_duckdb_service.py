"""
Unit Tests for DuckDBService and ChangeAnalyticsEngine

Tests the DuckDB integration and analytics functionality including query execution,
view creation, and comprehensive analytics reporting in Phase 4 implementation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import pandas as pd  # type: ignore[import-untyped]  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402

from services.duckdb_service import DuckDBService, ChangeAnalyticsEngine  # noqa: E402, E501


class TestDuckDBService:
    """Test suite for DuckDBService."""

    @pytest.fixture
    def sample_s3_config(self):
        """Create sample S3 configuration."""
        return {
            "bucket": "test-bucket",
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
            "aws_region": "us-east-1"
        }

    @patch('services.duckdb_service.DUCKDB_AVAILABLE', True)
    @patch('services.duckdb_service.duckdb')
    def test_init_duckdb_service_with_duckdb_available(self, mock_duckdb, sample_s3_config):
        """Test DuckDBService initialization when DuckDB is available."""
        # Setup
        mock_connection = Mock()
        mock_duckdb.connect.return_value = mock_connection

        # Execute
        service = DuckDBService(db_path="/test/path", s3_config=sample_s3_config)

        # Verify
        assert service.db_path == "/test/path"
        assert service.s3_config == sample_s3_config
        assert service.connection == mock_connection

        mock_duckdb.connect.assert_called_once_with("/test/path")
        mock_connection.execute.assert_called()  # Extension loading

    @patch('services.duckdb_service.DUCKDB_AVAILABLE', False)
    def test_init_duckdb_service_without_duckdb(self, sample_s3_config):
        """Test DuckDBService initialization when DuckDB is not available."""
        # Execute
        service = DuckDBService(db_path=None, s3_config=sample_s3_config)

        # Verify
        assert service.db_path is None
        assert service.s3_config == sample_s3_config
        assert service.connection is None

    @patch('services.duckdb_service.DUCKDB_AVAILABLE', True)
    def test_execute_query_success(self):
        """Test successful query execution."""
        # Setup
        mock_connection = Mock()
        service = DuckDBService()
        service.connection = mock_connection

        mock_result = Mock()
        mock_df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        mock_result.df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        # Execute
        result = service.execute_query("SELECT * FROM test_table")

        # Verify
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "col1" in result.columns
        assert "col2" in result.columns

        mock_connection.execute.assert_called_once_with("SELECT * FROM test_table")


class TestChangeAnalyticsEngine:
    """Test suite for ChangeAnalyticsEngine."""

    @pytest.fixture
    def mock_duckdb_service(self):
        """Create mock DuckDBService."""
        return Mock(spec=DuckDBService)

    @pytest.fixture
    def sample_s3_config(self):
        """Create sample S3 configuration."""
        return {"bucket": "test-bucket"}

    @pytest.fixture
    def analytics_engine(self, mock_duckdb_service, sample_s3_config):
        """Create ChangeAnalyticsEngine instance with mocked dependencies."""
        mock_duckdb_service.s3_config = sample_s3_config
        return ChangeAnalyticsEngine(duckdb_service=mock_duckdb_service)

    @patch('services.duckdb_service.DUCKDB_AVAILABLE', True)
    def test_get_change_summary_with_data(self, analytics_engine, mock_duckdb_service):
        """Test change summary retrieval with actual data."""
        # Setup
        sample_data = pd.DataFrame({
            "total_changes": [150],
            "entities_modified": [45],
            "active_users": [12],
            "changesets": [25],
            "period_start": ["2024-01-01T00:00:00Z"],
            "period_end": ["2024-01-31T23:59:59Z"]
        })

        mock_duckdb_service.execute_query.return_value = sample_data
        analytics_engine._view_exists = Mock(return_value=True)

        # Execute
        result = analytics_engine.get_change_summary(days=30)

        # Verify
        assert result["total_changes"] == 150
        assert result["entities_modified"] == 45
        assert result["active_users"] == 12
        assert result["changesets"] == 25

        mock_duckdb_service.execute_query.assert_called_once()

    @patch('services.duckdb_service.DUCKDB_AVAILABLE', False)
    def test_get_change_summary_fallback(self, analytics_engine):
        """Test change summary fallback when DuckDB is not available."""
        # Execute
        result = analytics_engine.get_change_summary(days=30)

        # Verify fallback response
        assert result["total_changes"] == 0
        assert result["entities_modified"] == 0
        assert result["active_users"] == 0
        assert result["changesets"] == 0
        assert result["period_start"] is None
        assert result["period_end"] is None


if __name__ == "__main__":
    pytest.main([__file__])
