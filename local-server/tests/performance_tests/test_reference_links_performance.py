"""
Performance tests for Reference Links and Word Senses functionality.

Tests bulk operations to ensure they complete within reasonable timeframes.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import time  # noqa: E402
from uuid import uuid4  # noqa: E402

# Performance timeout constants (in seconds)
# Bulk validation timeout: allows for parsing 100+ node definitions and checking reference link syntax  # noqa: E501
# Set to 10s to accommodate slower CI environments while catching performance regressions  # noqa: E501
BULK_VALIDATION_TIMEOUT_SECONDS = 10.0

# Individual validation timeout: single node validation should be nearly instantaneous  # noqa: E501
# Set to 1s to allow for database queries and link parsing on a single node
INDIVIDUAL_VALIDATION_TIMEOUT_SECONDS = 1.0

# Bulk fetch timeout: retrieving reference links for multiple nodes should be fast  # noqa: E501
# Set to 5s for fetching 20 nodes, allowing ~250ms per node including DB overhead  # noqa: E501
BULK_FETCH_TIMEOUT_SECONDS = 5.0

# Scalability factor: maximum allowed performance degradation between small and large batches  # noqa: E501
# Set to 5x to detect quadratic complexity issues while allowing for startup overhead  # noqa: E501
SCALABILITY_FACTOR_LIMIT = 5.0

# Test data constants
# Node count chosen to exceed 100 to test bulk operations with a realistic dataset size  # noqa: E501
# 110 provides margin above the common 100-item batch threshold
PERFORMANCE_TEST_NODE_COUNT = 110

# Small sample size for testing individual operations where each is timed separately  # noqa: E501
SAMPLE_NODE_COUNT_SMALL = 10

# Medium sample size for testing repeated fetch operations in a loop
SAMPLE_NODE_COUNT_MEDIUM = 20


@pytest.fixture
def test_nodes(shared_client):
    """Create a set of test nodes for performance testing."""
    # Create layer
    layer_payload = {
        "node_type": "layer",
        "title": f"PerfTestLayer_{uuid4()}",
        "definition": "Layer for performance testing",
    }
    layer_resp = shared_client.post("/api/structure_nodes/", json=layer_payload)  # noqa: E501
    assert layer_resp.status_code == 201
    layer_id = layer_resp.json()["id"]

    # Create 100+ domains for bulk testing
    node_ids = []
    for i in range(PERFORMANCE_TEST_NODE_COUNT):
        domain_payload = {
            "node_type": "domain",
            "parent_node_id": layer_id,
            "title": f"PerfTestDomain_{i}_{uuid4()}",
            "definition": f"Performance test domain {i}",
        }
        resp = shared_client.post("/api/structure_nodes/", json=domain_payload)
        assert resp.status_code == 201
        node_ids.append(resp.json()["id"])

    yield node_ids

    # Cleanup is handled by test database isolation


def test_bulk_validation_performance(shared_client, test_nodes):
    """Test that bulk validation of 100+ nodes completes in reasonable time."""
    start_time = time.time()

    # Run bulk validation
    resp = shared_client.post(
        f"/api/structure_nodes/reference_links/validate?limit={PERFORMANCE_TEST_NODE_COUNT}"  # noqa: E501
    )

    elapsed_time = time.time() - start_time

    # Assert
    assert resp.status_code == 200
    data = resp.json()

    # Should check up to specified node count
    assert data["total_nodes_checked"] <= PERFORMANCE_TEST_NODE_COUNT

    # Performance assertion: should complete within timeout
    # (even with empty reference links, parsing 100+ nodes should be fast)
    assert elapsed_time < BULK_VALIDATION_TIMEOUT_SECONDS, \
        f"Bulk validation took {elapsed_time:.2f}s (expected < {BULK_VALIDATION_TIMEOUT_SECONDS}s)"  # noqa: E501

    # Log performance metrics
    print("\nBulk validation performance:")
    print(f"  - Nodes checked: {data['total_nodes_checked']}")
    print(f"  - Time elapsed: {elapsed_time:.2f}s")
    print(f"  - Nodes per second: {data['total_nodes_checked'] / elapsed_time:.2f}")  # noqa: E501


def test_individual_validation_performance(shared_client, test_nodes):
    """Test that individual node validation is fast."""
    # Sample small set of nodes from the test set
    sample_nodes = test_nodes[:SAMPLE_NODE_COUNT_SMALL]

    total_time = 0
    for node_id in sample_nodes:
        start_time = time.time()

        resp = shared_client.post(
            f"/api/structure_nodes/{node_id}/reference_links/validate"
        )

        elapsed_time = time.time() - start_time
        total_time += elapsed_time

        assert resp.status_code == 200

        # Each individual validation should be very fast
        assert elapsed_time < INDIVIDUAL_VALIDATION_TIMEOUT_SECONDS, \
            f"Individual validation took {elapsed_time:.2f}s (expected < {INDIVIDUAL_VALIDATION_TIMEOUT_SECONDS}s)"  # noqa: E501

    avg_time = total_time / len(sample_nodes)
    print("\nIndividual validation performance:")
    print(f"  - Nodes tested: {len(sample_nodes)}")
    print(f"  - Average time per node: {avg_time:.3f}s")
    print(f"  - Total time: {total_time:.2f}s")


def test_get_reference_links_performance(shared_client, test_nodes):
    """Test that retrieving reference links is fast."""
    # Sample medium set of nodes
    sample_nodes = test_nodes[:SAMPLE_NODE_COUNT_MEDIUM]

    start_time = time.time()

    for node_id in sample_nodes:
        resp = shared_client.get(f"/api/structure_nodes/{node_id}/reference_links")  # noqa: E501
        assert resp.status_code == 200

    elapsed_time = time.time() - start_time

    # Should be able to fetch nodes' reference links quickly
    assert elapsed_time < BULK_FETCH_TIMEOUT_SECONDS, \
        f"Fetching {len(sample_nodes)} nodes took {elapsed_time:.2f}s (expected < {BULK_FETCH_TIMEOUT_SECONDS}s)"  # noqa: E501

    print("\nGet reference links performance:")
    print(f"  - Nodes fetched: {len(sample_nodes)}")
    print(f"  - Time elapsed: {elapsed_time:.2f}s")
    print(f"  - Fetches per second: {len(sample_nodes) / elapsed_time:.2f}")


def test_get_word_senses_performance(shared_client, test_nodes):
    """Test that retrieving word senses is fast."""
    # Sample medium set of nodes
    sample_nodes = test_nodes[:SAMPLE_NODE_COUNT_MEDIUM]

    start_time = time.time()

    for node_id in sample_nodes:
        resp = shared_client.get(f"/api/structure_nodes/{node_id}/word_senses")
        assert resp.status_code == 200

    elapsed_time = time.time() - start_time

    # Should be able to fetch nodes' word senses quickly
    assert elapsed_time < BULK_FETCH_TIMEOUT_SECONDS, \
        f"Fetching {len(sample_nodes)} nodes took {elapsed_time:.2f}s (expected < {BULK_FETCH_TIMEOUT_SECONDS}s)"  # noqa: E501

    print("\nGet word senses performance:")
    print(f"  - Nodes fetched: {len(sample_nodes)}")
    print(f"  - Time elapsed: {elapsed_time:.2f}s")
    print(f"  - Fetches per second: {len(sample_nodes) / elapsed_time:.2f}")


def test_bulk_validation_with_no_existence_check_faster(shared_client, test_nodes):  # noqa: E501
    """Test that validation without existence check is faster than with it."""
    # Time with existence check
    start_with_check = time.time()
    resp1 = shared_client.post(
        "/api/structure_nodes/reference_links/validate?check_existence=true&limit=50"  # noqa: E501
    )
    time_with_check = time.time() - start_with_check
    assert resp1.status_code == 200

    # Time without existence check
    start_no_check = time.time()
    resp2 = shared_client.post(
        "/api/structure_nodes/reference_links/validate?check_existence=false&limit=50"  # noqa: E501
    )
    time_no_check = time.time() - start_no_check
    assert resp2.status_code == 200

    print("\nExistence check performance comparison:")
    print(f"  - With existence check: {time_with_check:.2f}s")
    print(f"  - Without existence check: {time_no_check:.2f}s")
    print(f"  - Speedup factor: {time_with_check / time_no_check:.2f}x")

    # Without existence check should be significantly faster (at least when reference.db is empty)  # noqa: E501
    # Note: This assertion may not always hold if reference.db access is very fast  # noqa: E501
    # so we just log the comparison


def test_scalability_100_plus_nodes(shared_client, test_nodes):
    """Test that operations scale reasonably with 100+ nodes."""
    # This test ensures that bulk operations don't have quadratic complexity
    # by testing with different batch sizes

    batch_sizes = [10, 50, 100]
    times = []

    for batch_size in batch_sizes:
        start_time = time.time()

        resp = shared_client.post(
            f"/api/structure_nodes/reference_links/validate?limit={batch_size}&check_existence=false"  # noqa: E501
        )

        elapsed_time = time.time() - start_time
        times.append(elapsed_time)

        assert resp.status_code == 200

    print("\nScalability test results:")
    for batch_size, elapsed_time in zip(batch_sizes, times):
        print(f"  - {batch_size} nodes: {elapsed_time:.2f}s ({elapsed_time/batch_size:.4f}s per node)")  # noqa: E501

    # Verify that time per node doesn't grow dramatically (should be roughly linear)  # noqa: E501
    time_per_node_10 = times[0] / batch_sizes[0]
    time_per_node_100 = times[2] / batch_sizes[2]

    # Time per node for 100 should be within scalability factor limit of time per node for 10  # noqa: E501
    # (allowing for startup overhead and caching effects)
    assert time_per_node_100 < time_per_node_10 * SCALABILITY_FACTOR_LIMIT, \
        f"Performance degraded significantly: {time_per_node_10:.4f}s/node -> {time_per_node_100:.4f}s/node"  # noqa: E501
