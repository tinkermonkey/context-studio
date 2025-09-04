"""
Performance tests for pipeline flavor APIs.
"""

import pytest
import sys
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app


class TestPipelineFlavorPerformance:
    """Performance tests for pipeline flavor operations"""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app"""
        app = create_app()
        return TestClient(app)
    
    @pytest.fixture
    def sample_flavor_data(self):
        """Sample flavor data for testing"""
        return {
            "pipeline": "suggest_term_definition",
            "title": "Performance Test Flavor",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_config": {"temperature": 0.7, "max_tokens": 1000},
            "system_prompt": "Performance test system prompt",
            "user_prompt": "Performance test user prompt with {term} placeholder"
        }
    
    @pytest.mark.performance
    def test_flavor_creation_performance(self, client, sample_flavor_data):
        """Test flavor creation performance"""
        import uuid
        
        start_time = time.time()
        
        # Create multiple flavors with unique names
        num_flavors = 10
        test_id = str(uuid.uuid4())[:8]  # Short unique ID for this test run
        
        for i in range(num_flavors):
            flavor_data = sample_flavor_data.copy()
            flavor_data["title"] = f"PerfTest-{test_id}-{i}"
            
            response = client.post("/api/pipeline-flavors", json=flavor_data)
            assert response.status_code == 201
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should create 10 flavors in under 5 seconds
        assert duration < 5.0, f"Flavor creation took {duration:.2f}s, expected < 5.0s"
        
        # Average time per flavor should be reasonable
        avg_time_per_flavor = duration / num_flavors
        assert avg_time_per_flavor < 0.5, f"Average time per flavor: {avg_time_per_flavor:.2f}s"
    
    @pytest.mark.performance
    def test_flavor_listing_performance(self, client):
        """Test flavor listing performance"""
        start_time = time.time()
        
        # List flavors multiple times
        num_requests = 20
        for _ in range(num_requests):
            response = client.get("/api/pipeline-flavors")
            assert response.status_code == 200
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle 20 list requests in under 2 seconds
        assert duration < 2.0, f"Flavor listing took {duration:.2f}s, expected < 2.0s"
        
        # Average time per request should be fast
        avg_time_per_request = duration / num_requests
        assert avg_time_per_request < 0.1, f"Average time per request: {avg_time_per_request:.2f}s"
    
    @pytest.mark.performance
    def test_concurrent_flavor_operations(self, client, sample_flavor_data):
        """Test concurrent flavor operations"""
        def create_flavor(flavor_id):
            flavor_data = sample_flavor_data.copy()
            flavor_data["title"] = f"Concurrent Test Flavor {flavor_id}"
            response = client.post("/api/pipeline-flavors", json=flavor_data)
            return response.status_code == 201
        
        start_time = time.time()
        
        # Run concurrent flavor creation
        num_concurrent = 5
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(create_flavor, i) for i in range(num_concurrent)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        duration = end_time - start_time
        
        # All operations should succeed
        assert all(results), "Some concurrent operations failed"
        
        # Should complete concurrent operations in reasonable time
        assert duration < 3.0, f"Concurrent operations took {duration:.2f}s, expected < 3.0s"
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_streaming_response_performance(self, client):
        """Test streaming response performance"""
        request_data = {
            "term": "artificial intelligence",
            "domain_title": "Computer Science",
            "flavor": "default"
        }
        
        start_time = time.time()
        
        response = client.post(
            "/api/llm/suggest_term_definition/stream",
            json=request_data
        )
        
        # Measure time to first byte
        first_byte_time = time.time()
        time_to_first_byte = first_byte_time - start_time
        
        # Read full response
        content = response.content.decode()
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Check performance metrics
        assert response.status_code == 200
        assert time_to_first_byte < 1.0, f"Time to first byte: {time_to_first_byte:.2f}s"
        
        # Note: Total duration depends on LLM response, so we're lenient
        # In a real environment with valid API keys, this would be more specific
        assert total_duration < 30.0, f"Total streaming duration: {total_duration:.2f}s"
        
        # Check that we got streaming data
        assert "data:" in content


class TestDatabasePerformance:
    """Performance tests for database operations"""
    
    @pytest.mark.performance
    def test_database_query_performance(self, client):
        """Test database query performance"""
        # Create some test data first
        sample_data = {
            "pipeline": "suggest_term_definition",
            "title": "DB Performance Test",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_config": {"temperature": 0.7},
            "system_prompt": "Test",
            "user_prompt": "Test {term}"
        }
        
        response = client.post("/api/pipeline-flavors", json=sample_data)
        assert response.status_code == 201
        flavor_id = response.json()["id"]
        
        # Test individual record retrieval performance
        start_time = time.time()
        
        num_queries = 50
        for _ in range(num_queries):
            response = client.get(f"/api/pipeline-flavors/{flavor_id}")
            assert response.status_code == 200
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle 50 individual queries quickly
        assert duration < 2.0, f"Database queries took {duration:.2f}s, expected < 2.0s"
        
        avg_query_time = duration / num_queries
        assert avg_query_time < 0.04, f"Average query time: {avg_query_time:.3f}s"
    
    @pytest.mark.performance
    def test_filtered_query_performance(self, client):
        """Test filtered query performance"""
        start_time = time.time()
        
        # Test filtered queries
        num_queries = 30
        pipeline_types = ["suggest_term_definition", "suggest_layer_definition", "suggest_domain_definition"]
        
        for i in range(num_queries):
            pipeline = pipeline_types[i % len(pipeline_types)]
            response = client.get(f"/api/pipeline-flavors?pipeline={pipeline}")
            assert response.status_code == 200
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle filtered queries efficiently
        assert duration < 1.5, f"Filtered queries took {duration:.2f}s, expected < 1.5s"


class TestMemoryUsage:
    """Tests for memory usage patterns"""
    
    @pytest.mark.performance
    def test_streaming_memory_usage(self, client):
        """Test that streaming doesn't cause memory leaks"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        request_data = {
            "term": "complex machine learning algorithm",
            "domain_title": "Artificial Intelligence",
            "flavor": "default"
        }
        
        # Make multiple streaming requests
        for _ in range(5):
            response = client.post(
                "/api/llm/suggest_term_definition/stream",
                json=request_data
            )
            # Read the full response to simulate real usage
            content = response.content
            assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        max_increase = 50 * 1024 * 1024  # 50MB
        assert memory_increase < max_increase, f"Memory increased by {memory_increase / 1024 / 1024:.1f}MB"


class TestLoadTesting:
    """Load testing for the flavor system"""
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_flavor_system_under_load(self, client):
        """Test flavor system under moderate load"""
        import threading
        import queue
        
        results_queue = queue.Queue()
        num_threads = 10
        requests_per_thread = 5
        
        def worker_thread(thread_id):
            try:
                # Mix of different operations
                for i in range(requests_per_thread):
                    if i % 3 == 0:
                        # List flavors
                        response = client.get("/api/pipeline-flavors")
                        results_queue.put(('list', response.status_code == 200))
                    elif i % 3 == 1:
                        # Get specific flavor (try default)
                        list_response = client.get("/api/pipeline-flavors")
                        if list_response.status_code == 200:
                            flavors = list_response.json()["flavors"]
                            if flavors:
                                flavor_id = flavors[0]["id"]
                                response = client.get(f"/api/pipeline-flavors/{flavor_id}")
                                results_queue.put(('get', response.status_code == 200))
                    else:
                        # Create and delete flavor
                        flavor_data = {
                            "pipeline": "suggest_term_definition",
                            "title": f"Load Test {thread_id}-{i}",
                            "llm_provider": "openai",
                            "llm_model": "gpt-4",
                            "llm_config": {"temperature": 0.7},
                            "system_prompt": "Load test",
                            "user_prompt": "Load test {term}"
                        }
                        create_response = client.post("/api/pipeline-flavors", json=flavor_data)
                        if create_response.status_code == 201:
                            flavor_id = create_response.json()["id"]
                            delete_response = client.delete(f"/api/pipeline-flavors/{flavor_id}")
                            results_queue.put(('create_delete', delete_response.status_code == 204))
                        else:
                            results_queue.put(('create_delete', False))
            except Exception as e:
                results_queue.put(('error', str(e)))
        
        start_time = time.time()
        
        # Start all threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Analyze results
        success_count = sum(1 for op, success in results if success)
        total_operations = len(results)
        success_rate = success_count / total_operations if total_operations > 0 else 0
        
        # Load test should complete in reasonable time
        assert duration < 15.0, f"Load test took {duration:.2f}s, expected < 15.0s"
        
        # Most operations should succeed
        assert success_rate > 0.8, f"Success rate: {success_rate:.2%}, expected > 80%"
        
        # Should handle the expected number of operations
        expected_operations = num_threads * requests_per_thread
        assert total_operations >= expected_operations * 0.8, f"Only {total_operations} operations completed"
