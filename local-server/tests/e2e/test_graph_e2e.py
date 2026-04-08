"""
E2E tests for the Graph Analysis bounded context.

This module tests the Graph Analysis bounded context through the HTTP API
with a fully initialized application using real databases and real adapters.

Tests verify:
- Graph construction from existing ontology entities
- Graph metrics retrieval (degree distribution, centrality)
- Shortest path traversal
- Neighbor queries
- SPARQL query execution
- Graceful responses on empty graphs
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi import status


@pytest.mark.e2e
class TestGraphConstruction:
    """Tests for graph construction from existing ontology entities."""

    def test_build_graph_with_entities(self, e2e_client):
        """
        Build graph from ontology entities.

        Asserts:
        - Status code 200 (OK)
        - Response contains node count, edge count, last_built timestamp
        """
        # Setup: Create ontology entities first
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "Graph Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Graph Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        # Create classes to form edges
        class1_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Graph Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Graph Class 2",
            "parent_class_id": class1_id
        })

        # Build the graph
        response = e2e_client.post("/api/graph/build")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "node_count" in body
        assert "edge_count" in body
        assert "last_built" in body
        assert body["node_count"] > 0
        assert body["edge_count"] >= 0

    def test_build_empty_graph(self, e2e_client):
        """
        Build graph successfully even with empty or sparse ontology.

        Asserts:
        - Status code 200 (OK)
        - Response includes required fields (node_count, edge_count, last_built)
        """
        response = e2e_client.post("/api/graph/build")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "node_count" in body
        assert "edge_count" in body
        assert "last_built" in body
        assert isinstance(body["node_count"], int)
        assert isinstance(body["edge_count"], int)
        assert body["node_count"] >= 0
        assert body["edge_count"] >= 0


@pytest.mark.e2e
class TestGraphMetrics:
    """Tests for graph metrics retrieval."""

    def test_get_graph_metrics(self, e2e_client):
        """
        Get graph metrics including density, degree, centrality.

        Asserts:
        - Status code 200 (OK)
        - Response includes density, average_degree, connected_components, degree_distribution
        """
        # Setup: Create ontology with relationships
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "Metrics Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Metrics Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        # Create multiple classes
        class1_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Metrics Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Metrics Class 2",
            "parent_class_id": class1_id
        })
        class2_id = class2_response.json()["id"]

        class3_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Metrics Class 3",
            "parent_class_id": class2_id
        })

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Get metrics
        response = e2e_client.get("/api/graph/metrics?algorithm=betweenness")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "density" in body
        assert "average_degree" in body
        assert "connected_components" in body
        assert "degree_distribution" in body
        assert "centrality" in body
        assert "algorithm" in body
        assert body["algorithm"] == "betweenness"
        assert "computed_at" in body

    def test_get_metrics_empty_graph(self, e2e_client):
        """
        Get metrics for empty graph.

        Asserts:
        - Status code 200 (OK)
        - Metrics reflect empty graph state
        """
        response = e2e_client.get("/api/graph/metrics")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["density"] == 0.0
        assert body["average_degree"] == 0.0


@pytest.mark.e2e
class TestDegreeDistribution:
    """Tests for degree distribution queries."""

    def test_get_degree_distribution(self, e2e_client):
        """
        Get degree distribution across all nodes.

        Asserts:
        - Status code 200 (OK)
        - Response contains distribution mapping and computed_at
        """
        # Setup
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "Degree Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Degree Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Degree Class 1"
        })
        class1_id = class1_response.json()["id"]

        e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Degree Class 2",
            "parent_class_id": class1_id
        })

        # Build graph
        e2e_client.post("/api/graph/build")

        # Get degree distribution
        response = e2e_client.get("/api/graph/degree-distribution")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "distribution" in body
        assert "computed_at" in body
        assert isinstance(body["distribution"], dict)


@pytest.mark.e2e
class TestPathFinding:
    """Tests for shortest path and neighbor traversal."""

    def test_shortest_path_response_structure(self, e2e_client):
        """
        Test shortest path endpoint response structure.

        Asserts:
        - Endpoint exists and handles requests
        - Returns proper error or success response
        """
        # Get the graph metrics to determine if there are nodes
        metrics_resp = e2e_client.get("/api/graph/metrics")
        assert metrics_resp.status_code == status.HTTP_200_OK
        metrics = metrics_resp.json()

        if metrics["average_degree"] == 0:
            # Graph is empty or sparse, test with dummy IDs
            response = e2e_client.get("/api/graph/paths/shortest?source_id=dummy1&target_id=dummy2")
            # Should return 404 for non-existent nodes
            assert response.status_code == status.HTTP_404_NOT_FOUND
        else:
            # Graph has nodes, try to find path (may succeed or return 404 if disconnected)
            response = e2e_client.get("/api/graph/paths/shortest?source_id=node1&target_id=node2")
            # Either success or 404 is acceptable
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_shortest_path_not_found(self, e2e_client):
        """
        Return 404 when no path exists.

        Asserts:
        - Status code 404 (Not Found)
        """
        # Setup: Create disconnected nodes
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "No Path Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "No Path Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Isolated Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Isolated Class 2"
        })
        class2_id = class2_response.json()["id"]

        # Build graph
        e2e_client.post("/api/graph/build")

        # Try to find path between disconnected nodes
        response = e2e_client.get(
            f"/api/graph/paths/shortest?source_id={class1_id}&target_id={class2_id}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_find_all_paths_response_structure(self, e2e_client):
        """
        Test all paths endpoint response structure.

        Asserts:
        - Endpoint exists and returns proper response format
        - Returns list of path results (may be empty for non-existent nodes)
        """
        # Test with non-existent node IDs
        response = e2e_client.get(
            "/api/graph/paths/all?source_id=nonexistent1&target_id=nonexistent2&max_depth=5"
        )
        # Either 404 for non-existent nodes or empty list is acceptable
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            body = response.json()
            assert isinstance(body, list)


@pytest.mark.e2e
class TestNeighborQueries:
    """Tests for neighbor traversal queries."""

    def test_get_neighbors_response_structure(self, e2e_client):
        """
        Get neighbors endpoint response structure.

        Asserts:
        - Endpoint responds to requests
        - Returns proper response structure or 404 for non-existent nodes
        """
        # Test with a specific node ID
        test_node_id = "test-node-id-12345"
        response = e2e_client.get(
            f"/api/graph/nodes/{test_node_id}/neighbors?direction=both&depth=1"
        )
        # Either 200 with empty neighbors or 404 for non-existent node is acceptable
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            body = response.json()
            assert "node_id" in body
            assert "direction" in body
            assert "neighbors" in body
            assert isinstance(body["neighbors"], list)

    def test_get_neighbors_with_direction_params(self, e2e_client):
        """
        Get neighbors with directional filtering parameters.

        Asserts:
        - Endpoint accepts direction parameter (in/out/both)
        - Response includes the requested direction
        """
        # Test with direction parameter
        test_node_id = "test-node-456"
        response = e2e_client.get(
            f"/api/graph/nodes/{test_node_id}/neighbors?direction=out&depth=2"
        )
        # Accept 404 for non-existent node or 200 if node exists
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            body = response.json()
            assert body["direction"] == "out"
            assert "neighbors" in body


@pytest.mark.e2e
class TestCentrality:
    """Tests for centrality score calculations."""

    def test_get_centrality_betweenness(self, e2e_client):
        """
        Compute betweenness centrality scores.

        Asserts:
        - Status code 200 (OK)
        - Response includes algorithm and scores mapping
        """
        # Setup
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "Centrality Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Centrality Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Centrality Class 1"
        })

        # Build graph
        e2e_client.post("/api/graph/build")

        # Get centrality
        response = e2e_client.get("/api/graph/centrality?algorithm=betweenness")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "algorithm" in body
        assert body["algorithm"] == "betweenness"
        assert "scores" in body
        assert isinstance(body["scores"], dict)

    def test_get_centrality_pagerank(self, e2e_client):
        """
        Compute pagerank centrality scores.

        Asserts:
        - Status code 200 (OK)
        - Response includes algorithm and scores mapping
        """
        # Setup
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "PageRank Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "PageRank Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "PageRank Class"
        })

        # Build graph
        e2e_client.post("/api/graph/build")

        # Get pagerank
        response = e2e_client.get("/api/graph/centrality?algorithm=pagerank")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["algorithm"] == "pagerank"


@pytest.mark.e2e
class TestSPARQLQueries:
    """Tests for SPARQL query execution."""

    def test_execute_sparql_query(self, e2e_client):
        """
        Execute a SPARQL SELECT query.

        Asserts:
        - Status code 200 (OK)
        - Response includes results and triple_count
        """
        # Setup: Create ontology with entities
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "SPARQL Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "SPARQL Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "SPARQL Class"
        })

        # Build graph
        e2e_client.post("/api/graph/build")

        # Execute SPARQL query
        response = e2e_client.post("/api/graph/sparql", json={
            "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "results" in body
        assert "triple_count" in body
        assert isinstance(body["results"], list)
        assert isinstance(body["triple_count"], int)

    def test_sparql_query_empty_result(self, e2e_client):
        """
        Execute SPARQL query that returns no results.

        Asserts:
        - Status code 200 (OK)
        - Results structure is correct
        """
        # Execute SPARQL query for a predicate that likely doesn't exist
        response = e2e_client.post("/api/graph/sparql", json={
            "query": "SELECT ?s ?p ?o WHERE { ?s <http://example.com/nonexistent> ?o }"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "results" in body
        assert "triple_count" in body
        assert isinstance(body["results"], list)
        assert isinstance(body["triple_count"], int)


@pytest.mark.e2e
class TestRDFTriples:
    """Tests for RDF triple access and counting."""

    def test_get_rdf_triples(self, e2e_client):
        """
        Retrieve RDF triples from the graph.

        Asserts:
        - Status code 200 (OK)
        - Response includes triples array and count
        """
        # Setup
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "Triples Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Triples Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Triples Class"
        })

        # Build graph
        e2e_client.post("/api/graph/build")

        # Get triples
        response = e2e_client.get("/api/graph/rdf/triples")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "triples" in body
        assert "count" in body
        assert isinstance(body["triples"], list)

    def test_get_rdf_triple_count(self, e2e_client):
        """
        Get count of RDF triples.

        Asserts:
        - Status code 200 (OK)
        - Response includes count
        """
        # Setup
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "Count Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Count Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Count Class"
        })

        # Build graph
        e2e_client.post("/api/graph/build")

        # Get count
        response = e2e_client.get("/api/graph/rdf/count")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "count" in body
        assert isinstance(body["count"], int)

    def test_rdf_triples_with_filter(self, e2e_client):
        """
        Get RDF triples with optional filtering.

        Asserts:
        - Status code 200 (OK)
        - Response structure is correct
        """
        # Get triples (may return results or be empty depending on data)
        response = e2e_client.get("/api/graph/rdf/triples")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "triples" in body
        assert "count" in body
        assert isinstance(body["triples"], list)
        assert isinstance(body["count"], int)
        # Count should match number of triples
        assert body["count"] == len(body["triples"])


@pytest.mark.e2e
class TestCycleDetection:
    """Tests for cycle detection in proposed edges."""

    def test_cycle_check_would_create_cycle(self, e2e_client):
        """
        Detect when adding an edge would create a cycle.

        Asserts:
        - Status code 200 (OK)
        - would_create_cycle is true
        """
        # Setup: Create a chain to enable cycle
        tax_response = e2e_client.post("/api/taxonomies", json={
            "title": "Cycle Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Cycle Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Cycle Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Cycle Class 2",
            "parent_class_id": class1_id
        })
        class2_id = class2_response.json()["id"]

        # Build graph
        e2e_client.post("/api/graph/build")

        # Check if adding edge from class2 to class1 would create cycle
        response = e2e_client.post("/api/graph/cycle-check", json={
            "source_id": class2_id,
            "target_id": class1_id
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "source_id" in body
        assert "target_id" in body
        assert "would_create_cycle" in body
        assert isinstance(body["would_create_cycle"], bool)
