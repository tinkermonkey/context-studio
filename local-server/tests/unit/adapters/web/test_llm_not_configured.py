"""A call that needs a model with no LLM provider key answers 503 and names the settings to fill in."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.llm.provider_router import LLMProviderRouter
from adapters.web.llm_errors import add_llm_error_handlers
from adapters.web.pipelines_routes import _handle_domain_error
from domain.pipelines.exceptions import (
    LLM_NOT_CONFIGURED_MESSAGE,
    ExtractionFailedError,
    LLMNotConfiguredError,
)


@pytest.fixture
def client() -> TestClient:
    """An app whose only route calls a router built with no key, as the real app does."""
    app = FastAPI()
    add_llm_error_handlers(app)
    router = LLMProviderRouter()

    @app.get("/needs-a-model")
    def needs_a_model():
        return router.complete("system", "user", "claude-sonnet-5-5").content

    return TestClient(app)


class TestWebAnswer:
    def test_a_route_that_does_not_catch_it_answers_503_with_the_message(self, client):
        response = client.get("/needs-a-model")

        assert response.status_code == 503
        assert response.json() == {"detail": LLM_NOT_CONFIGURED_MESSAGE}

    def test_the_message_names_the_settings_to_fill_in(self):
        for field in ("llm.openai_api_key", "llm.anthropic_api_key", "llm.openrouter_api_key"):
            assert field in LLM_NOT_CONFIGURED_MESSAGE


class TestPipelineRoutes:
    def test_the_error_maps_to_503_with_the_message(self):
        assert _handle_domain_error(LLMNotConfiguredError()) == (503, LLM_NOT_CONFIGURED_MESSAGE)

    def test_a_failed_extraction_whose_reason_is_the_missing_key_maps_to_503(self):
        failure = ExtractionFailedError(
            "Extraction stopped at chunk 1 of 4, leaving 3 untried, because every later chunk"
            f" would fail the same way: {LLM_NOT_CONFIGURED_MESSAGE}"
        )

        assert _handle_domain_error(failure) == (503, LLM_NOT_CONFIGURED_MESSAGE)

    def test_a_failed_extraction_for_another_reason_stays_a_500_with_its_reason(self):
        failure = ExtractionFailedError("The LLM response was still incomplete after 3 attempts")

        status_code, message = _handle_domain_error(failure)

        assert status_code == 500
        assert message == "The LLM response was still incomplete after 3 attempts"
