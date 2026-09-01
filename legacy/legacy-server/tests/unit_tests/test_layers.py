# Unit tests for cosine_similarity and layer API endpoints
import math
import os
import sys
import uuid

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
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
    assert math.isclose(
        cosine_similarity(arr.tolist(), np.frombuffer(b, dtype=np.float32).tolist()),
        1.0,
        abs_tol=1e-6,
    )


# Layer API tests - using unified structure_nodes API
def test_create_get_update_delete_layer(shared_client):
    # Create layer (using structure_nodes API)
    layer_data = {
        "node_type": "layer",
        "title": "Layer 1",
        "definition": "Def 1",
        "parent_node_id": None,
    }
    resp = shared_client.post("/api/structure_nodes/", json=layer_data)
    assert resp.status_code == 201, resp.text
    layer = resp.json()
    layer_id = layer["id"]

    # Get
    resp = shared_client.get(f"/api/structure_nodes/{layer_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Layer 1"

    # Update
    resp = shared_client.put(
        f"/api/structure_nodes/{layer_id}", json={"title": "Layer 1 Updated"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Layer 1 Updated"

    # Delete
    resp = shared_client.delete(f"/api/structure_nodes/{layer_id}")
    assert resp.status_code == 204

    # Get after delete
    resp = shared_client.get(f"/api/structure_nodes/{layer_id}")
    assert resp.status_code == 404


def test_layer_bad_input(shared_client):
    # Missing required title
    resp = shared_client.post(
        "/api/structure_nodes/", json={"node_type": "layer", "definition": "Def"}
    )
    assert resp.status_code == 422
    assert "title" in resp.text.lower()

    # Title too short
    resp = shared_client.post(
        "/api/structure_nodes/",
        json={"node_type": "layer", "title": "A", "definition": "Def"},
    )
    assert resp.status_code == 422
    assert "title" in resp.text.lower()

    # Empty definition should now be allowed (no longer fails)
    resp = shared_client.post(
        "/api/structure_nodes/",
        json={"node_type": "layer", "title": "Layer", "definition": ""},
    )
    assert resp.status_code == 201


def test_layer_duplicate_title(shared_client):
    resp1 = shared_client.post(
        "/api/structure_nodes/", json={"node_type": "layer", "title": "Layer X"}
    )
    assert resp1.status_code == 201
    resp2 = shared_client.post(
        "/api/structure_nodes/", json={"node_type": "layer", "title": "Layer X"}
    )
    assert resp2.status_code == 409
    assert "unique" in resp2.json()["detail"][0]["msg"].lower()


def test_update_layer_to_duplicate_title(shared_client):
    resp1 = shared_client.post(
        "/api/structure_nodes/", json={"node_type": "layer", "title": "Layer A"}
    )
    resp2 = shared_client.post(
        "/api/structure_nodes/", json={"node_type": "layer", "title": "Layer B"}
    )
    resp1.json()["id"]
    id_b = resp2.json()["id"]
    resp = shared_client.put(f"/api/structure_nodes/{id_b}", json={"title": "Layer A"})
    assert resp.status_code == 409
    assert "unique" in resp.json()["detail"][0]["msg"].lower()


def test_get_nonexistent_layer(shared_client):
    resp = shared_client.get(f"/api/structure_nodes/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_update_nonexistent_layer(shared_client):
    resp = shared_client.put(
        f"/api/structure_nodes/{uuid.uuid4()}", json={"title": "Doesn't exist"}
    )
    assert resp.status_code == 404


def test_delete_nonexistent_layer(shared_client):
    resp = shared_client.delete(f"/api/structure_nodes/{uuid.uuid4()}")
    assert resp.status_code == 404
