"""
Route tests for GET /api/decision-models: lists instances, never credentials.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.decision.registry import build_decision_models
from adapters.web.decision_routes import router
from config import DecisionModelsConfig
from tests.fakes.fake_llm_provider import FakeLLMProvider

CONFIG = DecisionModelsConfig(
    default="primary",
    models={
        "primary": {
            "adapter": "workers_ai",
            "model": "@cf/vendor/model-large",
            "price_per_mtok_in": 0.24,
            "options": {"account_id": "acct-secret-id", "api_token": "token-secret"},
            "fallback": "llm",
        },
        "unset": {"adapter": "workers_ai", "model": "@cf/vendor/model-small"},
        "llm": {"adapter": "llm", "model": "test-model"},
    },
)


def client_for(config: DecisionModelsConfig) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.decision_models = build_decision_models(config, FakeLLMProvider())
    return TestClient(app)


def test_lists_instances_with_adapter_model_and_configured_flag():
    response = client_for(CONFIG).get("/api/decision-models")

    assert response.status_code == 200
    body = response.json()
    assert body["default"] == "primary"
    models = {m["name"]: m for m in body["models"]}
    assert models["primary"] == {
        "name": "primary",
        "adapter": "workers_ai",
        "model": "@cf/vendor/model-large",
        "configured": True,
        "is_default": True,
        "fallback": "llm",
    }
    assert models["unset"]["configured"] is False
    assert models["llm"]["adapter"] == "llm"


def test_never_returns_credentials():
    text = client_for(CONFIG).get("/api/decision-models").text
    assert "secret" not in text
    assert "api_token" not in text
    assert "account_id" not in text


def test_empty_section_lists_nothing():
    body = client_for(DecisionModelsConfig()).get("/api/decision-models").json()
    assert body == {"default": None, "models": []}
