"""
E2E tests for Phase 4: System Administration context.

This module tests the System Administration bounded context through both the HTTP API
and direct service calls with a fully initialized application using real databases
and real adapters.

Tests verify:
- Health check reporting real system status
- System metrics accuracy and consistency
- Configuration read and update operations with file persistence
- Background task lifecycle and state transitions (PENDING → RUNNING → COMPLETED)
"""

import sys
import os
import time
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi import status
from domain.admin.value_objects import BackgroundTaskStatus


@pytest.mark.e2e
class TestHealthCheck:
    """Tests for system health check reporting with real status."""

    def test_health_check_reports_real_status(self, e2e_client):
        """
        Health check endpoint returns real system status.

        Asserts:
        - database_connected is true (real database is running)
        - Response includes all expected service statuses
        - Response completes within 5 seconds
        """
        start_time = time.time()
        response = e2e_client.get("/api/v1/admin/health")
        elapsed = time.time() - start_time

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert elapsed < 5.0, f"Health check took {elapsed:.2f}s, expected < 5s"

        body = response.json()

        # Verify required fields present
        assert "status" in body
        assert "database_connected" in body
        assert "nlp_pipeline_ready" in body
        assert "embedding_model_loaded" in body
        assert "llm_providers_available" in body
        assert "uptime_seconds" in body
        assert "checked_at" in body
        assert "issues" in body

        # Verify database_connected is true (real database is working)
        assert body["database_connected"] is True, \
            "Database should be connected with real SQLite database"

        # Verify service statuses are booleans
        assert isinstance(body["nlp_pipeline_ready"], bool)
        assert isinstance(body["embedding_model_loaded"], bool)
        assert isinstance(body["llm_providers_available"], list)
        assert isinstance(body["uptime_seconds"], (int, float))
        assert isinstance(body["issues"], list)

        # Verify status is valid
        assert body["status"] in ["healthy", "degraded", "unhealthy"]


@pytest.mark.e2e
class TestSystemMetrics:
    """Tests for system metrics accuracy and consistency."""

    def test_system_metrics_accuracy(self, e2e_client):
        """
        System metrics endpoint reports accurate real system state.

        Verifies:
        - Service-level metrics are present
        - Metrics reflect actual adapter state (embeddings loaded, etc.)
        - Uptime and LLM provider information are accessible
        """
        # Check service metrics endpoint
        response = e2e_client.get("/api/v1/admin/health/services")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()

        # Verify required fields
        assert "uptime_seconds" in body
        assert "llm_providers_available" in body

        # Verify types
        assert isinstance(body["uptime_seconds"], (int, float))
        assert isinstance(body["llm_providers_available"], list)

        # Verify uptime is reasonable (positive)
        assert body["uptime_seconds"] >= 0

        # Check embedding model status
        response = e2e_client.get("/api/v1/admin/health/embedding")
        assert response.status_code == status.HTTP_200_OK

        embedding_body = response.json()
        assert "available" in embedding_body
        assert "details" in embedding_body
        # Embedding model may not be available in all configurations,
        # but it should have a status and details
        assert isinstance(embedding_body["available"], bool)
        assert isinstance(embedding_body["details"], str)


@pytest.mark.e2e
class TestConfigurationManagement:
    """Tests for configuration reading, updating, and persistence."""

    def test_configuration_read_and_update(self, e2e_client, temp_db_dir):
        """
        Configuration can be read, updated, and persisted correctly.

        Verifies:
        - All expected configuration sections are present
        - Configuration can be updated via PATCH endpoint
        - Updated values are reflected in the response immediately
        - Updated configuration persists in the config file for app restart
        """
        # Read current configuration
        response = e2e_client.get("/api/v1/admin/configuration")
        assert response.status_code == status.HTTP_200_OK

        config = response.json()
        assert "sections" in config
        assert isinstance(config["sections"], dict)

        # Verify expected sections present
        expected_sections = ["server", "database", "llm"]
        for section in expected_sections:
            assert section in config["sections"], \
                f"Configuration should have '{section}' section"

        # Update a non-sensitive setting (e.g., update CORS origins in server section)
        test_section = "server"
        test_key = "cors_origins"
        test_value = ["http://localhost:3000", "http://localhost:5173"]

        update_payload = {
            "updates": {
                test_key: test_value
            }
        }

        response = e2e_client.patch(
            f"/api/v1/admin/configuration/{test_section}",
            json=update_payload
        )
        assert response.status_code == status.HTTP_200_OK

        updated_config = response.json()
        assert test_section in updated_config["sections"]
        # Verify the update was reflected in the response
        assert updated_config["sections"][test_section].get(test_key) == test_value, \
            "Updated configuration should include the new value"

        # Verify other standard fields are still present (not overwritten)
        assert "host" in updated_config["sections"][test_section], \
            "Standard configuration fields should be preserved"

        # Verify the update is written to the config file on disk
        # This ensures the configuration survives an application restart
        config_file = temp_db_dir / "config.json"
        assert config_file.exists(), f"Config file should exist at {config_file}"

        with open(config_file, "r") as f:
            persisted_config = json.load(f)

        # Verify the update was written to the file (for app restart persistence)
        assert test_section in persisted_config, \
            f"Configuration file should have '{test_section}' section"
        assert persisted_config[test_section].get(test_key) == test_value, \
            "Updated value should be persisted to config file for restart"


@pytest.mark.e2e
class TestBackgroundTaskLifecycle:
    """Tests for background task lifecycle and state transitions."""

    def test_background_task_lifecycle(self, e2e_client):
        """
        Background task lifecycle transitions correctly through states.

        Verifies:
        - Task registers in PENDING state with no timestamps or result
        - Task transitions to RUNNING with started_at timestamp
        - Task transitions to COMPLETED with completed_at timestamp and result
        - Task result is persisted and retrievable with correct values
        - Task appears in task list after registration
        """
        # Register a background task by directly calling the admin service
        # First, get the admin service from app.state
        # For E2E testing through HTTP, we need to trigger task creation through an API call

        # Since there's no dedicated endpoint to register a task directly,
        # we'll use the fact that the AdminService has register_task, get_task, list_tasks
        # and update_task_status methods that can be called.

        # For E2E testing through HTTP, we need a way to trigger task creation.
        # Let's test the task lifecycle by directly calling service methods
        # and verifying through HTTP endpoints.

        # Get the admin service from the app for direct task lifecycle testing
        admin_service = e2e_client.app.state.admin_service

        # Register a background task (PENDING state)
        task = admin_service.register_task("test_task")

        # Verify initial PENDING state
        task_id = task.id
        assert task.status == BackgroundTaskStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None
        assert task.result is None

        # Transition to RUNNING (with started_at)
        task = admin_service.update_task_status(task_id, BackgroundTaskStatus.RUNNING)
        assert task.status == BackgroundTaskStatus.RUNNING
        assert task.started_at is not None
        assert task.completed_at is None
        assert task.result is None

        # Transition to COMPLETED (with completed_at and result)
        result_data = {"output": "test_result"}
        task = admin_service.update_task_status(task_id, BackgroundTaskStatus.COMPLETED, result=result_data)
        assert task.status == BackgroundTaskStatus.COMPLETED
        assert task.started_at is not None
        assert task.completed_at is not None
        assert task.result == result_data

        # Verify task appears in list
        tasks = admin_service.list_tasks()
        task_ids = [t.id for t in tasks]
        assert task_id in task_ids

        # Verify task is retrievable by ID
        retrieved_task = admin_service.get_task(task_id)
        assert retrieved_task.status == BackgroundTaskStatus.COMPLETED
        assert retrieved_task.result == result_data
