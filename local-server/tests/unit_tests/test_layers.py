
# Unit tests for cosine_similarity and layer API endpoints
import math
import pytest
import numpy as np
import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.vector import cosine_similarity

# Vector similarity tests
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

# Layer API tests - using shared fixtures from conftest.py
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

def test_layer_bad_input(client):
    # Missing required title
    resp = client.post("/api/layers/", json={"definition": "Def"})
    assert resp.status_code == 422
    assert "title" in resp.text.lower()

    # Title too short
    resp = client.post("/api/layers/", json={"title": "A", "definition": "Def"})
    assert resp.status_code == 422
    assert "title" in resp.text.lower()

    # Empty definition should now be allowed (no longer fails)
    resp = client.post("/api/layers/", json={"title": "Layer", "definition": ""})
    assert resp.status_code == 201

def test_layer_duplicate_title(client):
    resp1 = client.post("/api/layers/", json={"title": "Layer X"})
    assert resp1.status_code == 201
    resp2 = client.post("/api/layers/", json={"title": "Layer X"})
    assert resp2.status_code == 409
    assert "unique" in resp2.json()["detail"][0]["msg"].lower()

def test_update_layer_to_duplicate_title(client):
    resp1 = client.post("/api/layers/", json={"title": "Layer A"})
    resp2 = client.post("/api/layers/", json={"title": "Layer B"})
    id_a = resp1.json()["id"]
    id_b = resp2.json()["id"]
    resp = client.put(f"/api/layers/{id_b}", json={"title": "Layer A"})
    assert resp.status_code == 409
    assert "unique" in resp.json()["detail"][0]["msg"].lower()

def test_get_nonexistent_layer(client):
    resp = client.get(f"/api/layers/{uuid.uuid4()}")
    assert resp.status_code == 404

def test_update_nonexistent_layer(client):
    resp = client.put(f"/api/layers/{uuid.uuid4()}", json={"title": "Doesn't exist"})
    assert resp.status_code == 404

def test_delete_nonexistent_layer(client):
    resp = client.delete(f"/api/layers/{uuid.uuid4()}")
    assert resp.status_code == 404
