"""
Integration tests for generic Pipeline Orchestration API routes.

Tests verify the full pipeline type enumeration, implementation discovery,
and pipeline run management via REST API.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.web.pipelines_routes import router
from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)


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
def registries():
    """Create initialized registries."""
    impl_registry = PipelineImplementationRegistry()
    config_registry = PipelineConfigurationRegistry()

    return {
        "implementation_registry": impl_registry,
        "config_registry": config_registry,
    }


@pytest.fixture
def client(pipeline_run_repo, registries):
    """Create a TestClient with pipeline routes and registries."""
    app = FastAPI()
    app.include_router(router)

    # Store in app.state for route handlers
    app.state.pipeline_run_repo = pipeline_run_repo
    app.state.implementation_registry = registries["implementation_registry"]
    app.state.config_registry = registries["config_registry"]

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
        """GET /api/pipelines/types/{type}/implementations returns empty list when none registered."""
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
        # Register a dummy implementation and configuration
        class DummyImpl:
            pass

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", DummyImpl
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model", "batch_size": 32},
        )

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
        assert body["status"] == "pending"
        assert body["created_at"] is not None

    def test_create_and_retrieve_run(self, client, registries):
        """POST creates a run, GET retrieves it with matching structure."""
        # Register implementation and configuration
        class DummyImpl:
            pass

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", DummyImpl
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Create a run
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
        class DummyImpl:
            pass

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", DummyImpl
        )
        registries["config_registry"].register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "default",
            {"model": "test-model"},
        )

        # Create a run
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
        class DummyImpl:
            pass

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", DummyImpl
        )
        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_NODE_GROUNDING, "default", DummyImpl
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
        class DummyImpl:
            pass

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", DummyImpl
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
        class DummyImpl:
            pass

        registries["implementation_registry"].register_impl(
            PipelineType.SCHEMA_EXTRACTION, "default", DummyImpl
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
            "input_summary",
            "output_summary",
            "llm_metadata",
            "status",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in body, f"Missing field: {field}"
