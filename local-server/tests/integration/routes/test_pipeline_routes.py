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

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from domain.pipeline.services import PipelineService
from domain.extraction.ports import LLMProvider
from domain.ports import EventPublisher
from adapters.persistence.sqlite.operations.models import Base
from adapters.persistence.sqlite.pipeline_repo import SQLitePipelineRepository
from adapters.events.in_process import InProcessEventPublisher
from adapters.web.pipeline_routes import router


# Mock LLM provider for testing
class MockLLMProvider:
    """Mock LLM provider for testing pipeline execution."""

    def complete(self, system_prompt, user_prompt, model, temperature, max_tokens, response_format):
        """Return mock LLM response."""
        from domain.extraction.ports import LLMResponse
        return LLMResponse(
            content='{"result": "test output"}',
            model=model,
            tokens_in=10,
            tokens_out=20,
        )


@pytest.fixture
def temp_ops_db():
    """Create a temporary operations SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "operations.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

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
    """Create PipelineService with mock LLM adapter."""
    service = PipelineService(
        pipeline_repo=pipeline_repository,
        llm=MockLLMProvider(),
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
        )
        pipeline_id = create_response.json()["id"]

        # Update the pipeline
        response = client.put(
            f"/api/pipelines/{pipeline_id}",
            json={
                "title": "Updated Pipeline 4",
                "system_prompt": "Updated system prompt",
            }
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
            }
        )
        pipeline_id = create_response.json()["id"]

        # Update the pipeline
        client.put(
            f"/api/pipelines/{pipeline_id}",
            json={"title": "New Title", "enabled": False}
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
            }
        )
        original_version = create_response.json()["version"]
        pipeline_id = create_response.json()["id"]

        # Update the pipeline
        response = client.put(
            f"/api/pipelines/{pipeline_id}",
            json={"title": "New Title"}
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
            }
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
            }
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
            }
        )
        pipeline_id = create_response.json()["id"]

        # Execute the pipeline
        response = client.post(
            f"/api/pipelines/{pipeline_id}/execute",
            json={"input_text": "Test input"}
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
            }
        )
        pipeline_id = create_response.json()["id"]

        # Execute the pipeline
        response = client.post(
            f"/api/pipelines/{pipeline_id}/execute",
            json={"input_text": "Test input"}
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
            f"/api/pipelines/{uuid4()}/execute",
            json={"input_text": "Test input"}
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
            }
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
            }
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
            }
        )
        pipeline_id = create_response.json()["id"]

        # Execute the pipeline
        execute_response = client.post(
            f"/api/pipelines/{pipeline_id}/execute",
            json={"input_text": "Test input"}
        )
        execution_id = execute_response.json()["id"]

        # Get executions
        response = client.get(f"/api/pipelines/{pipeline_id}/executions")
        body = response.json()

        # Executed pipeline should be in the list
        ids = [e["id"] for e in body]
        assert execution_id in ids
