
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from fastapi.testclient import TestClient
from app import create_app
from database.utils import get_engine, get_session_local, init_db
import uuid
import tempfile


@pytest.fixture(scope="function")
def test_app():
    # Use a temporary file-based SQLite DB for reliable cross-thread access
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_url = f"sqlite:///{tf.name}"
    try:
        engine = get_engine(db_url)
        session_local = get_session_local(engine)
        init_db(engine=engine, skip_vec=False)
        app = create_app(engine=engine, session_local=session_local, skip_vec=False)
        yield app
    finally:
        os.unlink(tf.name)

@pytest.fixture(scope="function")
def client(test_app):
    with TestClient(test_app) as c:
        yield c

def create_layer(client, title="Test Layer"):
    resp = client.post("/api/layers/", json={"title": title})
    if resp.status_code != 201:
        print(f"Layer creation failed: {resp.status_code} {resp.text}")
    assert resp.status_code == 201
    # Force a new connection/session for SQLite visibility
    client.get("/api/layers/")
    return resp.json()["id"]

def debug_list_layers(client):
    resp = client.get("/api/layers/")
    print(f"DEBUG: Layers in DB before domain creation: {resp.status_code} {resp.text}")
    return resp

def test_create_get_update_delete_domain(client):
    layer_id = create_layer(client, str(uuid.uuid4()))
    debug_list_layers(client)
    resp = client.post("/api/domains/", json={
        "title": "Test Domain",
        "definition": "A test domain.",
        "layer_id": layer_id
    })
    if resp.status_code != 201:
        print(f"Domain creation failed: {resp.status_code} {resp.text}")
    assert resp.status_code == 201
    domain = resp.json()
    domain_id = domain["id"]
    resp = client.get(f"/api/domains/{domain_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test Domain"
    resp = client.put(f"/api/domains/{domain_id}", json={"title": "Updated Domain"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Domain"
    resp = client.delete(f"/api/domains/{domain_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    resp = client.get(f"/api/domains/{domain_id}")
    assert resp.status_code == 404

def test_domain_duplicate_title(client):
    layer_id = create_layer(client, str(uuid.uuid4()))
    resp1 = client.post("/api/domains/", json={
        "title": "Unique Domain",
        "definition": "A domain.",
        "layer_id": layer_id
    })
    if resp1.status_code != 201:
        print(f"Domain creation failed: {resp1.status_code} {resp1.text}")
    assert resp1.status_code == 201
    resp2 = client.post("/api/domains/", json={
        "title": "Unique Domain",
        "definition": "Another domain.",
        "layer_id": layer_id
    })
    if resp2.status_code != 409:
        print(f"Duplicate domain test failed: {resp2.status_code} {resp2.text}")
    assert resp2.status_code == 409
    assert "unique" in resp2.json()["detail"][0]["msg"].lower()

def test_domain_invalid_layer(client):
    resp = client.post("/api/domains/", json={
        "title": "Bad Domain",
        "definition": "No such layer.",
        "layer_id": str(uuid.uuid4())
    })
    assert resp.status_code == 400
    assert "layer does not exist" in resp.json()["detail"][0]["msg"].lower()

def test_list_domains(client):
    layer_id = create_layer(client, str(uuid.uuid4()))
    for i in range(3):
        client.post("/api/domains/", json={
            "title": f"Domain {i}",
            "definition": f"Def {i}",
            "layer_id": layer_id
        })
    resp = client.get("/api/domains/?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) <= 2
    resp = client.get(f"/api/domains/?layer_id={layer_id}")
    assert resp.status_code == 200
    assert all(d["layer_id"] == layer_id for d in resp.json())


def test_move_domains_basic(client):
    """Test basic domain movement between layers"""
    # Create two layers
    source_layer_id = create_layer(client, f"Source Layer {uuid.uuid4()}")
    target_layer_id = create_layer(client, f"Target Layer {uuid.uuid4()}")
    
    # Create a domain in the source layer
    domain_resp = client.post("/api/domains/", json={
        "title": f"Test Domain {uuid.uuid4()}",
        "definition": "Test definition",
        "layer_id": source_layer_id
    })
    assert domain_resp.status_code == 201
    domain_id = domain_resp.json()["id"]
    
    # Move the domain to the target layer
    move_resp = client.post("/api/domains/move", json={
        "domain_ids": [domain_id],
        "target_layer_id": target_layer_id,
        "move_terms": True
    })
    assert move_resp.status_code == 200
    move_data = move_resp.json()
    
    # Verify the domain was moved
    assert len(move_data["moved_domains"]) == 1
    assert move_data["moved_domains"][0]["layer_id"] == target_layer_id
    
    # Verify the domain is in the target layer
    domain_resp = client.get(f"/api/domains/{domain_id}")
    assert domain_resp.status_code == 200
    assert domain_resp.json()["layer_id"] == target_layer_id


def test_move_domains_with_terms(client):
    """Test moving domains with their terms"""
    # Create two layers
    source_layer_id = create_layer(client, f"Source Layer {uuid.uuid4()}")
    target_layer_id = create_layer(client, f"Target Layer {uuid.uuid4()}")
    
    # Create a domain in the source layer
    domain_resp = client.post("/api/domains/", json={
        "title": f"Test Domain {uuid.uuid4()}",
        "definition": "Test definition",
        "layer_id": source_layer_id
    })
    assert domain_resp.status_code == 201
    domain_id = domain_resp.json()["id"]
    
    # Create a term in the domain
    term_resp = client.post("/api/terms/", json={
        "title": f"Test Term {uuid.uuid4()}",
        "definition": "Test term definition",
        "domain_id": domain_id,
        "layer_id": source_layer_id
    })
    assert term_resp.status_code == 201
    term_id = term_resp.json()["id"]
    
    # Move the domain with terms
    move_resp = client.post("/api/domains/move", json={
        "domain_ids": [domain_id],
        "target_layer_id": target_layer_id,
        "move_terms": True
    })
    assert move_resp.status_code == 200
    
    # Verify the term was also moved to the target layer
    term_resp = client.get(f"/api/terms/{term_id}")
    assert term_resp.status_code == 200
    assert term_resp.json()["layer_id"] == target_layer_id


def test_move_domains_conflict_warning(client):
    """Test that domain move detects title conflicts"""
    # Create two layers
    source_layer_id = create_layer(client, f"Source Layer {uuid.uuid4()}")
    target_layer_id = create_layer(client, f"Target Layer {uuid.uuid4()}")
    
    domain_title = f"Conflicting Domain {uuid.uuid4()}"
    
    # Create domain in source layer
    source_domain_resp = client.post("/api/domains/", json={
        "title": domain_title,
        "definition": "Source definition",
        "layer_id": source_layer_id
    })
    assert source_domain_resp.status_code == 201
    source_domain_id = source_domain_resp.json()["id"]
    
    # Create domain with same title in target layer
    target_domain_resp = client.post("/api/domains/", json={
        "title": domain_title,
        "definition": "Target definition",
        "layer_id": target_layer_id
    })
    assert target_domain_resp.status_code == 201
    
    # Try to move source domain to target layer (should generate warning)
    move_resp = client.post("/api/domains/move", json={
        "domain_ids": [source_domain_id],
        "target_layer_id": target_layer_id,
        "move_terms": True
    })
    assert move_resp.status_code == 200
    move_data = move_resp.json()
    
    # Should have warnings about title conflict
    assert len(move_data["warnings"]) > 0
    assert any("already exists" in warning for warning in move_data["warnings"])


def test_move_domains_invalid_target(client):
    """Test moving domain to non-existent layer"""
    source_layer_id = create_layer(client, f"Source Layer {uuid.uuid4()}")
    invalid_layer_id = str(uuid.uuid4())
    
    # Create a domain
    domain_resp = client.post("/api/domains/", json={
        "title": f"Test Domain {uuid.uuid4()}",
        "definition": "Test definition",
        "layer_id": source_layer_id
    })
    assert domain_resp.status_code == 201
    domain_id = domain_resp.json()["id"]
    
    # Try to move to invalid layer
    move_resp = client.post("/api/domains/move", json={
        "domain_ids": [domain_id],
        "target_layer_id": invalid_layer_id,
        "move_terms": True
    })
    assert move_resp.status_code == 400
    assert "Target layer does not exist" in move_resp.json()["detail"]
