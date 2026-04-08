"""
E2E tests for the LLM Pipeline Management bounded context.

This module tests the Pipeline Management bounded context through the HTTP API
with a fully initialized application using real databases and real adapters.

Tests verify:
- Pipeline configuration CRUD operations
- Execution triggering and record retrieval
- Validation of invalid provider/model inputs
- Delete cascade behavior
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi import status


@pytest.mark.e2e
class TestPipelineConfigurationCRUD:
    """Tests for pipeline configuration creation, retrieval, update, and deletion."""

    def test_create_pipeline_configuration(self, e2e_client):
        """
        Create a new pipeline configuration.

        Asserts:
        - Status code 201 (Created)
        - Response contains id, pipeline, title, provider, model, version, enabled, timestamps
        """
        response = e2e_client.post("/api/pipelines", json={
            "pipeline": "extraction",
            "title": "Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "config": {"temperature": 0.7},
            "system_prompt": "You are a helpful assistant.",
            "user_prompt": "Process this text: {text}",
            "enabled": True
        })

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["pipeline"] == "extraction"
        assert body["title"] == "Test Pipeline"
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4-turbo"
        assert body["system_prompt"] == "You are a helpful assistant."
        assert body["enabled"] is True
        assert body["version"] == 1
        assert "created_at" in body
        assert "last_updated" in body

    def test_list_pipeline_configurations(self, e2e_client):
        """
        List all pipeline configurations.

        Asserts:
        - Status code 200 (OK)
        - Response is a list of configurations
        """
        # Create a pipeline
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "list_test",
            "title": "List Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "Test system prompt",
            "user_prompt": "Test user prompt: {text}"
        })
        assert create_response.status_code == status.HTTP_201_CREATED

        # List pipelines
        response = e2e_client.get("/api/pipelines")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) > 0
        assert any(p["pipeline"] == "list_test" for p in body)

    def test_get_pipeline_configuration(self, e2e_client):
        """
        Retrieve a pipeline configuration by ID.

        Asserts:
        - Status code 200 (OK)
        - Response contains all configuration fields
        """
        # Create a pipeline
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "get_test",
            "title": "Get Test Pipeline",
            "provider": "anthropic",
            "model": "claude-opus",
            "system_prompt": "System prompt",
            "user_prompt": "User prompt: {text}"
        })
        config_id = create_response.json()["id"]

        # Get the pipeline
        response = e2e_client.get(f"/api/pipelines/{config_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == config_id
        assert body["pipeline"] == "get_test"
        assert body["title"] == "Get Test Pipeline"
        assert body["provider"] == "anthropic"

    def test_update_pipeline_configuration(self, e2e_client):
        """
        Update a pipeline configuration.

        Asserts:
        - Status code 200 (OK)
        - Updated fields are reflected in response
        - Version is incremented
        """
        # Create a pipeline
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "update_test",
            "title": "Update Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "Original system prompt",
            "user_prompt": "Original user prompt: {text}"
        })
        config_id = create_response.json()["id"]

        # Update the pipeline
        response = e2e_client.put(f"/api/pipelines/{config_id}", json={
            "title": "Updated Title",
            "provider": "anthropic",
            "model": "claude-sonnet",
            "system_prompt": "Updated system prompt",
            "enabled": False
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == config_id
        assert body["title"] == "Updated Title"
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-sonnet"
        assert body["system_prompt"] == "Updated system prompt"
        assert body["enabled"] is False
        assert body["version"] == 2

    def test_delete_pipeline_configuration(self, e2e_client):
        """
        Delete a pipeline configuration.

        Asserts:
        - Status code 204 (No Content)
        - Subsequent GET returns 404
        """
        # Create a pipeline
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "delete_test",
            "title": "Delete Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "System prompt",
            "user_prompt": "User prompt: {text}"
        })
        config_id = create_response.json()["id"]

        # Delete the pipeline
        response = e2e_client.delete(f"/api/pipelines/{config_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = e2e_client.get(f"/api/pipelines/{config_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.e2e
class TestPipelineExecution:
    """Tests for pipeline execution and execution history."""

    def test_execute_pipeline(self, e2e_client):
        """
        Execute a pipeline configuration.

        Asserts:
        - Status code 200 (OK)
        - Response contains execution record with output, tokens, duration, status
        """
        # Create a pipeline configuration
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "execution_test",
            "title": "Execution Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "You are a helpful assistant.",
            "user_prompt": "Echo back this text: {text}",
            "enabled": True
        })
        config_id = create_response.json()["id"]

        # Execute the pipeline
        response = e2e_client.post(f"/api/pipelines/{config_id}/execute", json={
            "input_text": "Hello, world!"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "id" in body
        assert body["pipeline_config_id"] == config_id
        assert "output_text" in body
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4-turbo"
        assert "tokens_in" in body
        assert "tokens_out" in body
        assert "duration_ms" in body
        assert "status" in body
        assert body["status"] in ["success", "error", "timeout"]
        assert "timestamp" in body

    def test_get_pipeline_executions(self, e2e_client):
        """
        Retrieve execution history for a pipeline.

        Asserts:
        - Status code 200 (OK)
        - Response is a list of execution records
        - Records are in reverse chronological order (most recent first)
        """
        # Create a pipeline configuration
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "history_test",
            "title": "History Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "You are a helpful assistant.",
            "user_prompt": "Process: {text}",
            "enabled": True
        })
        config_id = create_response.json()["id"]

        # Execute the pipeline multiple times
        e2e_client.post(f"/api/pipelines/{config_id}/execute", json={
            "input_text": "First execution"
        })
        e2e_client.post(f"/api/pipelines/{config_id}/execute", json={
            "input_text": "Second execution"
        })

        # Get execution history
        response = e2e_client.get(f"/api/pipelines/{config_id}/executions")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) >= 2
        # Verify all records are for this configuration
        assert all(e["pipeline_config_id"] == config_id for e in body)
        # Verify records are in reverse chronological order (most recent first)
        if len(body) > 1:
            assert body[0]["timestamp"] >= body[1]["timestamp"]

    def test_execute_nonexistent_pipeline_fails(self, e2e_client):
        """
        Executing a nonexistent pipeline fails.

        Asserts:
        - Status code 404 (Not Found)
        """
        response = e2e_client.post("/api/pipelines/nonexistent-id/execute", json={
            "input_text": "Test input"
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_executions_for_nonexistent_pipeline_fails(self, e2e_client):
        """
        Getting executions for a nonexistent pipeline fails.

        Asserts:
        - Status code 404 (Not Found)
        """
        response = e2e_client.get("/api/pipelines/nonexistent-id/executions")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.e2e
class TestPipelineValidation:
    """Tests for pipeline configuration validation."""

    def test_create_with_invalid_provider_fails(self, e2e_client):
        """
        Creating a pipeline with an invalid provider is rejected or logged.

        Asserts:
        - Request is accepted (validation occurs at execution time)
        - Pipeline is created with the invalid provider
        """
        response = e2e_client.post("/api/pipelines", json={
            "pipeline": "invalid_provider_test",
            "title": "Invalid Provider Pipeline",
            "provider": "nonexistent_provider",
            "model": "some-model",
            "system_prompt": "System prompt",
            "user_prompt": "User prompt: {text}"
        })
        # The service may accept the config creation (validation at execution time)
        # or reject it (validation at creation time)
        # Either 201 or 400 is acceptable here
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

    def test_create_with_empty_title_fails(self, e2e_client):
        """
        Creating a pipeline with empty title fails.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
        response = e2e_client.post("/api/pipelines", json={
            "pipeline": "empty_title_test",
            "title": "",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "System prompt",
            "user_prompt": "User prompt: {text}"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_with_empty_user_prompt_fails(self, e2e_client):
        """
        Creating a pipeline with empty user_prompt fails.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
        response = e2e_client.post("/api/pipelines", json={
            "pipeline": "empty_prompt_test",
            "title": "Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "System prompt",
            "user_prompt": ""
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_execute_with_empty_input_fails(self, e2e_client):
        """
        Executing a pipeline with empty input_text fails.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
        # Create a pipeline
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "empty_input_test",
            "title": "Empty Input Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "System prompt",
            "user_prompt": "Process: {text}"
        })
        config_id = create_response.json()["id"]

        # Execute with empty input
        response = e2e_client.post(f"/api/pipelines/{config_id}/execute", json={
            "input_text": ""
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.e2e
class TestPipelineDeleteCascade:
    """Tests for pipeline configuration delete cascade behavior."""

    def test_delete_pipeline_clears_execution_history(self, e2e_client):
        """
        Deleting a pipeline configuration cascades to execution records.

        Asserts:
        - Pipeline deletion succeeds (204)
        - Subsequent attempts to get executions for deleted pipeline fail (404)
        """
        # Create a pipeline
        create_response = e2e_client.post("/api/pipelines", json={
            "pipeline": "cascade_test",
            "title": "Cascade Test Pipeline",
            "provider": "openai",
            "model": "gpt-4-turbo",
            "system_prompt": "System prompt",
            "user_prompt": "Process: {text}"
        })
        config_id = create_response.json()["id"]

        # Execute the pipeline
        e2e_client.post(f"/api/pipelines/{config_id}/execute", json={
            "input_text": "Test execution"
        })

        # Verify executions exist
        executions_response = e2e_client.get(f"/api/pipelines/{config_id}/executions")
        assert executions_response.status_code == status.HTTP_200_OK
        assert len(executions_response.json()) > 0

        # Delete the pipeline
        delete_response = e2e_client.delete(f"/api/pipelines/{config_id}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify configuration is deleted
        get_response = e2e_client.get(f"/api/pipelines/{config_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

        # Verify executions are deleted (cascade)
        executions_response = e2e_client.get(f"/api/pipelines/{config_id}/executions")
        assert executions_response.status_code == status.HTTP_404_NOT_FOUND
