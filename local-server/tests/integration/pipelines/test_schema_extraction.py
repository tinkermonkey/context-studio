"""
HTTP-level smoke tests for the schema extraction pipeline.

Exercises POST /api/pipelines/schema_extraction/run and the companion
read endpoints through the FastAPI test client with a schema-aware mock LLM.
"""

import asyncio
import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette import status

from adapters.web.pipelines_routes import router
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator
from domain.pipelines.ports import LLMResponse
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.bootstrap import register_schema_extraction
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)
from tests.fixtures.schema_extraction_fixtures import get_microservices_text
from tests.integration.fixtures.pipelines.harness import (
    run_pipeline_against_fixture,
)


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
        elif (
            "extract" in system_prompt.lower() and "candidate" in system_prompt.lower()
        ):
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

    async def complete_async(
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
        return self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return ["google/gemini-3-flash-preview"]


@pytest.fixture
def schema_client(pipeline_run_repo, batch_repo):
    """FastAPI test client wired with a schema-aware mock LLM."""
    impl_registry = PipelineImplementationRegistry()
    impl_registry.register_impl(PipelineType.NO_OP, "default", NoOpPipelineOrchestrator)
    register_schema_extraction(impl_registry, None)

    config_registry = PipelineConfigurationRegistry()
    register_schema_extraction(None, config_registry)

    # Create mocks for required services to satisfy service wiring validation
    mock_ontology_repo = MagicMock()
    mock_extraction_service = MagicMock()
    mock_extraction_repo = MagicMock()
    mock_grounding_adapter = MagicMock()
    mock_grounding_scorer = MagicMock()

    app = FastAPI()
    app.include_router(router)
    app.state.pipeline_run_repo = pipeline_run_repo
    app.state.batch_repo = batch_repo
    app.state.implementation_registry = impl_registry
    app.state.config_registry = config_registry
    app.state.llm_router = _SchemaExtractionMockLLM()
    app.state.ontology_repo = mock_ontology_repo
    app.state.extraction_service = mock_extraction_service
    app.state.extraction_repo = mock_extraction_repo
    app.state.grounding_adapter = mock_grounding_adapter
    app.state.grounding_scorer = mock_grounding_scorer

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


# ---------------------------------------------------------------------------- #
# Canon-driven assertions                                                      #
# ---------------------------------------------------------------------------- #
#
# The HTTP tests above use synthetic microservices text. The tests below feed a
# real canon paper (Fowler microservices article) through the orchestrator
# directly, with a canon-aware mock LLM, and assert that the produced candidates
# include canon-aligned concept terms.


_CANON_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "datafiles"
    / "canon"
    / "software_architecture"
)


def _load_canon_paper(name: str) -> dict:
    return json.loads((_CANON_DIR / f"paper_{name}.json").read_text(encoding="utf-8"))


class _CanonSchemaLLM:
    """
    Mock LLM that returns canon-aware responses for the 7-stage schema-extraction
    flow. Responses are derived from the active canon paper's expected_entities
    and expected_relationships so the orchestrator produces canon-aligned
    candidates and connections.
    """

    def __init__(self, paper: dict) -> None:
        self._paper = paper
        self._candidate_labels = [
            e["label"] for e in paper.get("expected_entities", [])
        ]
        self._definitions = {
            e["label"]: e.get("context", f"Canon concept: {e['label']}")
            for e in paper.get("expected_entities", [])
        }
        self._relationships = paper.get("expected_relationships", [])
        self.call_count = 0

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
        self.call_count += 1
        if "Return a JSON object mapping each label" in system_prompt:
            content = json.dumps(self._definitions)
        elif "disambiguation" in system_prompt.lower():
            content = '{"ambiguous_terms": []}'
        elif "relationships and properties" in user_prompt.lower():
            content = json.dumps(
                {
                    "relationships": [
                        {
                            "subject": rel["subject"].replace("_", " "),
                            "predicate": rel["predicate"],
                            "object": rel["object"].replace("_", " "),
                            "confidence": 0.85,
                        }
                        for rel in self._relationships[:5]
                    ],
                    "properties": [],
                }
            )
        else:
            # Candidate identification — return canon entity labels.
            content = json.dumps(self._candidate_labels)

        return LLMResponse(
            content=content,
            tokens_in=10,
            tokens_out=30,
            duration_ms=5,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(
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
        return self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return ["google/gemini-3-flash-preview"]


def _run_orchestrator(paper: dict) -> SchemaExtractionState:
    """Drive the SchemaExtractionOrchestrator end-to-end with a canon paper."""
    fake_llm = _CanonSchemaLLM(paper)
    orchestrator = SchemaExtractionOrchestrator(llm_provider=fake_llm)

    state = SchemaExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [paper["source_text"]],
            "model": "google/gemini-3-flash-preview",
        },
    )
    result = asyncio.run(orchestrator.execute(state))
    return cast(SchemaExtractionState, result)


class TestSchemaExtractionAgainstCanon:
    """Schema extraction against a real canon paper, asserting canon alignment."""

    def test_canon_microservices_paper_produces_candidates(self):
        paper = _load_canon_paper("fowler_microservices_article")
        result_state = _run_orchestrator(paper)

        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert result_state.result is not None
        candidate_count = result_state.result.get("candidate_count", 0)
        assert (
            candidate_count > 0
        ), f"Expected ≥1 candidate; got {candidate_count}. result={result_state.result}"

    def test_canon_candidates_include_microservice_terminology(self):
        """At least one produced candidate must match a canon expected entity label."""
        paper = _load_canon_paper("fowler_microservices_article")
        result_state = _run_orchestrator(paper)

        candidates = result_state.result.get("candidates", [])
        produced_labels = {c.get("label", "").lower() for c in candidates}
        expected_labels = {
            e["label"].lower() for e in paper.get("expected_entities", [])
        }
        overlap = produced_labels & expected_labels
        assert overlap, (
            f"No produced candidate aligned with canon expected_entities. "
            f"produced={sorted(produced_labels)} expected={sorted(expected_labels)}"
        )

    def test_candidates_have_kind_and_confidence(self):
        """Every produced candidate must declare kind ∈ {class, property_definition}."""
        paper = _load_canon_paper("fowler_microservices_article")
        result_state = _run_orchestrator(paper)

        candidates = result_state.result.get("candidates", [])
        assert candidates, "Expected at least one candidate"
        for cand in candidates:
            assert cand.get("kind") in (
                "class",
                "property_definition",
            ), f"Unexpected kind {cand.get('kind')!r} in {cand}"
            confidence = cand.get("confidence")
            assert confidence is None or 0.0 <= confidence <= 1.0

    def test_connections_emitted_for_paper_with_relationships(self):
        """Fowler microservices canon has expected_relationships → expect ≥1 connection."""
        paper = _load_canon_paper("fowler_microservices_article")
        result_state = _run_orchestrator(paper)

        connection_count = result_state.result.get("connection_count", 0)
        assert connection_count >= 1, (
            f"Expected ≥1 connection from a paper with "
            f"{len(paper.get('expected_relationships', []))} expected_relationships; "
            f"got {connection_count}. result={result_state.result}"
        )

    def test_canon_crdt_paper_also_produces_candidates(self):
        """Same orchestrator path on a structurally different canon paper."""
        paper = _load_canon_paper("shapiro_crdt_survey")
        result_state = _run_orchestrator(paper)
        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert (result_state.result or {}).get("candidate_count", 0) > 0


class TestSchemaExtractionViaHarness:
    """Harness-based integration tests using shared fixture infrastructure."""

    @pytest.mark.asyncio
    async def test_harness_loads_and_runs_basic_extraction(self):
        """Harness successfully loads fixture and runs schema extraction orchestrator."""
        llm_provider = _SchemaExtractionMockLLM()
        orchestrator = SchemaExtractionOrchestrator(llm_provider)

        actual, expected = await run_pipeline_against_fixture(
            orchestrator,
            "schema_extraction",
            "basic",
        )

        # Verify outputs were loaded and execution succeeded
        assert actual is not None
        assert expected is not None
        assert actual["status"] == "completed"
        assert "result" in actual
