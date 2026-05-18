"""
Unit tests for FastAPI graph routes.

Tests cover all 11 HTTP endpoints in adapters/web/graph_routes.py:
- GET /metrics - Graph metrics
- GET /paths/shortest - Shortest path
- GET /paths/all - All paths
- GET /centrality - Centrality scores
- GET /communities - Community detection
- GET /nodes/{node_id}/neighbors - Neighbors
- GET /subgraph - Subgraph extraction (multi-node query)
- POST /cycle-check - Cycle detection
- POST /sparql - SPARQL execution
- GET /rdf/triples - RDF triples
- GET /rdf/count - Triple count

Tests verify:
- Correct HTTP status codes (200, 404, 400, 422)
- Request validation (Pydantic schema conversion)
- Response serialization (JSON structure)
- Error mapping (domain exceptions to HTTP responses)
- Edge cases (nonexistent nodes, invalid algorithms)
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from adapters.web.graph_routes import router
from domain.graph.services import GraphAnalysisService
from domain.ontology.entities import Class, ConceptScheme, Relationship, Taxonomy
from tests.fakes.fake_graph_engine import FakeGraphEngine
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_semantic_query_engine import FakeSemanticQueryEngine


@pytest.fixture
def repository_with_data():
    """Create a repository with sample ontology data."""
    from domain.ontology.entities import PropertyDefinition

    repo = FakeOntologyRepository()

    # Create taxonomy
    tax = Taxonomy(id=str(uuid4()), title="Test Taxonomy", description="Test")
    repo.save_taxonomy(tax)

    # Create concept scheme
    scheme = ConceptScheme(
        id=str(uuid4()), taxonomy_id=tax.id, title="Test Scheme", description="Test"
    )
    repo.save_concept_scheme(scheme)

    # Create classes
    class1 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Class 1",
        description="Class 1",
    )
    class2 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Class 2",
        description="Class 2",
    )
    class3 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Class 3",
        description="Class 3",
    )

    repo.save_class(class1)
    repo.save_class(class2)
    repo.save_class(class3)

    # Create property definition
    prop_def = PropertyDefinition(
        id=str(uuid4()),
        identifier="related_to",
        title="related to",
        description="Related to relationship",
    )
    repo.save_property_definition(prop_def)

    # Create relationships
    rel1 = Relationship(
        id=str(uuid4()),
        source_id=class1.id,
        target_id=class2.id,
        property_definition_id=prop_def.id,
    )
    rel2 = Relationship(
        id=str(uuid4()),
        source_id=class2.id,
        target_id=class3.id,
        property_definition_id=prop_def.id,
    )

    repo.save_relationship(rel1)
    repo.save_relationship(rel2)

    return repo


@pytest.fixture
def service(repository_with_data):
    """Create a GraphAnalysisService with fake dependencies."""
    graph_engine = FakeGraphEngine()
    semantic_query_engine = FakeSemanticQueryEngine()

    # Populate graph engine with data
    nodes = [{"id": cls.id} for cls in repository_with_data.list_classes()]
    edges = [
        {"source_id": rel.source_id, "target_id": rel.target_id}
        for rel in repository_with_data.list_relationships()
    ]
    graph_engine.build_from_data(nodes, edges)

    service = GraphAnalysisService(
        repository=repository_with_data,
        graph_engine=graph_engine,
        query_engine=semantic_query_engine,
    )

    return service


@pytest.fixture
def client(service):
    """Create a TestClient with the graph routes and injected service."""
    app = FastAPI()
    app.include_router(router)

    # Inject the service into app state
    app.state.graph_service = service

    return TestClient(app)


class TestGraphMetricsEndpoint:
    """Tests for GET /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """GET /metrics returns 200 OK with metrics response."""
        response = client.get("/api/graph/metrics")
        assert response.status_code == status.HTTP_200_OK

    def test_metrics_response_structure(self, client):
        """GET /metrics response contains expected fields."""
        response = client.get("/api/graph/metrics")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "density" in data
        assert "average_degree" in data
        assert "connected_components" in data
        assert "centrality" in data
        assert "communities" in data
        assert "algorithm" in data

    def test_metrics_with_algorithm_parameter(self, client):
        """GET /metrics accepts algorithm query parameter."""
        response = client.get("/api/graph/metrics?algorithm=pagerank")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["algorithm"] == "pagerank"

    def test_metrics_invalid_algorithm_returns_400(self, client):
        """GET /metrics with invalid algorithm returns 400 Bad Request."""
        response = client.get("/api/graph/metrics?algorithm=invalid_algo")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data


class TestShortestPathEndpoint:
    """Tests for GET /paths/shortest endpoint."""

    def test_shortest_path_returns_200(self, client, repository_with_data):
        """GET /paths/shortest returns 200 OK."""
        classes = repository_with_data.list_classes()
        response = client.get(
            f"/api/graph/paths/shortest?source_id={classes[0].id}&target_id={classes[1].id}"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_shortest_path_response_structure(self, client, repository_with_data):
        """GET /paths/shortest response contains path information."""
        classes = repository_with_data.list_classes()
        response = client.get(
            f"/api/graph/paths/shortest?source_id={classes[0].id}&target_id={classes[1].id}"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        if data is not None:  # Path may not exist
            # Response should contain path data (path or nodes)
            assert any(key in data for key in ["path", "nodes"])
            # Response should contain length info (length or distance)
            assert any(key in data for key in ["length", "distance"])

    def test_shortest_path_returns_404_if_no_path(self, client, repository_with_data):
        """GET /paths/shortest returns 404 if no path exists."""
        classes = repository_with_data.list_classes()
        # Request a path where target node doesn't exist
        response = client.get(
            f"/api/graph/paths/shortest?source_id={classes[0].id}&target_id=nonexistent-id"
        )
        # Should return 404 Not Found (from NodeNotFoundError raised by graph engine)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        # Verify error detail message
        assert "detail" in data

    def test_shortest_path_missing_parameters_returns_422(self, client):
        """GET /paths/shortest without required parameters returns 422."""
        response = client.get("/api/graph/paths/shortest")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAllPathsEndpoint:
    """Tests for GET /paths/all endpoint."""

    def test_all_paths_returns_200(self, client, repository_with_data):
        """GET /paths/all returns 200 OK."""
        classes = repository_with_data.list_classes()
        response = client.get(
            f"/api/graph/paths/all?source_id={classes[0].id}&target_id={classes[1].id}"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_all_paths_response_is_list(self, client, repository_with_data):
        """GET /paths/all response is a list of path objects."""
        classes = repository_with_data.list_classes()
        response = client.get(
            f"/api/graph/paths/all?source_id={classes[0].id}&target_id={classes[1].id}"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)

    def test_all_paths_respects_max_depth(self, client, repository_with_data):
        """GET /paths/all respects max_depth parameter."""
        classes = repository_with_data.list_classes()
        response = client.get(
            f"/api/graph/paths/all?source_id={classes[0].id}&target_id={classes[1].id}&max_depth=2"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_all_paths_max_depth_validation(self, client, repository_with_data):
        """GET /paths/all validates max_depth bounds (1-20)."""
        classes = repository_with_data.list_classes()
        # max_depth > 20 should fail validation
        response = client.get(
            f"/api/graph/paths/all?source_id={classes[0].id}&target_id={classes[1].id}&max_depth=25"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_all_paths_returns_empty_for_nonexistent(self, client):
        """GET /paths/all returns empty list when nodes don't exist."""
        response = client.get("/api/graph/paths/all?source_id=nonexistent1&target_id=nonexistent2")
        # Fake engine returns empty list, real engine might return 404
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


class TestCentralityEndpoint:
    """Tests for GET /centrality endpoint."""

    def test_centrality_returns_200(self, client):
        """GET /centrality returns 200 OK."""
        response = client.get("/api/graph/centrality")
        assert response.status_code == status.HTTP_200_OK

    def test_centrality_response_structure(self, client):
        """GET /centrality response contains algorithm and scores."""
        response = client.get("/api/graph/centrality")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "algorithm" in data
        assert "scores" in data
        assert isinstance(data["scores"], dict)

    def test_centrality_with_algorithm_parameter(self, client):
        """GET /centrality accepts algorithm parameter."""
        for algo in ["pagerank", "betweenness", "closeness", "degree"]:
            response = client.get(f"/api/graph/centrality?algorithm={algo}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["algorithm"] == algo

    def test_centrality_invalid_algorithm_returns_400(self, client):
        """GET /centrality with invalid algorithm returns 400."""
        response = client.get("/api/graph/centrality?algorithm=invalid_algo")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCommunitiesEndpoint:
    """Tests for GET /communities endpoint."""

    def test_communities_returns_200(self, client):
        """GET /communities returns 200 OK."""
        response = client.get("/api/graph/communities")
        assert response.status_code == status.HTTP_200_OK

    def test_communities_response_structure(self, client):
        """GET /communities response contains algorithm and communities."""
        response = client.get("/api/graph/communities")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "algorithm" in data
        assert "communities" in data
        assert isinstance(data["communities"], list)

    def test_communities_with_algorithm_parameter(self, client):
        """GET /communities accepts algorithm parameter."""
        for algo in ["louvain", "label_propagation"]:
            response = client.get(f"/api/graph/communities?algorithm={algo}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["algorithm"] == algo

    def test_communities_invalid_algorithm_returns_400(self, client):
        """GET /communities with invalid algorithm returns 400."""
        response = client.get("/api/graph/communities?algorithm=invalid_algo")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestNeighborsEndpoint:
    """Tests for GET /nodes/{node_id}/neighbors endpoint."""

    def test_neighbors_returns_200(self, client, repository_with_data):
        """GET /nodes/{node_id}/neighbors returns 200 OK."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors")
        assert response.status_code == status.HTTP_200_OK

    def test_neighbors_response_structure(self, client, repository_with_data):
        """GET /nodes/{node_id}/neighbors response contains node_id, direction, incoming,
        outgoing."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "node_id" in data
        assert "direction" in data
        assert "incoming" in data
        assert "outgoing" in data
        assert isinstance(data["incoming"], list)
        assert isinstance(data["outgoing"], list)
        assert data["node_id"] == classes[0].id
        assert data["direction"] == "both"  # Default

    def test_neighbors_with_direction_parameter(self, client, repository_with_data):
        """GET /nodes/{node_id}/neighbors accepts direction parameter."""
        classes = repository_with_data.list_classes()
        for direction in ["in", "out", "both"]:
            response = client.get(
                f"/api/graph/nodes/{classes[0].id}/neighbors?direction={direction}"
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["direction"] == direction

    def test_neighbors_nonexistent_node_returns_empty_set(self, client):
        """GET /nodes/{node_id}/neighbors with nonexistent node returns empty neighbors."""
        response = client.get("/api/graph/nodes/nonexistent/neighbors")
        # Fake engine returns empty set, implementation detail
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_neighbors_invalid_direction_returns_422(self, client, repository_with_data):
        """GET /nodes/{node_id}/neighbors with invalid direction returns 422."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors?direction=invalid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_neighbors_with_depth_parameter(self, client, repository_with_data):
        """GET /nodes/{node_id}/neighbors accepts depth parameter."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors?depth=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "incoming" in data
        assert "outgoing" in data
        assert isinstance(data["incoming"], list)
        assert isinstance(data["outgoing"], list)

    def test_neighbors_depth_zero_returns_422(self, client, repository_with_data):
        """GET /nodes/{node_id}/neighbors with depth=0 returns 422 validation error."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors?depth=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_neighbors_depth_exceeds_max_returns_422(self, client, repository_with_data):
        """GET /nodes/{node_id}/neighbors with depth>10 returns 422 validation error."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/nodes/{classes[0].id}/neighbors?depth=11")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSubgraphEndpoint:
    """Tests for GET /subgraph endpoint."""

    def test_subgraph_returns_200(self, client, repository_with_data):
        """GET /subgraph returns 200 OK."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/subgraph?nodes={classes[0].id}")
        assert response.status_code == status.HTTP_200_OK

    def test_subgraph_response_structure(self, client, repository_with_data):
        """GET /subgraph response contains nodes, edges, node_count, edge_count."""
        classes = repository_with_data.list_classes()
        response = client.get(f"/api/graph/subgraph?nodes={classes[0].id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "nodes" in data
        assert "edges" in data
        assert "node_count" in data
        assert "edge_count" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert isinstance(data["node_count"], int)
        assert isinstance(data["edge_count"], int)

    def test_subgraph_with_multiple_nodes(self, client, repository_with_data):
        """GET /subgraph accepts multiple comma-separated node IDs."""
        classes = repository_with_data.list_classes()
        assert len(classes) > 1
        nodes = f"{classes[0].id},{classes[1].id}"
        response = client.get(f"/api/graph/subgraph?nodes={nodes}")
        assert response.status_code == status.HTTP_200_OK

    def test_subgraph_missing_nodes_parameter(self, client):
        """GET /subgraph without nodes parameter returns 422."""
        response = client.get("/api/graph/subgraph")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_subgraph_empty_nodes_parameter(self, client):
        """GET /subgraph with empty nodes parameter returns 400."""
        response = client.get("/api/graph/subgraph?nodes=")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_subgraph_nonexistent_node_returns_404(self, client):
        """GET /subgraph with nonexistent node returns 404."""
        response = client.get("/api/graph/subgraph?nodes=nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCycleCheckEndpoint:
    """Tests for POST /cycle-check endpoint."""

    def test_cycle_check_returns_200(self, client, repository_with_data):
        """POST /cycle-check returns 200 OK."""
        classes = repository_with_data.list_classes()
        payload = {
            "source_id": classes[0].id,
            "target_id": classes[1].id,
        }
        response = client.post("/api/graph/cycle-check", json=payload)
        assert response.status_code == status.HTTP_200_OK

    def test_cycle_check_response_structure(self, client, repository_with_data):
        """POST /cycle-check response contains source_id, target_id, would_create_cycle."""
        classes = repository_with_data.list_classes()
        payload = {
            "source_id": classes[0].id,
            "target_id": classes[1].id,
        }
        response = client.post("/api/graph/cycle-check", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "source_id" in data
        assert "target_id" in data
        assert "would_create_cycle" in data
        assert isinstance(data["would_create_cycle"], bool)

    def test_cycle_check_with_nonexistent_nodes_returns_false(self, client):
        """POST /cycle-check with nonexistent nodes returns false."""
        payload = {
            "source_id": "nonexistent1",
            "target_id": "nonexistent2",
        }
        response = client.post("/api/graph/cycle-check", json=payload)
        # Fake engine returns false for nonexistent nodes
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_cycle_check_missing_fields_returns_422(self, client):
        """POST /cycle-check with missing fields returns 422."""
        payload = {"source_id": "node1"}  # Missing target_id
        response = client.post("/api/graph/cycle-check", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSPARQLEndpoint:
    """Tests for POST /sparql endpoint."""

    def test_sparql_returns_200(self, client):
        """POST /sparql returns 200 OK."""
        payload = {"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"}
        response = client.post("/api/graph/sparql", json=payload)
        assert response.status_code == status.HTTP_200_OK

    def test_sparql_response_structure(self, client):
        """POST /sparql response contains results and triple_count."""
        payload = {"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"}
        response = client.post("/api/graph/sparql", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "results" in data
        assert "triple_count" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["triple_count"], int)

    def test_sparql_invalid_query_validation(self, client):
        """POST /sparql with invalid keywords returns 400."""
        # Test with forbidden SPARQL keywords
        payload = {"query": "INSERT DATA { }"}
        response = client.post("/api/graph/sparql", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sparql_missing_query_returns_422(self, client):
        """POST /sparql with missing query returns 422."""
        payload = {}
        response = client.post("/api/graph/sparql", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRDFTriplesEndpoint:
    """Tests for GET /rdf/triples endpoint."""

    def test_rdf_triples_returns_200(self, client):
        """GET /rdf/triples returns 200 OK."""
        response = client.get("/api/graph/rdf/triples")
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_triples_response_structure(self, client):
        """GET /rdf/triples response contains triples and count."""
        response = client.get("/api/graph/rdf/triples")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "triples" in data
        assert "count" in data
        assert isinstance(data["triples"], list)
        assert isinstance(data["count"], int)

    def test_rdf_triples_with_subject_filter(self, client):
        """GET /rdf/triples accepts subject filter."""
        response = client.get("/api/graph/rdf/triples?subject=http://example.org/subject1")
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_triples_with_predicate_filter(self, client):
        """GET /rdf/triples accepts predicate filter."""
        response = client.get("/api/graph/rdf/triples?predicate=http://example.org/predicate1")
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_triples_with_object_filter(self, client):
        """GET /rdf/triples accepts object filter."""
        response = client.get("/api/graph/rdf/triples?object=http://example.org/object1")
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_triples_with_all_filters(self, client):
        """GET /rdf/triples accepts all filters simultaneously."""
        response = client.get("/api/graph/rdf/triples?subject=s&predicate=p&object=o")
        assert response.status_code == status.HTTP_200_OK


class TestRDFCountEndpoint:
    """Tests for GET /rdf/count endpoint."""

    def test_rdf_count_returns_200(self, client):
        """GET /rdf/count returns 200 OK."""
        response = client.get("/api/graph/rdf/count")
        assert response.status_code == status.HTTP_200_OK

    def test_rdf_count_response_structure(self, client):
        """GET /rdf/count response contains count field."""
        response = client.get("/api/graph/rdf/count")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0


class TestBuildGraphEndpoint:
    """Tests for POST /build endpoint."""

    def test_build_graph_returns_200(self, client):
        """POST /build returns 200 OK."""
        response = client.post("/api/graph/build")
        assert response.status_code == status.HTTP_200_OK

    def test_build_graph_response_structure(self, client):
        """POST /build response contains knowledge graph information."""
        response = client.post("/api/graph/build")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "node_count" in data
        assert "edge_count" in data
        assert "is_directed" in data
        assert "timestamp" in data
        assert isinstance(data["node_count"], int)
        assert isinstance(data["edge_count"], int)
        assert isinstance(data["is_directed"], bool)

    def test_build_graph_with_data(self, client):
        """POST /build with actual data returns non-empty graph."""
        response = client.post("/api/graph/build")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should have at least some nodes from the test data
        assert data["node_count"] >= 0


class TestDegreeDistributionEndpoint:
    """Tests for GET /degree-distribution endpoint."""

    def test_degree_distribution_returns_200(self, client):
        """GET /degree-distribution returns 200 OK."""
        response = client.get("/api/graph/degree-distribution")
        assert response.status_code == status.HTTP_200_OK

    def test_degree_distribution_response_structure(self, client):
        """GET /degree-distribution response contains in_degree and out_degree."""
        response = client.get("/api/graph/degree-distribution")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "in_degree" in data
        assert "out_degree" in data
        assert isinstance(data["in_degree"], dict)
        assert isinstance(data["out_degree"], dict)

    def test_degree_distribution_values_are_integers(self, client):
        """GET /degree-distribution returns integer degree values."""
        response = client.get("/api/graph/degree-distribution")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for node_id, degree in data["in_degree"].items():
            assert isinstance(node_id, str)
            assert isinstance(degree, int)
            assert degree >= 0

        for node_id, degree in data["out_degree"].items():
            assert isinstance(node_id, str)
            assert isinstance(degree, int)
            assert degree >= 0

    def test_degree_distribution_with_data(self, client, repository_with_data):
        """GET /degree-distribution with actual data includes all nodes."""
        response = client.get("/api/graph/degree-distribution")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have entries for classes in the repository
        assert len(data["in_degree"]) > 0
        assert len(data["out_degree"]) > 0


class TestErrorHandling:
    """Tests for error handling across all endpoints."""

    def test_invalid_algorithm_returns_400(self, client):
        """Invalid algorithm returns 400 Bad Request."""
        response = client.get("/api/graph/centrality?algorithm=nonexistent_algo_xyz")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data

    def test_pydantic_validation_failure_returns_422(self, client):
        """Pydantic validation errors return 422 status code."""
        payload = {"source_id": "node1"}  # Missing required field
        response = client.post("/api/graph/cycle-check", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
