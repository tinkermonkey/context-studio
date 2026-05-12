"""
Integration tests for LLM Pipeline Management API routes.

Tests verify the full pipeline configuration and execution workflow with:
- Real SQLite database (operations.db)
- PipelineRepository backed by actual persistence
- LLM provider for execution
- HTTP routes via TestClient
- End-to-end request/response validation

These tests exercise the complete stack: routes → domain service → adapters → database.
"""

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

import pytest
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from domain.pipeline.services import PipelineService
from domain.pipeline.exceptions import LayerExecutionError
from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.pipeline_repo import SQLitePipelineRepository
from adapters.events.in_process import InProcessEventPublisher
from adapters.web.pipeline_routes import router
from tests.fakes.fake_llm_provider import FakeLLMProvider


@pytest.fixture
def temp_ops_db():
    """Create a temporary operations SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "operations.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        OperationsBase.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def operations_session_factory(temp_ops_db):
    """Create a session factory for the temporary operations database."""
    engine = create_engine(temp_ops_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def pipeline_repository(operations_session_factory):
    """Create a real SQLitePipelineRepository with actual persistence."""
    return SQLitePipelineRepository(session_factory=operations_session_factory)


@pytest.fixture
def event_publisher():
    """Create event publisher."""
    return InProcessEventPublisher()


@pytest.fixture
def pipeline_service(pipeline_repository, event_publisher):
    """Create PipelineService with fake LLM adapter."""
    service = PipelineService(
        pipeline_repo=pipeline_repository,
        flavor_repo=pipeline_repository,
        llm=FakeLLMProvider(response_content='{"result": "test output"}'),
        event_publisher=event_publisher,
    )
    return service


@pytest.fixture
def client(pipeline_service):
    """Create a TestClient with real pipeline service."""
    app = FastAPI()
    app.include_router(router)
    app.state.pipeline_service = pipeline_service

    return TestClient(app)


class TestPipelineRoutes:
    """Integration tests for pipeline routes."""

    def test_create_pipeline_configuration_returns_201(self, client):
        """POST /api/pipelines returns 201 with valid payload."""
        response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline",
                "title": "Test Pipeline",
                "provider": "openai",
                "model": "gpt-4",
                "config": {"temperature": 0.0, "max_tokens": 2000},
                "system_prompt": "You are a helpful assistant.",
                "user_prompt": "Process: {text}",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_pipeline_configuration_response_structure(self, client):
        """POST /api/pipelines response has correct structure."""
        response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline",
                "title": "Test Pipeline",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "You are helpful.",
                "user_prompt": "Process: {text}",
            },
        )
        body = response.json()

        # Verify required fields
        assert "id" in body
        assert "pipeline" in body
        assert "title" in body
        assert "provider" in body
        assert "model" in body
        assert "config" in body
        assert "system_prompt" in body
        assert "user_prompt" in body
        assert "version" in body
        assert "enabled" in body
        assert "created_at" in body
        assert "last_updated" in body

        # Verify types
        assert isinstance(body["id"], str)
        assert isinstance(body["version"], int)
        assert isinstance(body["enabled"], bool)
        assert body["enabled"] is True

    def test_create_pipeline_configuration_generates_id(self, client):
        """POST /api/pipelines generates server-side ID."""
        response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline",
                "title": "Test Pipeline",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "You are helpful.",
                "user_prompt": "Process: {text}",
            },
        )
        body = response.json()

        # ID should be a non-empty string
        assert body["id"]
        assert len(body["id"]) > 0

    def test_list_pipelines_returns_200(self, client):
        """GET /api/pipelines returns 200."""
        response = client.get("/api/pipelines")
        assert response.status_code == status.HTTP_200_OK

    def test_list_pipelines_response_is_list(self, client):
        """GET /api/pipelines response is a list."""
        response = client.get("/api/pipelines")
        body = response.json()
        assert isinstance(body, list)

    def test_list_pipelines_includes_created(self, client):
        """GET /api/pipelines includes previously created pipelines."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_1",
                "title": "Test Pipeline 1",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "You are helpful.",
                "user_prompt": "Process: {text}",
            },
        )
        created_id = create_response.json()["id"]

        # List pipelines
        list_response = client.get("/api/pipelines")
        body = list_response.json()

        # Created pipeline should be in the list
        ids = [p["id"] for p in body]
        assert created_id in ids

    def test_get_pipeline_returns_200(self, client):
        """GET /api/pipelines/{id} returns 200 for existing pipeline."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_2",
                "title": "Test Pipeline 2",
                "provider": "anthropic",
                "model": "claude-opus",
                "config": {},
                "system_prompt": "You are helpful.",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Get the pipeline
        response = client.get(f"/api/pipelines/{pipeline_id}")
        assert response.status_code == status.HTTP_200_OK

    def test_get_pipeline_returns_correct_data(self, client):
        """GET /api/pipelines/{id} returns correct pipeline data."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_3",
                "title": "Test Pipeline 3",
                "provider": "openai",
                "model": "gpt-4",
                "config": {"temperature": 0.5},
                "system_prompt": "System message",
                "user_prompt": "User: {text}",
            },
        )
        created_data = create_response.json()
        pipeline_id = created_data["id"]

        # Get the pipeline
        response = client.get(f"/api/pipelines/{pipeline_id}")
        body = response.json()

        # Data should match
        assert body["id"] == pipeline_id
        assert body["pipeline"] == "test_pipeline_3"
        assert body["title"] == "Test Pipeline 3"
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4"

    def test_get_pipeline_nonexistent_returns_404(self, client):
        """GET /api/pipelines/{id} returns 404 for nonexistent pipeline."""
        response = client.get(f"/api/pipelines/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_pipeline_returns_200(self, client):
        """PUT /api/pipelines/{id} returns 200 for existing pipeline."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_4",
                "title": "Test Pipeline 4",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Original system prompt",
                "user_prompt": "Original user prompt",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Update the pipeline
        response = client.put(
            f"/api/pipelines/{pipeline_id}",
            json={
                "title": "Updated Pipeline 4",
                "system_prompt": "Updated system prompt",
            },
        )
        assert response.status_code == status.HTTP_200_OK

    def test_update_pipeline_applies_changes(self, client):
        """PUT /api/pipelines/{id} applies updates correctly."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_5",
                "title": "Test Pipeline 5",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Original",
                "user_prompt": "Original",
                "enabled": True,
            },
        )
        pipeline_id = create_response.json()["id"]

        # Update the pipeline
        client.put(
            f"/api/pipelines/{pipeline_id}",
            json={"title": "New Title", "enabled": False},
        )

        # Get the pipeline to verify update
        response = client.get(f"/api/pipelines/{pipeline_id}")
        body = response.json()
        assert body["title"] == "New Title"
        assert body["enabled"] is False

    def test_update_pipeline_increments_version(self, client):
        """PUT /api/pipelines/{id} increments version number."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_6",
                "title": "Test Pipeline 6",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Test",
            },
        )
        original_version = create_response.json()["version"]
        pipeline_id = create_response.json()["id"]

        # Update the pipeline
        response = client.put(
            f"/api/pipelines/{pipeline_id}", json={"title": "New Title"}
        )
        new_version = response.json()["version"]

        # Version should increment
        assert new_version == original_version + 1

    def test_delete_pipeline_returns_204(self, client):
        """DELETE /api/pipelines/{id} returns 204 for existing pipeline."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_7",
                "title": "Test Pipeline 7",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Test",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Delete the pipeline
        response = client.delete(f"/api/pipelines/{pipeline_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_pipeline_removes_it(self, client):
        """DELETE /api/pipelines/{id} removes the pipeline."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_8",
                "title": "Test Pipeline 8",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Test",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Delete the pipeline
        client.delete(f"/api/pipelines/{pipeline_id}")

        # Subsequent GET should return 404
        response = client.get(f"/api/pipelines/{pipeline_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_pipeline_nonexistent_returns_404(self, client):
        """DELETE /api/pipelines/{id} returns 404 for nonexistent pipeline."""
        response = client.delete(f"/api/pipelines/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_execute_pipeline_returns_200(self, client):
        """POST /api/pipelines/{id}/execute returns 200."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_9",
                "title": "Test Pipeline 9",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute the pipeline
        response = client.post(
            f"/api/pipelines/{pipeline_id}/execute", json={"input_text": "Test input"}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_execute_pipeline_response_structure(self, client):
        """POST /api/pipelines/{id}/execute response has correct structure."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_10",
                "title": "Test Pipeline 10",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute the pipeline
        response = client.post(
            f"/api/pipelines/{pipeline_id}/execute", json={"input_text": "Test input"}
        )
        body = response.json()

        # Verify required fields
        assert "id" in body
        assert "pipeline_config_id" in body
        assert "output_text" in body
        assert "tokens_in" in body
        assert "tokens_out" in body
        assert "duration_ms" in body
        assert "status" in body
        assert "error_message" in body
        assert "timestamp" in body

        # Verify types
        assert isinstance(body["id"], str)
        assert isinstance(body["output_text"], str)
        assert isinstance(body["tokens_in"], int)
        assert isinstance(body["tokens_out"], int)
        assert isinstance(body["duration_ms"], int)
        assert body["status"] in ["success", "error", "timeout"]

    def test_execute_pipeline_nonexistent_returns_404(self, client):
        """POST /api/pipelines/{id}/execute returns 404 for nonexistent pipeline."""
        response = client.post(
            f"/api/pipelines/{uuid4()}/execute", json={"input_text": "Test input"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_pipeline_executions_returns_200(self, client):
        """GET /api/pipelines/{id}/executions returns 200."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_11",
                "title": "Test Pipeline 11",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Get executions
        response = client.get(f"/api/pipelines/{pipeline_id}/executions")
        assert response.status_code == status.HTTP_200_OK

    def test_get_pipeline_executions_response_is_list(self, client):
        """GET /api/pipelines/{id}/executions response is a list."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_12",
                "title": "Test Pipeline 12",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Get executions
        response = client.get(f"/api/pipelines/{pipeline_id}/executions")
        body = response.json()
        assert isinstance(body, list)

    def test_get_pipeline_executions_includes_executed(self, client):
        """GET /api/pipelines/{id}/executions includes previously executed pipelines."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_13",
                "title": "Test Pipeline 13",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute the pipeline
        execute_response = client.post(
            f"/api/pipelines/{pipeline_id}/execute", json={"input_text": "Test input"}
        )
        execution_id = execute_response.json()["id"]

        # Get executions
        response = client.get(f"/api/pipelines/{pipeline_id}/executions")
        body = response.json()

        # Executed pipeline should be in the list
        ids = [e["id"] for e in body]
        assert execution_id in ids


class TestPipelineErrorHandling:
    """Tests for error handling in pipeline routes."""

    def test_unexpected_error_returns_500(self, client, monkeypatch):
        """Unexpected exceptions (e.g., ValueError) return 500."""
        # Create a pipeline first
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_error",
                "title": "Test Pipeline Error",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Mock the service to raise ValueError
        def mock_get_config(*args, **kwargs):
            raise ValueError("Simulated server-side ValueError")

        original_service = client.app.state.pipeline_service
        original_get_config = original_service.get_config
        original_service.get_config = mock_get_config

        try:
            # Request should return 500 for unexpected exception
            response = client.get(f"/api/pipelines/{pipeline_id}")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json()["detail"] == "An unexpected error occurred"
        finally:
            # Restore original service
            original_service.get_config = original_get_config

    def test_type_error_returns_500(self, client):
        """TypeError (another unexpected exception) returns 500."""
        # Create a pipeline first
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_typeerror",
                "title": "Test Pipeline TypeError",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Mock the service to raise TypeError
        def mock_get_config(*args, **kwargs):
            raise TypeError("Simulated server-side TypeError")

        original_service = client.app.state.pipeline_service
        original_get_config = original_service.get_config
        original_service.get_config = mock_get_config

        try:
            # Request should return 500 for unexpected exception
            response = client.get(f"/api/pipelines/{pipeline_id}")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json()["detail"] == "An unexpected error occurred"
        finally:
            # Restore original service
            original_service.get_config = original_get_config

    def test_error_message_generic_for_unexpected_errors(self, client):
        """Unexpected error messages are generic (no internal details exposed)."""
        # Create a pipeline first
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_generic_msg",
                "title": "Test Pipeline Generic Message",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        create_response.json()["id"]

        # Mock the service to raise an exception with sensitive details
        def mock_list_configs(*args, **kwargs):
            raise RuntimeError("Database connection failed at 192.168.1.100:5432")

        original_service = client.app.state.pipeline_service
        original_list_configs = original_service.list_configs
        original_service.list_configs = mock_list_configs

        try:
            # Request should return 500 with generic message
            response = client.get("/api/pipelines")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            # Should NOT contain the sensitive database details
            body = response.json()
            assert "192.168.1.100" not in body["detail"]
            assert "5432" not in body["detail"]
            assert body["detail"] == "An unexpected error occurred"
        finally:
            # Restore original service
            original_service.list_configs = original_list_configs

    def test_layer_execution_error_returns_500(self, client):
        """LayerExecutionError returns 500 (server error)."""
        # Create a pipeline first
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_layer_error",
                "title": "Test Pipeline Layer Error",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Mock the service to raise LayerExecutionError
        def mock_execute_pipeline(*args, **kwargs):
            raise LayerExecutionError("Layer processing failed during execution")

        original_service = client.app.state.pipeline_service
        original_execute = original_service.execute_pipeline
        original_service.execute_pipeline = mock_execute_pipeline

        try:
            # Request should return 500 for LayerExecutionError
            response = client.post(
                f"/api/pipelines/{pipeline_id}/execute",
                json={"input_text": "Test input"},
            )
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json()["detail"] == "Pipeline layer failed to execute"
        finally:
            # Restore original service
            original_service.execute_pipeline = original_execute

    def test_layer_execution_error_returns_500_on_get_config(self, client):
        """LayerExecutionError returns 500 even when raised during config retrieval."""
        # Create a pipeline first
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_layer_get_error",
                "title": "Test Pipeline Layer Get Error",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Mock the service to raise LayerExecutionError
        def mock_get_config(*args, **kwargs):
            raise LayerExecutionError("Unexpected layer error during config retrieval")

        original_service = client.app.state.pipeline_service
        original_get_config = original_service.get_config
        original_service.get_config = mock_get_config

        try:
            # Request should return 500 for LayerExecutionError
            response = client.get(f"/api/pipelines/{pipeline_id}")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json()["detail"] == "Pipeline layer failed to execute"
        finally:
            # Restore original service
            original_service.get_config = original_get_config

    def test_layer_execution_error_checked_before_pipeline_error(self, client):
        """
        Verify LayerExecutionError is checked before PipelineError in exception ordering.

        This test ensures that if the isinstance checks are reordered in _handle_domain_error,
        the test will catch the regression. LayerExecutionError is a subclass of PipelineError,
        so checking PipelineError first would incorrectly return HTTP 400 instead of 500.
        """
        # Create a pipeline first
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "test_pipeline_ordering",
                "title": "Test Pipeline Ordering",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Mock the service to raise LayerExecutionError
        def mock_list_executions(*args, **kwargs):
            raise LayerExecutionError("Layer execution ordering test error")

        original_service = client.app.state.pipeline_service
        original_list_executions = original_service.list_executions
        original_service.list_executions = mock_list_executions

        try:
            # Request should return 500, NOT 400
            response = client.get(f"/api/pipelines/{pipeline_id}/executions")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            # Verify it's not 400 (which would indicate PipelineError was matched instead)
            assert response.status_code != status.HTTP_400_BAD_REQUEST
        finally:
            # Restore original service
            original_service.list_executions = original_list_executions


class TestListAllPipelineExecutions:
    """Tests for the list_all_executions paginated endpoint."""

    def test_list_all_executions_returns_200(self, client):
        """GET /api/pipelines/executions returns 200."""
        response = client.get("/api/pipelines/executions")
        assert response.status_code == status.HTTP_200_OK

    def test_list_all_executions_response_structure(self, client):
        """GET /api/pipelines/executions returns paginated list with total count."""
        response = client.get("/api/pipelines/executions")
        body = response.json()

        # Verify required fields
        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body

        # Verify types
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)
        assert isinstance(body["limit"], int)
        assert isinstance(body["offset"], int)

    def test_list_all_executions_empty_list(self, client):
        """GET /api/pipelines/executions returns empty list when no executions."""
        response = client.get("/api/pipelines/executions")
        body = response.json()

        assert body["items"] == []
        assert body["total"] == 0
        assert body["offset"] == 0
        assert body["limit"] == 100

    def test_list_all_executions_includes_all_pipelines(self, client):
        """GET /api/pipelines/executions includes executions from all pipelines."""
        # Create two pipelines
        pipeline1_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "pipeline_list_all_1",
                "title": "Pipeline 1",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline1_id = pipeline1_response.json()["id"]

        pipeline2_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "pipeline_list_all_2",
                "title": "Pipeline 2",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline2_id = pipeline2_response.json()["id"]

        # Execute both pipelines
        exec1_response = client.post(
            f"/api/pipelines/{pipeline1_id}/execute", json={"input_text": "Test 1"}
        )
        exec1_id = exec1_response.json()["id"]

        exec2_response = client.post(
            f"/api/pipelines/{pipeline2_id}/execute", json={"input_text": "Test 2"}
        )
        exec2_id = exec2_response.json()["id"]

        # List all executions
        response = client.get("/api/pipelines/executions")
        body = response.json()

        # Both executions should be in the list
        exec_ids = [e["id"] for e in body["items"]]
        assert exec1_id in exec_ids
        assert exec2_id in exec_ids
        assert body["total"] == 2

    def test_list_all_executions_with_pagination_offset(self, client):
        """GET /api/pipelines/executions respects offset parameter."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "pipeline_pagination",
                "title": "Pipeline Pagination",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute pipeline 3 times
        for i in range(3):
            client.post(
                f"/api/pipelines/{pipeline_id}/execute", json={"input_text": f"Test {i}"}
            )

        # List with offset=0, limit=2
        response = client.get("/api/pipelines/executions?offset=0&limit=2")
        body = response.json()

        assert len(body["items"]) == 2
        assert body["offset"] == 0
        assert body["limit"] == 2
        assert body["total"] == 3

        # List with offset=2, limit=2
        response = client.get("/api/pipelines/executions?offset=2&limit=2")
        body = response.json()

        assert len(body["items"]) == 1
        assert body["offset"] == 2
        assert body["limit"] == 2
        assert body["total"] == 3

    def test_list_all_executions_with_limit(self, client):
        """GET /api/pipelines/executions respects limit parameter."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "pipeline_limit_test",
                "title": "Pipeline Limit Test",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute pipeline 5 times
        for i in range(5):
            client.post(
                f"/api/pipelines/{pipeline_id}/execute", json={"input_text": f"Test {i}"}
            )

        # List with limit=3
        response = client.get("/api/pipelines/executions?limit=3")
        body = response.json()

        assert len(body["items"]) == 3
        assert body["limit"] == 3
        assert body["total"] == 5

    def test_list_all_executions_with_status_filter_success(self, client):
        """GET /api/pipelines/executions filters by status_filter=success."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "pipeline_status_filter",
                "title": "Pipeline Status Filter",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute pipeline (should succeed)
        client.post(
            f"/api/pipelines/{pipeline_id}/execute", json={"input_text": "Test"}
        )

        # List with status_filter=success filter
        response = client.get("/api/pipelines/executions?status_filter=success")
        body = response.json()

        # Should have the execution with success status
        assert body["total"] == 1
        assert all(e["status"] == "success" for e in body["items"])

    def test_list_all_executions_with_invalid_status_returns_422(self, client):
        """GET /api/pipelines/executions returns 422 for invalid status_filter."""
        response = client.get("/api/pipelines/executions?status_filter=invalid_status")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()
        assert "detail" in body

    def test_list_all_executions_includes_pipeline_title(self, client):
        """GET /api/pipelines/executions includes pipeline_title in response."""
        # Create a pipeline with specific title
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "pipeline_with_title",
                "title": "My Custom Pipeline Title",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute the pipeline
        client.post(
            f"/api/pipelines/{pipeline_id}/execute", json={"input_text": "Test"}
        )

        # List all executions
        response = client.get("/api/pipelines/executions")
        body = response.json()

        # Check that pipeline_title is included
        assert len(body["items"]) > 0
        execution = body["items"][0]
        assert "pipeline_title" in execution
        assert execution["pipeline_title"] == "My Custom Pipeline Title"

    def test_list_all_executions_reverse_chronological_order(self, client):
        """GET /api/pipelines/executions returns results in reverse chronological order."""
        # Create a pipeline
        create_response = client.post(
            "/api/pipelines",
            json={
                "pipeline": "pipeline_chrono_order",
                "title": "Pipeline Chrono Order",
                "provider": "openai",
                "model": "gpt-4",
                "config": {},
                "system_prompt": "Test",
                "user_prompt": "Process: {text}",
            },
        )
        pipeline_id = create_response.json()["id"]

        # Execute pipeline twice with a small delay
        exec_ids = []
        for i in range(2):
            response = client.post(
                f"/api/pipelines/{pipeline_id}/execute", json={"input_text": f"Test {i}"}
            )
            exec_ids.append(response.json()["id"])
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # List all executions
        response = client.get("/api/pipelines/executions")
        body = response.json()

        # Last executed (exec_ids[1]) should come first (reverse chronological)
        returned_ids = [e["id"] for e in body["items"]]
        assert returned_ids[0] == exec_ids[1]
        assert returned_ids[1] == exec_ids[0]


class TestFlavorRoutes:
    """Integration tests for flavor routes."""

    def test_create_flavor(self, client):
        """POST /api/pipelines/flavors creates a new flavor."""
        response = client.post(
            "/api/pipelines/flavors",
            json={
                "name": "Extract PDF",
                "description": "Template for PDF extraction",
                "steps": [{"type": "parse", "target": "pdf"}],
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "Extract PDF"
        assert body["description"] == "Template for PDF extraction"
        assert body["step_count"] == 1
        assert body["created_at"] is not None
        assert body["last_updated"] is not None


    def test_list_flavors(self, client):
        """GET /api/pipelines/flavors returns all flavors."""
        flavor1 = client.post(
            "/api/pipelines/flavors",
            json={
                "name": "Flavor 1",
                "description": "First",
                "steps": [],
            },
        ).json()

        flavor2 = client.post(
            "/api/pipelines/flavors",
            json={
                "name": "Flavor 2",
                "description": "Second",
                "steps": [{"type": "step"}],
            },
        ).json()

        response = client.get("/api/pipelines/flavors")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert len(body) == 2
        assert any(f["id"] == flavor1["id"] for f in body)
        assert any(f["id"] == flavor2["id"] for f in body)

    def test_list_flavors_empty(self, client):
        """GET /api/pipelines/flavors returns empty list when no flavors."""
        response = client.get("/api/pipelines/flavors")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body == []

    def test_get_flavor(self, client):
        """GET /api/pipelines/flavors/{id} returns a specific flavor."""
        created = client.post(
            "/api/pipelines/flavors",
            json={
                "name": "Test Flavor",
                "description": "A test flavor",
                "steps": [{"type": "parse"}, {"type": "extract"}],
            },
        ).json()

        response = client.get(f"/api/pipelines/flavors/{created['id']}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert body["id"] == created["id"]
        assert body["name"] == "Test Flavor"
        assert body["description"] == "A test flavor"
        assert body["step_count"] == 2
        assert body["steps"] == [{"type": "parse"}, {"type": "extract"}]

    def test_get_flavor_not_found(self, client):
        """GET /api/pipelines/flavors/{id} returns 404 for non-existent flavor."""
        response = client.get("/api/pipelines/flavors/nonexistent-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_flavor(self, client):
        """PUT /api/pipelines/flavors/{id} updates a flavor."""
        created = client.post(
            "/api/pipelines/flavors",
            json={
                "name": "Original",
                "description": "Original desc",
                "steps": [],
            },
        ).json()

        response = client.put(
            f"/api/pipelines/flavors/{created['id']}",
            json={
                "name": "Updated",
                "description": "Updated desc",
                "steps": [{"type": "new"}],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert body["name"] == "Updated"
        assert body["description"] == "Updated desc"
        assert body["step_count"] == 1

    def test_update_flavor_partial(self, client):
        """PUT /api/pipelines/flavors/{id} with partial fields."""
        created = client.post(
            "/api/pipelines/flavors",
            json={
                "name": "Original",
                "description": "Original desc",
                "steps": [{"type": "old"}],
            },
        ).json()

        response = client.put(
            f"/api/pipelines/flavors/{created['id']}",
            json={"name": "Updated"},
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert body["name"] == "Updated"
        assert body["description"] == "Original desc"
        assert body["step_count"] == 1

    def test_update_flavor_not_found(self, client):
        """PUT /api/pipelines/flavors/{id} returns 404 for non-existent."""
        response = client.put(
            "/api/pipelines/flavors/nonexistent-id",
            json={"name": "Updated"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_flavor(self, client):
        """DELETE /api/pipelines/flavors/{id} deletes a flavor."""
        created = client.post(
            "/api/pipelines/flavors",
            json={
                "name": "To Delete",
                "description": "This will be deleted",
                "steps": [],
            },
        ).json()

        response = client.delete(f"/api/pipelines/flavors/{created['id']}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        get_response = client.get(f"/api/pipelines/flavors/{created['id']}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_flavor_not_found(self, client):
        """DELETE /api/pipelines/flavors/{id} returns 404 for non-existent."""
        response = client.delete("/api/pipelines/flavors/nonexistent-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND
