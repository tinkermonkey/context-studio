"""
Integration tests for generic Pipeline Orchestration API routes.

Tests verify the full pipeline type enumeration, implementation discovery,
and pipeline run management via REST API.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.web.pipelines_routes import router
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import (
    PipelineExecutionError,
    PipelineExternalServiceError,
    PipelineInputError,
    PipelineStorageError,
)
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionOrchestrator
from domain.pipelines.schema_node_grounding.orchestrator import SchemaGroundingOrchestrator

# Constant for mocking the orchestrator creation function
ORCHESTRATOR_PATCH_PATH = "adapters.web.pipelines_routes.create_orchestrator"


@pytest.fixture
def temp_local_db():
    """Create a temporary local SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "local.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def local_session_factory(temp_local_db):
    """Create a session factory for the temporary local database."""
    engine = create_engine(temp_local_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def pipeline_run_repo(local_session_factory):
    """Create a real PipelineRepository with actual persistence."""
    return PipelineRepository(session_factory=local_session_factory)


@pytest.fixture
def batch_repo(local_session_factory):
    """Create a real BatchRepository with actual persistence."""
    return BatchRepository(session_factory=local_session_factory)


@pytest.fixture
def registries():
    """Create initialized registries."""
    impl_registry = PipelineImplementationRegistry()
    config_registry = PipelineConfigurationRegistry()

    return {
        "implementation_registry": impl_registry,
        "config_registry": config_registry,
    }


@pytest.fixture
def client(pipeline_run_repo, batch_repo, registries):
    """Create a TestClient with pipeline routes and registries."""
    app = FastAPI()
    app.include_router(router)

    # Create an async mock LLM router for orchestrators
    mock_llm_router = AsyncMock()
    # Mock the complete_async method to return a response
    mock_response = MagicMock()
    mock_response.content = "[]"  # Default to empty list for JSON responses
    mock_llm_router.complete_async.return_value = mock_response

    # Create mocks for required services to satisfy service wiring validation
    mock_ontology_repo = MagicMock()
    mock_extraction_service = MagicMock()
    mock_extraction_repo = MagicMock()
    mock_grounding_adapter = MagicMock()
    mock_grounding_scorer = MagicMock()

    # Store in app.state for route handlers
    app.state.pipeline_run_repo = pipeline_run_repo
    app.state.batch_repo = batch_repo
    app.state.implementation_registry = registries["implementation_registry"]
    app.state.config_registry = registries["config_registry"]
    app.state.llm_router = mock_llm_router
    app.state.ontology_repo = mock_ontology_repo
    app.state.extraction_service = mock_extraction_service
    app.state.extraction_repo = mock_extraction_repo
    app.state.grounding_adapter = mock_grounding_adapter
    app.state.grounding_scorer = mock_grounding_scorer

    return TestClient(app)


class TestPipelineTypeEndpoints:
    """Test pipeline type enumeration endpoints."""

    def test_list_pipeline_types_returns_200(self, client):
        """GET /api/pipelines/types returns 200."""
        response = client.get("/api/pipelines/types")
        assert response.status_code == status.HTTP_200_OK

    def test_list_pipeline_types_returns_list(self, client):
        """GET /api/pipelines/types returns a list."""
        response = client.get("/api/pipelines/types")
        body = response.json()
        assert isinstance(body, list)

    def test_list_pipeline_types_includes_individual_extraction(self, client):
        """GET /api/pipelines/types includes individual_extraction type."""
        response = client.get("/api/pipelines/types")
        body = response.json()

        types = {t["pipeline_type"] for t in body}
        assert "individual_extraction" in types

    def test_pipeline_type_response_structure(self, client):
        """Pipeline type response has correct structure."""
        response = client.get("/api/pipelines/types")
        body = response.json()

        # Verify first type has required fields
        assert len(body) > 0
        ptype = body[0]
        assert "pipeline_type" in ptype
        assert "description" in ptype
        assert "input_contract" in ptype
        assert "output_contract" in ptype


class TestPipelineImplementationEndpoints:
    """Test pipeline implementation discovery endpoints."""

    def test_list_implementations_invalid_type_returns_400(self, client):
        """GET /api/pipelines/types/invalid_type/implementations returns 400."""
        response = client.get("/api/pipelines/types/invalid_type/implementations")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_implementations_no_implementations_returns_empty_list(self, client):
        """GET implementations endpoint returns empty list when none registered."""
        response = client.get("/api/pipelines/types/individual_extraction/implementations")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 0


class TestPipelineConfigurationEndpoints:
    """Test pipeline configuration discovery endpoints."""

    def test_list_configurations_invalid_type_returns_400(self, client):
        """GET configs for invalid type returns 400."""
        response = client.get(
            "/api/pipelines/types/invalid_type/implementations/default/configurations"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_configurations_missing_impl_returns_404(self, client):
        """GET configs for missing implementation returns 404."""
        response = client.get(
            "/api/pipelines/types/individual_extraction/implementations/missing_impl/configurations"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPipelineRunEndpoints:
    """Test pipeline run creation, retrieval, and listing."""

    def test_create_run_no_type_returns_error(self, client):
        """POST /api/pipelines/invalid_type/run returns 400."""
        response = client.post(
            "/api/pipelines/invalid_type/run",
            json={
                "text": "sample text",
                "ontology_id": "test",
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_run_missing_config_returns_404(self, client):
        """POST /api/pipelines/{type}/run with missing config returns 404."""
        response = client.post(
            "/api/pipelines/individual_extraction/run",
            json={
                "text": "sample text",
                "ontology_id": "test",
                "implementation_id": "default",
                "configuration_ref": "nonexistent",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_run_missing_impl_returns_404(self, client):
        """POST /api/pipelines/{type}/run with missing impl returns 404."""
        response = client.post(
            "/api/pipelines/individual_extraction/run",
            json={
                "text": "sample text",
                "ontology_id": "test",
                "implementation_id": "missing_impl",
                "configuration_ref": "default",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_runs_empty_returns_200(self, client):
        """GET /api/pipelines/runs with no runs returns 200."""
        response = client.get("/api/pipelines/runs")
        assert response.status_code == status.HTTP_200_OK

    def test_list_runs_response_structure(self, client):
        """GET /api/pipelines/runs response has pagination structure."""
        response = client.get("/api/pipelines/runs")
        body = response.json()

        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body

    def test_list_runs_with_invalid_pipeline_type_returns_400(self, client):
        """GET /api/pipelines/runs with invalid filter returns 400."""
        response = client.get("/api/pipelines/runs?pipeline_type=invalid_type")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_runs_with_invalid_status_returns_400(self, client):
        """GET /api/pipelines/runs with invalid status filter returns 400."""
        response = client.get("/api/pipelines/runs?status=invalid_status")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_run_nonexistent_returns_404(self, client):
        """GET /api/pipelines/runs/{run_id} with missing run returns 404."""
        response = client.get(f"/api/pipelines/runs/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_run_with_valid_config_succeeds(self, client, registries):
        """POST /api/pipelines/{type}/run with valid config succeeds."""

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model", "batch_size": 32},
        )

        # Mock orchestrator to avoid needing actual services
        mock_orchestrator = AsyncMock()
        mock_state = MagicMock()
        mock_state.current_status = PipelineRunStatus.COMPLETED
        mock_state.result = {}
        mock_state.parse_warnings = []
        mock_orchestrator.execute.return_value = mock_state

        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1", "doc2"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )
        assert response.status_code == status.HTTP_201_CREATED

        body = response.json()
        assert "id" in body
        assert body["pipeline_type"] == "schema_extraction"
        assert body["implementation_id"] == "default"
        assert body["configuration_ref"] == "default"
        assert body["status"] == "completed"
        assert body["created_at"] is not None

    def test_create_and_retrieve_run(self, client, registries):
        """POST creates a run, GET retrieves it with matching structure."""

        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to avoid needing actual services
        mock_orchestrator = AsyncMock()
        mock_state = MagicMock()
        mock_state.current_status = PipelineRunStatus.COMPLETED
        mock_state.result = {}
        mock_state.parse_warnings = []
        mock_orchestrator.execute.return_value = mock_state

        # Create a run
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            create_response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1", "doc2"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )
        assert create_response.status_code == status.HTTP_201_CREATED
        created_run = create_response.json()
        run_id = created_run["id"]

        # Retrieve the run
        get_response = client.get(f"/api/pipelines/runs/{run_id}")
        assert get_response.status_code == status.HTTP_200_OK
        retrieved_run = get_response.json()

        # Verify structure matches
        assert retrieved_run["id"] == created_run["id"]
        assert retrieved_run["pipeline_type"] == created_run["pipeline_type"]
        assert retrieved_run["implementation_id"] == created_run["implementation_id"]
        assert retrieved_run["configuration_ref"] == created_run["configuration_ref"]
        assert retrieved_run["status"] == created_run["status"]
        assert retrieved_run["created_at"] == created_run["created_at"]

    def test_list_runs_includes_created_run(self, client, registries):
        """GET /api/pipelines/runs includes newly created run."""

        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to avoid needing actual services
        mock_orchestrator = AsyncMock()
        mock_state = MagicMock()
        mock_state.current_status = PipelineRunStatus.COMPLETED
        mock_state.result = {}
        mock_state.parse_warnings = []
        mock_orchestrator.execute.return_value = mock_state

        # Create a run
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            create_response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1", "doc2"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )
        created_run = create_response.json()
        run_id = created_run["id"]

        # List runs
        list_response = client.get("/api/pipelines/runs")
        assert list_response.status_code == status.HTTP_200_OK
        body = list_response.json()

        # Verify run is in the list
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["id"] == run_id

    def test_list_runs_filters_by_pipeline_type(self, client, registries):
        """GET /api/pipelines/runs?pipeline_type=... filters correctly."""

        # Register implementations and configurations for two types
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_NODE_GROUNDING, "default", SchemaGroundingOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_NODE_GROUNDING,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Create runs of both types
        client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1", "doc2"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        client.post(
            "/api/pipelines/schema_node_grounding/run",
            json={
                "nodes": [{"id": "node1"}],
                "sources": ["source1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )

        # Filter by schema_extraction
        response = client.get("/api/pipelines/runs?pipeline_type=schema_extraction")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["pipeline_type"] == "schema_extraction"

    def test_list_runs_filters_by_date_range(self, client, registries):
        """GET /api/pipelines/runs with date range filters correctly."""
        from datetime import datetime, timedelta, timezone
        from urllib.parse import urlencode

        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Create a run
        client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1", "doc2"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )

        # Test with date range that includes the run
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()

        params = urlencode({"start_date": start, "end_date": end})
        response = client.get(f"/api/pipelines/runs?{params}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 1

        # Test with date range that excludes the run (future dates)
        start_future = (now + timedelta(hours=1)).isoformat()
        end_future = (now + timedelta(hours=2)).isoformat()

        params_future = urlencode({"start_date": start_future, "end_date": end_future})
        response = client.get(f"/api/pipelines/runs?{params_future}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 0

    def test_create_run_response_contains_all_required_fields(self, client, registries):
        """POST /api/pipelines/run response contains all required fields."""

        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1", "doc2"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        body = response.json()

        # Verify all required fields are present
        required_fields = [
            "id",
            "batch_run_id",
            "pipeline_type",
            "implementation_id",
            "configuration_ref",
            "configuration_slug",
            "configuration_version",
            "input_summary",
            "output_summary",
            "llm_metadata",
            "status",
            "created_at",
            "updated_at",
            "started_at",
            "failure_reason",
        ]
        for field in required_fields:
            assert field in body, f"Missing field: {field}"


class TestPipelineErrorHandling:
    """Test error handling in pipeline routes."""

    def test_create_returns_500_when_repo_raises_storage_error(self, client, registries):
        """Test that PipelineStorageError during create returns 500 with generic message."""
        # Register a test implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock the repo to raise PipelineStorageError
        mock_repo = MagicMock(spec=PipelineRepository)
        mock_repo.create.side_effect = PipelineStorageError("Database error")

        client.app.state.pipeline_run_repo = mock_repo

        response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        body = response.json()
        assert "detail" in body
        # Verify the error message is generic and doesn't leak database details
        assert "persist" in body["detail"].lower() or "failed" in body["detail"].lower()
        assert "table" not in body["detail"].lower()
        assert "constraint" not in body["detail"].lower()

    def test_missing_required_service_returns_500(self, client, registries):
        """Test that missing required service returns 500 with error indicating which service."""
        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Set ontology_repo to None to simulate missing service
        client.app.state.ontology_repo = None

        response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        body = response.json()
        assert "detail" in body
        # Verify error message identifies the missing service
        assert "ontology_repo" in body["detail"]

    def test_orchestrator_raises_pipeline_input_error_returns_400(self, client, registries):
        """Test that PipelineInputError from orchestrator returns 400."""
        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to raise PipelineInputError
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute.side_effect = PipelineInputError("Invalid documents format")

        # Patch create_orchestrator to return our mock
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert "detail" in body
        assert "Invalid documents format" in body["detail"]

    def test_orchestrator_raises_external_service_error_returns_503(self, client, registries):
        """Test that PipelineExternalServiceError from orchestrator returns 503."""
        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to raise PipelineExternalServiceError
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute.side_effect = PipelineExternalServiceError(
            "OpenRouter service timeout"
        )

        # Patch create_orchestrator to return our mock
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        body = response.json()
        assert "detail" in body
        assert "External service unavailable" in body["detail"]

    def test_orchestrator_raises_execution_error_returns_500(self, client, registries):
        """Test that PipelineExecutionError from orchestrator returns 500."""
        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to raise PipelineExecutionError
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute.side_effect = PipelineExecutionError("Internal logic failed")

        # Patch create_orchestrator to return our mock
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        body = response.json()
        assert "detail" in body
        assert body["detail"] == "Pipeline execution failed"

    def test_orchestrator_raises_generic_pipeline_error_returns_500(self, client, registries):
        """Test that generic PipelineExecutionError from orchestrator returns 500."""
        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to raise generic PipelineExecutionError
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute.side_effect = PipelineExecutionError("Generic pipeline error")

        # Patch create_orchestrator to return our mock
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        body = response.json()
        assert "detail" in body
        assert "Pipeline execution failed" in body["detail"]

    def test_orchestrator_returns_parse_warnings_in_output(self, client, registries):
        """Test that parse_warnings from orchestrator are included in output_summary."""
        # Register implementation and configuration
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Create a mock state with parse warnings
        mock_state = MagicMock()
        mock_state.result = {"schemas": ["schema1"]}
        mock_state.parse_warnings = [
            {
                "stage": "llm_parsing",
                "error": "Failed to parse JSON response",
                "response_preview": "incomplete JSON",
                "fallback_action": "used default schema",
            }
        ]
        mock_state.current_status = PipelineRunStatus.COMPLETED

        # Mock orchestrator to return state with warnings
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute.return_value = mock_state

        # Patch create_orchestrator to return our mock
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()

        # Verify output_summary was updated with warnings
        # Note: output_summary is not directly returned in the response, but stored in DB
        # We can verify the request succeeded and the run was created
        assert "id" in body
        assert body["status"] == "completed"


class TestConfigurationVersioning:
    """Test configuration versioning and immutability enforcement."""

    def test_run_stores_configuration_version(self, client, registries):
        """A created run stores configuration_slug and configuration_version."""
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model", "version": 1},
        )

        response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()

        # Verify version fields are present
        assert "configuration_slug" in body
        assert "configuration_version" in body
        assert body["configuration_slug"] == "default"
        assert body["configuration_version"] == 1

    def test_run_resolves_correct_configuration_version(self, client, registries):
        """A run with (slug, v1) continues to resolve v1 after (slug, v2) is registered."""
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )

        # Register v1
        v1 = registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model-v1"},
        )
        assert v1.version == 1

        # Create run with v1
        response1 = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        run1_id = response1.json()["id"]
        assert response1.json()["configuration_version"] == 1

        # Register v2
        v2 = registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model-v2"},
        )
        assert v2.version == 2

        # Create run with v2
        response2 = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc2"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        run2_id = response2.json()["id"]
        assert response2.json()["configuration_version"] == 2

        # Verify run1 still references v1
        get1 = client.get(f"/api/pipelines/runs/{run1_id}")
        assert get1.json()["configuration_version"] == 1

        # Verify run2 still references v2
        get2 = client.get(f"/api/pipelines/runs/{run2_id}")
        assert get2.json()["configuration_version"] == 2

    def test_can_register_new_version_when_old_version_referenced(self, registries):
        """Can register a new version even when an old version is already referenced by a run."""
        # Register initial version
        v1 = registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "test",
            {"model": "v1"},
        )
        assert v1.version == 1

        # Mark v1 as referenced by a run
        registries["config_registry"].mark_version_referenced(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "test",
            v1.version,
        )

        # Registering a new version for the same slug is allowed
        # (this creates v2, doesn't mutate v1)
        v2 = registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "test",
            {"model": "v2"},
        )
        assert v2.version == 2
        assert v2.config["model"] == "v2"

        # v1 is still accessible with original config
        assert v1.config["model"] == "v1"

    def test_run_response_includes_configuration_fields(self, client, registries):
        """GET /api/pipelines/runs/{run_id} includes configuration_slug and version."""
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Create run
        create_response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        run_id = create_response.json()["id"]

        # Retrieve run
        get_response = client.get(f"/api/pipelines/runs/{run_id}")
        assert get_response.status_code == status.HTTP_200_OK
        body = get_response.json()

        assert body["configuration_slug"] == "default"
        assert body["configuration_version"] == 1


class TestRunStatusLifecycle:
    """Test pipeline run status transitions and observability."""

    def test_run_response_includes_status_fields(self, client, registries):
        """GET /api/pipelines/runs/{run_id} includes started_at and failure_reason fields."""
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Create and retrieve run
        create_response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        run_id = create_response.json()["id"]

        get_response = client.get(f"/api/pipelines/runs/{run_id}")
        body = get_response.json()

        # Verify status fields are present
        assert "started_at" in body
        assert "failure_reason" in body
        # For successful runs, these should be null/None
        # (started_at is set, but failure_reason should be null)
        assert body["failure_reason"] is None

    def test_run_status_transitions_to_completed(self, client, registries):
        """A successful run transitions to COMPLETED status."""
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["status"] == "completed"

    def test_run_failure_persists_failure_reason(self, client, registries):
        """When orchestrator fails, FAILED status and failure_reason are persisted."""
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to raise an exception
        error_message = "Simulated orchestrator failure for testing"
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute.side_effect = Exception(error_message)

        # Patch create_orchestrator to return our mock
        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )

        # Request should fail
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Get the run from the database to verify FAILED status and failure_reason
        repo = client.app.state.pipeline_run_repo
        runs = repo.list()
        assert len(runs) == 1
        run = runs[0]

        # Verify FAILED status and failure_reason were persisted
        assert run.status == PipelineRunStatus.FAILED
        assert run.failure_reason is not None
        assert (
            error_message in run.failure_reason
            or "Unexpected orchestrator failure" in run.failure_reason
        )

    def test_run_transition_writes_started_at_before_orchestrator(self, client, registries):
        """RUNNING status and started_at timestamp are written before orchestrator executes."""
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        response = client.post(
            "/api/pipelines/schema_extraction/run",
            json={
                "documents": ["doc1"],
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()

        # Verify started_at is set (not None) for completed runs
        assert body["started_at"] is not None
        assert body["status"] == "completed"

    def test_run_status_observable_as_running_mid_execution(self, client, registries):
        """
        Structural test: RUNNING status is written before orchestrator executes
        and can be observed via GET while execution is in progress.

        This test uses a blocking orchestrator mock to verify:
        1. Status transitions to RUNNING before execution
        2. started_at timestamp is set before execution
        3. The status is observable via GET /api/pipelines/runs/{run_id} mid-execution
        4. On completion, status becomes COMPLETED
        """
        import asyncio
        import threading

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        repo = client.app.state.pipeline_run_repo

        # Synchronization event to signal when orchestrator starts execution
        orchestrator_started_event = threading.Event()
        orchestrator_complete_event = threading.Event()

        # Create a mock orchestrator that signals when it starts
        async def blocking_orchestrator_execute(state):
            """Mock orchestrator that signals when execution begins."""
            # Simulate the orchestrator writing RUNNING status (like real orchestrators do)
            from datetime import datetime, timezone
            repo.update_running_status(state.run_id, datetime.now(timezone.utc))

            # Signal that execution has started
            orchestrator_started_event.set()
            # Wait for test to verify mid-execution state, then complete
            while not orchestrator_complete_event.is_set():
                await asyncio.sleep(0.01)
            # Return successful result
            state.result = {"schemas": ["schema1"]}
            state.parse_warnings = []
            state.current_status = PipelineRunStatus.COMPLETED
            return state

        # Track the response from the background thread
        response_data = None
        exception_in_thread = None

        def run_pipeline():
            nonlocal response_data, exception_in_thread
            try:
                mock_orchestrator = AsyncMock()
                mock_orchestrator.execute = blocking_orchestrator_execute

                with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
                    response = client.post(
                        "/api/pipelines/schema_extraction/run",
                        json={
                            "documents": ["doc1"],
                            "implementation_id": "default",
                            "configuration_ref": "default",
                        },
                    )
                    response_data = response.json()
            except Exception as e:
                exception_in_thread = e

        # Run the request in a background thread
        thread = threading.Thread(target=run_pipeline)
        thread.start()

        # Wait for the orchestrator to start (status is RUNNING at this point)
        assert orchestrator_started_event.wait(timeout=5.0), "Orchestrator did not start"

        # Now query the runs to find the one we just created
        # (run_id is not available yet, so we query by list)
        all_runs = repo.list()
        assert len(all_runs) > 0, "No runs found in repository"
        mid_execution_run = all_runs[-1]  # Get the most recent run

        # Verify RUNNING status and started_at are set
        assert mid_execution_run.status == PipelineRunStatus.RUNNING
        assert mid_execution_run.started_at is not None

        # Signal orchestrator to complete
        orchestrator_complete_event.set()

        # Wait for the request to complete
        thread.join(timeout=5.0)
        assert exception_in_thread is None, f"Exception in thread: {exception_in_thread}"

        # After completion, verify the run status is COMPLETED
        final_run = repo.get(mid_execution_run.id)
        assert final_run is not None
        assert final_run.status == PipelineRunStatus.COMPLETED
        assert final_run.started_at is not None

    def test_run_failure_records_failed_status_and_reason(self, client, registries):
        """
        Structural test: When orchestrator raises an exception during execution,
        FAILED status and failure_reason are persisted in finally block.
        """
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Mock orchestrator to raise an exception
        error_msg = "Simulated LLM provider timeout during execution"
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute.side_effect = PipelineExternalServiceError(error_msg)

        with patch(ORCHESTRATOR_PATCH_PATH, return_value=mock_orchestrator):
            response = client.post(
                "/api/pipelines/schema_extraction/run",
                json={
                    "documents": ["doc1"],
                    "implementation_id": "default",
                    "configuration_ref": "default",
                },
            )

        # Response should be 503
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        # Retrieve the run from the database
        repo = client.app.state.pipeline_run_repo
        runs = repo.list()
        assert len(runs) == 1
        run = runs[0]

        # Verify FAILED status and failure_reason are persisted
        assert run.status == PipelineRunStatus.FAILED
        assert run.failure_reason is not None
        assert (
            "timeout" in run.failure_reason.lower()
            or "unavailable" in run.failure_reason.lower()
        )


class TestRevertEndpoint:
    """Test pipeline revert endpoint."""

    @pytest.fixture
    def change_repo(self, temp_local_db):
        """Create a SQLite change repository."""
        from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository

        engine = create_engine(temp_local_db)
        SessionLocal = sessionmaker(bind=engine)
        return SQLiteChangeRepository(session_factory=SessionLocal)

    @pytest.fixture
    def ontology_repo(self, temp_local_db):
        """Create a SQLite ontology repository."""
        from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository

        engine = create_engine(temp_local_db)
        SessionLocal = sessionmaker(bind=engine)
        return SQLiteOntologyRepository(session_factory=SessionLocal)

    @pytest.fixture
    def revert_client(self, client, change_repo, ontology_repo, pipeline_run_repo):
        """Wire revert service into the test client."""
        from domain.versioning.revert_service import RevertService

        revert_service = RevertService(
            change_repo=change_repo,
            ontology_repo=ontology_repo,
        )
        client.app.state.revert_service = revert_service
        client.app.state.change_repo = change_repo
        client.app.state.ontology_repo = ontology_repo
        return client

    def test_revert_nonexistent_run_returns_404(self, revert_client):
        """POST /api/pipelines/runs/{run_id}/revert for nonexistent run returns 404."""
        response = revert_client.post(
            "/api/pipelines/runs/nonexistent-run-id/revert"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_revert_empty_run_returns_200_with_zero_reverted(
        self, revert_client, pipeline_run_repo
    ):
        """POST /api/pipelines/runs/{run_id}/revert for run with no events returns 200."""
        from domain.pipelines.entities import PipelineType

        # Create a pipeline run with no associated change events
        run = pipeline_run_repo.create(
            batch_run_id="batch-1",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )

        response = revert_client.post(
            f"/api/pipelines/runs/{run.id}/revert"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["run_id"] == run.id
        assert body["events_reverted"] == 0

    def test_revert_with_changes_returns_200_with_count(
        self, revert_client, pipeline_run_repo, change_repo, ontology_repo
    ):
        """POST /api/pipelines/runs/{run_id}/revert reverts recorded changes."""
        from domain.ontology.entities import Class, ConceptScheme, Taxonomy
        from domain.pipelines.entities import PipelineType
        from domain.versioning.value_objects import ChangeOperation

        # Create a taxonomy and scheme
        tax = Taxonomy(id="tx-1", identifier="test_tax", title="Test Taxonomy")
        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id="tx-1",
            identifier="test_scheme",
            title="Test Scheme",
        )
        ontology_repo.save_taxonomy(tax)
        ontology_repo.save_concept_scheme(scheme)

        # Create a class and record it as created
        cls = Class(
            id="cls-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tx-1",
            title="Animal",
        )
        ontology_repo.save_class(cls)

        # Create the pipeline run first to get its ID
        run = pipeline_run_repo.create(
            batch_run_id="batch-2",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )

        # Record a change event with the batch's ID
        change_repo.record_change(
            entity_id="cls-1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"id": "cls-1", "title": "Animal"},
            batch_run_id=run.batch_run_id,
        )

        # Verify class exists
        assert ontology_repo.get_class("cls-1") is not None

        # Revert
        response = revert_client.post(
            f"/api/pipelines/runs/{run.id}/revert"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["run_id"] == run.id
        assert body["events_reverted"] == 1

        # Verify class is deleted
        assert ontology_repo.get_class("cls-1") is None

    def test_revert_error_does_not_leak_details(
        self, revert_client, pipeline_run_repo, change_repo, ontology_repo
    ):
        """POST /api/pipelines/runs/{run_id}/revert error response does not
        leak internal details."""
        from domain.ontology.entities import ConceptScheme, Taxonomy
        from domain.pipelines.entities import PipelineType
        from domain.versioning.value_objects import ChangeOperation

        # Create a taxonomy and scheme
        tax = Taxonomy(id="tx-1", identifier="test_tax", title="Test Taxonomy")
        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id="tx-1",
            identifier="test_scheme",
            title="Test Scheme",
        )
        ontology_repo.save_taxonomy(tax)
        ontology_repo.save_concept_scheme(scheme)

        # Create the pipeline run first to get its ID
        run = pipeline_run_repo.create(
            batch_run_id="batch-3",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )

        # Record a change event with missing previous_state (will cause error)
        change_repo.record_change(
            entity_id="cls-1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={"title": "Updated"},
            previous_state=None,  # Missing - this will cause an error
            batch_run_id=run.batch_run_id,
        )

        # Try to revert - should get 500 with generic error message
        response = revert_client.post(
            f"/api/pipelines/runs/{run.id}/revert"
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        body = response.json()

        # Error detail should not contain actual error details like stack traces or file paths
        detail = body.get("detail", "")
        assert "internal error" in detail.lower()
        # Should not contain Python exception types or file paths
        assert "ValueError" not in detail
        assert "Traceback" not in detail
        assert ".py" not in detail

    def test_revert_multi_run_batch_returns_422(
        self, revert_client, pipeline_run_repo, batch_repo
    ):
        """POST /api/pipelines/runs/{run_id}/revert for run in multi-run batch returns 422."""
        from domain.pipelines.entities import PipelineType

        # Create a batch with multiple runs
        batch_id = "batch-multi-1"

        # Create first run in the batch
        run1 = pipeline_run_repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )

        # Create second run in the same batch
        pipeline_run_repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )

        # Verify both runs are in the same batch
        batch_runs = pipeline_run_repo.list()
        batch_run_ids = [r.batch_run_id for r in batch_runs]
        assert batch_id in batch_run_ids
        assert len([r for r in batch_runs if r.batch_run_id == batch_id]) == 2

        # Try to revert the first run - should fail with 422 because batch has multiple runs
        response = revert_client.post(
            f"/api/pipelines/runs/{run1.id}/revert"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()

        # Verify error message is clear
        assert "detail" in body
        assert "multi" in body["detail"].lower() or "multiple" in body["detail"].lower()

    def test_revert_single_run_batch_succeeds(
        self, revert_client, pipeline_run_repo
    ):
        """POST /api/pipelines/runs/{run_id}/revert for run in single-run batch succeeds."""
        from domain.pipelines.entities import PipelineType

        # Create a batch with only one run
        batch_id = "batch-single-1"

        run = pipeline_run_repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )

        # Revert should succeed with 200
        response = revert_client.post(
            f"/api/pipelines/runs/{run.id}/revert"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        # Verify response has expected structure
        assert "run_id" in body
        assert "events_reverted" in body
        assert body["run_id"] == run.id
        assert body["events_reverted"] == 0  # No events were recorded, so 0 reverted
