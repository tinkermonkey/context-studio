"""
Integration tests for Reference Links and Word Senses API endpoints.

Tests the new structure_nodes endpoints for managing reference links and word senses.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import uuid4
import pytest


# Integration tests use shared session-scoped fixtures for performance:
# - shared_client (session-scoped test client, reused across all tests)
# - db_session (function-scoped, provides clean database state per test)


def create_layer(shared_client):
    """Helper function to create a test layer."""
    unique_title = f"TestLayer_{uuid4()}"
    payload = {
        "node_type": "layer",
        "title": unique_title,
        "definition": "Layer for integration test.",
    }
    response = shared_client.post("/api/structure_nodes/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_domain(shared_client, layer_id, title=None, definition=None):
    """Helper function to create a test domain."""
    unique_title = title if title else f"TestDomain_{uuid4()}"
    unique_definition = definition if definition else "Domain for reference links test."
    payload = {
        "node_type": "domain",
        "parent_node_id": layer_id,
        "title": unique_title,
        "definition": unique_definition,
    }
    resp = shared_client.post("/api/structure_nodes/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def create_term(shared_client, domain_id, title=None, definition=None):
    """Helper function to create a test term."""
    unique_title = title if title else f"TestTerm_{uuid4()}"
    unique_definition = definition if definition else "Term for reference links test."
    payload = {
        "node_type": "term",
        "parent_node_id": domain_id,
        "title": unique_title,
        "definition": unique_definition,
    }
    resp = shared_client.post("/api/structure_nodes/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


# ============================================================================
# Reference Links Tests
# ============================================================================


def test_add_reference_links_success(shared_client):
    """Test adding reference links to a structure node."""
    # Create a test node
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Person_{uuid4()}")

    # Add reference links
    reference_links = [
        {"source": "schema.org", "external_id": "Person"},
        {"source": "wikidata", "external_id": "Q5"},
    ]

    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links
    )
    assert resp.status_code == 200, f"Failed with response: {resp.text}"

    # Verify response contains the added links
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Verify link details
    sources = [link["source"] for link in data]
    external_ids = [link["external_id"] for link in data]
    assert "schema.org" in sources
    assert "wikidata" in sources
    assert "Person" in external_ids
    assert "Q5" in external_ids


def test_get_reference_links_empty(shared_client):
    """Test getting reference links when none exist."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    resp = shared_client.get(f"/api/structure_nodes/{domain_id}/reference_links")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_reference_links_success(shared_client):
    """Test getting reference links after adding them."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Organization_{uuid4()}")

    # Add reference links
    reference_links = [
        {"source": "schema.org", "external_id": "Organization"},
    ]

    add_resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links
    )
    assert add_resp.status_code == 200

    # Get reference links
    get_resp = shared_client.get(f"/api/structure_nodes/{domain_id}/reference_links")
    assert get_resp.status_code == 200

    data = get_resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "schema.org"
    assert data[0]["external_id"] == "Organization"


def test_add_reference_links_duplicate_ignored(shared_client):
    """Test that adding duplicate reference links doesn't create duplicates."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Event_{uuid4()}")

    # Add reference link first time
    reference_links = [{"source": "schema.org", "external_id": "Event"}]

    resp1 = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links
    )
    assert resp1.status_code == 200
    assert len(resp1.json()) == 1

    # Add same reference link again
    resp2 = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links
    )
    assert resp2.status_code == 200

    # Should still only have 1 link (duplicate ignored)
    data = resp2.json()
    assert len(data) == 1


def test_remove_reference_links_success(shared_client):
    """Test removing reference links from a structure node."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Place_{uuid4()}")

    # Add multiple reference links
    reference_links = [
        {"source": "schema.org", "external_id": "Place"},
        {"source": "wikidata", "external_id": "Q17334923"},
    ]

    add_resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links
    )
    assert add_resp.status_code == 200
    assert len(add_resp.json()) == 2

    # Remove one reference link
    links_to_remove = [{"source": "schema.org", "external_id": "Place"}]

    remove_resp = shared_client.delete(
        f"/api/structure_nodes/{domain_id}/reference_links", json=links_to_remove
    )
    assert remove_resp.status_code == 200

    # Verify only one link remains
    data = remove_resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "wikidata"
    assert data[0]["external_id"] == "Q17334923"


def test_remove_reference_links_nonexistent_ignored(shared_client):
    """Test that removing non-existent reference links doesn't cause errors."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Product_{uuid4()}")

    # Add one reference link
    reference_links = [{"source": "schema.org", "external_id": "Product"}]

    add_resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links
    )
    assert add_resp.status_code == 200

    # Try to remove a different link (doesn't exist)
    links_to_remove = [{"source": "wikidata", "external_id": "Q12345"}]

    remove_resp = shared_client.delete(
        f"/api/structure_nodes/{domain_id}/reference_links", json=links_to_remove
    )
    assert remove_resp.status_code == 200

    # Original link should still be there
    data = remove_resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "schema.org"


def test_add_reference_links_invalid_reference(shared_client):
    """Test adding reference links with non-existent reference in reference.db."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Try to add a reference that doesn't exist in reference.db
    invalid_links = [{"source": "invalid_source", "external_id": "nonexistent_id"}]

    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=invalid_links
    )
    # Should return 400 because reference doesn't exist
    assert resp.status_code == 400
    assert "reference not found" in resp.text.lower() or "not found" in resp.text.lower()


def test_reference_links_node_not_found(shared_client):
    """Test reference links operations with non-existent node ID."""
    fake_node_id = str(uuid4())

    # Test GET
    get_resp = shared_client.get(f"/api/structure_nodes/{fake_node_id}/reference_links")
    assert get_resp.status_code == 404

    # Test POST
    reference_links = [{"source": "schema.org", "external_id": "Person"}]
    post_resp = shared_client.post(
        f"/api/structure_nodes/{fake_node_id}/reference_links", json=reference_links
    )
    assert post_resp.status_code == 404

    # Test DELETE
    delete_resp = shared_client.delete(
        f"/api/structure_nodes/{fake_node_id}/reference_links", json=reference_links
    )
    assert delete_resp.status_code == 404


def test_reference_links_invalid_node_id(shared_client):
    """Test reference links operations with invalid UUID format."""
    invalid_node_id = "not-a-valid-uuid"

    # Test GET
    get_resp = shared_client.get(f"/api/structure_nodes/{invalid_node_id}/reference_links")
    assert get_resp.status_code == 422  # FastAPI validation error

    # Test POST
    reference_links = [{"source": "schema.org", "external_id": "Person"}]
    post_resp = shared_client.post(
        f"/api/structure_nodes/{invalid_node_id}/reference_links", json=reference_links
    )
    assert post_resp.status_code == 422

    # Test DELETE
    delete_resp = shared_client.delete(
        f"/api/structure_nodes/{invalid_node_id}/reference_links", json=reference_links
    )
    assert delete_resp.status_code == 422


def test_reference_links_validation_missing_fields(shared_client):
    """Test reference links validation with missing required fields."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Missing external_id
    invalid_links = [{"source": "schema.org"}]

    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=invalid_links
    )
    assert resp.status_code == 422  # Validation error

    # Missing source
    invalid_links = [{"external_id": "Person"}]

    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=invalid_links
    )
    assert resp.status_code == 422  # Validation error


def test_reference_links_empty_array(shared_client):
    """Test adding/removing empty array of reference links."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Add empty array (should succeed but not change anything)
    resp = shared_client.post(f"/api/structure_nodes/{domain_id}/reference_links", json=[])
    assert resp.status_code == 200
    assert len(resp.json()) == 0

    # Remove empty array (should succeed but not change anything)
    resp = shared_client.request("DELETE", f"/api/structure_nodes/{domain_id}/reference_links", json=[])
    assert resp.status_code == 200
    assert len(resp.json()) == 0


# ============================================================================
# Word Senses Tests
# ============================================================================


def test_get_word_senses_empty(shared_client):
    """Test getting word senses when none exist."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    resp = shared_client.get(f"/api/structure_nodes/{domain_id}/word_senses")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_word_senses_node_not_found(shared_client):
    """Test getting word senses for non-existent node."""
    fake_node_id = str(uuid4())

    resp = shared_client.get(f"/api/structure_nodes/{fake_node_id}/word_senses")
    assert resp.status_code == 404


def test_get_word_senses_invalid_node_id(shared_client):
    """Test getting word senses with invalid UUID format."""
    invalid_node_id = "not-a-valid-uuid"

    resp = shared_client.get(f"/api/structure_nodes/{invalid_node_id}/word_senses")
    assert resp.status_code == 422  # FastAPI validation error


# Note: Word senses are populated automatically by the event processor when
# a node's title changes. These tests verify the API endpoint works correctly
# when word senses data exists in the database. The actual word sense extraction
# and update logic is tested in the service layer unit tests and event processor
# integration tests.


def test_word_senses_structure(shared_client):
    """Test that word senses endpoint returns correct data structure."""
    # This test verifies the endpoint returns the correct structure
    # even when no word senses exist yet
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title="bank")

    resp = shared_client.get(f"/api/structure_nodes/{domain_id}/word_senses")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)

    # If word senses were populated (by event processor), verify structure
    # For now, we just verify empty list is returned correctly
    # In Phase 4, when event processor is wired up, this will contain actual senses
    if len(data) > 0:
        # Verify each sense has required fields
        for sense in data:
            assert "term" in sense
            assert "sense_type" in sense
            assert "sense_id" in sense
            assert "definition" in sense
            # domain is optional
            assert isinstance(sense["term"], str)
            assert isinstance(sense["sense_type"], str)
            assert isinstance(sense["sense_id"], str)
            assert isinstance(sense["definition"], str)
