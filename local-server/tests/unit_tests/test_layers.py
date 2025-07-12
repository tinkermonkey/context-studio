

# Unit tests for cosine_similarity
import math
import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.vector import cosine_similarity

def test_cosine_similarity_identical_vectors():
    v1 = [1.0, 2.0, 3.0]
    v2 = [1.0, 2.0, 3.0]
    assert math.isclose(cosine_similarity(v1, v2), 1.0, abs_tol=1e-6)

def test_cosine_similarity_orthogonal_vectors():
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    assert math.isclose(cosine_similarity(v1, v2), 0.0, abs_tol=1e-6)

def test_cosine_similarity_opposite_vectors():
    v1 = [1.0, 0.0]
    v2 = [-1.0, 0.0]
    assert math.isclose(cosine_similarity(v1, v2), -1.0, abs_tol=1e-6)

def test_cosine_similarity_with_zero_vector():
    v1 = [0.0, 0.0, 0.0]
    v2 = [1.0, 2.0, 3.0]
    assert cosine_similarity(v1, v2) == 0.0
    assert cosine_similarity(v2, v1) == 0.0

def test_cosine_similarity_with_none():
    v1 = None
    v2 = [1.0, 2.0, 3.0]
    assert cosine_similarity(v1, v2) == 0.0
    assert cosine_similarity(v2, v1) == 0.0

def test_cosine_similarity_bytes_input():
    arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    b = arr.tobytes()
    # Should decode bytes to float array and compute similarity
    assert math.isclose(cosine_similarity(arr.tolist(), np.frombuffer(b, dtype=np.float32).tolist()), 1.0, abs_tol=1e-6)

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
        init_db(engine=engine, skip_vec=True)
        app = create_app(engine=engine, session_local=session_local, skip_vec=True)
        yield app
    finally:
        os.unlink(tf.name)

@pytest.fixture(scope="function")
def client(test_app):
    with TestClient(test_app) as c:
        yield c

def test_create_get_update_delete_layer(client):
    # Create
    resp = client.post("/api/layers/", json={"title": "Layer 1", "definition": "Def 1"})
    assert resp.status_code == 201, resp.text
    layer = resp.json()
    layer_id = layer["id"]
    # Get
    resp = client.get(f"/api/layers/{layer_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Layer 1"
    # Update
    resp = client.put(f"/api/layers/{layer_id}", json={"title": "Layer 1 Updated"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Layer 1 Updated"
    # Delete
    resp = client.delete(f"/api/layers/{layer_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Get after delete
    resp = client.get(f"/api/layers/{layer_id}")
    assert resp.status_code == 404

def test_layer_duplicate_title(client):
    resp1 = client.post("/api/layers/", json={"title": "Layer X"})
    assert resp1.status_code == 201
    resp2 = client.post("/api/layers/", json={"title": "Layer X"})
    assert resp2.status_code == 400
    assert "unique" in resp2.json()["detail"].lower()

def test_update_layer_to_duplicate_title(client):
    resp1 = client.post("/api/layers/", json={"title": "Layer A"})
    resp2 = client.post("/api/layers/", json={"title": "Layer B"})
    id_a = resp1.json()["id"]
    id_b = resp2.json()["id"]
    resp = client.put(f"/api/layers/{id_b}", json={"title": "Layer A"})
    assert resp.status_code == 400
    assert "unique" in resp.json()["detail"].lower()

def test_get_nonexistent_layer(client):
    resp = client.get(f"/api/layers/{uuid.uuid4()}")
    assert resp.status_code == 404

def test_update_nonexistent_layer(client):
    resp = client.put(f"/api/layers/{uuid.uuid4()}", json={"title": "Doesn't exist"})
    assert resp.status_code == 404

def test_delete_nonexistent_layer(client):
    resp = client.delete(f"/api/layers/{uuid.uuid4()}")
    assert resp.status_code == 404
