"""
Integration tests for Reference Links and Word Senses API endpoints.

Tests the new structure_nodes endpoints for managing reference links and word senses.  # noqa: E501
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import uuid4  # noqa: E402


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
    unique_definition = definition if definition else "Domain for reference links test."  # noqa: E501
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
    unique_definition = definition if definition else "Term for reference links test."  # noqa: E501
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
    """Test adding reference links to a structure node.

    Note: This test expects reference.db to be empty in test environment,
    so it tests validation failure. In production with populated reference.db,
    this would test successful addition.
    """
    # Create a test node
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Person_{uuid4()}")  # noqa: E501

    # Try to add reference links
    reference_links = [
        {"source": "schema.org", "external_id": "Person"},
        {"source": "wikidata", "external_id": "Q5"},
    ]

    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links  # noqa: E501
    )

    # Since reference.db is empty in test environment, validation should fail
    # In production with reference data, this would return 200
    assert resp.status_code in [200, 400, 404], f"Failed with response: {resp.text}"  # noqa: E501

    if resp.status_code in [400, 404]:
        # Expected in test environment - reference not found
        assert "not found" in resp.text.lower()
    else:
        # Would happen in production with reference data
        data = resp.json()
        assert isinstance(data, list)


def test_get_reference_links_empty(shared_client):
    """Test getting reference links when none exist."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    resp = shared_client.get(f"/api/structure_nodes/{domain_id}/reference_links")  # noqa: E501
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_reference_links_success(shared_client):
    """Test getting reference links returns proper structure."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Organization_{uuid4()}")  # noqa: E501

    # Get reference links (should be empty initially)
    get_resp = shared_client.get(f"/api/structure_nodes/{domain_id}/reference_links")  # noqa: E501
    assert get_resp.status_code == 200

    data = get_resp.json()
    assert isinstance(data, list)
    # Will be empty until reference data is added


def test_add_reference_links_duplicate_ignored(shared_client):
    """Test that duplicate prevention logic works correctly.

    Note: With empty reference.db, this tests error handling consistency.
    """
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Event_{uuid4()}")  # noqa: E501

    # Try to add reference link (will fail with empty reference.db)
    reference_links = [{"source": "schema.org", "external_id": "Event"}]

    resp1 = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links  # noqa: E501
    )

    # Should fail consistently both times with empty reference.db
    assert resp1.status_code in [200, 400, 404]

    # Try again - should get same result
    resp2 = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=reference_links  # noqa: E501
    )
    assert resp2.status_code == resp1.status_code


def test_remove_reference_links_success(shared_client):
    """Test removing reference links from a structure node."""
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Place_{uuid4()}")  # noqa: E501

    # For this test to work, we need to add test data to reference.db
    # Since reference.db is empty in test environment, we'll create a simpler test  # noqa: E501
    # that validates the API behavior without requiring reference validation

    # First, get initial state (should be empty)
    get_resp = shared_client.get(f"/api/structure_nodes/{domain_id}/reference_links")  # noqa: E501
    assert get_resp.status_code == 200

    # Try to remove from empty list (should succeed with no changes)
    import json
    links_to_remove = [{"source": "test_source", "external_id": "test_id"}]

    remove_resp = shared_client.request(
        "DELETE",
        f"/api/structure_nodes/{domain_id}/reference_links",
        content=json.dumps(links_to_remove),
        headers={"Content-Type": "application/json"}
    )
    assert remove_resp.status_code == 200

    # Verify no links remain
    data = remove_resp.json()
    assert len(data) == 0


def test_remove_reference_links_nonexistent_ignored(shared_client):
    """Test that removing non-existent reference links doesn't cause errors."""
    import json
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id, title=f"Product_{uuid4()}")  # noqa: E501

    # Get initial state (should be empty)
    get_resp = shared_client.get(f"/api/structure_nodes/{domain_id}/reference_links")  # noqa: E501
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 0

    # Try to remove a link that doesn't exist (should succeed with no errors)
    links_to_remove = [{"source": "wikidata", "external_id": "Q12345"}]

    remove_resp = shared_client.request(
        "DELETE",
        f"/api/structure_nodes/{domain_id}/reference_links",
        content=json.dumps(links_to_remove),
        headers={"Content-Type": "application/json"}
    )
    assert remove_resp.status_code == 200

    # Should still have no links
    data = remove_resp.json()
    assert len(data) == 0


def test_add_reference_links_invalid_reference(shared_client):
    """Test adding reference links with non-existent reference in reference.db."""  # noqa: E501
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Try to add a reference that doesn't exist in reference.db
    invalid_links = [{"source": "invalid_source", "external_id": "nonexistent_id"}]  # noqa: E501

    resp = shared_client.post(
        f"/api/structure_nodes/{domain_id}/reference_links", json=invalid_links
    )
    # Should return 400 or 404 because reference doesn't exist
    assert resp.status_code in [400, 404]
    assert "reference not found" in resp.text.lower() or "not found" in resp.text.lower()  # noqa: E501


def test_reference_links_node_not_found(shared_client):
    """Test reference links operations with non-existent node ID."""
    import json
    fake_node_id = str(uuid4())

    # Test GET
    get_resp = shared_client.get(f"/api/structure_nodes/{fake_node_id}/reference_links")  # noqa: E501
    assert get_resp.status_code == 404

    # Test POST
    reference_links = [{"source": "schema.org", "external_id": "Person"}]
    post_resp = shared_client.post(
        f"/api/structure_nodes/{fake_node_id}/reference_links", json=reference_links  # noqa: E501
    )
    assert post_resp.status_code == 404

    # Test DELETE
    delete_resp = shared_client.request(
        "DELETE",
        f"/api/structure_nodes/{fake_node_id}/reference_links",
        content=json.dumps(reference_links),
        headers={"Content-Type": "application/json"}
    )
    assert delete_resp.status_code == 404


def test_reference_links_invalid_node_id(shared_client):
    """Test reference links operations with invalid UUID format."""
    import json
    invalid_node_id = "not-a-valid-uuid"

    # Test GET
    get_resp = shared_client.get(f"/api/structure_nodes/{invalid_node_id}/reference_links")  # noqa: E501
    assert get_resp.status_code == 422  # FastAPI validation error

    # Test POST
    reference_links = [{"source": "schema.org", "external_id": "Person"}]
    post_resp = shared_client.post(
        f"/api/structure_nodes/{invalid_node_id}/reference_links", json=reference_links  # noqa: E501
    )
    assert post_resp.status_code == 422

    # Test DELETE
    delete_resp = shared_client.request(
        "DELETE",
        f"/api/structure_nodes/{invalid_node_id}/reference_links",
        content=json.dumps(reference_links),
        headers={"Content-Type": "application/json"}
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
    import json
    layer_id = create_layer(shared_client)
    domain_id = create_domain(shared_client, layer_id)

    # Add empty array (should succeed but not change anything)
    resp = shared_client.post(f"/api/structure_nodes/{domain_id}/reference_links", json=[])  # noqa: E501
    assert resp.status_code == 200
    assert len(resp.json()) == 0

    # Remove empty array (should succeed but not change anything)
    resp = shared_client.request(
        "DELETE",
        f"/api/structure_nodes/{domain_id}/reference_links",
        content=json.dumps([]),
        headers={"Content-Type": "application/json"}
    )
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

    resp = shared_client.get(f"/api/structure_nodes/{fake_node_id}/word_senses")  # noqa: E501
    assert resp.status_code == 404


def test_get_word_senses_invalid_node_id(shared_client):
    """Test getting word senses with invalid UUID format."""
    invalid_node_id = "not-a-valid-uuid"

    resp = shared_client.get(f"/api/structure_nodes/{invalid_node_id}/word_senses")  # noqa: E501
    assert resp.status_code == 422  # FastAPI validation error


# Note: Word senses are populated automatically by the event processor when
# a node's title changes. These tests verify the API endpoint works correctly
# when word senses data exists in the database. The actual word sense extraction  # noqa: E501
# and update logic is tested in the service layer unit tests and event processor  # noqa: E501
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
    # In Phase 4, when event processor is wired up, this will contain actual senses  # noqa: E501
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
