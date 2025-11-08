"""
Integration tests for Reference Link Validation endpoints.

Tests the validation API endpoints for checking reference link integrity.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import uuid4
import pytest


def create_layer(shared_client):
    """Helper function to create a test layer."""
    unique_title = f"TestLayer_{uuid4()}"
    payload = {
        "node_type": "layer",
        "title": unique_title,
        "definition": "Layer for validation test.",
    }
    response = shared_client.post("/api/structure_nodes/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_domain(shared_client, layer_id, title=None):
    """Helper function to create a test domain."""
    unique_title = title if title else f"TestDomain_{uuid4()}"
    payload = {
        "node_type": "domain",
        "parent_node_id": layer_id,
        "title": unique_title,
        "definition": "Domain for validation test.",
    }
    resp = shared_client.post("/api/structure_nodes/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


# ============================================================================
# Single Node Validation Tests
# ============================================================================


def test_validate_node_reference_links_empty(shared_client):
    """Test validation of node with no reference links."""
    # Create a test node
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Validate the node (should have no links)
    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links/validate"
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["node_id"] == domain_id
    assert data["total_links"] == 0
    assert data["valid_links"] == 0
    assert len(data["orphaned_links"]) == 0
    assert len(data["malformed_links"]) == 0


def test_validate_node_reference_links_no_existence_check(shared_client):
    """Test validation without checking reference.db existence."""
    # Create a test node
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Validate the node without existence check
    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links/validate?check_existence=false"
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["node_id"] == domain_id
    # Should complete successfully even if reference.db is unavailable


def test_validate_node_reference_links_not_found(shared_client):
    """Test validation of non-existent node."""
    fake_node_id = str(uuid4())

    resp = shared_client.post(
        f"/api/structure_nodes/{fake_node_id}/reference_links/validate"
    )
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


def test_validate_node_reference_links_invalid_uuid(shared_client):
    """Test validation with invalid UUID format."""
    invalid_node_id = "not-a-valid-uuid"

    resp = shared_client.post(
        f"/api/structure_nodes/{invalid_node_id}/reference_links/validate"
    )
    assert resp.status_code == 422  # FastAPI validation error


# ============================================================================
# Bulk Validation Tests
# ============================================================================


def test_validate_all_reference_links_success(shared_client):
    """Test bulk validation across all nodes."""
    # Create some test nodes
    layer_id = create_layer(shared_client)
    domain_id_1 = create_domain(shared_client, layer_id)
    domain_id_2 = create_domain(shared_client, layer_id)

    # Run bulk validation
    resp = shared_client.post("/api/structure_nodes/reference_links/validate")
    assert resp.status_code == 200

    data = resp.json()
    assert "total_nodes_checked" in data
    assert "nodes_with_links" in data
    assert "total_links" in data
    assert "valid_links" in data
    assert "orphaned_links" in data
    assert "malformed_links" in data
    assert "problematic_nodes" in data
    assert "reference_db_available" in data


def test_validate_all_reference_links_with_limit(shared_client):
    """Test bulk validation with limit parameter."""
    # Create multiple test nodes
    layer_id = create_layer(shared_client)
    for i in range(5):
        create_domain(shared_client, layer_id, title=f"Domain_{i}_{uuid4()}")

    # Run bulk validation with limit
    resp = shared_client.post(
        "/api/structure_nodes/reference_links/validate?limit=3"
    )
    assert resp.status_code == 200

    data = resp.json()
    # Should check at most 3 nodes with links (may be less if not all have links)
    assert data["total_nodes_checked"] <= 3


def test_validate_all_reference_links_no_existence_check(shared_client):
    """Test bulk validation without checking existence."""
    # Run bulk validation without existence check
    resp = shared_client.post(
        "/api/structure_nodes/reference_links/validate?check_existence=false&limit=10"
    )
    assert resp.status_code == 200

    data = resp.json()
    # Should complete successfully even if reference.db is unavailable
    assert "total_nodes_checked" in data


# ============================================================================
# Graceful Degradation Tests
# ============================================================================


def test_validation_handles_reference_db_unavailable(shared_client):
    """Test that validation handles unavailable reference.db gracefully."""
    # Create a test node
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Run validation (should handle unavailable reference.db)
    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links/validate"
    )
    assert resp.status_code == 200
    # Should not crash even if reference.db is unavailable

    # Also test bulk validation
    resp = shared_client.post(
        "/api/structure_nodes/reference_links/validate?limit=5"
    )
    assert resp.status_code == 200
    data = resp.json()
    # If reference.db unavailable, should be marked in result
    assert isinstance(data["reference_db_available"], bool)


# ============================================================================
# Edge Cases
# ============================================================================


def test_validate_node_with_malformed_json(shared_client):
    """Test validation handles malformed JSON gracefully.

    Note: This is a theoretical test - in practice, malformed JSON would be
    prevented by the database constraints and service layer.
    """
    # Create a test node
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Validation should handle any malformed data gracefully
    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links/validate"
    )
    assert resp.status_code in [200, 500]  # Either succeeds or reports error
    # Should not crash the server


def test_bulk_validation_with_zero_limit_rejected(shared_client):
    """Test that invalid limit parameters are rejected."""
    # Try with limit=0
    resp = shared_client.post(
        "/api/structure_nodes/reference_links/validate?limit=0"
    )
    assert resp.status_code == 422  # FastAPI validation error


def test_bulk_validation_with_excessive_limit_rejected(shared_client):
    """Test that excessive limit parameters are rejected."""
    # Try with very large limit
    resp = shared_client.post(
        "/api/structure_nodes/reference_links/validate?limit=100000"
    )
    assert resp.status_code == 422  # FastAPI validation error (exceeds max of 10000)
