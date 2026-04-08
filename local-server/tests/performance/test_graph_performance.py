"""Performance tests for graph operations at various scales.

Tests measure graph build time, shortest path queries, SPARQL queries, and
centrality calculations at multiple graph sizes (100, 500, 1000, 5000 nodes).
"""

import sys
import os
import time
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.graph.networkx_engine import NetworkXGraphEngine


def _create_graph_data(num_nodes: int) -> tuple[list[dict], list[dict]]:
    """Create test graph data with specified number of nodes.

    Args:
        num_nodes: Number of nodes to create

    Returns:
        Tuple of (nodes list, edges list)
    """
    nodes = [{"id": f"node_{i}", "title": f"Node {i}", "type": "class"} for i in range(num_nodes)]

    # Create edges: each node connects to next 2 nodes (creating a DAG)
    edges = []
    for i in range(num_nodes):
        if i + 1 < num_nodes:
            edges.append({"source_id": f"node_{i}", "target_id": f"node_{i + 1}"})
        if i + 2 < num_nodes:
            edges.append({"source_id": f"node_{i}", "target_id": f"node_{i + 2}"})

    return nodes, edges


@pytest.mark.performance
def test_graph_build_100_nodes():
    """Measure time to build a graph with 100 nodes."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(100)

    start = time.perf_counter()
    graph.build_from_data(nodes, edges)
    elapsed = time.perf_counter() - start

    print(f"\nGraph build (100 nodes): {elapsed:.4f}s")
    assert graph.node_count() == 100
    assert elapsed < 0.5  # Generous upper bound


@pytest.mark.performance
def test_graph_build_500_nodes():
    """Measure time to build a graph with 500 nodes."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(500)

    start = time.perf_counter()
    graph.build_from_data(nodes, edges)
    elapsed = time.perf_counter() - start

    print(f"\nGraph build (500 nodes): {elapsed:.4f}s")
    assert graph.node_count() == 500
    assert elapsed < 1.0


@pytest.mark.performance
def test_graph_build_1000_nodes():
    """Measure time to build a graph with 1000 nodes."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(1000)

    start = time.perf_counter()
    graph.build_from_data(nodes, edges)
    elapsed = time.perf_counter() - start

    print(f"\nGraph build (1000 nodes): {elapsed:.4f}s")
    assert graph.node_count() == 1000
    assert elapsed < 2.0


@pytest.mark.performance
def test_graph_build_5000_nodes():
    """Measure time to build a graph with 5000 nodes."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(5000)

    start = time.perf_counter()
    graph.build_from_data(nodes, edges)
    elapsed = time.perf_counter() - start

    print(f"\nGraph build (5000 nodes): {elapsed:.4f}s")
    assert graph.node_count() == 5000
    assert elapsed < 5.0


@pytest.mark.performance
def test_shortest_path_query_100_nodes():
    """Measure shortest path query time in a 100-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(100)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    path = graph.shortest_path("node_0", "node_99")
    elapsed = time.perf_counter() - start

    print(f"\nShortest path query (100 nodes): {elapsed:.4f}s")
    assert path is not None
    assert elapsed < 0.1


@pytest.mark.performance
def test_shortest_path_query_500_nodes():
    """Measure shortest path query time in a 500-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(500)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    path = graph.shortest_path("node_0", "node_499")
    elapsed = time.perf_counter() - start

    print(f"\nShortest path query (500 nodes): {elapsed:.4f}s")
    assert path is not None
    assert elapsed < 0.1


@pytest.mark.performance
def test_shortest_path_query_1000_nodes():
    """Measure shortest path query time in a 1000-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(1000)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    path = graph.shortest_path("node_0", "node_999")
    elapsed = time.perf_counter() - start

    print(f"\nShortest path query (1000 nodes): {elapsed:.4f}s")
    assert path is not None
    assert elapsed < 0.2


@pytest.mark.performance
def test_shortest_path_query_5000_nodes():
    """Measure shortest path query time in a 5000-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(5000)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    path = graph.shortest_path("node_0", "node_4999")
    elapsed = time.perf_counter() - start

    print(f"\nShortest path query (5000 nodes): {elapsed:.4f}s")
    assert path is not None
    assert elapsed < 0.5


@pytest.mark.performance
def test_centrality_calculation_100_nodes():
    """Measure centrality calculation time in a 100-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(100)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    centrality = graph.centrality("betweenness")
    elapsed = time.perf_counter() - start

    print(f"\nCentrality calculation (100 nodes): {elapsed:.4f}s")
    assert len(centrality) == 100
    assert elapsed < 0.5


@pytest.mark.performance
def test_centrality_calculation_500_nodes():
    """Measure centrality calculation time in a 500-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(500)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    centrality = graph.centrality("betweenness")
    elapsed = time.perf_counter() - start

    print(f"\nCentrality calculation (500 nodes): {elapsed:.4f}s")
    assert len(centrality) == 500
    assert elapsed < 2.0


@pytest.mark.performance
def test_centrality_calculation_1000_nodes():
    """Measure centrality calculation time in a 1000-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(1000)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    centrality = graph.centrality("betweenness")
    elapsed = time.perf_counter() - start

    print(f"\nCentrality calculation (1000 nodes): {elapsed:.4f}s")
    assert len(centrality) == 1000
    assert elapsed < 5.0


@pytest.mark.performance
def test_centrality_calculation_5000_nodes():
    """Measure centrality calculation time in a 5000-node graph."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(5000)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    centrality = graph.centrality("betweenness")
    elapsed = time.perf_counter() - start

    print(f"\nCentrality calculation (5000 nodes): {elapsed:.4f}s")
    assert len(centrality) == 5000
    assert elapsed < 120.0
