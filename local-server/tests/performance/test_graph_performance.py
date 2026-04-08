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
from adapters.graph.rdflib_engine import RDFLibQueryEngine


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
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.5),
    (500, 1.0),
    (1000, 2.0),
    (5000, 5.0),
])
def test_graph_build(num_nodes: int, max_time: float) -> None:
    """Measure time to build a graph with specified number of nodes."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(num_nodes)

    start = time.perf_counter()
    graph.build_from_data(nodes, edges)
    elapsed = time.perf_counter() - start

    print(f"\nGraph build ({num_nodes} nodes): {elapsed:.4f}s")
    assert graph.node_count() == num_nodes
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.1),
    (500, 0.1),
    (1000, 0.2),
    (5000, 0.5),
])
def test_shortest_path_query(num_nodes: int, max_time: float) -> None:
    """Measure shortest path query time in a graph of specified size."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(num_nodes)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    path = graph.shortest_path("node_0", f"node_{num_nodes - 1}")
    elapsed = time.perf_counter() - start

    print(f"\nShortest path query ({num_nodes} nodes): {elapsed:.4f}s")
    assert path is not None
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.5),
    (500, 2.0),
    (1000, 5.0),
    (5000, 120.0),
])
def test_centrality_calculation(num_nodes: int, max_time: float) -> None:
    """Measure centrality calculation time in a graph of specified size."""
    graph = NetworkXGraphEngine()
    nodes, edges = _create_graph_data(num_nodes)
    graph.build_from_data(nodes, edges)

    start = time.perf_counter()
    centrality = graph.centrality("betweenness")
    elapsed = time.perf_counter() - start

    print(f"\nCentrality calculation ({num_nodes} nodes): {elapsed:.4f}s")
    assert len(centrality) == num_nodes
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.5),
    (500, 1.0),
    (1000, 2.0),
    (5000, 5.0),
])
def test_sparql_query(num_nodes: int, max_time: float) -> None:
    """Measure SPARQL query execution time in a graph of specified size."""
    # Create RDF-based query engine
    engine = RDFLibQueryEngine()
    nodes, edges = _create_graph_data(num_nodes)

    # Load ontology into RDF graph
    start = time.perf_counter()
    engine.load_ontology(nodes, edges, [])
    elapsed = time.perf_counter() - start
    print(f"\nSPARQL graph load ({num_nodes} nodes): {elapsed:.4f}s")

    # Execute a simple SPARQL query to count entities
    sparql_query = """
    PREFIX cs: <http://context-studio.local/vocab/>
    PREFIX entity: <http://context-studio.local/entity/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT (COUNT(?entity) as ?count)
    WHERE {
        ?entity rdf:type cs:Class .
    }
    """

    start = time.perf_counter()
    results = engine.execute_sparql(sparql_query)
    elapsed = time.perf_counter() - start

    print(f"\nSPARQL query ({num_nodes} nodes): {elapsed:.4f}s")
    assert len(results) > 0
    assert elapsed < max_time
