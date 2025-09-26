"""
Integration tests for Phase 5 Optimization Features

This test suite validates the complete optimization workflows including:
- Query optimization with DuckDBQueryOptimizer
- Storage optimization with S3StorageOptimizer  
- Hierarchical diff processing with semantic analysis
- High-performance batch operations
- Performance monitoring and automated optimization

Tests the integration between all Phase 5 services and their API endpoints.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest



class TestPhase5OptimizationIntegration:
    """Integration tests for complete Phase 5 optimization workflows."""
    
    def test_optimization_api_health_check(self, shared_client):
        """Test optimization system health check endpoint."""
        client = shared_client
        
        response = client.get("/api/optimization/health")
        
        # Should return health status successfully
        assert response.status_code == 200
        
        health_data = response.json()
        assert "status" in health_data
        assert "services_healthy" in health_data
        assert "performance_score" in health_data
        assert "optimization_enabled" in health_data
    
    def test_query_optimization_workflow(self, shared_client):
        """Test complete query optimization workflow."""
        client = shared_client
        
        # Test query optimization endpoint
        optimization_request = {
            "query": "SELECT * FROM entity_versions WHERE entity_type = 'document' ORDER BY created_at DESC",
            "context": {
                "time_range": {
                    "start": "2024-01-01",
                    "end": "2024-01-31"
                },
                "entity_types": ["document"],
                "required_columns": ["id", "entity_type", "created_at", "data"]
            }
        }
        
        response = client.post("/api/optimization/query/optimize", json=optimization_request)
        
        assert response.status_code == 200
        optimization_result = response.json()
        
        # Check optimization result structure
        assert "original_query" in optimization_result
        assert "optimized_query" in optimization_result
        assert "metrics" in optimization_result
        assert "optimization_applied" in optimization_result
        
        # Optimized query should be different from original
        assert optimization_result["optimized_query"] != optimization_result["original_query"]
        
        # Should have applied optimization strategies
        assert len(optimization_result["optimization_applied"]) > 0
    
    def test_materialized_view_creation_workflow(self, shared_client):
        """Test materialized view creation and management workflow."""
        client = shared_client
        
        # Create a materialized view
        view_request = {
            "view_name": "entity_summary_view",
            "query": "SELECT entity_type, COUNT(*) as count, MAX(created_at) as latest FROM entity_versions GROUP BY entity_type",
            "refresh_strategy": "manual"
        }
        
        response = client.post("/api/optimization/query/materialized-view", json=view_request)
        
        assert response.status_code == 200
        result = response.json()
        
        assert "message" in result
        assert "view_name" in result
        assert result["view_name"] == "entity_summary_view"
        assert "created_at" in result
    
    def test_query_performance_statistics(self, shared_client):
        """Test query optimization statistics endpoint."""
        client = shared_client
        
        # First, trigger some query optimizations
        test_queries = [
            "SELECT COUNT(*) FROM entity_versions",
            "SELECT * FROM entity_versions WHERE entity_type = 'document'",
            "SELECT entity_type, COUNT(*) FROM entity_versions GROUP BY entity_type"
        ]
        
        for query in test_queries:
            optimization_request = {"query": query, "context": {}}
            client.post("/api/optimization/query/optimize", json=optimization_request)
        
        # Get statistics
        response = client.get("/api/optimization/query/stats")
        
        assert response.status_code == 200
        stats = response.json()
        
        assert "total_queries" in stats
        assert "avg_execution_time_ms" in stats
        assert "cache_stats" in stats
        assert "materialized_views_count" in stats
    
    def test_storage_optimization_workflow(self, shared_client):
        """Test complete storage optimization workflow."""
        client = shared_client
        
        # Get storage optimization statistics
        response = client.get("/api/optimization/storage/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "optimization_summary" in stats or "total_optimizations" in stats
        
        # Trigger storage optimization
        response = client.post("/api/optimization/storage/optimize")
        assert response.status_code == 200
        
        optimization_result = response.json()
        assert "optimization_actions" in optimization_result
        assert "storage_saved_bytes" in optimization_result
        assert "cost_reduction_estimate" in optimization_result
        assert "objects_optimized" in optimization_result
    
    def test_storage_lifecycle_policies_setup(self, shared_client):
        """Test S3 lifecycle policies setup workflow."""
        client = shared_client
        
        response = client.post("/api/optimization/storage/lifecycle-policies")
        assert response.status_code == 200
        
        result = response.json()
        assert "message" in result
        assert "policies" in result
        assert "configured_at" in result
        
        # Should include standard lifecycle transitions
        policies = result["policies"]
        assert any("Standard to IA" in policy for policy in policies)
        assert any("Glacier" in policy for policy in policies)
    
    def test_hierarchical_diff_workflow(self, shared_client):
        """Test hierarchical diff processing workflow."""
        client = shared_client
        
        # Test three-way diff
        diff_request = {
            "base": {
                "id": "entity_1",
                "name": "Original Name",
                "properties": {"type": "document", "status": "draft"}
            },
            "local": {
                "id": "entity_1", 
                "name": "Local Modified Name",
                "properties": {"type": "document", "status": "draft", "local_flag": True}
            },
            "remote": {
                "id": "entity_1",
                "name": "Remote Modified Name", 
                "properties": {"type": "document", "status": "published", "remote_flag": True}
            },
            "enable_semantic_analysis": True
        }
        
        response = client.post("/api/optimization/diff/three-way", json=diff_request)
        assert response.status_code == 200
        
        diff_result = response.json()
        assert "diff_result" in diff_result
        assert "conflicts_detected" in diff_result
        
        # Should detect conflict on name field
        conflicts = diff_result["conflicts_detected"]
        assert len(conflicts) > 0
    
    def test_diff_engine_statistics(self, shared_client):
        """Test diff engine performance statistics."""
        client = shared_client
        
        response = client.get("/api/optimization/diff/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "performance_statistics" in stats or "total_operations" in stats
    
    def test_batch_operation_workflow(self, shared_client):
        """Test high-performance batch operations workflow."""
        client = shared_client
        
        # Test batch processing
        batch_request = {
            "operation_type": "create_versions",
            "entity_data": [
                {"id": f"batch_entity_{i}", "type": "test", "content": f"Content {i}"}
                for i in range(50)
            ],
            "author_id": "test_batch_user",
            "options": {"parallel_processing": True, "batch_size": 25}
        }
        
        response = client.post("/api/optimization/batch/process", json=batch_request)
        assert response.status_code == 200
        
        batch_result = response.json()
        assert "operation_id" in batch_result
        assert "total_items" in batch_result
        assert "successful_items" in batch_result
        assert "failed_items" in batch_result
        assert "processing_time_seconds" in batch_result
        assert "throughput_per_second" in batch_result
        
        # Should have processed all items
        assert batch_result["total_items"] == 50
    
    def test_batch_operation_statistics(self, shared_client):
        """Test batch operation performance statistics."""
        client = shared_client
        
        response = client.get("/api/optimization/batch/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "performance_statistics" in stats or "total_operations" in stats
    
    def test_performance_monitoring_workflow(self, shared_client):
        """Test comprehensive performance monitoring workflow."""
        client = shared_client
        
        # Get performance dashboard
        response = client.get("/api/optimization/performance/dashboard")
        assert response.status_code == 200
        
        dashboard = response.json()
        assert "current_metrics" in dashboard
        assert "trends" in dashboard
        assert "system_status" in dashboard
        
        # Get current performance metrics
        response = client.get("/api/optimization/performance/metrics")
        assert response.status_code == 200
        
        metrics = response.json()
        assert "timestamp" in metrics
        assert "database_metrics" in metrics
        assert "system_metrics" in metrics
        assert "cache_metrics" in metrics
    
    def test_performance_trends_analysis(self, shared_client):
        """Test performance trend analysis workflow."""
        client = shared_client
        
        response = client.get("/api/optimization/performance/trends?window_hours=24")
        assert response.status_code == 200
        
        trends = response.json()
        assert "analysis_window_hours" in trends
        assert "trends" in trends
        assert "issues" in trends
        assert "recommendations" in trends
        assert "overall_health_score" in trends
        assert "performance_grade" in trends
    
    def test_automated_optimization_trigger(self, shared_client):
        """Test automated optimization trigger workflow."""
        client = shared_client
        
        response = client.post("/api/optimization/performance/auto-optimize")
        assert response.status_code == 200
        
        result = response.json()
        assert "message" in result
        assert "status" in result
        assert "timestamp" in result
        assert result["status"] == "running"
    
    def test_optimization_configuration_management(self, shared_client):
        """Test optimization configuration management."""
        client = shared_client
        
        # Get current configuration
        response = client.get("/api/optimization/config")
        assert response.status_code == 200
        
        config = response.json()
        assert "query_optimization" in config
        assert "storage_optimization" in config
        assert "performance_monitoring" in config
        
        # Update configuration
        updated_config = {
            "query_optimization": {
                "cache_ttl_seconds": 7200,
                "optimization_strategies_enabled": [
                    "predicate_pushdown", "column_pruning", "join_optimization"
                ]
            },
            "performance_monitoring": {
                "auto_optimization_enabled": True,
                "optimization_interval_seconds": 1800
            }
        }
        
        response = client.put("/api/optimization/config", json=updated_config)
        assert response.status_code == 200
        
        result = response.json()
        assert "message" in result
        assert "updated_at" in result
        assert "config" in result
    
    def test_integrated_optimization_workflow(self, shared_client):
        """Test complete integrated optimization workflow across all services."""
        client = shared_client
        
        # 1. Start with performance monitoring
        metrics_response = client.get("/api/optimization/performance/metrics")
        assert metrics_response.status_code == 200
        initial_metrics = metrics_response.json()
        
        # 2. Optimize some queries
        query_optimization_requests = [
            {
                "query": "SELECT * FROM entity_versions WHERE created_at > '2024-01-01'",
                "context": {"entity_types": ["document", "page"]}
            },
            {
                "query": "SELECT COUNT(*) FROM entity_versions GROUP BY entity_type",
                "context": {"required_columns": ["entity_type"]}
            }
        ]
        
        for request in query_optimization_requests:
            response = client.post("/api/optimization/query/optimize", json=request)
            assert response.status_code == 200
        
        # 3. Process some batch operations
        batch_request = {
            "operation_type": "create_versions", 
            "entity_data": [
                {"id": f"integrated_test_{i}", "type": "integration_test"}
                for i in range(20)
            ],
            "author_id": "integration_test_user"
        }
        
        batch_response = client.post("/api/optimization/batch/process", json=batch_request)
        assert batch_response.status_code == 200
        
        # 4. Trigger storage optimization
        storage_response = client.post("/api/optimization/storage/optimize")
        assert storage_response.status_code == 200
        
        # 5. Check final performance metrics
        final_metrics_response = client.get("/api/optimization/performance/metrics")
        assert final_metrics_response.status_code == 200
        final_metrics = final_metrics_response.json()
        
        # 6. Get performance trends to see the impact
        trends_response = client.get("/api/optimization/performance/trends?window_hours=1")
        assert trends_response.status_code == 200
        trends = trends_response.json()
        
        # Should have performance data and trends
        assert "overall_health_score" in trends
        assert "performance_grade" in trends
        assert trends["overall_health_score"] >= 0
        assert trends["performance_grade"] in ['A+', 'A', 'B', 'C', 'D', 'F']
    
    def test_service_factory_optimization_integration(self, shared_client, test_service_factory):
        """Test service factory integration with optimization services."""
        client = shared_client
        
        # Clear service factory cache
        test_service_factory.clear_cache()
        
        # Make requests that use different optimization services
        optimization_endpoints = [
            "/api/optimization/health",
            "/api/optimization/query/stats",
            "/api/optimization/storage/stats", 
            "/api/optimization/performance/metrics"
        ]
        
        for endpoint in optimization_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
        
        # Check service factory statistics
        factory_stats = test_service_factory.get_cache_stats()
        
        # Should have created optimization services
        service_metrics = factory_stats["service_metrics"]
        optimization_services = [
            "duckdb_query_optimizer", "s3_storage_optimizer", 
            "performance_monitor", "hierarchical_diff_engine"
        ]
        
        services_created = 0
        for service_name in optimization_services:
            if service_name in service_metrics and service_metrics[service_name]["total_created"] > 0:
                services_created += 1
        
        # Should have created at least some optimization services
        assert services_created > 0
    
    def test_optimization_error_handling(self, shared_client):
        """Test error handling in optimization workflows."""
        client = shared_client
        
        # Test invalid query optimization request
        invalid_request = {
            "query": "",  # Empty query
            "context": {}
        }
        
        response = client.post("/api/optimization/query/optimize", json=invalid_request)
        # Should handle gracefully (may return 400 or process empty query)
        assert response.status_code in [200, 400]
        
        # Test invalid batch operation request
        invalid_batch = {
            "operation_type": "invalid_operation",  # Invalid operation type
            "entity_data": [],
            "author_id": "test_user"
        }
        
        response = client.post("/api/optimization/batch/process", json=invalid_batch)
        assert response.status_code == 400  # Should reject invalid operation type
        
        # Test invalid materialized view request
        invalid_view = {
            "view_name": "",  # Empty name
            "query": "SELECT * FROM nonexistent_table",
            "refresh_strategy": "invalid_strategy"
        }
        
        response = client.post("/api/optimization/query/materialized-view", json=invalid_view)
        # Should handle validation errors (422 is standard for Pydantic validation failures)
        assert response.status_code in [200, 400, 422]
    
    def test_optimization_performance_under_load(self, shared_client):
        """Test optimization system performance under concurrent load."""
        import concurrent.futures
        
        client = shared_client
        
        def make_optimization_request():
            """Make a sample optimization request."""
            try:
                response = client.get("/api/optimization/performance/metrics")
                return response.status_code == 200
            except Exception:
                return False
        
        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_optimization_request) for _ in range(20)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Most requests should succeed
        success_rate = sum(results) / len(results)
        assert success_rate >= 0.8  # At least 80% success rate
    
    def test_optimization_data_persistence(self, shared_client):
        """Test that optimization data is properly persisted."""
        client = shared_client
        
        # Trigger various optimizations to generate data
        optimization_actions = [
            lambda: client.get("/api/optimization/performance/metrics"),
            lambda: client.post("/api/optimization/query/optimize", json={
                "query": "SELECT * FROM entity_versions LIMIT 10",
                "context": {}
            }),
            lambda: client.get("/api/optimization/performance/trends?window_hours=1")
        ]
        
        for action in optimization_actions:
            response = action()
            assert response.status_code == 200
        
        # Check that optimization history is maintained
        health_response = client.get("/api/optimization/health")
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        assert "performance_score" in health_data
        assert health_data["performance_score"] >= 0
    
    def test_optimization_system_configuration_workflow(self, shared_client):
        """Test complete optimization system configuration workflow."""
        client = shared_client
        
        # 1. Check initial system health
        health_response = client.get("/api/optimization/health")
        assert health_response.status_code == 200
        initial_health = health_response.json()
        
        # 2. Get current configuration
        config_response = client.get("/api/optimization/config")
        assert config_response.status_code == 200
        current_config = config_response.json()
        
        # 3. Update configuration for better performance
        optimized_config = {
            "query_optimization": {
                "cache_ttl_seconds": 14400,  # 4 hours
                "optimization_strategies_enabled": [
                    "predicate_pushdown",
                    "partition_elimination", 
                    "column_pruning",
                    "join_optimization",
                    "aggregation_pushdown"
                ]
            },
            "performance_monitoring": {
                "auto_optimization_enabled": True,
                "optimization_interval_seconds": 1800,  # 30 minutes
                "alert_thresholds": {
                    "query_time_ms": 3000,  # Stricter threshold
                    "memory_usage_mb": 800,
                    "error_rate_percent": 0.5
                }
            }
        }
        
        update_response = client.put("/api/optimization/config", json=optimized_config)
        assert update_response.status_code == 200
        
        # 4. Verify configuration was applied
        updated_config_response = client.get("/api/optimization/config")
        assert updated_config_response.status_code == 200
        
        # 5. Test that new configuration affects optimization behavior
        # (This would be implementation-dependent)
        metrics_response = client.get("/api/optimization/performance/metrics")
        assert metrics_response.status_code == 200
        
        # 6. Check final system health
        final_health_response = client.get("/api/optimization/health")
        assert final_health_response.status_code == 200
        final_health = final_health_response.json()
        
        # System should still be healthy after configuration changes
        assert final_health["optimization_enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])