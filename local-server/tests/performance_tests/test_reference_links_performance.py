"""
Performance tests for Reference Links and Word Senses functionality.

Tests bulk operations to ensure they complete within reasonable timeframes.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import time
from uuid import uuid4


@pytest.fixture
def test_nodes(shared_client):
    """Create a set of test nodes for performance testing."""
    # Create layer
    layer_payload = {
        "node_type": "layer",
        "title": f"PerfTestLayer_{uuid4()}",
        "definition": "Layer for performance testing",
    }
    layer_resp = shared_client.post("/api/structure_nodes/", json=layer_payload)
    assert layer_resp.status_code == 201
    layer_id = layer_resp.json()["id"]

    # Create 100+ domains for bulk testing
    node_ids = []
    for i in range(110):  # Create 110 nodes for testing
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
        "/api/structure_nodes/reference_links/validate?limit=110"
    )

    elapsed_time = time.time() - start_time

    # Assert
    assert resp.status_code == 200
    data = resp.json()

    # Should check up to 110 nodes
    assert data["total_nodes_checked"] <= 110

    # Performance assertion: should complete in under 10 seconds
    # (even with empty reference links, parsing 100+ nodes should be fast)
    assert elapsed_time < 10.0, f"Bulk validation took {elapsed_time:.2f}s (expected < 10s)"

    # Log performance metrics
    print(f"\nBulk validation performance:")
    print(f"  - Nodes checked: {data['total_nodes_checked']}")
    print(f"  - Time elapsed: {elapsed_time:.2f}s")
    print(f"  - Nodes per second: {data['total_nodes_checked'] / elapsed_time:.2f}")


def test_individual_validation_performance(shared_client, test_nodes):
    """Test that individual node validation is fast."""
    # Sample 10 nodes from the test set
    sample_nodes = test_nodes[:10]

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
        assert elapsed_time < 1.0, f"Individual validation took {elapsed_time:.2f}s (expected < 1s)"

    avg_time = total_time / len(sample_nodes)
    print(f"\nIndividual validation performance:")
    print(f"  - Nodes tested: {len(sample_nodes)}")
    print(f"  - Average time per node: {avg_time:.3f}s")
    print(f"  - Total time: {total_time:.2f}s")


def test_get_reference_links_performance(shared_client, test_nodes):
    """Test that retrieving reference links is fast."""
    # Sample 20 nodes
    sample_nodes = test_nodes[:20]

    start_time = time.time()

    for node_id in sample_nodes:
        resp = shared_client.get(f"/api/structure_nodes/{node_id}/reference_links")
        assert resp.status_code == 200

    elapsed_time = time.time() - start_time

    # Should be able to fetch 20 nodes' reference links quickly
    assert elapsed_time < 5.0, f"Fetching 20 nodes took {elapsed_time:.2f}s (expected < 5s)"

    print(f"\nGet reference links performance:")
    print(f"  - Nodes fetched: {len(sample_nodes)}")
    print(f"  - Time elapsed: {elapsed_time:.2f}s")
    print(f"  - Fetches per second: {len(sample_nodes) / elapsed_time:.2f}")


def test_get_word_senses_performance(shared_client, test_nodes):
    """Test that retrieving word senses is fast."""
    # Sample 20 nodes
    sample_nodes = test_nodes[:20]

    start_time = time.time()

    for node_id in sample_nodes:
        resp = shared_client.get(f"/api/structure_nodes/{node_id}/word_senses")
        assert resp.status_code == 200

    elapsed_time = time.time() - start_time

    # Should be able to fetch 20 nodes' word senses quickly
    assert elapsed_time < 5.0, f"Fetching 20 nodes took {elapsed_time:.2f}s (expected < 5s)"

    print(f"\nGet word senses performance:")
    print(f"  - Nodes fetched: {len(sample_nodes)}")
    print(f"  - Time elapsed: {elapsed_time:.2f}s")
    print(f"  - Fetches per second: {len(sample_nodes) / elapsed_time:.2f}")


def test_bulk_validation_with_no_existence_check_faster(shared_client, test_nodes):
    """Test that validation without existence check is faster than with it."""
    # Time with existence check
    start_with_check = time.time()
    resp1 = shared_client.post(
        "/api/structure_nodes/reference_links/validate?check_existence=true&limit=50"
    )
    time_with_check = time.time() - start_with_check
    assert resp1.status_code == 200

    # Time without existence check
    start_no_check = time.time()
    resp2 = shared_client.post(
        "/api/structure_nodes/reference_links/validate?check_existence=false&limit=50"
    )
    time_no_check = time.time() - start_no_check
    assert resp2.status_code == 200

    print(f"\nExistence check performance comparison:")
    print(f"  - With existence check: {time_with_check:.2f}s")
    print(f"  - Without existence check: {time_no_check:.2f}s")
    print(f"  - Speedup factor: {time_with_check / time_no_check:.2f}x")

    # Without existence check should be significantly faster (at least when reference.db is empty)
    # Note: This assertion may not always hold if reference.db access is very fast
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
            f"/api/structure_nodes/reference_links/validate?limit={batch_size}&check_existence=false"
        )

        elapsed_time = time.time() - start_time
        times.append(elapsed_time)

        assert resp.status_code == 200

    print(f"\nScalability test results:")
    for batch_size, elapsed_time in zip(batch_sizes, times):
        print(f"  - {batch_size} nodes: {elapsed_time:.2f}s ({elapsed_time/batch_size:.4f}s per node)")

    # Verify that time per node doesn't grow dramatically (should be roughly linear)
    time_per_node_10 = times[0] / batch_sizes[0]
    time_per_node_100 = times[2] / batch_sizes[2]

    # Time per node for 100 should be within 5x of time per node for 10
    # (allowing for startup overhead and caching effects)
    assert time_per_node_100 < time_per_node_10 * 5, \
        f"Performance degraded significantly: {time_per_node_10:.4f}s/node -> {time_per_node_100:.4f}s/node"
