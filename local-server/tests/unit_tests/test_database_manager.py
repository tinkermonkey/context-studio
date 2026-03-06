"""
Unit tests for DatabaseManager - Testing enhanced database management functionality.  # noqa: E501

Tests connection pooling strategies, health monitoring, performance optimization,  # noqa: E501
and resource cleanup.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: E501
)

import pytest  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.pool import NullPool, StaticPool  # noqa: E402

from database.utils import (  # noqa: E402
    DatabaseManager,
    PoolStrategy,
    PoolConfiguration,
    ConnectionMetrics,
    get_database_manager,
    cleanup_database_resources,
)


class TestDatabaseManager:
    """Test cases for DatabaseManager functionality."""

    @pytest.fixture
    def database_manager(self):
        """Create a fresh DatabaseManager instance for testing."""
        return DatabaseManager()

    @pytest.fixture
    def test_db_url(self):
        """Create a test database URL."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        # Clean up the file so SQLite can create it fresh
        os.unlink(db_path)
        return f"sqlite:///{db_path}"

    @pytest.fixture
    def memory_db_url(self):
        """Create an in-memory database URL."""
        return "sqlite:///:memory:"

    def test_database_manager_initialization(self, database_manager):
        """Test DatabaseManager initialization."""
        assert isinstance(database_manager.metrics, ConnectionMetrics)
        assert len(database_manager._engines) == 0
        assert len(database_manager._session_locals) == 0
        assert database_manager._health_check_interval == 30
        assert database_manager._loaded_connections == {}
        assert database_manager._connection_lifecycles == {}

    def test_get_optimal_pool_strategy(self, database_manager):
        """Test optimal pool strategy selection."""
        # SQLite file database should use NULL_POOL
        strategy = database_manager.get_optimal_pool_strategy("sqlite:///test.db")  # noqa: E501
        assert strategy == PoolStrategy.NULL_POOL

        # SQLite in-memory should use STATIC_POOL
        strategy = database_manager.get_optimal_pool_strategy("sqlite:///:memory:")  # noqa: E501
        assert strategy == PoolStrategy.STATIC_POOL

        # PostgreSQL should use QUEUE_POOL
        strategy = database_manager.get_optimal_pool_strategy(
            "postgresql://user:pass@host/db"
        )
        assert strategy == PoolStrategy.QUEUE_POOL

    def test_get_pool_configuration(self, database_manager):
        """Test pool configuration generation."""
        # SQLite configuration
        config = database_manager.get_pool_configuration("sqlite:///test.db")
        assert isinstance(config, PoolConfiguration)
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
        assert config.pool_pre_ping is True

        # Should have SQLite-specific connect_args
        assert "check_same_thread" in config.connect_args
        assert "timeout" in config.connect_args
        assert "isolation_level" in config.connect_args

        # Non-SQLite configuration
        config = database_manager.get_pool_configuration("postgresql://test")
        assert config.connect_args == {}  # Should be empty for non-SQLite

    def test_create_optimized_engine_sqlite_file(self, database_manager, test_db_url):  # noqa: E501
        """Test optimized engine creation for SQLite file database."""
        engine = database_manager.create_optimized_engine(test_db_url, "test_engine")  # noqa: E501

        assert engine is not None
        assert "test_engine" in database_manager._engines
        assert "test_engine" in database_manager._session_locals

        # Should use NullPool for SQLite file databases
        assert isinstance(engine.pool, NullPool)

        # Test that same engine ID returns cached engine
        engine2 = database_manager.create_optimized_engine(test_db_url, "test_engine")  # noqa: E501
        assert engine is engine2

        # Cleanup
        engine.dispose()

    def test_create_optimized_engine_sqlite_memory(
        self, database_manager, memory_db_url
    ):
        """Test optimized engine creation for SQLite in-memory database."""
        engine = database_manager.create_optimized_engine(
            memory_db_url, "memory_engine"
        )

        assert engine is not None
        assert "memory_engine" in database_manager._engines

        # Should use StaticPool for in-memory databases
        assert isinstance(engine.pool, StaticPool)

        # Cleanup
        engine.dispose()

    def test_create_optimized_engine_custom_config(self, database_manager, test_db_url):  # noqa: E501
        """Test engine creation with custom pool configuration."""
        custom_config = PoolConfiguration(
            pool_size=10,
            max_overflow=20,
            pool_timeout=60,
            pool_recycle=7200,
            pool_pre_ping=False,
        )

        engine = database_manager.create_optimized_engine(
            test_db_url, "custom_engine", custom_config
        )

        assert engine is not None
        assert "custom_engine" in database_manager._engines

        # Cleanup
        engine.dispose()

    def test_get_optimized_session_context_manager(self, database_manager, test_db_url):  # noqa: E501
        """Test optimized session context manager."""
        engine_id = "session_test"

        # Create engine first
        database_manager.create_optimized_engine(test_db_url, engine_id)

        # Test context manager
        with database_manager.get_optimized_session(engine_id) as session:
            assert session is not None
            # Test basic query
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1
            # Session should be active during context
            assert session.is_active is True

        # After context manager, session should be closed (but may still be active)  # noqa: E501
        # The important thing is that it's no longer bound to a transaction
        assert not session.in_transaction()

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_get_optimized_session_auto_create_engine(
        self, database_manager, test_db_url
    ):
        """Test auto-creation of engine when not found."""
        engine_id = "auto_create_test"

        with database_manager.get_optimized_session(engine_id, test_db_url) as session:  # noqa: E501
            assert session is not None
            # Engine should have been created automatically
            assert engine_id in database_manager._engines

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_get_session_factory(self, database_manager, test_db_url):
        """Test session factory retrieval."""
        engine_id = "factory_test"

        # No factory should exist initially
        factory = database_manager.get_session_factory(engine_id)
        assert factory is None

        # Create engine
        database_manager.create_optimized_engine(test_db_url, engine_id)

        # Factory should now exist
        factory = database_manager.get_session_factory(engine_id)
        assert factory is not None

        # Test creating session from factory
        session = factory()
        assert session is not None
        session.close()

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_perform_health_check(self, database_manager, test_db_url):
        """Test health check functionality."""
        # Create engine
        engine_id = "health_test"
        database_manager.create_optimized_engine(test_db_url, engine_id)

        # Perform health check
        health_status = database_manager.perform_health_check()

        # Check structure
        required_keys = [
            "timestamp",
            "overall_status",
            "engines",
            "metrics",
            "warnings",
            "errors",
        ]
        for key in required_keys:
            assert key in health_status

        # Should be healthy initially
        assert health_status["overall_status"] == "healthy"

        # Should have engine health info
        assert engine_id in health_status["engines"]
        engine_health = health_status["engines"][engine_id]
        assert "status" in engine_health
        assert "response_time_ms" in engine_health

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_health_check_caching(self, database_manager, test_db_url):
        """Test health check result caching."""
        # Create engine
        engine_id = "cache_test"
        database_manager.create_optimized_engine(test_db_url, engine_id)

        # First health check
        health1 = database_manager.perform_health_check()
        timestamp1 = health1["timestamp"]

        # Immediate second health check should return cached result
        health2 = database_manager.perform_health_check()
        timestamp2 = health2["timestamp"]

        assert timestamp1 == timestamp2  # Should be same cached result

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_metrics_summary(self, database_manager, test_db_url):
        """Test metrics summary generation."""
        # Create engine and do some operations
        engine_id = "metrics_test"
        database_manager.create_optimized_engine(test_db_url, engine_id)

        # Use session to generate metrics
        with database_manager.get_optimized_session(engine_id) as session:
            session.execute(text("SELECT 1"))

        # Get metrics
        metrics = database_manager._get_metrics_summary()

        required_keys = [
            "total_connections_created",
            "active_connections",
            "peak_connections",
            "pool_hits",
            "pool_misses",
            "connection_errors",
            "avg_connection_time_ms",
            "total_queries_executed",
            "avg_query_time_ms",
            "uptime_seconds",
            "pool_efficiency_percent",
        ]

        for key in required_keys:
            assert key in metrics
            assert isinstance(metrics[key], (int, float))

        # Should have some activity
        assert metrics["total_connections_created"] >= 1

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_optimize_for_workload(self, database_manager, test_db_url):
        """Test workload optimization."""
        # Create engine
        engine_id = "workload_test"
        database_manager.create_optimized_engine(test_db_url, engine_id)

        # Test different workload optimizations
        workload_types = ["read_heavy", "write_heavy", "analytics", "mixed"]

        for workload in workload_types:
            result = database_manager.optimize_for_workload(workload)

            assert "workload_type" in result
            assert "optimizations_applied" in result
            assert "timestamp" in result
            assert result["workload_type"] == workload
            assert isinstance(result["optimizations_applied"], list)

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_cleanup_resources(self, database_manager, test_db_url):
        """Test resource cleanup."""
        # Create multiple engines
        engine_ids = ["cleanup_test1", "cleanup_test2"]
        for engine_id in engine_ids:
            database_manager.create_optimized_engine(test_db_url, engine_id)

        assert len(database_manager._engines) == 2
        assert len(database_manager._session_locals) == 2

        # Cleanup
        database_manager.cleanup_resources()

        # Everything should be cleaned up
        assert len(database_manager._engines) == 0
        assert len(database_manager._session_locals) == 0
        assert len(database_manager._loaded_connections) == 0
        assert len(database_manager._connection_lifecycles) == 0

    def test_get_performance_report(self, database_manager, test_db_url):
        """Test performance report generation."""
        # Create engine and generate some activity
        engine_id = "perf_test"
        database_manager.create_optimized_engine(test_db_url, engine_id)

        with database_manager.get_optimized_session(engine_id) as session:
            session.execute(text("SELECT 1"))

        # Get performance report
        report = database_manager.get_performance_report()

        required_keys = [
            "report_timestamp",
            "health_status",
            "performance_metrics",
            "active_engines",
            "recommendations",
        ]
        for key in required_keys:
            assert key in report

        assert engine_id in report["active_engines"]
        assert isinstance(report["recommendations"], list)

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_generate_performance_recommendations(self, database_manager, test_db_url):  # noqa: E501
        """Test performance recommendation generation with actual database activity."""  # noqa: E501
        # Create engine and generate some database activity
        engine_id = "recommendations_test"
        database_manager.create_optimized_engine(test_db_url, engine_id)

        # Reset metrics for clean start
        database_manager.metrics.reset()

        # Generate some database activity to create realistic metrics
        with database_manager.get_optimized_session(engine_id) as session:
            # Execute several queries to generate pool activity
            for _ in range(10):
                session.execute(text("SELECT 1"))

        # Artificially improve metrics to get optimal recommendation
        # Set good pool efficiency (above 80% threshold)
        database_manager.metrics.pool_hits = 15
        database_manager.metrics.pool_misses = 2  # 88% hit rate

        # Set reasonable performance metrics
        database_manager.metrics.avg_connection_time_ms = 50  # Below 100ms threshold  # noqa: E501
        database_manager.metrics.avg_query_time_ms = 25  # Below 50ms threshold
        database_manager.metrics.peak_connections = 5  # Below 50 threshold

        # Get recommendations
        recommendations = database_manager._generate_performance_recommendations()  # noqa: E501

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # With good metrics across the board, should get optimal recommendation
        assert "Database performance is optimal" in recommendations

        # Cleanup
        database_manager._engines[engine_id].dispose()

    def test_thread_safety(self, database_manager, test_db_url):
        """Test thread safety of database manager operations."""
        results = []
        exceptions = []

        def create_engine_and_session():
            try:
                engine_id = f"thread_test_{threading.current_thread().ident}"
                database_manager.create_optimized_engine(test_db_url, engine_id)  # noqa: E501

                with database_manager.get_optimized_session(engine_id) as session:  # noqa: E501
                    result = session.execute(text("SELECT 1")).scalar()
                    results.append(result)

                # Cleanup
                database_manager._engines[engine_id].dispose()

            except Exception as e:
                exceptions.append(e)

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_engine_and_session)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 5
        assert all(result == 1 for result in results)


class TestConnectionMetrics:
    """Test cases for ConnectionMetrics data structure."""

    def test_metrics_initialization(self):
        """Test ConnectionMetrics initialization."""
        metrics = ConnectionMetrics()

        assert metrics.total_connections_created == 0
        assert metrics.active_connections == 0
        assert metrics.peak_connections == 0
        assert metrics.pool_hits == 0
        assert metrics.pool_misses == 0
        assert metrics.connection_errors == 0
        assert metrics.avg_connection_time_ms == 0.0
        assert metrics.total_queries_executed == 0
        assert metrics.avg_query_time_ms == 0.0
        assert metrics.last_reset_time is not None

    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        metrics = ConnectionMetrics()

        # Set some values
        metrics.total_connections_created = 10
        metrics.active_connections = 5
        metrics.pool_hits = 20

        # Reset
        metrics.reset()

        # Should be back to initial state
        assert metrics.total_connections_created == 0
        assert metrics.active_connections == 0
        assert metrics.pool_hits == 0


class TestPoolConfiguration:
    """Test cases for PoolConfiguration data structure."""

    def test_pool_configuration_defaults(self):
        """Test PoolConfiguration default values."""
        config = PoolConfiguration()

        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
        assert config.pool_pre_ping is True
        assert config.connect_args == {}

    def test_pool_configuration_custom_values(self):
        """Test PoolConfiguration with custom values."""
        custom_args = {"check_same_thread": False}
        config = PoolConfiguration(
            pool_size=20,
            max_overflow=30,
            pool_timeout=60,
            pool_recycle=7200,
            pool_pre_ping=False,
            connect_args=custom_args,
        )

        assert config.pool_size == 20
        assert config.max_overflow == 30
        assert config.pool_timeout == 60
        assert config.pool_recycle == 7200
        assert config.pool_pre_ping is False
        assert config.connect_args == custom_args


class TestGlobalDatabaseManager:
    """Test cases for global database manager functions."""

    def test_get_database_manager_singleton(self):
        """Test global database manager singleton behavior."""
        # Get manager multiple times
        manager1 = get_database_manager()
        manager2 = get_database_manager()

        # Should be same instance
        assert manager1 is manager2
        assert isinstance(manager1, DatabaseManager)

    def test_cleanup_database_resources(self):
        """Test global cleanup function."""
        # Start with a clean slate
        cleanup_database_resources()

        # Get fresh manager and create some engines
        manager = get_database_manager()
        original_manager_id = id(manager)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        os.unlink(db_path)
        test_db_url = f"sqlite:///{db_path}"

        # Create test engine
        manager.create_optimized_engine(test_db_url, "cleanup_global_test")

        # Should have our test engine
        assert "cleanup_global_test" in manager._engines
        len(manager._engines)

        # Perform cleanup
        cleanup_database_resources()

        # Check that the global manager reference was cleared
        import database.utils

        assert (
            database.utils._database_manager is None
        ), "Global database manager should be None after cleanup"

        # Get new manager - should be a different instance
        new_manager = get_database_manager()
        new_manager_id = id(new_manager)

        # Should be a different instance and should start clean
        assert (
            new_manager_id != original_manager_id
        ), "Should get a new manager instance after cleanup"
        assert (
            len(new_manager._engines) == 0
        ), f"New manager should be clean, but has engines: {list(new_manager._engines.keys())}"  # noqa: E501


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
