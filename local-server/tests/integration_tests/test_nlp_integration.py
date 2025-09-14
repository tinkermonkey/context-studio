import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Integration tests use shared session-scoped fixtures for performance:
# - shared_client (session-scoped test client, reused across all tests)
# - client (function-scoped, delegates to shared_client for backwards compatibility)
# - db_session (function-scoped, provides clean database state per test)


def test_nlp_analysis_integration(client):
    payload = {"text": "Barack Obama was the 44th President of the United States."}
    response = client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "tokens" in data["data"]
    assert "entities" in data["data"]
    assert data["data"]["text"] == payload["text"]
    # Check at least one entity is detected
    assert len(data["data"]["entities"]) > 0


def test_nlp_analysis_success(client):
    """Test successful NLP analysis with proper response structure."""
    payload = {"text": "Apple is a company based in Cupertino."}
    response = client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "tokens" in data["data"]
    assert "entities" in data["data"]
    assert data["data"]["text"] == payload["text"]


def test_nlp_analysis_empty_text(client):
    """Test NLP analysis with empty text should return error."""
    payload = {"text": ""}
    response = client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "Text cannot be empty" in data["error"]


def test_nlp_analysis_text_too_long(client):
    """Test NLP analysis with text exceeding maximum length."""
    payload = {"text": "a" * 600}
    response = client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "maximum length" in data["error"]


def test_nlp_analysis_malformed_request(client):
    """Test NLP analysis with malformed request should return validation error."""
    payload = {"bad_field": "test"}
    response = client.post("/api/nlp_analysis", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "Invalid request format" in data["error"]
