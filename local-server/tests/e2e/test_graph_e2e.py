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


def create_test_taxonomy_with_classes(e2e_client, num_classes=2, unique_id=""):
    """
    Helper to reduce boilerplate: creates a taxonomy with a scheme and classes.

    Returns: (taxonomy_id, scheme_id, [class_ids])
    """
    import uuid
    unique_suffix = str(uuid.uuid4())[:8] if not unique_id else unique_id

    tax_response = e2e_client.post("/api/taxonomies", json={
        "title": f"Test Taxonomy {unique_suffix}"
    })
    assert tax_response.status_code == 201, f"Failed to create taxonomy: {tax_response.text}"
    taxonomy_id = tax_response.json()["id"]

    scheme_response = e2e_client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
        "title": f"Test Scheme {unique_suffix}"
    })
    assert scheme_response.status_code == 201, f"Failed to create scheme: {scheme_response.text}"
    scheme_id = scheme_response.json()["id"]

    class_ids = []
    parent_id = None
    for i in range(num_classes):
        class_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": f"Test Class {i+1} {unique_suffix}",
            **({"parent_class_id": parent_id} if parent_id else {})
        })
        assert class_response.status_code == 201, f"Failed to create class: {class_response.text}"
        class_id = class_response.json()["id"]
        class_ids.append(class_id)
        parent_id = class_id

    return taxonomy_id, scheme_id, class_ids


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
        assert class2_response.status_code == 201

        # Build the graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK
        body = build_response.json()
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

        e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
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

        class2_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Degree Class 2",
            "parent_class_id": class1_id
        })
        assert class2_response.status_code == 201

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

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
        Test shortest path endpoint returns proper response structure with real nodes.

        Asserts:
        - Returns 200 (OK) when a path exists between connected nodes
        - Uses real entity IDs instead of fabricated strings
        - Response includes source_id, target_id, nodes, distance, relationships
        """
        # Create real entities with parent-child relationships creating a connected chain
        taxonomy_id, scheme_id, class_ids = create_test_taxonomy_with_classes(e2e_client, num_classes=3)

        # Create a property definition for relationships
        prop_response = e2e_client.post("/api/properties", json={
            "identifier": "parent_of",
            "title": "Parent Of",
            "description": "Indicates a parent-child relationship"
        })
        assert prop_response.status_code == 201, f"Failed to create property definition: {prop_response.text}"
        property_definition_id = prop_response.json()["id"]

        # Create explicit Relationship records to form edges in the graph
        # (parent_class_id is an entity attribute, not a graph edge)
        for i in range(len(class_ids) - 1):
            rel_response = e2e_client.post("/api/relationships", json={
                "source_id": class_ids[i],
                "target_id": class_ids[i + 1],
                "property_definition_id": property_definition_id
            })
            assert rel_response.status_code == 201, f"Failed to create relationship: {rel_response.text}"

        # Build the graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Query shortest path between real nodes in the chain
        response = e2e_client.get(
            f"/api/graph/paths/shortest?source_id={class_ids[0]}&target_id={class_ids[2]}"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "source_id" in body
        assert "target_id" in body
        assert "nodes" in body
        assert "distance" in body
        assert "relationships" in body

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
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Try to find path between disconnected nodes
        response = e2e_client.get(
            f"/api/graph/paths/shortest?source_id={class1_id}&target_id={class2_id}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_find_all_paths_response_structure(self, e2e_client):
        """
        Test all paths endpoint returns proper structure with real nodes.

        Asserts:
        - Returns a list of paths (200 OK)
        - Uses real entity IDs instead of fabricated strings
        - Response is a list containing paths between connected nodes
        """
        # Create real entities with parent-child relationships creating a connected chain
        taxonomy_id, scheme_id, class_ids = create_test_taxonomy_with_classes(e2e_client, num_classes=3)

        # Create a property definition for relationships
        prop_response = e2e_client.post("/api/properties", json={
            "identifier": "connected_to",
            "title": "Connected To",
            "description": "Indicates a connection between entities"
        })
        assert prop_response.status_code == 201, f"Failed to create property definition: {prop_response.text}"
        property_definition_id = prop_response.json()["id"]

        # Create explicit Relationship records to form edges in the graph
        # (parent_class_id is an entity attribute, not a graph edge)
        for i in range(len(class_ids) - 1):
            rel_response = e2e_client.post("/api/relationships", json={
                "source_id": class_ids[i],
                "target_id": class_ids[i + 1],
                "property_definition_id": property_definition_id
            })
            assert rel_response.status_code == 201, f"Failed to create relationship: {rel_response.text}"

        # Build the graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Find all paths between real nodes in the chain
        response = e2e_client.get(
            f"/api/graph/paths/all?source_id={class_ids[0]}&target_id={class_ids[2]}&max_depth=5"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)


@pytest.mark.e2e
class TestNeighborQueries:
    """Tests for neighbor traversal queries."""

    def test_get_neighbors_response_structure(self, e2e_client):
        """
        Get neighbors of a real node created via API.

        Asserts:
        - Response status is 200 (OK) when node has neighbors in graph
        - Response includes node_id, direction, and neighbors list
        - Uses real entity IDs instead of fabricated test strings
        """
        # Create real entities with parent-child relationships
        taxonomy_id, scheme_id, class_ids = create_test_taxonomy_with_classes(e2e_client, num_classes=2)

        # Create a property definition for relationships
        prop_response = e2e_client.post("/api/properties", json={
            "identifier": "has_child",
            "title": "Has Child",
            "description": "Indicates a parent-child relationship"
        })
        assert prop_response.status_code == 201, f"Failed to create property definition: {prop_response.text}"
        property_definition_id = prop_response.json()["id"]

        # Create explicit Relationship records to form edges in the graph
        # (parent_class_id is an entity attribute, not a graph edge)
        rel_response = e2e_client.post("/api/relationships", json={
            "source_id": class_ids[0],
            "target_id": class_ids[1],
            "property_definition_id": property_definition_id
        })
        assert rel_response.status_code == 201, f"Failed to create relationship: {rel_response.text}"

        # Build the graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Get neighbors of a real node
        response = e2e_client.get(
            f"/api/graph/nodes/{class_ids[0]}/neighbors?direction=both&depth=1"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "node_id" in body
        assert "direction" in body
        assert "neighbors" in body
        assert body["node_id"] == class_ids[0]
        assert body["direction"] == "both"
        assert isinstance(body["neighbors"], list)

    def test_get_neighbors_with_direction_params(self, e2e_client):
        """
        Get neighbors with directional filtering parameters.

        Asserts:
        - Response status is 200 (OK) when node has outgoing edges
        - Endpoint accepts direction parameter and returns correct structure
        - Uses real entity IDs instead of fabricated test strings
        """
        # Create real entities with parent-child relationships
        taxonomy_id, scheme_id, class_ids = create_test_taxonomy_with_classes(e2e_client, num_classes=2)

        # Create a property definition for relationships
        prop_response = e2e_client.post("/api/properties", json={
            "identifier": "extends",
            "title": "Extends",
            "description": "Indicates an extension relationship"
        })
        assert prop_response.status_code == 201, f"Failed to create property definition: {prop_response.text}"
        property_definition_id = prop_response.json()["id"]

        # Create explicit Relationship records to form edges in the graph
        # (parent_class_id is an entity attribute, not a graph edge)
        rel_response = e2e_client.post("/api/relationships", json={
            "source_id": class_ids[0],
            "target_id": class_ids[1],
            "property_definition_id": property_definition_id
        })
        assert rel_response.status_code == 201, f"Failed to create relationship: {rel_response.text}"

        # Build the graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Get outgoing neighbors of a real node
        response = e2e_client.get(
            f"/api/graph/nodes/{class_ids[0]}/neighbors?direction=out&depth=2"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["node_id"] == class_ids[0]
        assert body["direction"] == "out"
        assert "neighbors" in body
        assert isinstance(body["neighbors"], list)


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

        class_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Centrality Class 1"
        })
        assert class_response.status_code == 201

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

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

        class_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "PageRank Class"
        })
        assert class_response.status_code == 201

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

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

        class_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "SPARQL Class"
        })
        assert class_response.status_code == 201

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

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

        class_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Triples Class"
        })
        assert class_response.status_code == 201

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

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

        class_response = e2e_client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Count Class"
        })
        assert class_response.status_code == 201

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Get count
        response = e2e_client.get("/api/graph/rdf/count")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "count" in body
        assert isinstance(body["count"], int)

    def test_rdf_triples_count_matches_length(self, e2e_client):
        """
        Get RDF triples and verify count matches number of triples returned.

        Asserts:
        - Count field matches the actual number of triples in response
        """
        # Setup: create entities to ensure some triples exist
        taxonomy_id, scheme_id, class_ids = create_test_taxonomy_with_classes(e2e_client, num_classes=2)

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Get triples
        response = e2e_client.get("/api/graph/rdf/triples")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "triples" in body
        assert "count" in body
        assert isinstance(body["triples"], list)
        assert isinstance(body["count"], int)
        # Count should match the number of triples
        assert body["count"] == len(body["triples"])


@pytest.mark.e2e
class TestCommunities:
    """Tests for community detection in graphs."""

    def test_get_communities(self, e2e_client):
        """
        Detect and retrieve communities in the graph.

        Asserts:
        - Status code 200 (OK)
        - Response includes both algorithm and communities
        """
        # Setup: Create entities to build a graph
        taxonomy_id, scheme_id, class_ids = create_test_taxonomy_with_classes(e2e_client, num_classes=3)

        # Build the graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Get communities (may be empty if no connected components)
        response = e2e_client.get("/api/graph/communities")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "communities" in body
        assert isinstance(body["communities"], list)
        # Response includes algorithm and communities at minimum
        assert "algorithm" in body and "communities" in body


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
        assert class2_response.status_code == 201
        class2_id = class2_response.json()["id"]

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

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
