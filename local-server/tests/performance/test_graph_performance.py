"""Performance tests for graph operations at various scales.

Tests measure graph build time, shortest path queries, SPARQL queries, and
centrality calculations at multiple graph sizes (100, 500, 1000, 5000 nodes).
Tests exercise the domain GraphAnalysisService through its ports.
"""

import sys
import os
import time
import pytest
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.graph.services import GraphAnalysisService
from domain.ontology.entities import Taxonomy, ConceptScheme, Class, Relationship, PropertyDefinition
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


def _setup_graph_service(num_nodes: int) -> tuple[GraphAnalysisService, FakeOntologyRepository, list[str]]:
    """Set up graph analysis service with test data.

    Creates a taxonomy, concept scheme, and classes, building a DAG where
    each node connects to the next 2 nodes.

    Args:
        num_nodes: Number of classes to create

    Returns:
        Tuple of (service, repository, class_ids)
    """
    try:
        from adapters.graph.networkx_engine import NetworkXGraphEngine
        from adapters.graph.rdflib_engine import RDFLibQueryEngine
    except ImportError:
        pytest.skip("NetworkX or RDFLib not installed")

    repository = FakeOntologyRepository()

    # Create taxonomy and concept scheme
    taxonomy = Taxonomy(id=str(uuid4()), title="Test Taxonomy")
    scheme = ConceptScheme(id=str(uuid4()), title="Test Scheme", taxonomy_id=taxonomy.id)
    repository.save_taxonomy(taxonomy)
    repository.save_concept_scheme(scheme)

    # Create a property definition for relationships
    prop_def = PropertyDefinition(
        id=str(uuid4()),
        identifier="relates_to",
        title="Relates To"
    )
    repository.save_property_definition(prop_def)

    # Create classes
    class_ids = []
    for i in range(num_nodes):
        cls = Class(id=str(uuid4()), title=f"Node_{i}", concept_scheme_id=scheme.id, taxonomy_id=taxonomy.id)
        repository.save_class(cls)
        class_ids.append(cls.id)

    # Create edges: each class connects to next 2 classes (creating a DAG)
    for i in range(num_nodes):
        if i + 1 < num_nodes:
            rel = Relationship(
                id=str(uuid4()),
                source_id=class_ids[i],
                target_id=class_ids[i + 1],
                property_definition_id=prop_def.id
            )
            repository.save_relationship(rel)
        if i + 2 < num_nodes:
            rel = Relationship(
                id=str(uuid4()),
                source_id=class_ids[i],
                target_id=class_ids[i + 2],
                property_definition_id=prop_def.id
            )
            repository.save_relationship(rel)

    # Create service with ports
    graph_engine = NetworkXGraphEngine()
    query_engine = RDFLibQueryEngine()
    service = GraphAnalysisService(repository, graph_engine, query_engine)

    return service, repository, class_ids


@pytest.mark.performance
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.002),
    (500, 0.01),
    (1000, 0.02),
    (5000, 0.1),
])
def test_graph_build(num_nodes: int, max_time: float) -> None:
    """Measure time to build a graph with specified number of nodes."""
    service, _, _ = _setup_graph_service(num_nodes)

    start = time.perf_counter()
    result = service.build_graph()
    elapsed = time.perf_counter() - start

    print(f"\nGraph build ({num_nodes} nodes): {elapsed:.4f}s")
    # Graph includes: 1 taxonomy + 1 concept scheme + num_nodes classes + 1 property definition
    assert result.node_count == num_nodes + 3
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.005),
    (500, 0.01),
    (1000, 0.02),
    (5000, 0.13),
])
def test_shortest_path_query(num_nodes: int, max_time: float) -> None:
    """Measure shortest path query time in a graph of specified size."""
    service, _, class_ids = _setup_graph_service(num_nodes)
    service.build_graph()

    start = time.perf_counter()
    result = service.find_shortest_path(class_ids[0], class_ids[num_nodes - 1])
    elapsed = time.perf_counter() - start

    print(f"\nShortest path query ({num_nodes} nodes): {elapsed:.4f}s")
    assert result is not None
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.2),
    (500, 0.5),
    (1000, 2.5),
    (5000, 110.0),
])
def test_centrality_calculation(num_nodes: int, max_time: float) -> None:
    """Measure centrality calculation time in a graph of specified size."""
    service, _, _ = _setup_graph_service(num_nodes)

    start = time.perf_counter()
    centrality = service.get_centrality("betweenness")
    elapsed = time.perf_counter() - start

    print(f"\nCentrality calculation ({num_nodes} nodes): {elapsed:.4f}s")
    # Graph includes: 1 taxonomy + 1 concept scheme + num_nodes classes + 1 property definition
    assert len(centrality) == num_nodes + 3
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_nodes,max_time", [
    (100, 0.1),
    (500, 0.3),
    (1000, 0.5),
    (5000, 1.0),
])
def test_sparql_query(num_nodes: int, max_time: float) -> None:
    """Measure SPARQL query execution time in a graph of specified size."""
    service, _, _ = _setup_graph_service(num_nodes)
    service.build_graph()

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
    results = service.execute_sparql(sparql_query)
    elapsed = time.perf_counter() - start

    print(f"\nSPARQL query ({num_nodes} nodes): {elapsed:.4f}s")
    assert len(results) > 0
    assert elapsed < max_time
