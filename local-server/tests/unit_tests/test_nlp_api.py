import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# All fixtures are now provided by conftest.py

def test_nlp_analysis_success(shared_client):
    payload = {"text": "Apple is a company based in Cupertino."}
    response = shared_client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "tokens" in data["data"]
    assert "entities" in data["data"]
    assert data["data"]["text"] == payload["text"]

def test_nlp_analysis_empty_text(shared_client):
    payload = {"text": ""}
    response = shared_client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "Text cannot be empty" in data["error"]

def test_nlp_analysis_text_too_long(shared_client):
    payload = {"text": "a" * 600}
    response = shared_client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "maximum length" in data["error"]

def test_nlp_analysis_malformed_request(shared_client):
    payload = {"bad_field": "test"}
    response = shared_client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "Invalid request format" in data["error"]
