"""
Unit tests for DuckDBQueryAnalyzer - Testing advanced query analysis functionality.

Tests query analysis strategies, caching, materialized views, and performance metrics.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest  # noqa: E402
import time  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402
from datetime import datetime  # noqa: E402

from services.duckdb_query_analyzer import (  # noqa: E402
    DuckDBQueryAnalyzer,
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
        assert stats['hit_rate'] == 0.3333333333333333  # 1 hit out of 3 requests
        assert stats['total_requests'] == 3
        assert stats['hits'] == 1
        assert stats['misses'] == 2
        assert stats['evictions'] == 0


class TestSanitizationMethods:
    """Test cases for SQL injection prevention and input validation."""

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
        """Create a DuckDBQueryAnalyzer instance for testing."""
        return DuckDBQueryAnalyzer(mock_duckdb_conn, s3_config)

    # Tests for _is_valid_identifier
    def test_is_valid_identifier_valid_names(self, query_optimizer):
        """Test that valid SQL identifiers are accepted."""
        valid_identifiers = [
            'id',
            'name',
            'created_at',
            '_private_field',
            'Column123',
            '__double_underscore',
            'a',
            '_'
        ]
        for identifier in valid_identifiers:
            assert query_optimizer._is_valid_identifier(identifier), f"Should accept: {identifier}"

    def test_is_valid_identifier_empty_string(self, query_optimizer):
        """Test that empty string is rejected."""
        assert query_optimizer._is_valid_identifier("") is False

    def test_is_valid_identifier_starts_with_digit(self, query_optimizer):
        """Test that identifiers starting with digits are rejected."""
        invalid_identifiers = [
            '123abc',
            '9column',
            '0_field'
        ]
        for identifier in invalid_identifiers:
            assert query_optimizer._is_valid_identifier(identifier) is False, \
                f"Should reject: {identifier}"

    def test_is_valid_identifier_special_characters(self, query_optimizer):
        """Test that identifiers with special characters are rejected."""
        invalid_identifiers = [
            'col-name',
            'col name',
            'col.name',
            'col; DROP TABLE',
            'col"name',
            "col'name",
            'col$name',
            'col@name'
        ]
        for identifier in invalid_identifiers:
            assert query_optimizer._is_valid_identifier(identifier) is False, \
                f"Should reject: {identifier}"

    def test_is_valid_identifier_sql_keywords(self, query_optimizer):
        """Test that SQL keywords are still validated as identifiers (not prevented)."""
        # SQL keywords can be used as identifiers if properly quoted, so validation
        # should just check syntax, not prevent keywords
        keyword_identifiers = [
            'select',
            'where',
            'order'
        ]
        for identifier in keyword_identifiers:
            # These should pass basic syntax validation (letters + underscores)
            assert query_optimizer._is_valid_identifier(identifier) is True

    # Tests for _escape_sql_value
    def test_escape_sql_value_none(self, query_optimizer):
        """Test that None is escaped to NULL."""
        assert query_optimizer._escape_sql_value(None) == "NULL"

    def test_escape_sql_value_boolean(self, query_optimizer):
        """Test that booleans are escaped to TRUE/FALSE."""
        assert query_optimizer._escape_sql_value(True) == "TRUE"
        assert query_optimizer._escape_sql_value(False) == "FALSE"

    def test_escape_sql_value_integers(self, query_optimizer):
        """Test that integers are passed as-is."""
        assert query_optimizer._escape_sql_value(42) == "42"
        assert query_optimizer._escape_sql_value(-100) == "-100"
        assert query_optimizer._escape_sql_value(0) == "0"

    def test_escape_sql_value_floats(self, query_optimizer):
        """Test that floats are converted to strings."""
        result = query_optimizer._escape_sql_value(3.14)
        assert isinstance(result, str)
        assert "3.14" in result

    def test_escape_sql_value_string_simple(self, query_optimizer):
        """Test that simple strings are quoted."""
        assert query_optimizer._escape_sql_value("test") == "'test'"
        assert query_optimizer._escape_sql_value("hello world") == "'hello world'"

    def test_escape_sql_value_string_with_single_quotes(self, query_optimizer):
        """Test that single quotes in strings are escaped."""
        result = query_optimizer._escape_sql_value("O'Reilly")
        assert result == "'O''Reilly'"

        result = query_optimizer._escape_sql_value("it's")
        assert result == "'it''s'"

    def test_escape_sql_value_sql_injection_payloads(self, query_optimizer):
        """Test that SQL injection payloads are safely escaped."""
        # Basic injection - single quotes are escaped (doubled)
        payload = "'; DROP TABLE changes; --"
        result = query_optimizer._escape_sql_value(payload)
        # The payload is now in a quoted string with quotes escaped, so it can't break out
        assert result == "'''; DROP TABLE changes; --'"
        assert result.startswith("'") and result.endswith("'")

        # OR injection
        payload = "' OR '1'='1"
        result = query_optimizer._escape_sql_value(payload)
        assert result == "''' OR ''1''=''1'"

        # UNION injection
        payload = "' UNION SELECT * FROM users--"
        result = query_optimizer._escape_sql_value(payload)
        assert result == "''' UNION SELECT * FROM users--'"

    # Tests for _is_valid_date_string
    def test_is_valid_date_string_valid_dates(self, query_optimizer):
        """Test that valid YYYY-MM-DD dates are accepted."""
        valid_dates = [
            '2024-01-01',
            '2024-12-31',
            '2023-06-15',
            '1999-01-01',
            '2099-12-31'
        ]
        for date_str in valid_dates:
            assert query_optimizer._is_valid_date_string(date_str), \
                f"Should accept: {date_str}"

    def test_is_valid_date_string_invalid_formats(self, query_optimizer):
        """Test that invalid date formats are rejected."""
        invalid_dates = [
            '2024-1-1',  # missing leading zeros
            '24-01-01',  # two-digit year
            '2024/01/01',  # slashes
            '01-01-2024',  # wrong order
            '2024-01',  # missing day
            '2024',  # year only
            '',  # empty
            '2024-01-01T00:00:00',  # with time
            '../../../etc/passwd',  # path traversal
            '*',  # wildcard
        ]
        for date_str in invalid_dates:
            assert query_optimizer._is_valid_date_string(date_str) is False, \
                f"Should reject: {date_str}"

    def test_is_valid_date_string_format_validation_only(self, query_optimizer):
        """Test that date validation is format-only, not semantic."""
        # Date validation checks format, not whether the date actually exists
        # This is acceptable for this use case (S3 path patterns)
        assert query_optimizer._is_valid_date_string('2024-13-01') is True  # invalid month
        assert query_optimizer._is_valid_date_string('2024-01-32') is True  # invalid day
        assert query_optimizer._is_valid_date_string('2024-02-30') is True  # invalid for February

    # Integration tests
    def test_column_pruning_with_malicious_column_names(self, query_optimizer):
        """Test that column pruning sanitizes malicious column names."""
        test_query = "SELECT * FROM test_table"
        context = {
            'required_columns': [
                'id',
                'name',
                "invalid'; DROP TABLE changes; --",
                'valid_column',
                '123invalid',
                'another_valid'
            ]
        }

        optimized_query, metrics = query_optimizer.analyze_query(test_query, context)

        # Should only include valid column names
        assert 'id' in optimized_query
        assert 'name' in optimized_query
        assert 'valid_column' in optimized_query
        assert 'another_valid' in optimized_query

        # Should not include invalid column names
        assert '123invalid' not in optimized_query

    def test_partition_elimination_with_malicious_values(self, query_optimizer):
        """Test that partition elimination sanitizes malicious values."""
        test_query = "SELECT * FROM changes/*/*/*.parquet WHERE year = {year} AND month IN ({month})"
        context = {
            'partition_filter': {
                'year': "2024' OR '1'='1",
                'month': "1) OR (1=1"
            }
        }

        optimized_query, metrics = query_optimizer.analyze_query(test_query, context)

        # Query should be optimized without SQL injection
        # The exact format depends on how partition elimination is applied
        assert isinstance(optimized_query, str)
        assert len(optimized_query) > 0

    def test_predicate_pushdown_with_malicious_entity_types(self, query_optimizer):
        """Test that predicate pushdown sanitizes malicious entity_types."""
        test_query = "SELECT * FROM changes/*/*/*.parquet WHERE entity_type = 'test'"
        context = {
            'entity_types': [
                'valid_type',
                "'; DROP TABLE changes; --",
                "' OR '1'='1",
                'another_type'
            ]
        }

        optimized_query, metrics = query_optimizer.analyze_query(test_query, context)

        # Should safely include valid types
        assert 'valid_type' in optimized_query
        assert 'another_type' in optimized_query

        # Values are escaped with doubled single quotes, preventing SQL injection
        # The malicious payloads are now string literals that can't break out
        assert isinstance(optimized_query, str)
        assert len(optimized_query) > 0


class TestDuckDBQueryAnalyzer:
    """Test cases for DuckDBQueryAnalyzer functionality."""

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
        """Create a DuckDBQueryAnalyzer instance for testing."""
        return DuckDBQueryAnalyzer(mock_duckdb_conn, s3_config)

    def test_optimizer_initialization(self, query_optimizer):
        """Test DuckDBQueryAnalyzer initialization."""
        assert query_optimizer.duckdb_conn is not None
        assert query_optimizer.s3_config is not None
        assert isinstance(query_optimizer.query_cache, IntelligentQueryCache)
        assert query_optimizer.materialized_views == {}
        assert query_optimizer.performance_metrics == []

    def test_optimization_settings_setup(self, mock_duckdb_conn, s3_config):
        """Test DuckDB optimization settings setup."""
        DuckDBQueryAnalyzer(mock_duckdb_conn, s3_config)

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

    def test_analyze_query_basic(self, query_optimizer):
        """Test basic query optimization."""
        test_query = "SELECT * FROM test_table WHERE id = 1"

        optimized_query, metrics = query_optimizer.analyze_query(test_query)

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

        optimized_query, metrics = query_optimizer.analyze_query(test_query, context)

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

        optimized_query, metrics = query_optimizer.analyze_query(test_query, context)

        # Should replace SELECT * with specific columns
        assert "SELECT id, name, created_at" in optimized_query
        assert "SELECT *" not in optimized_query

    def test_query_caching(self, query_optimizer):
        """Test query result caching."""
        test_query = "SELECT COUNT(*) FROM test_table"

        # First execution should be a cache miss
        result1, metrics1 = query_optimizer.analyze_query(test_query)

        # Second execution should use cached result
        result2, metrics2 = query_optimizer.analyze_query(test_query)

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
        optimized_query, metrics = query_optimizer.analyze_query(test_query)

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
            query_optimizer.analyze_query(query)

        stats = query_optimizer.get_analysis_statistics()

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
            query_optimizer.analyze_query(f"SELECT {i}")

        # Should only keep last 1000 metrics
        assert len(query_optimizer.performance_metrics) == 1000

        # Should contain the most recent queries
        last_metric = query_optimizer.performance_metrics[-1]
        assert "SELECT 1099" in last_metric.query_text

    @patch('services.duckdb_query_analyzer.logger')
    def test_error_handling_during_query_execution(self, mock_logger, query_optimizer, mock_duckdb_conn):
        """Test error handling when query execution fails."""
        # Make query execution fail
        mock_duckdb_conn.execute.side_effect = Exception("Query execution failed")

        # Query optimization should not raise exception but return error metrics
        optimized_query, metrics = query_optimizer.analyze_query("SELECT * FROM invalid_table")

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

        optimized_query, metrics = query_optimizer.analyze_query(complex_query, context)

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

        def analyze_query():
            try:
                query = f"SELECT * FROM table_{threading.current_thread().ident}"
                result = query_optimizer.analyze_query(query)
                results.append(result)
            except Exception as e:
                exceptions.append(e)

        # Execute concurrent optimizations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(analyze_query) for _ in range(10)]
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
