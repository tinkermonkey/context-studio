"""
Integration tests for Graph Analysis API routes.

Tests verify the graph analysis workflow with:
- Real SQLite database (local.db)
- OntologyRepository backed by actual persistence
- NetworkX/RDFLib adapters with real algorithm implementations
- HTTP routes via TestClient
- End-to-end request/response validation

These tests exercise the complete stack: routes → domain service → adapters → database.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
from adapters.persistence.sqlite.models import Base
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
    return SQLiteOntologyRepository(session_factory)


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


class TestGraphBuild:
    """Integration tests for graph build endpoint."""

    def test_build_graph_returns_200(self, client):
        """POST /api/graph/build returns 200."""
        response = client.post("/api/graph/build")
        assert response.status_code == status.HTTP_200_OK

    def test_build_graph_response_structure(self, client):
        """POST /api/graph/build response has correct structure."""
        response = client.post("/api/graph/build")
        body = response.json()

        assert "node_count" in body
        assert "edge_count" in body
        assert "timestamp" in body
        assert body["node_count"] > 0
        assert body["edge_count"] > 0


class TestGraphMetrics:
    """Integration tests for metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """GET /api/graph/metrics returns 200."""
        response = client.get("/api/graph/metrics")
        assert response.status_code == status.HTTP_200_OK

    def test_metrics_response_structure(self, client):
        """GET /api/graph/metrics response has correct structure."""
        response = client.get("/api/graph/metrics")
        body = response.json()

        assert "density" in body
        assert "average_degree" in body
        assert "connected_components" in body
        assert "centrality" in body

        assert isinstance(body["density"], float)
        assert isinstance(body["average_degree"], float)
        assert isinstance(body["connected_components"], int)

    def test_metrics_with_algorithm_parameter(self, client):
        """GET /api/graph/metrics works with algorithm parameter."""
        response = client.get("/api/graph/metrics?algorithm=pagerank")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["algorithm"] == "pagerank"


class TestDegreeDistribution:
    """Integration tests for degree distribution endpoint."""

    def test_degree_distribution_returns_200(self, client):
        """GET /api/graph/degree-distribution returns 200."""
        response = client.get("/api/graph/degree-distribution")
        assert response.status_code == status.HTTP_200_OK

    def test_degree_distribution_response_structure(self, client):
        """GET /api/graph/degree-distribution response has correct structure."""
        response = client.get("/api/graph/degree-distribution")
        body = response.json()

        assert "in_degree" in body
        assert "out_degree" in body
        assert isinstance(body["in_degree"], dict)
        assert isinstance(body["out_degree"], dict)


class TestPathFinding:
    """Integration tests for path finding endpoints."""

    def test_shortest_path_returns_200(self, client, populated_repository):
        """GET /api/graph/paths/shortest returns 200."""
        classes = list(populated_repository.list_classes())
        assert len(classes) >= 2, "populated_repository fixture must contain at least 2 classes"
        response = client.get(
            f"/api/graph/paths/shortest?source_id={classes[0].id}&target_id={classes[1].id}"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_all_paths_returns_200(self, client, populated_repository):
        """GET /api/graph/paths/all returns 200."""
        classes = list(populated_repository.list_classes())
        assert len(classes) >= 2, "populated_repository fixture must contain at least 2 classes"
        response = client.get(
            f"/api/graph/paths/all?source_id={classes[0].id}&target_id={classes[1].id}"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)

    def test_shortest_path_nonexistent_node_returns_404(self, client):
        """GET /api/graph/paths/shortest returns 404 for nonexistent nodes."""
        response = client.get(
            f"/api/graph/paths/shortest?source_id={uuid4()}&target_id={uuid4()}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCentrality:
    """Integration tests for centrality endpoint."""

    def test_centrality_returns_200(self, client):
        """GET /api/graph/centrality returns 200."""
        response = client.get("/api/graph/centrality")
        assert response.status_code == status.HTTP_200_OK

    def test_centrality_response_structure(self, client):
        """GET /api/graph/centrality response has correct structure."""
        response = client.get("/api/graph/centrality")
        body = response.json()

        assert "algorithm" in body
        assert "scores" in body
        assert isinstance(body["scores"], dict)

    def test_centrality_with_different_algorithms(self, client):
        """GET /api/graph/centrality works with different algorithms."""
        algorithms = ["betweenness", "pagerank", "closeness", "degree"]
        for algo in algorithms:
            response = client.get(f"/api/graph/centrality?algorithm={algo}")
            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert body["algorithm"] == algo


class TestCommunities:
    """Integration tests for communities endpoint."""

    def test_communities_returns_200(self, client):
        """GET /api/graph/communities returns 200."""
        response = client.get("/api/graph/communities")
        assert response.status_code == status.HTTP_200_OK

    def test_communities_response_structure(self, client):
        """GET /api/graph/communities response has correct structure."""
        response = client.get("/api/graph/communities")
        body = response.json()

        assert "algorithm" in body
        assert "communities" in body
        assert isinstance(body["communities"], list)

    def test_communities_with_algorithm_parameter(self, client):
        """GET /api/graph/communities works with algorithm parameter."""
        response = client.get("/api/graph/communities?algorithm=louvain")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["algorithm"] == "louvain"


class TestNeighbors:
    """Integration tests for neighbors endpoint."""

    def test_neighbors_returns_200(self, client, populated_repository):
        """GET /api/graph/nodes/{id}/neighbors returns 200."""
        classes = list(populated_repository.list_classes())
        assert len(classes) > 0, "populated_repository fixture must contain at least 1 class"
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors")
        assert response.status_code == status.HTTP_200_OK

    def test_neighbors_response_structure(self, client, populated_repository):
        """GET /api/graph/nodes/{id}/neighbors response has correct structure."""
        classes = list(populated_repository.list_classes())
        assert len(classes) > 0, "populated_repository fixture must contain at least 1 class"
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors")
        body = response.json()

        assert "node_id" in body
        assert "incoming" in body
        assert "outgoing" in body
        assert isinstance(body["incoming"], list)
        assert isinstance(body["outgoing"], list)

    def test_neighbors_nonexistent_node_returns_404(self, client):
        """GET /api/graph/nodes/{id}/neighbors returns 404 for nonexistent node."""
        response = client.get(f"/api/graph/nodes/{uuid4()}/neighbors")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_neighbors_depth_parameter_respected(self, client, populated_repository):
        """GET /api/graph/nodes/{id}/neighbors respects the depth parameter."""
        classes = list(populated_repository.list_classes())
        assert len(classes) > 0, "populated_repository fixture must contain at least 1 class"

        # Get neighbors with depth=1 and depth=2
        response_depth1 = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors?depth=1")
        response_depth2 = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors?depth=2")

        assert response_depth1.status_code == status.HTTP_200_OK
        assert response_depth2.status_code == status.HTTP_200_OK

        # Depth 2 should return a superset of depth 1 neighbors
        neighbors1 = set(response_depth1.json()["incoming"] + response_depth1.json()["outgoing"])
        neighbors2 = set(response_depth2.json()["incoming"] + response_depth2.json()["outgoing"])

        assert neighbors1.issubset(neighbors2)


class TestCycleCheck:
    """Integration tests for cycle check endpoint."""

    def test_cycle_check_returns_200(self, client, populated_repository):
        """POST /api/graph/cycle-check returns 200."""
        classes = list(populated_repository.list_classes())
        assert len(classes) >= 2, "populated_repository fixture must contain at least 2 classes"
        response = client.post("/api/graph/cycle-check", json={
            "source_id": classes[0].id,
            "target_id": classes[1].id,
        })
        assert response.status_code == status.HTTP_200_OK

    def test_cycle_check_response_structure(self, client, populated_repository):
        """POST /api/graph/cycle-check response has correct structure."""
        classes = list(populated_repository.list_classes())
        assert len(classes) >= 2, "populated_repository fixture must contain at least 2 classes"
        response = client.post("/api/graph/cycle-check", json={
            "source_id": classes[0].id,
            "target_id": classes[1].id,
        })
        body = response.json()

        assert "would_create_cycle" in body
        assert isinstance(body["would_create_cycle"], bool)


class TestSPARQL:
    """Integration tests for SPARQL endpoint."""

    def test_sparql_returns_200(self, client):
        """POST /api/graph/sparql returns 200 with valid query."""
        response = client.post("/api/graph/sparql", json={
            "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
        })
        assert response.status_code == status.HTTP_200_OK

    def test_sparql_response_structure(self, client):
        """POST /api/graph/sparql response has correct structure."""
        response = client.post("/api/graph/sparql", json={
            "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
        })
        body = response.json()

        assert "results" in body
        assert isinstance(body["results"], list)

    def test_sparql_invalid_query_returns_400(self, client):
        """POST /api/graph/sparql returns 400 with invalid query."""
        response = client.post("/api/graph/sparql", json={
            "query": "INVALID SPARQL QUERY"
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRDF:
    """Integration tests for RDF endpoints."""

    def test_rdf_triples_returns_200(self, client):
        """GET /api/graph/rdf/triples returns 200."""
        response = client.get("/api/graph/rdf/triples")
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_triples_response_structure(self, client):
        """GET /api/graph/rdf/triples response has correct structure."""
        response = client.get("/api/graph/rdf/triples")
        body = response.json()

        assert "triples" in body
        assert isinstance(body["triples"], list)

    def test_rdf_count_returns_200(self, client):
        """GET /api/graph/rdf/count returns 200."""
        response = client.get("/api/graph/rdf/count")
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_count_response_structure(self, client):
        """GET /api/graph/rdf/count response has correct structure."""
        response = client.get("/api/graph/rdf/count")
        body = response.json()

        assert "count" in body
        assert isinstance(body["count"], int)
        assert body["count"] >= 0


class TestSubgraph:
    """Integration tests for subgraph endpoints."""

    def test_subgraph_returns_200(self, client, populated_repository):
        """GET /api/graph/subgraph returns 200."""
        classes = list(populated_repository.list_classes())
        assert len(classes) > 0, "populated_repository fixture must contain at least 1 class"
        response = client.get(f"/api/graph/subgraph?nodes={classes[0].id}")
        assert response.status_code == status.HTTP_200_OK

    def test_subgraph_response_structure(self, client, populated_repository):
        """GET /api/graph/subgraph response has correct structure."""
        classes = list(populated_repository.list_classes())
        assert len(classes) > 0, "populated_repository fixture must contain at least 1 class"
        response = client.get(f"/api/graph/subgraph?nodes={classes[0].id}")
        body = response.json()

        assert "nodes" in body
        assert "edges" in body
        assert isinstance(body["nodes"], list)
        assert isinstance(body["edges"], list)

    def test_node_subgraph_returns_200(self, client, populated_repository):
        """GET /api/graph/nodes/{id}/subgraph returns 200."""
        classes = list(populated_repository.list_classes())
        assert len(classes) > 0, "populated_repository fixture must contain at least 1 class"
        response = client.get(f"/api/graph/nodes/{classes[0].id}/subgraph")
        assert response.status_code == status.HTTP_200_OK

    def test_node_subgraph_response_structure(self, client, populated_repository):
        """GET /api/graph/nodes/{id}/subgraph response has correct structure."""
        classes = list(populated_repository.list_classes())
        assert len(classes) > 0, "populated_repository fixture must contain at least 1 class"
        response = client.get(f"/api/graph/nodes/{classes[0].id}/subgraph")
        body = response.json()

        assert "node_id" in body
        assert "subgraph" in body
        assert "depth" in body
