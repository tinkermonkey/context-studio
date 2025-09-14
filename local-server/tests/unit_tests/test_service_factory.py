"""
Unit tests for ServiceFactory - Testing the service factory pattern implementation.

Tests service caching, metrics tracking, performance optimization, and thread safety.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import time
import threading
from unittest.mock import Mock, patch

from services.service_factory import (
    ServiceFactory,
    ServiceType,
    ServiceMetrics,
    CachedServiceEntry,
)
from services.node_service import NodeService
from services.node_link_service import NodeLinkService


class TestServiceFactory:
    """Test cases for ServiceFactory functionality."""

    @pytest.fixture
    def service_factory(self):
        """Create a ServiceFactory instance for testing."""
        return ServiceFactory(cache_ttl_seconds=60, cleanup_interval=10)

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()

    def test_service_factory_initialization(self, service_factory):
        """Test ServiceFactory initialization."""
        assert service_factory._cache_ttl == 60
        assert service_factory._cleanup_interval == 10
        assert len(service_factory._cache) == 0
        assert len(service_factory._metrics) == len(ServiceType)

        # Check all service types have metrics initialized
        for service_type in ServiceType:
            assert service_type.value in service_factory._metrics
            assert isinstance(
                service_factory._metrics[service_type.value], ServiceMetrics
            )

    def test_create_node_service(self, service_factory, mock_db_session):
        """Test NodeService creation and caching."""
        # First call should create new service
        service1 = service_factory.create_node_service(mock_db_session)
        assert isinstance(service1, NodeService)

        # Check metrics
        stats = service_factory.get_cache_stats()
        node_metrics = stats["service_metrics"]["node_service"]
        assert node_metrics["total_created"] == 1
        assert node_metrics["cache_misses"] == 1
        assert node_metrics["cache_hits"] == 0

        # Second call should use cache (same class, different instance)
        service2 = service_factory.create_node_service(mock_db_session)
        assert isinstance(service2, NodeService)
        assert service1 is not service2  # Different instances

        # Check updated metrics
        stats = service_factory.get_cache_stats()
        node_metrics = stats["service_metrics"]["node_service"]
        assert node_metrics["total_created"] == 2
        assert node_metrics["cache_hits"] == 1
        assert node_metrics["cache_misses"] == 1

    def test_create_node_link_service(self, service_factory, mock_db_session):
        """Test NodeLinkService creation and caching."""
        service = service_factory.create_node_link_service(mock_db_session)
        assert isinstance(service, NodeLinkService)

        # Check metrics
        stats = service_factory.get_cache_stats()
        link_metrics = stats["service_metrics"]["node_link_service"]
        assert link_metrics["total_created"] == 1
        assert link_metrics["cache_misses"] == 1

    def test_service_caching_with_ttl(self, mock_db_session):
        """Test service cache expiration based on TTL."""
        # Create factory with very short TTL
        factory = ServiceFactory(cache_ttl_seconds=0.1, cleanup_interval=1)

        # Create service
        service1 = factory.create_node_service(mock_db_session)
        stats = factory.get_cache_stats()
        assert len(stats["cache_entries"]) == 1

        # Wait for cache to expire
        time.sleep(0.2)

        # Next creation should miss cache due to expiration
        service2 = factory.create_node_service(mock_db_session)
        stats = factory.get_cache_stats()
        node_metrics = stats["service_metrics"]["node_service"]
        assert node_metrics["cache_misses"] == 2  # Both were misses due to expiration

    def test_cache_cleanup(self, mock_db_session):
        """Test automatic cache cleanup."""
        factory = ServiceFactory(cache_ttl_seconds=0.1, cleanup_interval=1)

        # Create multiple services
        factory.create_node_service(mock_db_session)
        factory.create_node_link_service(mock_db_session)

        stats = factory.get_cache_stats()
        assert len(stats["cache_entries"]) == 2

        # Wait for entries to expire
        time.sleep(0.2)

        # Force cleanup
        cleaned_count = factory.force_cleanup()
        assert cleaned_count == 2

        stats = factory.get_cache_stats()
        assert len(stats["cache_entries"]) == 0

    def test_cache_stats_structure(self, service_factory, mock_db_session):
        """Test cache statistics structure and data."""
        # Create some services
        service_factory.create_node_service(mock_db_session)
        service_factory.create_node_link_service(mock_db_session)

        stats = service_factory.get_cache_stats()

        # Check top-level structure
        required_keys = [
            "factory_id",
            "cache_ttl_seconds",
            "cleanup_interval_seconds",
            "total_cache_entries",
            "cache_entries",
            "service_metrics",
        ]
        for key in required_keys:
            assert key in stats

        # Check service metrics structure
        assert "node_service" in stats["service_metrics"]
        assert "node_link_service" in stats["service_metrics"]

        node_metrics = stats["service_metrics"]["node_service"]
        required_metric_keys = [
            "total_created",
            "cache_hits",
            "cache_misses",
            "cache_hit_rate_percent",
            "avg_creation_time_ms",
        ]
        for key in required_metric_keys:
            assert key in node_metrics

    def test_performance_summary(self, service_factory, mock_db_session):
        """Test performance summary generation."""
        # Create some services to generate metrics
        service_factory.create_node_service(mock_db_session)
        service_factory.create_node_service(mock_db_session)  # Cache hit
        service_factory.create_node_link_service(mock_db_session)

        summary = service_factory.get_performance_summary()

        required_keys = [
            "factory_id",
            "overall_cache_hit_rate_percent",
            "total_services_created",
            "total_cache_entries",
            "best_performing_service",
            "worst_performing_service",
        ]
        for key in required_keys:
            assert key in summary

        # Should have created 3 services total
        assert summary["total_services_created"] == 3

        # Should have 50% hit rate (1 hit out of 2 total requests for node_service)
        assert summary["overall_cache_hit_rate_percent"] > 0

    def test_health_status(self, service_factory):
        """Test health status monitoring."""
        health = service_factory.get_health_status()

        required_keys = [
            "factory_id",
            "status",
            "issues",
            "cache_size",
            "last_cleanup_age_seconds",
            "checked_at",
        ]
        for key in required_keys:
            assert key in health

        # New factory should be healthy
        assert health["status"] == "healthy"
        assert len(health["issues"]) == 0

    def test_clear_cache(self, service_factory, mock_db_session):
        """Test cache clearing functionality."""
        # Create services
        service_factory.create_node_service(mock_db_session)
        service_factory.create_node_link_service(mock_db_session)

        stats_before = service_factory.get_cache_stats()
        assert len(stats_before["cache_entries"]) == 2

        # Clear cache
        service_factory.clear_cache()

        stats_after = service_factory.get_cache_stats()
        assert len(stats_after["cache_entries"]) == 0

        # Metrics should be reset
        for service_metrics in stats_after["service_metrics"].values():
            assert service_metrics["cache_hits"] == 0
            assert service_metrics["cache_misses"] == 0

    def test_llm_service_caching_with_parameters(self, service_factory):
        """Test LLM service caching with different parameters."""
        # Create LLM services with different parameters
        llm1 = service_factory.create_llm_service(
            model_name="gpt-3.5-turbo", temperature=0.0
        )
        llm2 = service_factory.create_llm_service(
            model_name="gpt-3.5-turbo", temperature=0.5
        )
        llm3 = service_factory.create_llm_service(
            model_name="gpt-3.5-turbo", temperature=0.0
        )  # Same as llm1

        # Check that different parameters create separate cache entries
        stats = service_factory.get_cache_stats()
        cache_entries = stats["cache_entries"]

        # Should have 2 different cache entries for different configurations
        assert len(cache_entries) == 2

        # Third call with same params should be cache hit
        llm_metrics = stats["service_metrics"]["llm_service"]
        assert llm_metrics["total_created"] == 3
        assert llm_metrics["cache_hits"] == 1  # llm3 was a hit
        assert llm_metrics["cache_misses"] == 2  # llm1 and llm2 were misses

    @patch("services.service_factory.logger")
    def test_error_handling_during_service_creation(
        self, mock_logger, service_factory, mock_db_session
    ):
        """Test error handling when service creation fails."""
        # Mock the NodeService constructor to raise an exception during instantiation
        original_node_service = service_factory._create_service.__globals__['NodeService']

        class FailingNodeService:
            def __init__(self, *args, **kwargs):
                raise Exception("Service creation failed")

        # Patch NodeService in the service factory's scope
        with patch('services.service_factory.NodeService', FailingNodeService):
            with pytest.raises(Exception, match="Service creation failed"):
                service_factory.create_node_service(mock_db_session)

            # Cache should remain clean after failed creation
            stats = service_factory.get_cache_stats()
            assert len(stats["cache_entries"]) == 0

    def test_thread_safety(self, service_factory, mock_db_session):
        """Test thread safety of service factory operations."""
        results = []
        exceptions = []

        def create_service():
            try:
                service = service_factory.create_node_service(mock_db_session)
                results.append(service)
            except Exception as e:
                exceptions.append(e)

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_service)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 10

        # All results should be NodeService instances
        for result in results:
            assert isinstance(result, NodeService)

        # Cache should have been hit multiple times
        stats = service_factory.get_cache_stats()
        node_metrics = stats["service_metrics"]["node_service"]
        assert node_metrics["total_created"] == 10
        assert node_metrics["cache_hits"] >= 8  # Most should be cache hits

    def test_service_metrics_accuracy(self, service_factory, mock_db_session):
        """Test accuracy of service creation and timing metrics."""
        # Create services and measure timing
        start_time = time.time()

        # First call (cache miss)
        service1 = service_factory.create_node_service(mock_db_session)

        # Second call (cache hit)
        service2 = service_factory.create_node_service(mock_db_session)

        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000

        stats = service_factory.get_cache_stats()
        node_metrics = stats["service_metrics"]["node_service"]

        # Check counts
        assert node_metrics["total_created"] == 2
        assert node_metrics["cache_hits"] == 1
        assert node_metrics["cache_misses"] == 1
        assert node_metrics["cache_hit_rate_percent"] == 50.0

        # Average creation time should be reasonable
        assert 0 < node_metrics["avg_creation_time_ms"] < total_time_ms

        # Timestamps should be present
        assert node_metrics["last_created_at"] is not None
        assert node_metrics["last_accessed_at"] is not None


class TestServiceMetrics:
    """Test cases for ServiceMetrics data structure."""

    def test_metrics_initialization(self):
        """Test ServiceMetrics initialization."""
        metrics = ServiceMetrics("test_service")

        assert metrics.service_type == "test_service"
        assert metrics.total_created == 0
        assert metrics.total_cache_hits == 0
        assert metrics.total_cache_misses == 0
        assert metrics.avg_creation_time_ms == 0.0
        assert metrics.last_created_at is None
        assert metrics.last_accessed_at is None
        assert len(metrics.creation_times) == 0

    def test_record_creation(self):
        """Test recording service creation events."""
        metrics = ServiceMetrics("test_service")

        # Record first creation
        metrics.record_creation(50.0)

        assert metrics.total_created == 1
        assert metrics.avg_creation_time_ms == 50.0
        assert len(metrics.creation_times) == 1
        assert metrics.last_created_at is not None

        # Record second creation
        metrics.record_creation(100.0)

        assert metrics.total_created == 2
        assert metrics.avg_creation_time_ms == 75.0  # Average of 50 and 100
        assert len(metrics.creation_times) == 2

    def test_creation_times_rolling_window(self):
        """Test that creation times list is capped at 100 entries."""
        metrics = ServiceMetrics("test_service")

        # Add 150 creation times
        for i in range(150):
            metrics.record_creation(float(i))

        # Should only keep last 100
        assert len(metrics.creation_times) == 100
        assert metrics.creation_times[0] == 50.0  # First of last 100
        assert metrics.creation_times[-1] == 149.0  # Last entry

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        metrics = ServiceMetrics("test_service")

        # No requests yet
        assert metrics.cache_hit_rate == 0.0

        # Record some hits and misses
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()

        # Should be 66.67% hit rate (2 hits out of 3 total)
        assert abs(metrics.cache_hit_rate - 66.66666666666667) < 0.01

        # Add more misses
        metrics.record_cache_miss()
        metrics.record_cache_miss()

        # Should be 40% hit rate (2 hits out of 5 total)
        assert metrics.cache_hit_rate == 40.0


class TestCachedServiceEntry:
    """Test cases for CachedServiceEntry data structure."""

    def test_entry_initialization(self):
        """Test CachedServiceEntry initialization."""
        mock_class = Mock
        entry = CachedServiceEntry(
            service_class=mock_class,
            service_key="test_key",
            created_at=time.time(),
            creation_time_ms=25.5,
        )

        assert entry.service_class == mock_class
        assert entry.service_key == "test_key"
        assert entry.access_count == 0
        assert entry.last_accessed == 0
        assert entry.creation_time_ms == 25.5

    def test_touch_functionality(self):
        """Test touch method for access tracking."""
        entry = CachedServiceEntry(
            service_class=Mock, service_key="test_key", created_at=time.time()
        )

        assert entry.access_count == 0
        assert entry.last_accessed == 0

        # Touch the entry
        entry.touch()

        assert entry.access_count == 1
        assert entry.last_accessed > 0

        # Touch again
        first_access_time = entry.last_accessed
        time.sleep(0.01)  # Small delay
        entry.touch()

        assert entry.access_count == 2
        assert entry.last_accessed > first_access_time

    def test_age_calculation(self):
        """Test age calculation property."""
        created_time = time.time() - 10  # Created 10 seconds ago
        entry = CachedServiceEntry(
            service_class=Mock, service_key="test_key", created_at=created_time
        )

        age = entry.age_seconds
        assert 9.9 < age < 10.1  # Should be approximately 10 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
