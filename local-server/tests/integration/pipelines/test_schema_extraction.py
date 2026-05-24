"""
HTTP-level smoke tests for the schema extraction pipeline.

Exercises POST /api/pipelines/schema_extraction/run and the companion
read endpoints through the FastAPI test client with a schema-aware mock LLM.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette import status

from adapters.web.pipelines_routes import router
from domain.pipelines.ports import LLMResponse
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.bootstrap import register_schema_extraction
from tests.fixtures.schema_extraction_fixtures import get_microservices_text


class _SchemaExtractionMockLLM:
    """Schema-aware mock LLM for HTTP smoke tests."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
        timeout=None,
        seed=None,
    ) -> LLMResponse:
        if "Return a JSON object mapping each label" in system_prompt:
            content = (
                '{"Microservice": "A small, independent service.", '
                '"API Gateway": "A server that routes requests to backend services.", '
                '"Service": "An independent unit of functionality.", '
                '"Message Queue": "A mechanism for async inter-service communication."}'
            )
        elif "disambiguation" in system_prompt.lower():
            content = '{"ambiguous_terms": []}'
        elif "relationships and properties" in user_prompt.lower():
            content = (
                '{"relationships": [{"subject": "Microservice", "predicate": "subclass_of",'
                ' "object": "Service", "confidence": 0.9}], "properties": []}'
            )
        elif "extract" in system_prompt.lower() and "candidate" in system_prompt.lower():
            content = '["Microservice", "API Gateway", "Service", "Message Queue"]'
        else:
            content = '["Microservice", "API Gateway", "Service", "Message Queue"]'

        return LLMResponse(
            content=content,
            tokens_in=10,
            tokens_out=30,
            duration_ms=5,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(self, **kwargs) -> LLMResponse:
        return self.complete(**kwargs)

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return ["google/gemini-3-flash-preview"]


@pytest.fixture
def schema_client(pipeline_run_repo):
    """FastAPI test client wired with a schema-aware mock LLM."""
    impl_registry = PipelineImplementationRegistry()
    impl_registry.register_impl(PipelineType.NO_OP, "default", NoOpPipelineOrchestrator)
    register_schema_extraction(impl_registry, None)

    config_registry = PipelineConfigurationRegistry()
    register_schema_extraction(None, config_registry)

    app = FastAPI()
    app.include_router(router)
    app.state.pipeline_run_repo = pipeline_run_repo
    app.state.implementation_registry = impl_registry
    app.state.config_registry = config_registry
    app.state.llm_router = _SchemaExtractionMockLLM()

    return TestClient(app)


_MICROSERVICES_PAYLOAD = {
    "implementation_id": "default",
    "configuration_ref": "schema-extraction-default",
    "documents": [get_microservices_text()],
    "model": "google/gemini-3-flash-preview",
}


class TestSchemaExtractionHTTP:
    """HTTP smoke tests for schema extraction pipeline."""

    def test_run_schema_extraction_completes(self, schema_client):
        """POST /api/pipelines/schema_extraction/run returns 200 with a run_id."""
        response = schema_client.post(
            "/api/pipelines/schema_extraction/run",
            json=_MICROSERVICES_PAYLOAD,
        )
        assert response.status_code == status.HTTP_201_CREATED

        body = response.json()
        assert "id" in body
        assert body["id"]
        assert body["pipeline_type"] == "schema_extraction"
        assert body["status"] == "completed"

    def test_run_schema_extraction_missing_documents(self, schema_client):
        """POST with empty documents list returns 400 from domain validation."""
        response = schema_client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "implementation_id": "default",
                "configuration_ref": "schema-extraction-default",
                "documents": [],
                "model": "google/gemini-3-flash-preview",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_run_schema_extraction_whitespace_documents(self, schema_client):
        """POST with only-whitespace documents returns 400 from domain validation."""
        response = schema_client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "implementation_id": "default",
                "configuration_ref": "schema-extraction-default",
                "documents": ["   ", "\n\n"],
                "model": "google/gemini-3-flash-preview",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_schema_extraction_run(self, schema_client):
        """GET /api/pipelines/runs/{run_id} returns the run record."""
        run_response = schema_client.post(
            "/api/pipelines/schema_extraction/run",
            json=_MICROSERVICES_PAYLOAD,
        )
        assert run_response.status_code == status.HTTP_201_CREATED
        run_id = run_response.json()["id"]

        get_response = schema_client.get(f"/api/pipelines/runs/{run_id}")
        assert get_response.status_code == status.HTTP_200_OK

        body = get_response.json()
        assert body["id"] == run_id
        assert body["pipeline_type"] == "schema_extraction"
        assert body["status"] == "completed"

    def test_candidates_in_output_summary(self, schema_client):
        """Schema extraction candidates are in output_summary, not the /candidates endpoint."""
        run_response = schema_client.post(
            "/api/pipelines/schema_extraction/run",
            json=_MICROSERVICES_PAYLOAD,
        )
        assert run_response.status_code == status.HTTP_201_CREATED
        run_id = run_response.json()["id"]

        get_response = schema_client.get(f"/api/pipelines/runs/{run_id}")
        assert get_response.status_code == status.HTTP_200_OK

        output_summary = get_response.json().get("output_summary", {})
        candidates = output_summary.get("candidates", [])
        assert isinstance(candidates, list)
        assert len(candidates) > 0

        for candidate in candidates:
            assert "kind" in candidate
            assert candidate["kind"] in ("class", "property_definition")
            assert "label" in candidate
            assert "confidence" in candidate

    def test_output_summary_has_candidate_counts(self, schema_client):
        """Completed run output_summary includes candidate, property, and connection counts."""
        response = schema_client.post(
            "/api/pipelines/schema_extraction/run",
            json=_MICROSERVICES_PAYLOAD,
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()

        summary = body.get("output_summary", {})
        assert "candidate_count" in summary
        assert "property_count" in summary
        assert "connection_count" in summary
        assert summary["candidate_count"] >= 0

    def test_get_run_not_found(self, schema_client):
        """GET for a non-existent run_id returns 404."""
        response = schema_client.get("/api/pipelines/runs/nonexistent-run-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND
