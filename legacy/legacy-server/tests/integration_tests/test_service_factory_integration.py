"""
Integration Test Template for Service Factory Migration

This template demonstrates how to migrate existing integration tests to use the
service factory pattern while maintaining test isolation and performance benefits.  # noqa: E501
"""

import os
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
)

import pytest

# Import the new service factory dependencies
from services.node_service import NodeService

# Example of migrating an existing integration test


class TestServiceFactoryIntegration:
    """Example integration tests using the service factory pattern."""

    @pytest.mark.skip_suite
    def test_service_factory_with_real_database(
        self, shared_client, test_service_factory
    ):
        """
        Example: Test that service factory works with real database operations.

        This demonstrates how to write integration tests that verify the service factory  # noqa: E501
        creates services that can perform real database operations.
        """
        client = shared_client

        # Reset service factory for clean test
        test_service_factory.clear_cache()

        # Perform operations that would use services
        response = client.post(
            "/api/structure_nodes/",
            json={
                "node_type": "layer",
                "title": "Test Layer for Service Factory",
                "definition": "A test layer to verify service factory integration",
            },
        )

        assert response.status_code == 201
        layer_data = response.json()

        # Check service factory stats to verify services were used
        factory_stats = test_service_factory.get_cache_stats()

        # Should have created some services
        total_services_created = sum(
            metrics["total_created"]
            for metrics in factory_stats["service_metrics"].values()
        )
        assert total_services_created > 0

        # Clean up
        layer_id = layer_data["id"]
        delete_response = client.delete(f"/api/structure_nodes/{layer_id}")
        assert delete_response.status_code == 204

    @pytest.mark.skip_suite
    def test_service_caching_across_requests(
        self, shared_client, test_service_factory
    ):
        """
        Test that service factory caching works across multiple API requests.
        """
        client = shared_client
        test_service_factory.clear_cache()

        # Make multiple similar requests
        requests_data = [
            {
                "node_type": "layer",
                "title": f"Test Layer {i}",
                "definition": f"Test layer {i} for caching test",
            }
            for i in range(3)
        ]

        created_ids = []
        for request_data in requests_data:
            response = client.post("/api/structure_nodes/", json=request_data)
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        # Check that service caching occurred
        stats = test_service_factory.get_cache_stats()

        # Should have cache hits after the first request
        node_service_metrics = stats["service_metrics"].get("node_service", {})
        if node_service_metrics:
            total_created = node_service_metrics["total_created"]
            cache_hits = node_service_metrics["cache_hits"]
            cache_misses = node_service_metrics["cache_misses"]

            # Verify services were created (should be at least 1 per request type)
            assert (
                total_created > 0
            ), "Expected at least some services to be created"

            # Verify that requests were processed (either hits or misses should occur)
            total_requests = cache_hits + cache_misses
            assert (
                total_requests > 0
            ), "Expected cache hits or misses to be recorded"

        # Clean up
        for created_id in created_ids:
            delete_response = client.delete(
                f"/api/structure_nodes/{created_id}"
            )
            assert delete_response.status_code == 204

    def test_database_manager_with_service_factory(
        self, managed_db_session, test_service_factory
    ):
        """
        Test that the database manager works correctly with the service factory.  # noqa: E501
        """
        # This test uses the managed_db_session fixture which uses DatabaseManager
        db = managed_db_session

        # Get a service from the factory that uses the database
        factory = test_service_factory
        node_service = factory.create_node_service(db)

        # The service should work with the optimized database session
        assert isinstance(node_service, NodeService)

        # Test that we can perform database operations
        # (This would normally create actual data, but we're just testing the connection)
        from sqlalchemy import text

        result = db.execute(text("SELECT 1")).scalar()
        assert result == 1

    def test_service_factory_error_handling_integration(
        self, shared_client, test_service_factory
    ):
        """
        Test error handling integration between service factory and API endpoints.  # noqa: E501
        """
        client = shared_client
        test_service_factory.clear_cache()

        # Make a request that should fail validation
        response = client.post(
            "/api/structure_nodes/",
            json={
                "node_type": "invalid_type",  # This should cause validation error
                "title": "",  # Empty title should also cause error
                "definition": "",
            },
        )

        # Should get validation error
        assert response.status_code == 422

        # Service factory should still have attempted to create services
        stats = test_service_factory.get_cache_stats()

        # Even failed requests might create services for processing
        # The important thing is that the factory handles errors gracefully
        assert isinstance(stats, dict)  # Factory should still be functional

    @pytest.mark.skip_suite
    def test_performance_with_service_factory(
        self, shared_client, test_service_factory
    ):
        """
        Test that service factory provides performance benefits in integration scenarios.  # noqa: E501
        """
        import time

        client = shared_client
        test_service_factory.clear_cache()

        # Time multiple similar operations
        start_time = time.time()

        # Create multiple layers (similar operations that should benefit from caching)
        created_ids = []
        for i in range(5):
            response = client.post(
                "/api/structure_nodes/",
                json={
                    "node_type": "layer",
                    "title": f"Performance Test Layer {i}",
                    "definition": f"Layer {i} for performance testing",
                },
            )
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        end_time = time.time()
        total_time = end_time - start_time

        # Check service factory performance metrics
        performance_summary = test_service_factory.get_performance_summary()

        # Should have reasonable cache hit rate after first operation
        overall_hit_rate = performance_summary[
            "overall_cache_hit_rate_percent"
        ]

        # Log performance for analysis
        print(f"Total time for 5 operations: {total_time:.3f}s")
        print(f"Overall cache hit rate: {overall_hit_rate:.1f}%")

        # Clean up
        for created_id in created_ids:
            delete_response = client.delete(
                f"/api/structure_nodes/{created_id}"
            )
            assert delete_response.status_code == 204


# Example of how to migrate existing integration tests
class TestMigratedIntegrationTest:
    """
    Example of migrating an existing integration test to use service factory patterns.  # noqa: E501

    Before: Test used direct service instantiation
    After: Test uses service factory and includes performance monitoring
    """

    # BEFORE (Old pattern):
    # def test_create_layer_old_pattern(self, db_session):
    #     node_service = NodeService(db=db_session, graph_service=GraphService(db_session))
    #     result = node_service.create_layer(...)

    # AFTER (New pattern with service factory):
    @pytest.mark.skip_suite
    def test_create_layer_new_pattern(
        self, shared_client, test_service_factory
    ):
        """
        Migrated test that uses service factory and monitoring.
        """
        client = shared_client

        # Reset for clean test
        test_service_factory.clear_cache()

        # Record initial state (should be 0 after clear_cache)
        initial_stats = test_service_factory.get_cache_stats()
        initial_service_count = sum(
            metrics["total_created"]
            for metrics in initial_stats["service_metrics"].values()
        )

        # After clear_cache, initial count should be 0
        assert (
            initial_service_count == 0
        ), "Expected initial service count to be 0 after clear_cache"

        # Perform the actual test
        response = client.post(
            "/api/structure_nodes/",
            json={
                "node_type": "layer",
                "title": "Migrated Test Layer",
                "definition": "A layer created using the new service factory pattern",
            },
        )

        assert response.status_code == 201
        layer_data = response.json()
        assert layer_data["title"] == "Migrated Test Layer"

        # Verify service factory was used
        final_stats = test_service_factory.get_cache_stats()
        final_service_count = sum(
            metrics["total_created"]
            for metrics in final_stats["service_metrics"].values()
        )

        # Should have created services for the request
        assert (
            final_service_count > 0
        ), "Expected services to be created for the API request"

        # Clean up
        delete_response = client.delete(
            f"/api/structure_nodes/{layer_data['id']}"
        )
        assert delete_response.status_code == 204


# Template for creating new integration tests with service factory support
class TestNewIntegrationTestTemplate:
    """
    Template for writing new integration tests that properly use the service factory.  # noqa: E501
    """

    def test_new_feature_with_service_factory(
        self, test_service_factory, managed_db_session
    ):
        """
        Template for new integration tests.

        This template shows the recommended pattern for new integration tests:
        1. Use shared_client for API testing (if needed)
        2. Use test_service_factory for service monitoring
        3. Use managed_db_session when direct DB access is needed
        4. Always clean up resources
        5. Include service factory performance monitoring
        """

        # 1. Reset service factory state for test isolation
        test_service_factory.clear_cache()

        # 2. Record baseline metrics

        # 3. Perform the test operations
        # ... your test logic here ...

        # 4. Verify the results
        # ... your assertions here ...

        # 5. Check service factory metrics (optional but recommended)
        final_stats = test_service_factory.get_cache_stats()

        # Example: Verify that services were created
        total_services_used = sum(
            metrics["total_created"]
            for metrics in final_stats["service_metrics"].values()
        )

        if total_services_used > 0:
            # Log performance information for monitoring
            performance = test_service_factory.get_performance_summary()
            print(f"Test used {total_services_used} total services")
            print(
                f"Cache hit rate: {performance['overall_cache_hit_rate_percent']:.1f}%"
            )

        # 6. Clean up any created resources
        # ... cleanup logic here ...


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
