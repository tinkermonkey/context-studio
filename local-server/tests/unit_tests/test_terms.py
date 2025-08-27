
import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# All fixtures are now provided by conftest.py

def create_layer_and_domain(client):
    layer_resp = client.post("/api/layers/", json={"title": str(uuid.uuid4())})
    assert layer_resp.status_code == 201
    layer_id = layer_resp.json()["id"]
    # Force visibility of layer
    client.get("/api/layers/")
    domain_resp = client.post("/api/domains/", json={"title": str(uuid.uuid4()), "definition": "def", "layer_id": layer_id})
    assert domain_resp.status_code == 201
    domain_id = domain_resp.json()["id"]
    # Force visibility of domain
    client.get("/api/domains/")
    return layer_id, domain_id

def create_term(client, domain_id, layer_id, title=None, definition=None, parent_term_id=None):
    data = {
        "title": title or str(uuid.uuid4()),
        "definition": definition or "def",
        "domain_id": domain_id,
        "layer_id": layer_id
    }
    if parent_term_id:
        data["parent_term_id"] = parent_term_id
    resp = client.post("/api/terms/", json=data)
    assert resp.status_code == 201, resp.text
    return resp.json()

def test_create_get_update_delete_term(client):
    layer_id, domain_id = create_layer_and_domain(client)
    term = create_term(client, domain_id, layer_id, title="T1", definition="D1")
    term_id = term["id"]
    # Get
    resp = client.get(f"/api/terms/{term_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "T1"
    # Update
    resp = client.put(f"/api/terms/{term_id}", json={"title": "T1 Updated"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "T1 Updated"
    # Delete
    resp = client.delete(f"/api/terms/{term_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Get after delete
    resp = client.get(f"/api/terms/{term_id}")
    assert resp.status_code == 404

def test_term_duplicate_title_within_domain(client):
    layer_id, domain_id = create_layer_and_domain(client)
    create_term(client, domain_id, layer_id, title="T1")
    resp = client.post("/api/terms/", json={"title": "T1", "definition": "def", "domain_id": domain_id, "layer_id": layer_id})
    assert resp.status_code == 409
    assert "unique" in resp.json()["detail"].lower()

def test_term_invalid_domain_or_layer(client):
    layer_id, domain_id = create_layer_and_domain(client)
    bad_uuid = str(uuid.uuid4())
    resp = client.post("/api/terms/", json={"title": "T", "definition": "D", "domain_id": bad_uuid, "layer_id": layer_id})
    assert resp.status_code == 422
    resp = client.post("/api/terms/", json={"title": "T", "definition": "D", "domain_id": domain_id, "layer_id": bad_uuid})
    assert resp.status_code == 422

def test_term_parent_and_circular_reference(client):
    layer_id, domain_id = create_layer_and_domain(client)
    t1 = create_term(client, domain_id, layer_id, title="Parent")
    t2 = create_term(client, domain_id, layer_id, title="Child", parent_term_id=t1["id"])
    # Parent must exist and belong to same domain
    bad_uuid = str(uuid.uuid4())
    resp = client.post("/api/terms/", json={"title": "Bad", "definition": "D", "domain_id": domain_id, "layer_id": layer_id, "parent_term_id": bad_uuid})
    assert resp.status_code == 422
    # Circular reference
    resp = client.put(f"/api/terms/{t1['id']}", json={"parent_term_id": t2["id"]})
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    print(f"DEBUG: circular reference error detail: {detail}")
    assert "circular" in detail

def test_list_terms_pagination(client):
    layer_id, domain_id = create_layer_and_domain(client)
    for i in range(5):
        create_term(client, domain_id, layer_id, title=f"T{i}")
    resp = client.get(f"/api/terms/?domain_id={domain_id}&limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) <= 2
    resp = client.get(f"/api/terms/?domain_id={domain_id}&sort=title")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == sorted(titles)

def test_create_get_update_delete_term_relationship(client):
    layer_id, domain_id = create_layer_and_domain(client)
    t1 = create_term(client, domain_id, layer_id, title="Abcdef")
    t2 = create_term(client, domain_id, layer_id, title="Bcdefg")
    # Create
    resp = client.post("/api/term-relationships/", json={"source_term_id": t1["id"], "target_term_id": t2["id"], "predicate": "rel"})
    assert resp.status_code == 201, resp.text
    rel = resp.json()
    rel_id = rel["id"]
    # Get
    resp = client.get(f"/api/term-relationships/{rel_id}")
    assert resp.status_code == 200
    assert resp.json()["predicate"] == "rel"
    # Update
    resp = client.put(f"/api/term-relationships/{rel_id}", json={"predicate": "rel2"})
    assert resp.status_code == 200
    assert resp.json()["predicate"] == "rel2"
    # Delete
    resp = client.delete(f"/api/term-relationships/{rel_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Get after delete
    resp = client.get(f"/api/term-relationships/{rel_id}")
    assert resp.status_code == 404

def test_term_relationship_invalid_cases(client):
    layer_id, domain_id = create_layer_and_domain(client)
    t1 = create_term(client, domain_id, layer_id)
    bad_uuid = str(uuid.uuid4())
    # Both terms must exist
    resp = client.post("/api/term-relationships/", json={"source_term_id": t1["id"], "target_term_id": bad_uuid, "predicate": "rel"})
    assert resp.status_code == 400
    # Duplicate relationship
    t2 = create_term(client, domain_id, layer_id)
    resp1 = client.post("/api/term-relationships/", json={"source_term_id": t1["id"], "target_term_id": t2["id"], "predicate": "rel"})
    assert resp1.status_code == 201
    resp2 = client.post("/api/term-relationships/", json={"source_term_id": t1["id"], "target_term_id": t2["id"], "predicate": "rel"})
    assert resp2.status_code == 409
    assert "duplicate" in resp2.json()["detail"].lower()
    # Update non-existent
    resp = client.put(f"/api/term-relationships/{bad_uuid}", json={"predicate": "x"})
    assert resp.status_code == 404
    # Delete non-existent
    resp = client.delete(f"/api/term-relationships/{bad_uuid}")
    assert resp.status_code == 404


def test_move_terms_basic(client):
    """Test basic term movement between domains"""
    # Create source domain
    source_layer_id, source_domain_id = create_layer_and_domain(client)
    
    # Create target domain in the same layer
    target_domain_resp = client.post("/api/domains/", json={
        "title": str(uuid.uuid4()),
        "definition": "Target domain",
        "layer_id": source_layer_id
    })
    assert target_domain_resp.status_code == 201
    target_domain_id = target_domain_resp.json()["id"]
    
    # Create a term in the source domain
    term = create_term(client, source_domain_id, source_layer_id, 
                      title=f"Test Term {uuid.uuid4()}")
    
    # Move the term to the target domain
    move_resp = client.post("/api/terms/move", json={
        "term_ids": [term["id"]],
        "target_domain_id": target_domain_id,
        "move_children": True
    })
    assert move_resp.status_code == 200
    move_data = move_resp.json()
    
    # Verify the term was moved
    assert len(move_data["moved_terms"]) == 1
    assert move_data["moved_terms"][0]["domain_id"] == target_domain_id
    
    # Verify the term is in the target domain
    term_resp = client.get(f"/api/terms/{term['id']}")
    assert term_resp.status_code == 200
    assert term_resp.json()["domain_id"] == target_domain_id


def test_move_terms_with_children(client):
    """Test moving terms with their children"""
    # Create domains
    source_layer_id, source_domain_id = create_layer_and_domain(client)
    target_domain_resp = client.post("/api/domains/", json={
        "title": str(uuid.uuid4()),
        "definition": "Target domain", 
        "layer_id": source_layer_id
    })
    assert target_domain_resp.status_code == 201
    target_domain_id = target_domain_resp.json()["id"]
    
    # Create parent term
    parent_term = create_term(client, source_domain_id, source_layer_id,
                             title=f"Parent Term {uuid.uuid4()}")
    
    # Create child term
    child_term = create_term(client, source_domain_id, source_layer_id,
                            title=f"Child Term {uuid.uuid4()}",
                            parent_term_id=parent_term["id"])
    
    # Move parent term with children
    move_resp = client.post("/api/terms/move", json={
        "term_ids": [parent_term["id"]],
        "target_domain_id": target_domain_id,
        "move_children": True
    })
    assert move_resp.status_code == 200
    move_data = move_resp.json()
    
    # Verify both parent and child were moved
    assert len(move_data["moved_terms"]) == 2
    
    # Verify child term is also in target domain
    child_resp = client.get(f"/api/terms/{child_term['id']}")
    assert child_resp.status_code == 200
    assert child_resp.json()["domain_id"] == target_domain_id


def test_move_terms_without_children(client):
    """Test moving terms without their children"""
    # Create domains
    source_layer_id, source_domain_id = create_layer_and_domain(client)
    target_domain_resp = client.post("/api/domains/", json={
        "title": str(uuid.uuid4()),
        "definition": "Target domain",
        "layer_id": source_layer_id
    })
    assert target_domain_resp.status_code == 201
    target_domain_id = target_domain_resp.json()["id"]
    
    # Create parent term
    parent_term = create_term(client, source_domain_id, source_layer_id,
                             title=f"Parent Term {uuid.uuid4()}")
    
    # Create child term
    child_term = create_term(client, source_domain_id, source_layer_id,
                            title=f"Child Term {uuid.uuid4()}",
                            parent_term_id=parent_term["id"])
    
    # Move parent term without children
    move_resp = client.post("/api/terms/move", json={
        "term_ids": [parent_term["id"]],
        "target_domain_id": target_domain_id,
        "move_children": False
    })
    assert move_resp.status_code == 200
    move_data = move_resp.json()
    
    # Verify only parent was moved
    assert len(move_data["moved_terms"]) == 1
    assert move_data["moved_terms"][0]["id"] == parent_term["id"]
    
    # Verify child term is still in source domain
    child_resp = client.get(f"/api/terms/{child_term['id']}")
    assert child_resp.status_code == 200
    assert child_resp.json()["domain_id"] == source_domain_id


def test_move_terms_conflict_warning(client):
    """Test that term move detects title conflicts"""
    # Create domains
    source_layer_id, source_domain_id = create_layer_and_domain(client)
    target_domain_resp = client.post("/api/domains/", json={
        "title": str(uuid.uuid4()),
        "definition": "Target domain",
        "layer_id": source_layer_id
    })
    assert target_domain_resp.status_code == 201
    target_domain_id = target_domain_resp.json()["id"]
    
    term_title = f"Conflicting Term {uuid.uuid4()}"
    
    # Create term in source domain
    source_term = create_term(client, source_domain_id, source_layer_id,
                             title=term_title)
    
    # Create term with same title in target domain
    target_term = create_term(client, target_domain_id, source_layer_id,
                             title=term_title)
    
    # Try to move source term to target domain (should generate warning)
    move_resp = client.post("/api/terms/move", json={
        "term_ids": [source_term["id"]],
        "target_domain_id": target_domain_id,
        "move_children": True
    })
    assert move_resp.status_code == 200
    move_data = move_resp.json()
    
    # Should have warnings about title conflict
    assert len(move_data["warnings"]) > 0
    assert any("already exists" in warning for warning in move_data["warnings"])


def test_move_terms_invalid_target(client):
    """Test moving term to non-existent domain"""
    source_layer_id, source_domain_id = create_layer_and_domain(client)
    invalid_domain_id = str(uuid.uuid4())
    
    # Create a term
    term = create_term(client, source_domain_id, source_layer_id,
                      title=f"Test Term {uuid.uuid4()}")
    
    # Try to move to invalid domain
    move_resp = client.post("/api/terms/move", json={
        "term_ids": [term["id"]],
        "target_domain_id": invalid_domain_id,
        "move_children": True
    })
    assert move_resp.status_code == 400
    assert "Target domain does not exist" in move_resp.json()["detail"]


def test_safe_deletion_workflow(client):
    """Test the safe deletion workflow: move children then delete parent"""
    source_layer_id, source_domain_id = create_layer_and_domain(client)
    
    # Create parent term
    parent_term = create_term(client, source_domain_id, source_layer_id,
                             title=f"Parent Term {uuid.uuid4()}")
    
    # Create child terms
    child1 = create_term(client, source_domain_id, source_layer_id,
                        title=f"Child 1 {uuid.uuid4()}",
                        parent_term_id=parent_term["id"])
    child2 = create_term(client, source_domain_id, source_layer_id,
                        title=f"Child 2 {uuid.uuid4()}",
                        parent_term_id=parent_term["id"])
    
    # Step 1: Move children to have no parent (orphan them)
    children_ids = [child1["id"], child2["id"]]
    
    # For orphaning, we can move them to have no parent by updating them individually
    for child_id in children_ids:
        update_resp = client.put(f"/api/terms/{child_id}", json={
            "parent_term_id": None
        })
        assert update_resp.status_code == 200
    
    # Step 2: Verify children are orphaned
    for child_id in children_ids:
        child_resp = client.get(f"/api/terms/{child_id}")
        assert child_resp.status_code == 200
        assert child_resp.json()["parent_term_id"] is None
    
    # Step 3: Delete the parent (should succeed without cascading)
    delete_resp = client.delete(f"/api/terms/{parent_term['id']}")
    assert delete_resp.status_code == 200
    
    # Step 4: Verify parent is deleted but children still exist
    parent_resp = client.get(f"/api/terms/{parent_term['id']}")
    assert parent_resp.status_code == 404
    
    for child_id in children_ids:
        child_resp = client.get(f"/api/terms/{child_id}")
        assert child_resp.status_code == 200
