import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_nlp_analysis_integration():
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
