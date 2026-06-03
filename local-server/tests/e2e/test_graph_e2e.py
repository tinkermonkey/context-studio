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

import pytest
from fastapi import status


def create_test_taxonomy_with_classes(e2e_client, num_classes=2, unique_id=""):
    """
    Helper to reduce boilerplate: creates a taxonomy with a scheme and classes.

    Returns: (taxonomy_id, scheme_id, [class_ids])
    """
    import uuid

    unique_suffix = str(uuid.uuid4())[:8] if not unique_id else unique_id

    tax_response = e2e_client.post(
        "/api/taxonomies", json={"title": f"Test Taxonomy {unique_suffix}"}
    )
    assert (
        tax_response.status_code == 201
    ), f"Failed to create taxonomy: {tax_response.text}"
    taxonomy_id = tax_response.json()["id"]

    scheme_response = e2e_client.post(
        f"/api/taxonomies/{taxonomy_id}/schemes",
        json={"title": f"Test Scheme {unique_suffix}"},
    )
    assert (
        scheme_response.status_code == 201
    ), f"Failed to create scheme: {scheme_response.text}"
    scheme_id = scheme_response.json()["id"]

    class_ids = []
    parent_id = None
    for i in range(num_classes):
        class_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={
                "title": f"Test Class {i+1} {unique_suffix}",
                **({"parent_class_id": parent_id} if parent_id else {}),
            },
        )
        assert (
            class_response.status_code == 201
        ), f"Failed to create class: {class_response.text}"
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
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Graph Test Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Graph Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Create classes to form edges
        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Graph Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Graph Class 2", "parent_class_id": class1_id},
        )
        assert class2_response.status_code == 201

        # Build the graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK
        body = build_response.json()
        assert "node_count" in body
        assert "edge_count" in body
        assert "timestamp" in body
        assert body["node_count"] > 0
        assert body["edge_count"] >= 0

    def test_build_empty_graph(self, e2e_client):
        """
        Build graph successfully even with empty or sparse ontology.

        Asserts:
        - Status code 200 (OK)
        - Response includes required fields (node_count, edge_count, timestamp)
        """
        response = e2e_client.post("/api/graph/build")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "node_count" in body
        assert "edge_count" in body
        assert "timestamp" in body
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
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Metrics Test Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Metrics Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Create multiple classes
        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Metrics Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Metrics Class 2", "parent_class_id": class1_id},
        )
        class2_id = class2_response.json()["id"]

        e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Metrics Class 3", "parent_class_id": class2_id},
        )

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
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Degree Test Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Degree Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Degree Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Degree Class 2", "parent_class_id": class1_id},
        )
        assert class2_response.status_code == 201

        # Build graph
        build_response = e2e_client.post("/api/graph/build")
        assert build_response.status_code == status.HTTP_200_OK

        # Get degree distribution
        response = e2e_client.get("/api/graph/degree-distribution")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "in_degree" in body
        assert "out_degree" in body
        assert isinstance(body["in_degree"], dict)
        assert isinstance(body["out_degree"], dict)
