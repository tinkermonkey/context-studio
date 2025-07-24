import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from database import models
from database.utils import init_db, get_session_local
from app import create_app

# Use a temporary file for the test database
test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{test_db_path}"
engine = init_db(database_url=SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, skip_vec=False)
TestingSessionLocal = get_session_local(engine)

# Create a test app instance with test DB engine/session
app = create_app(engine=engine, session_local=TestingSessionLocal)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    yield
    os.close(test_db_fd)
    os.unlink(test_db_path)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def create_layer(client, title=None):
    import uuid
    unique_title = title if title else f"Test Layer {uuid.uuid4()}"
    payload = {"title": unique_title, "definition": "Layer for terms test."}
    resp = client.post("/api/layers/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]

def create_domain(client, layer_id, title=None):
    import uuid
    unique_title = title if title else f"Test Domain {uuid.uuid4()}"
    payload = {"title": unique_title, "definition": "Domain for terms test.", "layer_id": layer_id}
    resp = client.post("/api/domains/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]

def create_term(client, domain_id, layer_id, title=None, definition=None, parent_term_id=None):
    import uuid
    unique_title = title if title else f"Test Term {uuid.uuid4()}"
    payload = {
        "title": unique_title,
        "definition": definition or "Term for integration test.",
        "domain_id": domain_id,
        "layer_id": layer_id,
        "parent_term_id": parent_term_id
    }
    resp = client.post("/api/terms/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()

def test_create_get_term(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    term = create_term(client, domain_id, layer_id)
    resp = client.get(f"/api/terms/{term['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == term["id"]
    assert data["title"] == term["title"]
    assert data["definition"] == term["definition"]
    assert data["domain_id"] == domain_id
    assert data["layer_id"] == layer_id

def test_create_term_invalid_domain_or_layer(client):
    # Invalid domain
    layer_id = create_layer(client)
    resp = client.post("/api/terms/", json={"title": "T1", "definition": "D", "domain_id": "bad", "layer_id": layer_id})
    assert resp.status_code == 422  # FastAPI returns 422 for invalid UUID
    # Invalid layer
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    resp = client.post("/api/terms/", json={"title": "T2", "definition": "D", "domain_id": domain_id, "layer_id": "bad"})
    assert resp.status_code == 422  # FastAPI returns 422 for invalid UUID

def test_create_term_duplicate_title_within_domain(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    t1 = create_term(client, domain_id, layer_id, title="DupTerm")
    resp = client.post("/api/terms/", json={"title": "DupTerm", "definition": "D", "domain_id": domain_id, "layer_id": layer_id})
    assert resp.status_code == 409
    assert "unique" in resp.json()["detail"][0]["msg"].lower()

def test_create_term_with_parent_and_circular_reference(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    parent = create_term(client, domain_id, layer_id)
    child = create_term(client, domain_id, layer_id, parent_term_id=parent["id"])
    # Parent must exist and be in same domain
    resp = client.post("/api/terms/", json={"title": "BadParent", "definition": "D", "domain_id": domain_id, "layer_id": layer_id, "parent_term_id": "badid"})
    assert resp.status_code == 422  # FastAPI returns 422 for invalid UUID
    # Circular reference
    resp = client.put(f"/api/terms/{parent['id']}", json={"parent_term_id": child["id"]})
    assert resp.status_code == 400
    assert "circular" in resp.json()["detail"][0]["msg"].lower()

def test_update_term(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    term = create_term(client, domain_id, layer_id)
    update = {"title": "Updated Term", "definition": "Updated def."}
    resp = client.put(f"/api/terms/{term['id']}", json=update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated Term"
    assert data["definition"] == "Updated def."

def test_update_term_duplicate_title(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    t1 = create_term(client, domain_id, layer_id, title="T1")
    t2 = create_term(client, domain_id, layer_id, title="T2")
    resp = client.put(f"/api/terms/{t2['id']}", json={"title": "T1"})
    assert resp.status_code == 409
    assert "unique" in resp.json()["detail"][0]["msg"].lower()

def test_update_term_not_found(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    resp = client.put("/api/terms/nonexistent-id", json={"title": "X"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_delete_term(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    term = create_term(client, domain_id, layer_id)
    resp = client.delete(f"/api/terms/{term['id']}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Confirm deletion
    get_resp = client.get(f"/api/terms/{term['id']}")
    assert get_resp.status_code == 404

def test_delete_term_not_found(client):
    resp = client.delete("/api/terms/nonexistent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_list_terms(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    t1 = create_term(client, domain_id, layer_id, title="T1")
    t2 = create_term(client, domain_id, layer_id, title="T2")
    resp = client.get(f"/api/terms/?domain_id={domain_id}")
    assert resp.status_code == 200
    data = resp.json()
    
    # Check pagination response structure
    assert "data" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    
    # Check pagination metadata
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 50
    assert len(data["data"]) == 2
    
    titles = [d["title"] for d in data["data"]]
    assert "T1" in titles and "T2" in titles
    
    # Test limit
    resp2 = client.get(f"/api/terms/?domain_id={domain_id}&limit=1")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 2
    assert data2["limit"] == 1
    assert len(data2["data"]) == 1

def test_find_term(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    t1 = create_term(client, domain_id, layer_id, title="Alpha Term", definition="Physics")
    t2 = create_term(client, domain_id, layer_id, title="Beta Term", definition="Chemistry")

    # Search by title
    resp = client.post("/api/terms/find", json={"title": "Alpha"})
    assert resp.status_code == 200
    data = resp.json()
    assert any("Alpha" in d["title"] for d in data)

    # Search by definition
    resp2 = client.post("/api/terms/find", json={"definition": "Chemistry"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert any("Chemistry" in d["definition"] for d in data2)

    # Search with a term that should return results (but with low score)
    resp3 = client.post("/api/terms/find", json={"title": "Beta", "minimum_score": 0.0})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3) > 0
    record3 = data3[0]
    assert "score" in record3
    assert "distance" in record3

def test_find_term_invalid_created_at(client):
    resp = client.post("/api/terms/find", json={"created_at": "not-a-date"})
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()

def test_terms_pagination(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id)
    
    # Create 5 terms
    terms = []
    for i in range(5):
        term = create_term(client, domain_id, layer_id, title=f"Term{i:02d}")
        terms.append(term)
    
    # Test pagination with limit=2
    resp = client.get(f"/api/terms/?domain_id={domain_id}&limit=2&sort=title")
    assert resp.status_code == 200
    data = resp.json()
    
    # Check pagination structure
    assert "data" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    
    # Check first page
    assert data["total"] == 5
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert len(data["data"]) == 2
    
    # Check that we can determine if more pages exist
    has_more_pages = (data["skip"] + data["limit"]) < data["total"]
    assert has_more_pages is True
    
    # Test second page
    resp2 = client.get(f"/api/terms/?domain_id={domain_id}&skip=2&limit=2&sort=title")
    assert resp2.status_code == 200
    data2 = resp2.json()
    
    assert data2["total"] == 5
    assert data2["skip"] == 2
    assert data2["limit"] == 2
    assert len(data2["data"]) == 2
    
    # Test last page
    resp3 = client.get(f"/api/terms/?domain_id={domain_id}&skip=4&limit=2&sort=title")
    assert resp3.status_code == 200
    data3 = resp3.json()
    
    assert data3["total"] == 5
    assert data3["skip"] == 4
    assert data3["limit"] == 2
    assert len(data3["data"]) == 1  # Only one item on last page
    
    # Check that this is the last page
    has_more_pages = (data3["skip"] + data3["limit"]) < data3["total"]
    assert has_more_pages is False
