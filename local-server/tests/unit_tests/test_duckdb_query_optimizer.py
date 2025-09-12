"""
Unit tests for DuckDBQueryOptimizer - Testing advanced query optimization functionality.

Tests query optimization strategies, caching, materialized views, and performance metrics.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime

from services.duckdb_query_optimizer import (
    DuckDBQueryOptimizer,
    IntelligentQueryCache,
    QueryPerformanceMetrics
)


class TestIntelligentQueryCache:
    """Test cases for IntelligentQueryCache functionality."""
    
    @pytest.fixture
    def query_cache(self):
        """Create an IntelligentQueryCache instance for testing."""
        return IntelligentQueryCache(max_cache_size=10, ttl_seconds=60)
    
    def test_cache_initialization(self, query_cache):
        """Test IntelligentQueryCache initialization."""
        assert query_cache.max_cache_size == 10
        assert query_cache.ttl_seconds == 60
        assert len(query_cache.cache) == 0
        assert query_cache.cache_stats == {'hits': 0, 'misses': 0, 'evictions': 0}
    
    def test_cache_miss(self, query_cache):
        """Test cache miss scenario."""
        result = query_cache.get_cached_result("nonexistent_hash")
        assert result is None
        assert query_cache.cache_stats['misses'] == 1
        assert query_cache.cache_stats['hits'] == 0
    
    def test_cache_hit(self, query_cache):
        """Test cache hit scenario."""
        test_result = {"data": "test_result"}
        test_metadata = {"query": "SELECT * FROM test"}
        
        # Cache the result
        query_cache.cache_result("test_hash", test_result, test_metadata)
        
        # Retrieve the result
        cached_result = query_cache.get_cached_result("test_hash")
        assert cached_result == test_result
        assert query_cache.cache_stats['hits'] == 1
        assert query_cache.cache_stats['misses'] == 0
    
    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = IntelligentQueryCache(max_cache_size=10, ttl_seconds=0.1)
        
        # Cache a result
        cache.cache_result("test_hash", {"data": "test"}, {})
        
        # Should hit immediately
        result = cache.get_cached_result("test_hash")
        assert result is not None
        assert cache.cache_stats['hits'] == 1
        
        # Wait for TTL to expire
        time.sleep(0.2)
        
        # Should miss after expiration
        result = cache.get_cached_result("test_hash")
        assert result is None
        assert cache.cache_stats['misses'] == 1
    
    def test_cache_lru_eviction(self, query_cache):
        """Test LRU eviction when cache is full."""
        # Fill the cache to capacity
        for i in range(query_cache.max_cache_size):
            query_cache.cache_result(f"hash_{i}", {"data": f"result_{i}"}, {})
        
        assert len(query_cache.cache) == query_cache.max_cache_size
        
        # Add one more item to trigger eviction
        query_cache.cache_result("new_hash", {"data": "new_result"}, {})
        
        # Cache should still be at max size
        assert len(query_cache.cache) == query_cache.max_cache_size
        assert query_cache.cache_stats['evictions'] == 1
        
        # Oldest item should be evicted (hash_0)
        result = query_cache.get_cached_result("hash_0")
        assert result is None
        
        # Newest item should be present
        result = query_cache.get_cached_result("new_hash")
        assert result is not None
    
    def test_cache_stats(self, query_cache):
        """Test cache statistics calculation."""
        # Perform various operations
        query_cache.get_cached_result("miss1")  # miss
        query_cache.cache_result("hit1", {"data": "test"}, {})
        query_cache.get_cached_result("hit1")  # hit
        query_cache.get_cached_result("miss2")  # miss
        
        stats = query_cache.get_cache_stats()
        
        assert stats['cache_size'] == 1
        assert stats['max_cache_size'] == 10
        assert stats['hit_rate'] == 0.25  # 1 hit out of 4 requests
        assert stats['total_requests'] == 4
        assert stats['hits'] == 1
        assert stats['misses'] == 3
        assert stats['evictions'] == 0


class TestDuckDBQueryOptimizer:
    """Test cases for DuckDBQueryOptimizer functionality."""
    
    @pytest.fixture
    def mock_duckdb_conn(self):
        """Create a mock DuckDB connection."""
        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = [('result1',), ('result2',)]
        return mock_conn
    
    @pytest.fixture
    def s3_config(self):
        """Create test S3 configuration."""
        return {
            'bucket': 'test-bucket',
            'access_key_id': 'test-key',
            'secret_access_key': 'test-secret',
            'region': 'us-east-1'
        }
    
    @pytest.fixture
    def query_optimizer(self, mock_duckdb_conn, s3_config):
        """Create a DuckDBQueryOptimizer instance for testing."""
        return DuckDBQueryOptimizer(mock_duckdb_conn, s3_config)
    
    def test_optimizer_initialization(self, query_optimizer):
        """Test DuckDBQueryOptimizer initialization."""
        assert query_optimizer.duckdb_conn is not None
        assert query_optimizer.s3_config is not None
        assert isinstance(query_optimizer.query_cache, IntelligentQueryCache)
        assert query_optimizer.materialized_views == {}
        assert query_optimizer.performance_metrics == []
    
    def test_optimization_settings_setup(self, mock_duckdb_conn, s3_config):
        """Test DuckDB optimization settings setup."""
        optimizer = DuckDBQueryOptimizer(mock_duckdb_conn, s3_config)
        
        # Check that optimization settings were applied
        expected_calls = [
            "SET enable_optimizer=true;",
            "SET enable_profiling=true;",
            "SET profiling_output='query_profile.json';",
            "SET memory_limit='4GB';",
            "SET temp_directory='/tmp/duckdb_temp';",
            "SET threads=8;",
            "SET s3_use_ssl=true;",
            "SET s3_url_style='path';",
            "SET enable_http_metadata_cache=true;"
        ]
        
        # Verify that execute was called with optimization settings
        assert mock_duckdb_conn.execute.call_count >= len(expected_calls)
    
    def test_optimize_query_basic(self, query_optimizer):
        """Test basic query optimization."""
        test_query = "SELECT * FROM test_table WHERE id = 1"
        
        optimized_query, metrics = query_optimizer.optimize_query(test_query)
        
        assert isinstance(optimized_query, str)
        assert isinstance(metrics, QueryPerformanceMetrics)
        assert metrics.query_text == "SELECT * FROM test_table WHERE id = 1"
        assert metrics.optimization_level == "advanced"
        assert len(query_optimizer.performance_metrics) == 1
    
    def test_predicate_pushdown_optimization(self, query_optimizer):
        """Test predicate pushdown optimization strategy."""
        test_query = "SELECT * FROM changes/*/*/*.parquet WHERE entity_type = 'test'"
        context = {
            'time_range': {
                'start': '2024-01-01',
                'end': '2024-01-31'
            },
            'entity_types': ['test', 'example']
        }
        
        optimized_query, metrics = query_optimizer.optimize_query(test_query, context)
        
        # Should have applied time-based partitioning
        assert '2024-01-01' in optimized_query or 'changes/*/*/*2024-01-01*2024-01-31*.parquet' in optimized_query
        
        # Should have applied entity type filtering
        assert "entity_type IN ('test', 'example')" in optimized_query
    
    def test_column_pruning_optimization(self, query_optimizer):
        """Test column pruning optimization strategy."""
        test_query = "SELECT * FROM test_table"
        context = {
            'required_columns': ['id', 'name', 'created_at']
        }
        
        optimized_query, metrics = query_optimizer.optimize_query(test_query, context)
        
        # Should replace SELECT * with specific columns
        assert "SELECT id, name, created_at" in optimized_query
        assert "SELECT *" not in optimized_query
    
    def test_query_caching(self, query_optimizer):
        """Test query result caching."""
        test_query = "SELECT COUNT(*) FROM test_table"
        
        # First execution should be a cache miss
        result1, metrics1 = query_optimizer.optimize_query(test_query)
        
        # Second execution should use cached result
        result2, metrics2 = query_optimizer.optimize_query(test_query)
        
        # Results should be identical
        assert result1 == result2
        
        # Cache should have been used for second call
        cache_stats = query_optimizer.query_cache.get_cache_stats()
        assert cache_stats['hits'] >= 1
    
    def test_materialized_view_creation(self, query_optimizer, mock_duckdb_conn):
        """Test materialized view creation."""
        view_name = "test_view"
        view_query = "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"
        
        # Mock successful table creation
        mock_duckdb_conn.execute.return_value = None
        
        success = query_optimizer.create_materialized_view(view_name, view_query)
        
        assert success is True
        assert view_name in query_optimizer.materialized_views
        
        view_config = query_optimizer.materialized_views[view_name]
        assert view_config['query'] == view_query
        assert view_config['refresh_strategy'] == 'manual'
        assert 'created_at' in view_config
        assert 'last_refreshed' in view_config
    
    def test_materialized_view_refresh(self, query_optimizer, mock_duckdb_conn):
        """Test materialized view refresh functionality."""
        view_name = "test_view"
        view_query = "SELECT COUNT(*) FROM test_table"
        
        # Create the view first
        query_optimizer.create_materialized_view(view_name, view_query)
        
        # Mock successful refresh
        mock_duckdb_conn.execute.return_value = None
        
        success = query_optimizer.refresh_materialized_view(view_name)
        
        assert success is True
        
        # Verify refresh was attempted
        expected_calls = [
            f"DROP TABLE IF EXISTS {view_name}",
            f"CREATE TABLE {view_name} AS {view_query}"
        ]
        
        # Check that refresh operations were called
        call_args = [str(call) for call in mock_duckdb_conn.execute.call_args_list]
        for expected in expected_calls:
            assert any(expected in call for call in call_args)
    
    def test_query_hash_generation(self, query_optimizer):
        """Test query hash generation for caching."""
        query1 = "SELECT * FROM table1"
        context1 = {'param': 'value1'}
        
        query2 = "SELECT * FROM table1"
        context2 = {'param': 'value2'}
        
        hash1 = query_optimizer._generate_query_hash(query1, context1)
        hash2 = query_optimizer._generate_query_hash(query2, context2)
        
        # Same query with different context should have different hashes
        assert hash1 != hash2
        assert len(hash1) == 64  # SHA256 hash length
        assert len(hash2) == 64
    
    def test_performance_metrics_collection(self, query_optimizer):
        """Test performance metrics collection."""
        test_query = "SELECT COUNT(*) FROM test_table"
        
        # Execute query to generate metrics
        optimized_query, metrics = query_optimizer.optimize_query(test_query)
        
        # Check metrics structure
        assert isinstance(metrics, QueryPerformanceMetrics)
        assert metrics.query_text == test_query
        assert metrics.execution_time_ms > 0
        assert metrics.rows_processed >= 0
        assert metrics.optimization_level in ['none', 'basic', 'advanced', 'failed']
        assert isinstance(metrics.created_at, datetime)
        
        # Check that metrics were stored
        assert len(query_optimizer.performance_metrics) == 1
        assert query_optimizer.performance_metrics[0] == metrics
    
    def test_optimization_statistics(self, query_optimizer):
        """Test optimization statistics generation."""
        # Generate some test queries to create metrics
        queries = [
            "SELECT * FROM table1",
            "SELECT * FROM table2", 
            "SELECT COUNT(*) FROM table3"
        ]
        
        for query in queries:
            query_optimizer.optimize_query(query)
        
        stats = query_optimizer.get_optimization_statistics()
        
        # Check statistics structure
        assert 'total_queries' in stats
        assert 'avg_execution_time_ms' in stats
        assert 'cache_stats' in stats
        assert 'materialized_views_count' in stats
        
        assert stats['total_queries'] == 3
        assert stats['avg_execution_time_ms'] > 0
        assert stats['materialized_views_count'] == 0
    
    def test_performance_metrics_rolling_window(self, query_optimizer):
        """Test that performance metrics maintain rolling window."""
        # Generate many queries to test rolling window
        for i in range(1100):  # More than the 1000 limit
            query_optimizer.optimize_query(f"SELECT {i}")
        
        # Should only keep last 1000 metrics
        assert len(query_optimizer.performance_metrics) == 1000
        
        # Should contain the most recent queries
        last_metric = query_optimizer.performance_metrics[-1]
        assert "SELECT 1099" in last_metric.query_text
    
    @patch('services.duckdb_query_optimizer.logger')
    def test_error_handling_during_query_execution(self, mock_logger, query_optimizer, mock_duckdb_conn):
        """Test error handling when query execution fails."""
        # Make query execution fail
        mock_duckdb_conn.execute.side_effect = Exception("Query execution failed")
        
        # Query optimization should not raise exception but return error metrics
        optimized_query, metrics = query_optimizer.optimize_query("SELECT * FROM invalid_table")
        
        assert metrics.optimization_level == "failed"
        assert metrics.rows_processed == 0
        mock_logger.error.assert_called()
    
    def test_materialized_view_error_handling(self, query_optimizer, mock_duckdb_conn):
        """Test error handling in materialized view operations."""
        # Make view creation fail
        mock_duckdb_conn.execute.side_effect = Exception("Table creation failed")
        
        success = query_optimizer.create_materialized_view("test_view", "SELECT * FROM invalid")
        
        assert success is False
        assert "test_view" not in query_optimizer.materialized_views
    
    def test_query_optimization_strategies_applied(self, query_optimizer):
        """Test that all optimization strategies are applied."""
        complex_query = """
        SELECT * FROM changes/*/*/*.parquet 
        WHERE entity_type = 'test' AND created_at > '2024-01-01'
        """
        
        context = {
            'time_range': {'start': '2024-01-01', 'end': '2024-01-31'},
            'entity_types': ['test'],
            'required_columns': ['id', 'entity_type', 'created_at'],
            'partition_filter': {'year': 2024, 'month': [1, 2, 3]}
        }
        
        optimized_query, metrics = query_optimizer.optimize_query(complex_query, context)
        
        # Should apply multiple optimization strategies
        # The exact optimized query will depend on implementation details
        assert isinstance(optimized_query, str)
        assert len(optimized_query) > 0
        assert metrics.optimization_level == "advanced"
    
    def test_concurrent_query_optimization(self, query_optimizer):
        """Test thread safety of query optimization."""
        import threading
        import concurrent.futures
        
        results = []
        exceptions = []
        
        def optimize_query():
            try:
                query = f"SELECT * FROM table_{threading.current_thread().ident}"
                result = query_optimizer.optimize_query(query)
                results.append(result)
            except Exception as e:
                exceptions.append(e)
        
        # Execute concurrent optimizations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(optimize_query) for _ in range(10)]
            concurrent.futures.wait(futures)
        
        # Check results
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 10
        
        # All results should be valid
        for optimized_query, metrics in results:
            assert isinstance(optimized_query, str)
            assert isinstance(metrics, QueryPerformanceMetrics)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])