import sys
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from database import models
from database.utils import init_db, get_session_local
from app import create_app
import datetime
from uuid import uuid4

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


def create_layer(client):
    unique_title = f"Test Layer {uuid4()}"
    payload = {
        "title": unique_title,
        "definition": "Layer for integration test.",
    }
    response = client.post("/api/layers/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_domain(client, layer_id, title=None, definition=None):
    unique_title = title if title else f"Test Domain {uuid4()}"
    unique_definition = definition if definition else "Domain for terms test."
    payload = {"title": unique_title, "definition": unique_definition, "layer_id": layer_id}
    resp = client.post("/api/domains/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_and_get_domain(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id, title="Physics", definition="The study of matter and energy.")
    get_resp = client.get(f"/api/domains/{domain_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["id"] == domain_id
    assert get_data["title"] == "Physics"
    assert get_data["definition"] == "The study of matter and energy."


def test_list_domains(client):
    layer_id = create_layer(client)
    # Create two domains
    for i in range(2):
        client.post("/api/domains/", json={"title": f"Domain {i}", "definition": f"Def {i}", "layer_id": layer_id})
    resp = client.get("/api/domains/?layer_id=" + layer_id)
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


def test_update_domain(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id, title="Chemistry")
    update = {"title": "Advanced Chemistry", "definition": "Advanced study."}
    put_resp = client.put(f"/api/domains/{domain_id}", json=update)
    assert put_resp.status_code == 200
    assert put_resp.json()["title"] == "Advanced Chemistry"


def test_delete_domain(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id, title="Biology")
    del_resp = client.delete(f"/api/domains/{domain_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True
    # Confirm deletion
    get_resp = client.get(f"/api/domains/{domain_id}")
    assert get_resp.status_code == 404


def test_find_domain(client):
    layer_id = create_layer(client)
    l1 = create_domain(client, layer_id, title="Alpha Domain", definition="Physics")
    l2 = create_domain(client, layer_id, title="Beta Domain", definition="Chemistry")

    # Search by title using the find endpoint
    resp = client.post("/api/domains/find", json={"title": "Alpha"})
    assert resp.status_code == 200
    data = resp.json()
    assert any("Alpha" in d["title"] for d in data)

    # Search by definition
    resp2 = client.post("/api/domains/find", json={"definition": "Chemistry"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert any("Chemistry" in d["definition"] for d in data2)

    # Search with a term that should return results (but with low minimum score)
    resp3 = client.post("/api/domains/find", json={"title": "Beta", "minimum_score": 0.0})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3) > 0
    record3 = data3[0]
    assert "score" in record3
    assert "distance" in record3


def test_find_domain_invalid_created_at(client):
    resp = client.post("/api/domains/find", json={"created_at": "not-a-date"})
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()


# Negative test: creating a domain with an invalid layer_id (should return 422 for invalid UUID)
def test_create_domain_invalid_layer_id(client):
    payload = {"title": "InvalidLayerDomain", "definition": "Should fail.", "layer_id": "not-a-uuid"}
    resp = client.post("/api/domains/", json=payload)
    assert resp.status_code == 422  # FastAPI returns 422 for invalid UUID

def test_domains_pagination(client):
    layer_id = create_layer(client)
    
    # Create 3 domains
    domains = []
    for i in range(3):
        domain_id = create_domain(client, layer_id, title=f"PaginationDomain{i:02d}")
        domains.append(domain_id)
    
    # Test pagination with limit=2
    resp = client.get(f"/api/domains/?layer_id={layer_id}&limit=2&sort=title")
    assert resp.status_code == 200
    data = resp.json()
    
    # Check pagination structure
    assert "data" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    
    # Check first page
    assert data["total"] == 3
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert len(data["data"]) == 2
    
    # Check that we can determine if more pages exist
    has_more_pages = (data["skip"] + data["limit"]) < data["total"]
    assert has_more_pages is True
    
    # Test second page
    resp2 = client.get(f"/api/domains/?layer_id={layer_id}&skip=2&limit=2&sort=title")
    assert resp2.status_code == 200
    data2 = resp2.json()
    
    assert data2["total"] == 3
    assert data2["skip"] == 2
    assert data2["limit"] == 2
    assert len(data2["data"]) == 1  # Only one item on last page
    
    # Check that this is the last page
    has_more_pages = (data2["skip"] + data2["limit"]) < data2["total"]
    assert has_more_pages is False
