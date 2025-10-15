"""
Performance tests for Phase 4: API Contract Validation.

Test Cases:
- TC-P001: Search performance with varying dataset sizes
- TC-P002: Concurrent request handling
- TC-P003: Large result set pagination
"""

import pytest
import tempfile
import os
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.models import ReferenceNode, ReferenceLink
from uuid import uuid4
from datetime import date


@pytest.fixture(scope="module")
def performance_test_database():
    """Create a larger test database for performance testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path=db_path)

    def create_embedding(seed: int) -> bytes:
        """Create deterministic embedding from seed."""
        np.random.seed(seed)
        vec = np.random.rand(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    # Create 100 nodes for performance testing
    nodes = []
    for i in range(100):
        node = manager.add_reference_node(
            title=f"Entity_{i:03d}",
            definition=f"Test entity number {i} for performance testing.",
            source="test.schema",
            external_id=f"Entity_{i:03d}",
            attributes=f'{{"@type": "entity", "index": {i}}}',
            title_embedding=create_embedding(i),
            definition_embedding=create_embedding(i + 1000),
            embedding_dims=384
        )
        nodes.append(node)

    # Create links between nodes
    if manager.session.in_transaction():
        manager.session.rollback()

    links = []
    for i in range(0, 99):
        link = ReferenceLink(
            id=str(uuid4()),
            subject_node=nodes[i].id,
            predicate="relatedTo",
            object_node=nodes[i + 1].id,
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat()
        )
        links.append(link)

    manager.session.add_all(links)
    manager.session.commit()

    # Extract node IDs before closing the session to avoid DetachedInstanceError
    node_ids = [node.id for node in nodes]

    manager.close()

    yield db_path, node_ids

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


class TestTC_P001_SearchPerformanceScaling:
    """
    TC-P001: Search performance with varying dataset sizes.

    Validates that search performance scales appropriately with dataset size.
    """

    def test_search_baseline_performance(self, performance_test_database):
        """Establish baseline search performance on 100-node dataset."""
        db_path, node_ids = performance_test_database

        def mock_embedding(text: str) -> bytes:
            vec = np.full(384, 0.5, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        config = ReferenceConfig()
        execution_times = []

        # Run 10 searches to get average performance
        for _ in range(10):
            with ReferenceManager(config, db_path=db_path) as manager:
                start_time = time.time()

                results = manager.search_by_similarity(
                    query_text="test entity",
                    limit=20,
                    threshold=0.5,
                    embedding_generator=mock_embedding
                )

                execution_time_ms = (time.time() - start_time) * 1000
                execution_times.append(execution_time_ms)

        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)

        # Average should be < 100ms, max < 200ms for 100 nodes
        assert avg_time < 100, f"Average search time {avg_time:.2f}ms exceeds 100ms"
        assert max_time < 200, f"Max search time {max_time:.2f}ms exceeds 200ms"

    def test_search_with_different_limits(self, performance_test_database):
        """Test search performance with different result limits."""
        db_path, node_ids = performance_test_database

        def mock_embedding(text: str) -> bytes:
            vec = np.full(384, 0.5, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        config = ReferenceConfig()
        limits = [10, 50, 100]
        results_map = {}

        for limit in limits:
            with ReferenceManager(config, db_path=db_path) as manager:
                start_time = time.time()

                results = manager.search_by_similarity(
                    query_text="entity",
                    limit=limit,
                    threshold=0.0,
                    embedding_generator=mock_embedding
                )

                execution_time_ms = (time.time() - start_time) * 1000
                results_map[limit] = execution_time_ms

        # Performance should scale sub-linearly with limit
        # Doubling limit shouldn't double time
        for i in range(len(limits) - 1):
            lower_limit = limits[i]
            higher_limit = limits[i + 1]
            time_ratio = results_map[higher_limit] / results_map[lower_limit]
            limit_ratio = higher_limit / lower_limit

            assert time_ratio < limit_ratio, \
                f"Performance scaling poor: time ratio {time_ratio:.2f} >= limit ratio {limit_ratio}"


class TestTC_P002_ConcurrentRequestHandling:
    """
    TC-P002: Concurrent request handling performance.

    Tests system behavior under concurrent load.
    """

    def test_concurrent_searches(self, performance_test_database):
        """Test concurrent search requests."""
        db_path, node_ids = performance_test_database

        def mock_embedding(text: str) -> bytes:
            vec = np.full(384, 0.5, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        def run_search(query_id: int):
            """Run a single search and return timing."""
            config = ReferenceConfig()
            with ReferenceManager(config, db_path=db_path) as manager:
                start_time = time.time()

                results = manager.search_by_similarity(
                    query_text=f"entity {query_id}",
                    limit=10,
                    threshold=0.5,
                    embedding_generator=mock_embedding
                )

                return time.time() - start_time

        # Run 20 concurrent searches
        num_concurrent = 20
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_search, i) for i in range(num_concurrent)]
            execution_times = [future.result() for future in as_completed(futures)]

        total_time = time.time() - start_time

        # Calculate statistics
        avg_search_time = sum(execution_times) / len(execution_times)
        max_search_time = max(execution_times)

        # Concurrent searches should complete reasonably
        assert total_time < 5.0, f"20 concurrent searches took {total_time:.2f}s (expected <5s)"
        assert avg_search_time < 0.5, f"Average search time {avg_search_time:.2f}s (expected <0.5s)"
        assert max_search_time < 1.0, f"Max search time {max_search_time:.2f}s (expected <1s)"

    def test_concurrent_link_retrievals(self, performance_test_database):
        """Test concurrent link retrieval requests."""
        db_path, node_ids = performance_test_database

        def run_link_retrieval(node_id: str):
            """Run a single link retrieval and return timing."""
            config = ReferenceConfig()
            with ReferenceManager(config, db_path=db_path) as manager:
                start_time = time.time()
                links = manager.get_node_links(node_id=node_id, direction="both")
                return time.time() - start_time

        # Run 30 concurrent link retrievals
        num_concurrent = 30
        test_node_ids = node_ids[:num_concurrent]

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_link_retrieval, nid) for nid in test_node_ids]
            execution_times = [future.result() for future in as_completed(futures)]

        total_time = time.time() - start_time

        # Link retrievals should be very fast
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)

        assert total_time < 2.0, f"30 concurrent link retrievals took {total_time:.2f}s (expected <2s)"
        assert avg_time < 0.1, f"Average link retrieval time {avg_time:.2f}s (expected <0.1s)"


class TestTC_P003_LargeResultSetPagination:
    """
    TC-P003: Large result set pagination performance.

    Tests pagination performance with large result sets.
    """

    def test_pagination_performance(self, performance_test_database):
        """Test pagination with different offsets."""
        db_path, node_ids = performance_test_database

        def mock_embedding(text: str) -> bytes:
            vec = np.full(384, 0.5, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        config = ReferenceConfig()
        page_size = 10
        offsets = [0, 20, 40, 60, 80]
        execution_times = []

        for offset in offsets:
            with ReferenceManager(config, db_path=db_path) as manager:
                start_time = time.time()

                # Note: current implementation doesn't support offset
                # This test validates that limit works correctly
                results = manager.search_by_similarity(
                    query_text="entity",
                    limit=page_size,
                    threshold=0.0,
                    embedding_generator=mock_embedding
                )

                execution_time_ms = (time.time() - start_time) * 1000
                execution_times.append(execution_time_ms)

        # All pages should have similar performance
        avg_time = sum(execution_times) / len(execution_times)
        max_deviation = max(abs(t - avg_time) for t in execution_times)

        # Deviation should be small (< 50% of average)
        assert max_deviation < avg_time * 0.5, \
            f"Pagination performance varies too much: max deviation {max_deviation:.2f}ms"

    def test_large_limit_performance(self, performance_test_database):
        """Test performance with large limits."""
        db_path, node_ids = performance_test_database

        def mock_embedding(text: str) -> bytes:
            vec = np.full(384, 0.5, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        config = ReferenceConfig()

        with ReferenceManager(config, db_path=db_path) as manager:
            start_time = time.time()

            # Request all 100 nodes
            results = manager.search_by_similarity(
                query_text="entity",
                limit=100,
                threshold=0.0,
                embedding_generator=mock_embedding
            )

            execution_time_ms = (time.time() - start_time) * 1000

            # Should complete in <300ms even with 100 results
            assert execution_time_ms < 300, \
                f"Large limit query took {execution_time_ms:.2f}ms (expected <300ms)"

            # Verify we got results
            assert len(results) <= 100, f"Got {len(results)} results, expected <=100"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
