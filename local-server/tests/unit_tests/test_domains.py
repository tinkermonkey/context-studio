import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# All fixtures are now provided by conftest.py


def create_layer(shared_client, title="Test Layer"):
    resp = shared_client.post(
        "/api/structure_nodes/", json={"node_type": "layer", "title": title}
    )
    if resp.status_code != 201:
        print(f"Layer creation failed: {resp.status_code} {resp.text}")
    assert resp.status_code == 201
    # Force a new connection/session for SQLite visibility
    shared_client.get("/api/structure_nodes/?node_type=layer")
    return resp.json()["id"]


def debug_list_layers(shared_client):
    resp = shared_client.get("/api/structure_nodes/?node_type=layer")
    print(f"DEBUG: Layers in DB before domain creation: {resp.status_code} {resp.text}")
    return resp


def test_create_get_update_delete_domain(shared_client):
    layer_id = create_layer(shared_client, str(uuid.uuid4()))
    debug_list_layers(shared_client)
    resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": "Test Domain",
            "definition": "A test domain.",
            "parent_node_id": layer_id,
        },
    )
    if resp.status_code != 201:
        print(f"Domain creation failed: {resp.status_code} {resp.text}")
    assert resp.status_code == 201
    domain = resp.json()
    domain_id = domain["id"]
    resp = shared_client.get(f"/api/structure_nodes/{domain_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test Domain"
    resp = shared_client.put(
        f"/api/structure_nodes/{domain_id}", json={"title": "Updated Domain"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Domain"
    resp = shared_client.delete(f"/api/structure_nodes/{domain_id}")
    assert resp.status_code == 204
    resp = shared_client.get(f"/api/structure_nodes/{domain_id}")
    assert resp.status_code == 404


def test_domain_duplicate_title(shared_client):
    layer_id = create_layer(shared_client, str(uuid.uuid4()))
    resp1 = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": "Unique Domain",
            "definition": "A domain.",
            "parent_node_id": layer_id,
        },
    )
    if resp1.status_code != 201:
        print(f"Domain creation failed: {resp1.status_code} {resp1.text}")
    assert resp1.status_code == 201
    resp2 = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": "Unique Domain",
            "definition": "Another domain.",
            "parent_node_id": layer_id,
        },
    )
    if resp2.status_code != 409:
        print(f"Duplicate domain test failed: {resp2.status_code} {resp2.text}")
    assert (
        resp2.status_code == 409
    )  # Conflict is more appropriate than Bad Request for duplicates
    assert "unique" in str(resp2.json()["detail"]).lower()


def test_domain_invalid_layer(shared_client):
    # Valid UUID but non-existent layer
    resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": "Bad Domain",
            "definition": "No such layer.",
            "parent_node_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 400
    assert "parent must be" in resp.json()["detail"].lower()

    # Invalid UUID format
    resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": "Bad Domain",
            "definition": "No such layer.",
            "parent_node_id": "not-a-uuid",
        },
    )
    assert resp.status_code == 422
    assert "parent_node_id" in resp.text.lower()

    # Missing required field
    resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": "Bad Domain",
            "definition": "No layer id",
        },
    )
    assert resp.status_code == 400
    assert "parent" in resp.text.lower()


def test_list_domains(shared_client):
    layer_id = create_layer(shared_client, str(uuid.uuid4()))
    for i in range(3):
        shared_client.post(
            "/api/structure_nodes/",
            json={
                "node_type": "domain",
                "title": f"Domain {i}",
                "definition": f"Def {i}",
                "parent_node_id": layer_id,
            },
        )
    resp = shared_client.get("/api/structure_nodes/?node_type=domain&limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) <= 2
    resp = shared_client.get(
        f"/api/structure_nodes/?node_type=domain&parent_node_id={layer_id}"
    )
    assert resp.status_code == 200
    assert all(d["parent_node_id"] == layer_id for d in resp.json()["data"])


def test_move_domains_basic(shared_client):
    """Test basic domain movement between layers using new move API"""
    # Create two layers
    source_layer_id = create_layer(shared_client, f"Source Layer {uuid.uuid4()}")
    target_layer_id = create_layer(shared_client, f"Target Layer {uuid.uuid4()}")

    # Create a domain in the source layer
    domain_resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": f"Test Domain {uuid.uuid4()}",
            "definition": "Test definition",
            "parent_node_id": source_layer_id,
        },
    )
    assert domain_resp.status_code == 201
    domain_id = domain_resp.json()["id"]

    # Move the domain to the target layer using the move API
    move_resp = shared_client.post(
        "/api/structure_nodes/move",
        json={
            "node_ids": [domain_id],
            "target_parent_id": target_layer_id,
            "move_children": True,
        },
    )
    assert move_resp.status_code == 200
    move_data = move_resp.json()

    # Verify the domain was moved
    assert len(move_data["moved_nodes"]) == 1
    assert move_data["moved_nodes"][0]["parent_node_id"] == target_layer_id

    # Verify the domain is in the target layer
    domain_resp = shared_client.get(f"/api/structure_nodes/{domain_id}")
    assert domain_resp.status_code == 200
    assert domain_resp.json()["parent_node_id"] == target_layer_id


def test_move_domains_with_terms(shared_client):
    """Test moving domains with their terms using new move API"""
    # Create two layers
    source_layer_id = create_layer(shared_client, f"Source Layer {uuid.uuid4()}")
    target_layer_id = create_layer(shared_client, f"Target Layer {uuid.uuid4()}")

    # Create a domain in the source layer
    domain_resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": f"Test Domain {uuid.uuid4()}",
            "definition": "Test definition",
            "parent_node_id": source_layer_id,
        },
    )
    assert domain_resp.status_code == 201
    domain_id = domain_resp.json()["id"]

    # Create a term in the domain
    term_resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "term",
            "title": f"Test Term {uuid.uuid4()}",
            "definition": "Test term definition",
            "parent_node_id": domain_id,
        },
    )
    assert term_resp.status_code == 201
    term_id = term_resp.json()["id"]

    # Move the domain with terms using the move API
    move_resp = shared_client.post(
        "/api/structure_nodes/move",
        json={
            "node_ids": [domain_id],
            "target_parent_id": target_layer_id,
            "move_children": True,
        },
    )
    assert move_resp.status_code == 200
    move_data = move_resp.json()

    # Verify the domain was moved
    assert len(move_data["moved_nodes"]) == 1
    assert move_data["moved_nodes"][0]["parent_node_id"] == target_layer_id

    # Verify the term is still under the domain (move_children behavior)
    term_resp = shared_client.get(f"/api/structure_nodes/{term_id}")
    assert term_resp.status_code == 200
    assert term_resp.json()["parent_node_id"] == domain_id


def test_move_domains_conflict_warning(shared_client):
    """Test that domain move detects title conflicts"""
    # Create two layers
    source_layer_id = create_layer(shared_client, f"Source Layer {uuid.uuid4()}")
    target_layer_id = create_layer(shared_client, f"Target Layer {uuid.uuid4()}")

    domain_title = f"Conflicting Domain {uuid.uuid4()}"

    # Create domain in source layer
    source_domain_resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": domain_title,
            "definition": "Source definition",
            "parent_node_id": source_layer_id,
        },
    )
    assert source_domain_resp.status_code == 201
    source_domain_id = source_domain_resp.json()["id"]

    # Create domain with same title in target layer
    target_domain_resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": domain_title,
            "definition": "Target definition",
            "parent_node_id": target_layer_id,
        },
    )
    assert target_domain_resp.status_code == 201

    # Try to move source domain to target layer (should generate warning)
    move_resp = shared_client.post(
        "/api/structure_nodes/move",
        json={
            "node_ids": [source_domain_id],
            "target_parent_id": target_layer_id,
            "move_children": True,
            "handle_conflicts": "warn",
        },
    )
    assert move_resp.status_code == 200
    move_data = move_resp.json()

    # Should have warnings about title conflict
    assert len(move_data["warnings"]) > 0
    assert any("already exists" in warning for warning in move_data["warnings"])


def test_move_domains_invalid_target(shared_client):
    """Test moving domain to non-existent parent"""
    source_layer_id = create_layer(shared_client, f"Source Layer {uuid.uuid4()}")
    invalid_layer_id = str(uuid.uuid4())

    # Create a domain
    domain_resp = shared_client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "title": f"Test Domain {uuid.uuid4()}",
            "definition": "Test definition",
            "parent_node_id": source_layer_id,
        },
    )
    assert domain_resp.status_code == 201
    domain_id = domain_resp.json()["id"]

    # Try to move to invalid layer
    move_resp = shared_client.post(
        "/api/structure_nodes/move",
        json={
            "node_ids": [domain_id],
            "target_parent_id": invalid_layer_id,
            "move_children": True,
        },
    )
    assert move_resp.status_code == 400
    assert "Target parent" in move_resp.json()["detail"]
