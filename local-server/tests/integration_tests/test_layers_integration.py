import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import pytest
from fastapi.testclient import TestClient
from database import models
from database.utils import init_db, get_session_local
from app import create_app


# Use a temporary file for the test database
test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{test_db_path}"
engine = init_db(database_url=SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, skip_vec=False)
TestingSessionLocal = get_session_local(engine)

# Create a test app instance with test DB engine/session
app = create_app(engine=engine, session_local=TestingSessionLocal, skip_vec=False)

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

def create_layer(client, title=None, definition=None, primary_predicate=None):
    import uuid
    unique_title = title if title else f"Test Layer {uuid.uuid4()}"
    payload = {
        "title": unique_title,
        "definition": definition or "Layer for integration test.",
        "primary_predicate": primary_predicate
    }
    response = client.post("/api/layers/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def test_create_layer(client):
    data = create_layer(client)
    assert "id" in data
    assert data["title"].startswith("Test Layer")
    assert data["definition"] == "Layer for integration test."
    assert data["created_at"]

def test_create_layer_duplicate_title(client):
    layer = create_layer(client, title="UniqueLayer")
    resp = client.post("/api/layers/", json={"title": "UniqueLayer", "definition": "Dup test."})
    assert resp.status_code == 409
    assert "unique" in resp.json()["detail"][0]["msg"].lower()

def test_get_layer(client):
    layer = create_layer(client)
    resp = client.get(f"/api/layers/{layer['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == layer["id"]
    assert data["title"] == layer["title"]

def test_get_layer_not_found(client):
    resp = client.get("/api/layers/nonexistent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_list_layers(client):
    # Create two layers
    l1 = create_layer(client, title="LayerA")
    l2 = create_layer(client, title="LayerB")
    resp = client.get("/api/layers/?sort=title")
    assert resp.status_code == 200
    data = resp.json()
    
    # Check pagination response structure
    assert "data" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    
    # Check pagination metadata
    assert data["total"] >= 2
    assert data["skip"] == 0
    assert data["limit"] == 50
    assert len(data["data"]) >= 2
    
    titles = [d["title"] for d in data["data"]]
    assert "LayerA" in titles and "LayerB" in titles
    
    # Test limit
    resp2 = client.get("/api/layers/?limit=1")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["limit"] == 1
    assert len(data2["data"]) == 1

def test_update_layer(client):
    layer = create_layer(client)
    update = {"title": "Updated Layer", "definition": "Updated def."}
    resp = client.put(f"/api/layers/{layer['id']}", json=update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated Layer"
    assert data["definition"] == "Updated def."

def test_update_layer_duplicate_title(client):
    l1 = create_layer(client, title="LayerDup1")
    l2 = create_layer(client, title="LayerDup2")
    update = {"title": "LayerDup1"}
    resp = client.put(f"/api/layers/{l2['id']}", json=update)
    assert resp.status_code == 409
    assert "unique" in resp.json()["detail"][0]["msg"].lower()

def test_update_layer_not_found(client):
    resp = client.put("/api/layers/nonexistent-id", json={"title": "X"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_delete_layer(client):
    layer = create_layer(client)
    resp = client.delete(f"/api/layers/{layer['id']}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Confirm deletion
    get_resp = client.get(f"/api/layers/{layer['id']}")
    assert get_resp.status_code == 404

def test_delete_layer_not_found(client):
    resp = client.delete("/api/layers/nonexistent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_find_layer(client):
    l1 = create_layer(client, title="Alpha Layer", definition="Physics")
    l2 = create_layer(client, title="Beta Layer", definition="Chemistry")

    # Search by title
    resp = client.post("/api/layers/find", json={"title": "Alpha"})
    assert resp.status_code == 200
    data = resp.json()
    assert any("Alpha" in d["title"] for d in data)

    # Search by definition
    resp2 = client.post("/api/layers/find", json={"definition": "Chemistry"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert any("Chemistry" in d["definition"] for d in data2)

    # Search with a term that should return results (but with low minimum score)
    resp3 = client.post("/api/layers/find", json={"title": "Beta", "minimum_score": 0.0})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3) > 0
    record3 = data3[0]
    assert "score" in record3
    assert "distance" in record3

def test_find_layer_invalid_created_at(client):
    resp = client.post("/api/layers/find", json={"created_at": "not-a-date"})
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()

def test_layers_pagination(client):
    # Create 4 layers
    layers = []
    for i in range(4):
        layer = create_layer(client, title=f"PaginationLayer{i:02d}")
        layers.append(layer)
    
    # Test pagination with limit=2
    resp = client.get("/api/layers/?limit=2&sort=title")
    assert resp.status_code == 200
    data = resp.json()
    
    # Check pagination structure
    assert "data" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    
    # Check first page (note: there might be other layers from other tests)
    assert data["total"] >= 4
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert len(data["data"]) == 2
    
    # Check that we can determine if more pages exist
    has_more_pages = (data["skip"] + data["limit"]) < data["total"]
    assert has_more_pages is True
    
    # Test second page
    resp2 = client.get("/api/layers/?skip=2&limit=2&sort=title")
    assert resp2.status_code == 200
    data2 = resp2.json()
    
    assert data2["total"] >= 4
    assert data2["skip"] == 2
    assert data2["limit"] == 2
    assert len(data2["data"]) <= 2  # Could be less if we're near the end
