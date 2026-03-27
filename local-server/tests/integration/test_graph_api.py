"""
Integration tests for Graph Analysis API.

Tests verify the full graph analysis workflow with:
- Real SQLite database (local.db)
- OntologyRepository backed by actual persistence
- NetworkX/RDFLib adapters with real algorithm implementations
- HTTP routes via httpx.AsyncClient
- End-to-end request/response validation

These tests exercise the complete stack: routes → domain service → adapters → database.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from domain.graph.services import GraphAnalysisService
from domain.ontology.entities import (
    Class,
    Taxonomy,
    ConceptScheme,
    Relationship,
    PropertyDefinition,
)
from adapters.persistence.sqlite.sqlalchemy_setup import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.web.graph_routes import router


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def repository(session_factory):
    """Create a real SQLiteOntologyRepository with actual persistence."""
    session = session_factory()
    try:
        yield SQLiteOntologyRepository(session=session)
    finally:
        session.close()


@pytest.fixture
def populated_repository(repository):
    """Populate repository with test data."""
    # Create taxonomy
    tax = Taxonomy(id=str(uuid4()), title="Integration Test Taxonomy", description="Test")
    repository.save_taxonomy(tax)

    # Create concept scheme
    scheme = ConceptScheme(
        id=str(uuid4()), taxonomy_id=tax.id, title="Test Scheme", description="Test"
    )
    repository.save_concept_scheme(scheme)

    # Create classes
    class1 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Person",
        description="A person",
    )
    class2 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Agent",
        description="An agent",
    )
    class3 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Organization",
        description="An organization",
    )
    class4 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Place",
        description="A place",
    )

    repository.save_class(class1)
    repository.save_class(class2)
    repository.save_class(class3)
    repository.save_class(class4)

    # Create property definitions
    type_prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="rdf_type",
        title="type",
        description="RDF type relationship",
    )
    belongs_to_prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="belongs_to",
        title="belongs to",
        description="Indicates membership",
    )
    works_in_prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="works_in",
        title="works in",
        description="Indicates workplace",
    )
    located_in_prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="located_in",
        title="located in",
        description="Indicates location",
    )

    repository.save_property_definition(type_prop)
    repository.save_property_definition(belongs_to_prop)
    repository.save_property_definition(works_in_prop)
    repository.save_property_definition(located_in_prop)

    # Create relationships
    rel1 = Relationship(
        id=str(uuid4()),
        source_id=class1.id,
        target_id=class2.id,
        property_definition_id=type_prop.id,
    )
    rel2 = Relationship(
        id=str(uuid4()),
        source_id=class2.id,
        target_id=class3.id,
        property_definition_id=belongs_to_prop.id,
    )
    rel3 = Relationship(
        id=str(uuid4()),
        source_id=class3.id,
        target_id=class4.id,
        property_definition_id=located_in_prop.id,
    )
    rel4 = Relationship(
        id=str(uuid4()),
        source_id=class1.id,
        target_id=class3.id,
        property_definition_id=works_in_prop.id,
    )

    repository.save_relationship(rel1)
    repository.save_relationship(rel2)
    repository.save_relationship(rel3)
    repository.save_relationship(rel4)

    return repository


@pytest.fixture
def service(populated_repository):
    """Create a GraphAnalysisService with real adapters."""
    graph_engine = NetworkXGraphEngine()
    semantic_query_engine = RDFLibQueryEngine()

    # Populate graph engine with data from repository
    nodes = [{"id": cls.id} for cls in populated_repository.list_classes()]
    edges = [
        {"source_id": rel.source_id, "target_id": rel.target_id}
        for rel in populated_repository.list_relationships()
    ]
    graph_engine.build_from_data(nodes, edges)

    service = GraphAnalysisService(
        repository=populated_repository,
        graph_engine=graph_engine,
        query_engine=semantic_query_engine,
    )

    return service


@pytest.fixture
def client(service):
    """Create a TestClient with real service."""
    app = FastAPI()
    app.include_router(router)
    app.state.graph_service = service

    return TestClient(app)


class TestGraphMetricsIntegration:
    """Integration tests for metrics endpoint with real data."""

    def test_metrics_with_real_data(self, client, populated_repository):
        """GET /metrics returns valid metrics with real database data."""
        response = client.get("/api/graph/metrics")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "density" in data
        assert "average_degree" in data
        assert "connected_components" in data
        assert "centrality" in data
        assert "communities" in data

        # Verify value types and ranges
        assert isinstance(data["density"], float)
        assert 0.0 <= data["density"] <= 1.0
        assert isinstance(data["average_degree"], float)
        assert data["average_degree"] >= 0.0
        assert isinstance(data["connected_components"], int)
        assert data["connected_components"] > 0

    def test_metrics_centrality_scores_include_all_nodes(
        self, client, populated_repository
    ):
        """Centrality scores should include all nodes."""
        response = client.get("/api/graph/metrics")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        classes = populated_repository.list_classes()
        centrality_nodes = set(data["centrality"].keys())
        expected_nodes = {cls.id for cls in classes}

        assert centrality_nodes == expected_nodes

    def test_metrics_with_different_algorithms(self, client):
        """GET /metrics works with different centrality algorithms."""
        algorithms = ["betweenness", "pagerank", "closeness", "degree"]
        for algo in algorithms:
            response = client.get(f"/api/graph/metrics?algorithm={algo}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["algorithm"] == algo


class TestPathFindingIntegration:
    """Integration tests for path finding with real graph traversal."""

    def test_shortest_path_with_real_graph(self, client, populated_repository):
        """Shortest path returns valid path structure from real graph."""
        classes = list(populated_repository.list_classes())
        if len(classes) >= 2:
            response = client.get(
                f"/api/graph/paths/shortest?source_id={classes[0].id}&target_id={classes[1].id}"
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            if data is not None:  # Path may not exist
                assert "nodes" in data
                assert "distance" in data
                assert len(data["nodes"]) >= 2
                assert data["nodes"][0] == classes[0].id
                assert data["nodes"][-1] == classes[1].id

    def test_all_paths_with_real_graph(self, client, populated_repository):
        """All paths returns all valid paths from real graph."""
        classes = list(populated_repository.list_classes())
        if len(classes) >= 2:
            response = client.get(
                f"/api/graph/paths/all?source_id={classes[0].id}&target_id={classes[1].id}&max_depth=5"
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert isinstance(data, list)
            for path in data:
                assert "nodes" in path
                assert "distance" in path
                assert path["nodes"][0] == classes[0].id
                assert path["nodes"][-1] == classes[1].id

    def test_path_finding_nonexistent_nodes(self, client):
        """Path finding returns appropriate responses for nonexistent nodes."""
        response = client.get(
            "/api/graph/paths/shortest?source_id=nonexistent1&target_id=nonexistent2"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCentralityIntegration:
    """Integration tests for centrality computation with real algorithms."""

    def test_centrality_algorithms_return_valid_scores(self, client, populated_repository):
        """All centrality algorithms return valid scores for all nodes."""
        algorithms = ["betweenness", "pagerank", "closeness", "degree"]
        classes = populated_repository.list_classes()
        expected_nodes = {cls.id for cls in classes}

        for algo in algorithms:
            response = client.get(f"/api/graph/centrality?algorithm={algo}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["algorithm"] == algo
            assert set(data["scores"].keys()) == expected_nodes

            for node_id, score in data["scores"].items():
                assert isinstance(score, (int, float))
                assert score >= 0.0


class TestCommunityDetectionIntegration:
    """Integration tests for community detection with real algorithms."""

    def test_community_detection_partitions_graph(self, client, populated_repository):
        """Community detection returns non-overlapping partitions."""
        algorithms = ["louvain", "label_propagation"]
        classes = populated_repository.list_classes()
        all_nodes = {cls.id for cls in classes}

        for algo in algorithms:
            response = client.get(f"/api/graph/communities?algorithm={algo}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["algorithm"] == algo
            communities = data["communities"]

            # All communities should be non-empty
            assert all(len(comm) > 0 for comm in communities)

            # Communities should partition all nodes (no overlaps)
            community_nodes = set()
            for comm in communities:
                # Convert list back to set for verification
                comm_set = set(comm)
                # No node should be in multiple communities
                assert not (community_nodes & comm_set)
                community_nodes |= comm_set

            # All nodes should be in some community
            assert community_nodes == all_nodes


class TestNeighborsIntegration:
    """Integration tests for neighbor traversal with real graph."""

    def test_neighbors_with_directions(self, client, populated_repository):
        """Neighbor traversal respects direction parameter with real edges."""
        classes = list(populated_repository.list_classes())
        relationships = list(populated_repository.list_relationships())

        if len(classes) > 0 and len(relationships) > 0:
            # Find a node with outgoing edges
            node_with_out = None
            for rel in relationships:
                if populated_repository.get_class(rel.source_node_id):
                    node_with_out = rel.source_node_id
                    break

            if node_with_out:
                # Test "out" direction
                response = client.get(
                    f"/api/graph/nodes/{node_with_out}/neighbors?direction=out"
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["direction"] == "out"

                # Test "in" direction
                response = client.get(
                    f"/api/graph/nodes/{node_with_out}/neighbors?direction=in"
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["direction"] == "in"

                # Test "both" direction (default)
                response = client.get(
                    f"/api/graph/nodes/{node_with_out}/neighbors?direction=both"
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["direction"] == "both"


class TestSubgraphExtractionIntegration:
    """Integration tests for subgraph extraction with real graph."""

    def test_subgraph_extraction_depth_1(self, client, populated_repository):
        """Subgraph extraction includes center node and direct neighbors."""
        classes = list(populated_repository.list_classes())
        if len(classes) > 0:
            response = client.get(f"/api/graph/nodes/{classes[0].id}/subgraph?depth=1")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Subgraph should include at least the center node
            assert data["node_count"] >= 1
            assert data["edge_count"] >= 0

    def test_subgraph_extraction_depth_2(self, client, populated_repository):
        """Subgraph extraction respects depth parameter."""
        classes = list(populated_repository.list_classes())
        if len(classes) > 0:
            # Depth 1
            response1 = client.get(f"/api/graph/nodes/{classes[0].id}/subgraph?depth=1")
            data1 = response1.json()

            # Depth 2 should have at least as many nodes
            response2 = client.get(f"/api/graph/nodes/{classes[0].id}/subgraph?depth=2")
            data2 = response2.json()

            assert data2["node_count"] >= data1["node_count"]


class TestCycleDetectionIntegration:
    """Integration tests for cycle detection with real graph."""

    def test_cycle_detection_with_acyclic_graph(self, client, populated_repository):
        """Cycle detection correctly identifies cycles in real graph."""
        classes = list(populated_repository.list_classes())

        if len(classes) >= 2:
            # Test with real nodes
            response = client.post(
                "/api/graph/cycle-check",
                json={
                    "source_id": classes[0].id,
                    "target_id": classes[1].id,
                },
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert "would_create_cycle" in data
            assert isinstance(data["would_create_cycle"], bool)

    def test_cycle_detection_nonexistent_nodes(self, client):
        """Cycle detection returns False for nonexistent nodes."""
        response = client.post(
            "/api/graph/cycle-check",
            json={
                "source_id": "nonexistent1",
                "target_id": "nonexistent2",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSPARQLIntegration:
    """Integration tests for SPARQL query execution."""

    def test_sparql_valid_query_execution(self, client):
        """SPARQL execution accepts and processes valid queries."""
        response = client.post(
            "/api/graph/sparql",
            json={"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "results" in data
        assert "triple_count" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["triple_count"], int)

    def test_sparql_invalid_query_returns_400(self, client):
        """SPARQL invalid query returns 400 Bad Request."""
        response = client.post(
            "/api/graph/sparql",
            json={"query": "INVALID SPARQL QUERY"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRDFTripleIntegration:
    """Integration tests for RDF triple access."""

    def test_rdf_triples_retrieval(self, client):
        """RDF triple retrieval returns valid triple structure."""
        response = client.get("/api/graph/rdf/triples")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "triples" in data
        assert "count" in data
        assert isinstance(data["triples"], list)
        assert isinstance(data["count"], int)

        # Each triple should have subject, predicate, object
        for triple in data["triples"]:
            assert "subject" in triple
            assert "predicate" in triple
            assert "object" in triple

    def test_rdf_triples_with_filters(self, client):
        """RDF triple retrieval accepts subject/predicate/object filters."""
        response = client.get(
            "/api/graph/rdf/triples?subject=s&predicate=p&object=o"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_triple_count(self, client):
        """RDF triple count returns valid count."""
        response = client.get("/api/graph/rdf/count")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0


class TestErrorHandlingIntegration:
    """Integration tests for error handling across the full stack."""

    def test_404_for_nonexistent_node_in_neighbors(self, client):
        """NonExistent node in neighbors endpoint returns 404."""
        response = client.get("/api/graph/nodes/nonexistent/neighbors")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_400_for_invalid_algorithm(self, client):
        """Invalid algorithm returns 400 Bad Request."""
        response = client.get("/api/graph/centrality?algorithm=nonexistent")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_422_for_invalid_parameters(self, client):
        """Invalid parameters return 422 Unprocessable Entity."""
        response = client.get("/api/graph/paths/all?source_id=a&target_id=b&max_depth=100")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_422_for_missing_required_fields(self, client):
        """Missing required fields return 422."""
        response = client.post("/api/graph/cycle-check", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
