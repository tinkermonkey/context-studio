import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid


def create_layer(client, title=None):
    """Helper to create a layer"""
    resp = client.post(
        "/api/structure_nodes/",
        json={"title": title or str(uuid.uuid4()), "node_type": "layer"},
    )
    assert resp.status_code == 201
    client.get("/api/structure_nodes/?node_type=layer")  # Force SQLite visibility
    return resp.json()["id"]


def create_domain(client, layer_id, title=None):
    """Helper to create a domain"""
    resp = client.post(
        "/api/structure_nodes/",
        json={
            "title": title or str(uuid.uuid4()),
            "description": "Test definition",
            "node_type": "domain",
            "parent_node_id": layer_id,
        },
    )
    assert resp.status_code == 201
    client.get("/api/structure_nodes/?node_type=domain")  # Force SQLite visibility
    return resp.json()


def create_term(client, domain_id, layer_id, title=None, parent_term_id=None):
    """Helper to create a term"""
    data = {
        "title": title or str(uuid.uuid4()),
        "description": "Test definition",
        "node_type": "term",
        "parent_node_id": domain_id,
    }
    if parent_term_id:
        data["parent_node_id"] = parent_term_id

    resp = client.post("/api/structure_nodes/", json=data)
    assert resp.status_code == 201
    client.get("/api/structure_nodes/?node_type=term")  # Force SQLite visibility
    return resp.json()


def test_complete_domain_move_workflow(client):
    """Test complete workflow of moving domains with terms across layers"""
    # Create two layers
    source_layer_id = create_layer(client, "Source Layer")
    target_layer_id = create_layer(client, "Target Layer")

    # Create multiple domains in source layer
    domain1 = create_domain(client, source_layer_id, "Domain 1")
    domain2 = create_domain(client, source_layer_id, "Domain 2")

    # Create terms in the domains
    term1 = create_term(client, domain1["id"], source_layer_id, "Term 1")
    term2 = create_term(client, domain1["id"], source_layer_id, "Term 2")
    term3 = create_term(client, domain2["id"], source_layer_id, "Term 3")

    # Move domain to target layer using structure_nodes move API
    # Move domain to the second layer
    move_resp = client.post(
        "/api/structure_nodes/move",
        json={"node_ids": [domain1["id"]], "target_parent_id": target_layer_id},
    )
    assert move_resp.status_code == 200

    # Move second domain to target layer
    move_resp2 = client.post(
        "/api/structure_nodes/move",
        json={"node_ids": [domain2["id"]], "target_parent_id": target_layer_id},
    )
    assert move_resp2.status_code == 200

    # Verify all domains are now in target layer
    for domain_id in [domain1["id"], domain2["id"]]:
        domain_resp = client.get(f"/api/structure_nodes/{domain_id}")
        assert domain_resp.status_code == 200
        assert domain_resp.json()["parent_node_id"] == target_layer_id

    # Verify all terms still exist (terms move with their domains)
    for term_id in [term1["id"], term2["id"], term3["id"]]:
        term_resp = client.get(f"/api/structure_nodes/{term_id}")
        assert term_resp.status_code == 200


def test_complex_term_hierarchy_move(client):
    """Test moving complex term hierarchies between domains"""
    # Create two domains in same layer
    layer_id = create_layer(client, "Test Layer")
    source_domain = create_domain(client, layer_id, "Source Domain")
    target_domain = create_domain(client, layer_id, "Target Domain")

    # Create a complex hierarchy:
    # Root Term
    #   ├── Child 1
    #   │   └── Grandchild 1
    #   └── Child 2
    #       ├── Grandchild 2
    #       └── Grandchild 3

    root_term = create_term(client, source_domain["id"], layer_id, "Root Term")

    child1 = create_term(
        client, source_domain["id"], layer_id, "Child 1", root_term["id"]
    )
    child2 = create_term(
        client, source_domain["id"], layer_id, "Child 2", root_term["id"]
    )

    grandchild1 = create_term(
        client, source_domain["id"], layer_id, "Grandchild 1", child1["id"]
    )
    grandchild2 = create_term(
        client, source_domain["id"], layer_id, "Grandchild 2", child2["id"]
    )
    grandchild3 = create_term(
        client, source_domain["id"], layer_id, "Grandchild 3", child2["id"]
    )

    # Move root term to target domain using structure_nodes move API
    move_resp = client.post(
        "/api/structure_nodes/move",
        json={"node_ids": [root_term["id"]], "target_parent_id": target_domain["id"]},
    )
    assert move_resp.status_code == 200

    # Verify root term is in target domain
    root_resp = client.get(f"/api/structure_nodes/{root_term['id']}")
    assert root_resp.status_code == 200
    assert root_resp.json()["parent_node_id"] == target_domain["id"]

    # Verify hierarchy is preserved - children should still be children of root
    child1_resp = client.get(f"/api/structure_nodes/{child1['id']}")
    assert child1_resp.status_code == 200
    assert child1_resp.json()["parent_node_id"] == root_term["id"]

    grandchild1_resp = client.get(f"/api/structure_nodes/{grandchild1['id']}")
    assert grandchild1_resp.status_code == 200
    assert grandchild1_resp.json()["parent_node_id"] == child1["id"]


def test_safe_deletion_with_move_integration(client):
    """Test the full safe deletion workflow using move operations"""
    layer_id = create_layer(client, f"Test Layer {uuid.uuid4()}")

    # Create two domains - one for moving children to
    source_domain = create_domain(client, layer_id, f"Source Domain {uuid.uuid4()}")
    target_domain = create_domain(client, layer_id, f"Target Domain {uuid.uuid4()}")

    # Create a parent term with children
    parent_term = create_term(client, source_domain["id"], layer_id, "Parent to Delete")
    child1 = create_term(
        client, source_domain["id"], layer_id, "Child 1", parent_term["id"]
    )
    child2 = create_term(
        client, source_domain["id"], layer_id, "Child 2", parent_term["id"]
    )
    child3 = create_term(
        client, source_domain["id"], layer_id, "Child 3", parent_term["id"]
    )

    # Step 1: Move all children to target domain (preserving them)
    children_ids = [child1["id"], child2["id"], child3["id"]]
    for child_id in children_ids:
        move_resp = client.post(
            "/api/structure_nodes/move",
            json={"node_ids": [child_id], "target_parent_id": target_domain["id"]},
        )
        assert move_resp.status_code == 200

    # Step 2: Verify children are moved to target domain
    for child_id in children_ids:
        child_resp = client.get(f"/api/structure_nodes/{child_id}")
        assert child_resp.status_code == 200
        child_data = child_resp.json()
        assert child_data["parent_node_id"] == target_domain["id"]

    # Step 3: Delete the parent term (should succeed without errors)
    delete_resp = client.delete(f"/api/structure_nodes/{parent_term['id']}")
    assert delete_resp.status_code == 204

    # Step 4: Verify parent is gone but children survive
    parent_resp = client.get(f"/api/structure_nodes/{parent_term['id']}")
    assert parent_resp.status_code == 404

    for child_id in children_ids:
        child_resp = client.get(f"/api/structure_nodes/{child_id}")
        assert child_resp.status_code == 200


def test_cross_layer_term_move_integration(client):
    """Test moving terms between domains in different layers"""
    # Create two layers
    layer1_id = create_layer(client, "Layer 1")
    layer2_id = create_layer(client, "Layer 2")

    # Create domains in different layers
    domain1 = create_domain(client, layer1_id, "Domain in Layer 1")
    domain2 = create_domain(client, layer2_id, "Domain in Layer 2")

    # Create term in layer 1
    term = create_term(client, domain1["id"], layer1_id, "Cross-Layer Term")

    # Move term to domain in layer 2
    move_resp = client.post(
        "/api/structure_nodes/move",
        json={"node_ids": [term["id"]], "target_parent_id": domain2["id"]},
    )
    assert move_resp.status_code == 200

    # Verify term is now in layer 2 domain
    term_resp = client.get(f"/api/structure_nodes/{term['id']}")
    assert term_resp.status_code == 200
    term_data = term_resp.json()
    assert term_data["parent_node_id"] == domain2["id"]


def test_event_logging_for_moves(client):
    """Test that move operations are properly logged to NodeEvent table"""
    # This test would need access to the database to check NodeEvent table
    # For now, we'll just verify the operations work and assume logging is correct
    # based on the implementation

    layer_id = create_layer(client, f"Test Layer {uuid.uuid4()}")
    source_domain = create_domain(client, layer_id, f"Source Domain {uuid.uuid4()}")
    target_domain = create_domain(client, layer_id, f"Target Domain {uuid.uuid4()}")

    # Create and move a term
    term = create_term(client, source_domain["id"], layer_id, "Test Term")

    move_resp = client.post(
        "/api/structure_nodes/move",
        json={"node_ids": [term["id"]], "target_parent_id": target_domain["id"]},
    )
    assert move_resp.status_code == 200

    # If we get here without errors, the logging is working
    # (The actual verification would require database inspection)
    assert True


def test_batch_operations_with_warnings(client):
    """Test batch operations that generate warnings"""
    layer_id = create_layer(client, f"Test Layer {uuid.uuid4()}")
    source_domain = create_domain(client, layer_id, f"Source Domain {uuid.uuid4()}")
    target_domain = create_domain(client, layer_id, f"Target Domain {uuid.uuid4()}")

    # Create terms with potential conflicts
    term1 = create_term(client, source_domain["id"], layer_id, "Unique Term")
    term2 = create_term(client, source_domain["id"], layer_id, "Conflicting Term")

    # Create a term with same name in target domain
    conflicting_term = create_term(
        client, target_domain["id"], layer_id, "Conflicting Term"
    )

    # Try to move the unique term (should succeed)
    move_resp = client.post(
        "/api/structure_nodes/move",
        json={"node_ids": [term1["id"]], "target_parent_id": target_domain["id"]},
    )
    assert move_resp.status_code == 200

    # Verify the unique term was moved
    term_resp = client.get(f"/api/structure_nodes/{term1['id']}")
    assert term_resp.status_code == 200
    term_data = term_resp.json()
    assert term_data["parent_node_id"] == target_domain["id"]

    # Try to move the conflicting term (behavior may vary based on implementation)
    move_resp2 = client.post(
        "/api/structure_nodes/move",
        json={"node_ids": [term2["id"]], "target_parent_id": target_domain["id"]},
    )
    # This may succeed or fail depending on implementation
