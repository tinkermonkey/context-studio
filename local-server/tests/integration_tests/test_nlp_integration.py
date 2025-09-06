import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

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
