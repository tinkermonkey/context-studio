
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
    assert "unique" in resp.json()["detail"][0]["msg"].lower()

def test_term_invalid_domain_or_layer(client):
    layer_id, domain_id = create_layer_and_domain(client)
    bad_uuid = str(uuid.uuid4())
    resp = client.post("/api/terms/", json={"title": "T", "definition": "D", "domain_id": bad_uuid, "layer_id": layer_id})
    assert resp.status_code == 400
    resp = client.post("/api/terms/", json={"title": "T", "definition": "D", "domain_id": domain_id, "layer_id": bad_uuid})
    assert resp.status_code == 400

def test_term_parent_and_circular_reference(client):
    layer_id, domain_id = create_layer_and_domain(client)
    t1 = create_term(client, domain_id, layer_id, title="Parent")
    t2 = create_term(client, domain_id, layer_id, title="Child", parent_term_id=t1["id"])
    # Parent must exist and belong to same domain
    bad_uuid = str(uuid.uuid4())
    resp = client.post("/api/terms/", json={"title": "Bad", "definition": "D", "domain_id": domain_id, "layer_id": layer_id, "parent_term_id": bad_uuid})
    assert resp.status_code == 400
    # Circular reference
    resp = client.put(f"/api/terms/{t1['id']}", json={"parent_term_id": t2["id"]})
    assert resp.status_code == 400
    detail = resp.json()["detail"][0]["msg"].lower()
    print(f"DEBUG: circular reference error detail: {detail}")
    assert "circular" in detail

def test_list_terms_pagination(client):
    layer_id, domain_id = create_layer_and_domain(client)
    for i in range(5):
        create_term(client, domain_id, layer_id, title=f"T{i}")
    resp = client.get(f"/api/terms/?domain_id={domain_id}&limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) <= 2
    resp = client.get(f"/api/terms/?domain_id={domain_id}&sort=title")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert titles == sorted(titles)

def test_create_get_update_delete_term_relationship(client):
    layer_id, domain_id = create_layer_and_domain(client)
    t1 = create_term(client, domain_id, layer_id, title="A")
    t2 = create_term(client, domain_id, layer_id, title="B")
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
    assert "duplicate" in resp2.json()["detail"][0]["msg"].lower()
    # Update non-existent
    resp = client.put(f"/api/term-relationships/{bad_uuid}", json={"predicate": "x"})
    assert resp.status_code == 404
    # Delete non-existent
    resp = client.delete(f"/api/term-relationships/{bad_uuid}")
    assert resp.status_code == 404
