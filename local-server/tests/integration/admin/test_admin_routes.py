"""
Integration tests for System Administration API routes.

Tests verify the full admin API workflow with:
- AdminService with faked metrics and configuration
- HTTP routes via TestClient
- End-to-end request/response validation
- Error handling for configuration and task not found scenarios

These tests exercise the complete stack: routes → domain service → adapters.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from domain.admin.services import AdminService
from domain.admin.exceptions import AdminError, ConfigurationError, TaskNotFoundError
from adapters.web.admin_routes import router
from tests.fakes.fake_metrics_collector import FakeMetricsCollector
from tests.fakes.fake_configuration_store import FakeConfigurationStore


@pytest.fixture
def metrics_collector():
    """Create a fake metrics collector for testing."""
    return FakeMetricsCollector()


@pytest.fixture
def config_store():
    """Create a fake configuration store for testing."""
    return FakeConfigurationStore()


@pytest.fixture
def admin_service(metrics_collector, config_store):
    """Create AdminService with fake adapters."""
    return AdminService(
        metrics_collector=metrics_collector,
        config_store=config_store,
    )


@pytest.fixture
def client(admin_service):
    """Create a TestClient with admin service."""
    app = FastAPI()
    app.include_router(router)
    app.state.admin_service = admin_service
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /api/v1/admin/health endpoint."""

    def test_check_health_returns_200(self, client):
        """GET /api/v1/admin/health returns 200."""
        response = client.get("/api/v1/admin/health")
        assert response.status_code == status.HTTP_200_OK

    def test_check_health_response_structure(self, client):
        """GET /api/v1/admin/health response has correct structure."""
        response = client.get("/api/v1/admin/health")
        body = response.json()

        # Verify required fields
        assert "status" in body
        assert "database_connected" in body
        assert "nlp_pipeline_ready" in body
        assert "embedding_model_loaded" in body
        assert "llm_providers_available" in body
        assert "uptime_seconds" in body
        assert "issues" in body
        assert "checked_at" in body

    def test_check_health_response_types(self, client):
        """GET /api/v1/admin/health response has correct types."""
        response = client.get("/api/v1/admin/health")
        body = response.json()

        # Verify types
        assert isinstance(body["status"], str)
        assert isinstance(body["database_connected"], bool)
        assert isinstance(body["nlp_pipeline_ready"], bool)
        assert isinstance(body["embedding_model_loaded"], bool)
        assert isinstance(body["llm_providers_available"], list)
        assert isinstance(body["uptime_seconds"], (int, float))
        assert isinstance(body["issues"], list)
        assert isinstance(body["checked_at"], str)

    def test_check_health_status_is_valid(self, client):
        """GET /api/v1/admin/health status is one of valid values."""
        response = client.get("/api/v1/admin/health")
        body = response.json()

        assert body["status"] in ["healthy", "degraded", "unhealthy"]

    def test_check_health_includes_providers_list(self, client):
        """GET /api/v1/admin/health includes LLM providers."""
        response = client.get("/api/v1/admin/health")
        body = response.json()

        # Response should include providers (may be empty list)
        assert isinstance(body["llm_providers_available"], list)


class TestConfigurationEndpoint:
    """Tests for configuration endpoints."""

    def test_get_configuration_returns_200(self, client):
        """GET /api/v1/admin/configuration returns 200."""
        response = client.get("/api/v1/admin/configuration")
        assert response.status_code == status.HTTP_200_OK

    def test_get_configuration_response_has_sections(self, client):
        """GET /api/v1/admin/configuration response has sections dict."""
        response = client.get("/api/v1/admin/configuration")
        body = response.json()

        assert "sections" in body
        assert isinstance(body["sections"], dict)

    def test_get_configuration_masks_api_keys(self, client, config_store):
        """GET /api/v1/admin/configuration masks API keys."""
        # Ensure config has API keys
        config_store.update_config({'llm': {'openai_api_key': 'sk-1234567890abcdef1234567890'}})

        # Get configuration
        response = client.get("/api/v1/admin/configuration")
        body = response.json()

        # API key should be masked
        llm_section = body["sections"].get("llm", {})
        assert "openai_api_key" in llm_section, "openai_api_key should be present in llm section"
        masked = llm_section["openai_api_key"]
        assert masked.startswith("***"), "API key should be masked with ***"
        assert masked != 'sk-1234567890abcdef1234567890', "Masked key should not be the original key"

    def test_update_configuration_section_returns_200(self, client):
        """PATCH /api/v1/admin/configuration/{section} returns 200."""
        response = client.patch(
            "/api/v1/admin/configuration/llm",
            json={"updates": {"temperature": 0.7}}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_update_configuration_response_structure(self, client):
        """PATCH /api/v1/admin/configuration/{section} response has sections."""
        response = client.patch(
            "/api/v1/admin/configuration/llm",
            json={"updates": {"temperature": 0.7}}
        )
        body = response.json()

        assert "sections" in body
        assert isinstance(body["sections"], dict)

    def test_update_configuration_applies_changes(self, client, config_store):
        """PATCH /api/v1/admin/configuration/{section} applies updates."""
        # Update a section
        response = client.patch(
            "/api/v1/admin/configuration/llm",
            json={"updates": {"test_key": "test_value"}}
        )
        body = response.json()

        # Verify update is in response
        if "llm" in body["sections"]:
            assert body["sections"]["llm"].get("test_key") == "test_value"

    def test_update_configuration_nonexistent_section_returns_400(self, client):
        """PATCH /api/v1/admin/configuration/{section} returns 400 for nonexistent section."""
        response = client.patch(
            "/api/v1/admin/configuration/nonexistent_section",
            json={"updates": {"key": "value"}}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_configuration_error_includes_message(self, client):
        """PATCH /api/v1/admin/configuration/{section} error includes detail."""
        response = client.patch(
            "/api/v1/admin/configuration/nonexistent_section",
            json={"updates": {"key": "value"}}
        )
        body = response.json()

        assert "detail" in body
        assert isinstance(body["detail"], str)


class TestTasksEndpoint:
    """Tests for background task endpoints."""

    def test_list_tasks_returns_200(self, client):
        """GET /api/v1/admin/tasks returns 200."""
        response = client.get("/api/v1/admin/tasks")
        assert response.status_code == status.HTTP_200_OK

    def test_list_tasks_response_is_list(self, client):
        """GET /api/v1/admin/tasks response is a list."""
        response = client.get("/api/v1/admin/tasks")
        body = response.json()

        assert isinstance(body, list)

    def test_list_tasks_includes_registered_task(self, client, admin_service):
        """GET /api/v1/admin/tasks includes previously registered tasks."""
        # Register a task
        task = admin_service.register_task("test_task")

        # List tasks
        response = client.get("/api/v1/admin/tasks")
        body = response.json()

        # Registered task should be in list
        ids = [t["id"] for t in body]
        assert task.id in ids

    def test_list_tasks_includes_task_details(self, client, admin_service):
        """GET /api/v1/admin/tasks includes task details."""
        # Register a task
        task = admin_service.register_task("detailed_task")

        # List tasks
        response = client.get("/api/v1/admin/tasks")
        body = response.json()

        # Find the task in the response
        task_response = next((t for t in body if t["id"] == task.id), None)
        assert task_response is not None
        assert task_response["name"] == "detailed_task"
        assert task_response["status"] == "pending"

    def test_get_task_returns_200(self, client, admin_service):
        """GET /api/v1/admin/tasks/{task_id} returns 200 for existing task."""
        # Register a task
        task = admin_service.register_task("get_test_task")

        # Get the task
        response = client.get(f"/api/v1/admin/tasks/{task.id}")
        assert response.status_code == status.HTTP_200_OK

    def test_get_task_response_structure(self, client, admin_service):
        """GET /api/v1/admin/tasks/{task_id} response has correct structure."""
        # Register a task
        task = admin_service.register_task("structure_test")

        # Get the task
        response = client.get(f"/api/v1/admin/tasks/{task.id}")
        body = response.json()

        # Verify required fields
        assert "id" in body
        assert "name" in body
        assert "status" in body
        assert "created_at" in body
        assert "started_at" in body
        assert "completed_at" in body
        assert "error" in body
        assert "result" in body

    def test_get_task_response_types(self, client, admin_service):
        """GET /api/v1/admin/tasks/{task_id} response has correct types."""
        # Register a task
        task = admin_service.register_task("type_test")

        # Get the task
        response = client.get(f"/api/v1/admin/tasks/{task.id}")
        body = response.json()

        # Verify types
        assert isinstance(body["id"], str)
        assert isinstance(body["name"], str)
        assert isinstance(body["status"], str)
        assert isinstance(body["created_at"], str)
        assert body["started_at"] is None or isinstance(body["started_at"], str)
        assert body["completed_at"] is None or isinstance(body["completed_at"], str)

    def test_get_task_returns_correct_data(self, client, admin_service):
        """GET /api/v1/admin/tasks/{task_id} returns correct task data."""
        # Register a task
        task = admin_service.register_task("data_test")

        # Get the task
        response = client.get(f"/api/v1/admin/tasks/{task.id}")
        body = response.json()

        # Data should match
        assert body["id"] == task.id
        assert body["name"] == "data_test"
        assert body["status"] == "pending"

    def test_get_task_nonexistent_returns_404(self, client):
        """GET /api/v1/admin/tasks/{task_id} returns 404 for nonexistent task."""
        response = client.get("/api/v1/admin/tasks/nonexistent-task-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_task_error_includes_message(self, client):
        """GET /api/v1/admin/tasks/{task_id} error includes detail."""
        response = client.get("/api/v1/admin/tasks/nonexistent-task-id")
        body = response.json()

        assert "detail" in body
        assert isinstance(body["detail"], str)

    def test_get_task_with_status_update(self, client, admin_service):
        """GET /api/v1/admin/tasks/{task_id} reflects task status changes."""
        # Register and update task
        task = admin_service.register_task("status_test")
        admin_service.update_task_status(task.id, "running")

        # Get the task
        response = client.get(f"/api/v1/admin/tasks/{task.id}")
        body = response.json()

        # Status should reflect update
        assert body["status"] == "running"
        assert body["started_at"] is not None

    def test_get_task_with_completion(self, client, admin_service):
        """GET /api/v1/admin/tasks/{task_id} includes result data."""
        # Register, run, and complete task
        task = admin_service.register_task("completion_test")
        admin_service.update_task_status(
            task.id,
            "completed",
            result={"output": "task completed"}
        )

        # Get the task
        response = client.get(f"/api/v1/admin/tasks/{task.id}")
        body = response.json()

        # Result should be in response
        assert body["status"] == "completed"
        assert body["result"] == {"output": "task completed"}
        assert body["completed_at"] is not None


class TestGranularHealthEndpoints:
    """Tests for granular health check endpoints."""

    def test_database_health_returns_200(self, client):
        """GET /api/v1/admin/health/database returns 200."""
        response = client.get("/api/v1/admin/health/database")
        assert response.status_code == status.HTTP_200_OK

    def test_database_health_response_structure(self, client):
        """GET /api/v1/admin/health/database response has correct structure."""
        response = client.get("/api/v1/admin/health/database")
        body = response.json()

        assert "connected" in body
        assert "issues" in body

    def test_database_health_response_types(self, client):
        """GET /api/v1/admin/health/database response has correct types."""
        response = client.get("/api/v1/admin/health/database")
        body = response.json()

        assert isinstance(body["connected"], bool)
        assert isinstance(body["issues"], list)

    def test_service_metrics_returns_200(self, client):
        """GET /api/v1/admin/health/services returns 200."""
        response = client.get("/api/v1/admin/health/services")
        assert response.status_code == status.HTTP_200_OK

    def test_service_metrics_response_structure(self, client):
        """GET /api/v1/admin/health/services response has correct structure."""
        response = client.get("/api/v1/admin/health/services")
        body = response.json()

        assert "uptime_seconds" in body
        assert "llm_providers_available" in body

    def test_service_metrics_response_types(self, client):
        """GET /api/v1/admin/health/services response has correct types."""
        response = client.get("/api/v1/admin/health/services")
        body = response.json()

        assert isinstance(body["uptime_seconds"], (int, float))
        assert isinstance(body["llm_providers_available"], list)

    def test_embedding_health_returns_200(self, client):
        """GET /api/v1/admin/health/embedding returns 200."""
        response = client.get("/api/v1/admin/health/embedding")
        assert response.status_code == status.HTTP_200_OK

    def test_embedding_health_response_structure(self, client):
        """GET /api/v1/admin/health/embedding response has correct structure."""
        response = client.get("/api/v1/admin/health/embedding")
        body = response.json()

        assert "available" in body
        assert "details" in body

    def test_embedding_health_response_types(self, client):
        """GET /api/v1/admin/health/embedding response has correct types."""
        response = client.get("/api/v1/admin/health/embedding")
        body = response.json()

        assert isinstance(body["available"], bool)
        assert isinstance(body["details"], str)

    def test_nlp_health_returns_200(self, client):
        """GET /api/v1/admin/health/nlp returns 200."""
        response = client.get("/api/v1/admin/health/nlp")
        assert response.status_code == status.HTTP_200_OK

    def test_nlp_health_response_structure(self, client):
        """GET /api/v1/admin/health/nlp response has correct structure."""
        response = client.get("/api/v1/admin/health/nlp")
        body = response.json()

        assert "available" in body
        assert "details" in body

    def test_nlp_health_response_types(self, client):
        """GET /api/v1/admin/health/nlp response has correct types."""
        response = client.get("/api/v1/admin/health/nlp")
        body = response.json()

        assert isinstance(body["available"], bool)
        assert isinstance(body["details"], str)

    def test_task_summary_returns_200(self, client):
        """GET /api/v1/admin/health/tasks returns 200."""
        response = client.get("/api/v1/admin/health/tasks")
        assert response.status_code == status.HTTP_200_OK

    def test_task_summary_response_structure(self, client):
        """GET /api/v1/admin/health/tasks response has correct structure."""
        response = client.get("/api/v1/admin/health/tasks")
        body = response.json()

        assert "total" in body
        assert "by_status" in body

    def test_task_summary_response_types(self, client):
        """GET /api/v1/admin/health/tasks response has correct types."""
        response = client.get("/api/v1/admin/health/tasks")
        body = response.json()

        assert isinstance(body["total"], int)
        assert isinstance(body["by_status"], dict)


class TestConfigurationResetEndpoint:
    """Tests for configuration reset endpoint."""

    def test_reset_configuration_returns_200(self, client):
        """POST /api/v1/admin/configuration/reset returns 200."""
        response = client.post("/api/v1/admin/configuration/reset")
        assert response.status_code == status.HTTP_200_OK

    def test_reset_configuration_response_structure(self, client):
        """POST /api/v1/admin/configuration/reset response has correct structure."""
        response = client.post("/api/v1/admin/configuration/reset")
        body = response.json()

        assert "sections" in body
        assert isinstance(body["sections"], dict)

    def test_reset_configuration_masks_credentials(self, client, config_store):
        """POST /api/v1/admin/configuration/reset masks credential fields."""
        # Set up config with credentials
        config_store.update_config({'llm': {'openai_api_key': 'sk-1234567890abcdef1234567890'}})

        # Reset configuration
        response = client.post("/api/v1/admin/configuration/reset")
        body = response.json()

        # Credentials should be masked
        llm_section = body["sections"].get("llm", {})
        assert "openai_api_key" in llm_section, "openai_api_key should be present in reset response"
        masked = llm_section["openai_api_key"]
        assert masked.startswith("***"), "Credential should be masked"

    def test_reset_configuration_restores_defaults(self, client, config_store, admin_service):
        """POST /api/v1/admin/configuration/reset restores default values."""
        # Get baseline config
        reset_config = admin_service.reset_configuration()
        dict(reset_config.sections)

        # Modify config
        response = client.patch(
            "/api/v1/admin/configuration/llm",
            json={"updates": {"custom_field": "custom_value"}}
        )
        assert response.status_code == status.HTTP_200_OK

        # Reset
        response = client.post("/api/v1/admin/configuration/reset")
        body = response.json()

        # Custom field should be removed in reset
        llm_section = body["sections"].get("llm", {})
        assert "custom_field" not in llm_section


class TestAdminErrorHandling:
    """Tests for error handling in admin routes."""

    def test_generic_exception_returns_500(self, client, admin_service, monkeypatch):
        """Test that non-AdminError exceptions return 500 Internal Server Error."""
        # Mock the service method to raise a non-AdminError exception
        def failing_check_health():
            raise RuntimeError("Unexpected database connection error")

        monkeypatch.setattr(admin_service, "check_health", failing_check_health)

        # Call health endpoint which should handle the RuntimeError
        response = client.get("/api/v1/admin/health")

        # Should return 500 for unexpected exceptions
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Response should have error detail
        body = response.json()
        assert "detail" in body
        assert body["detail"] == "An unexpected error occurred"

    def test_admin_error_returns_400(self, client, admin_service, monkeypatch):
        """Test that AdminError exceptions return 400 Bad Request."""
        # Mock the service method to raise an AdminError
        def failing_check_health():
            raise AdminError("Configuration incomplete")

        monkeypatch.setattr(admin_service, "check_health", failing_check_health)

        response = client.get("/api/v1/admin/health")

        # Should return 400 for AdminError
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        body = response.json()
        assert "detail" in body
        assert "Configuration incomplete" in body["detail"]

    def test_configuration_error_returns_400(self, client, admin_service, monkeypatch):
        """Test that ConfigurationError exceptions return 400 Bad Request."""
        # Mock the service method to raise a ConfigurationError
        def failing_update_config(section, updates):
            raise ConfigurationError(f"Invalid section: {section}")

        monkeypatch.setattr(admin_service, "update_configuration", failing_update_config)

        response = client.patch(
            "/api/v1/admin/configuration/invalid",
            json={"updates": {"key": "value"}}
        )

        # Should return 400 for ConfigurationError
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        body = response.json()
        assert "detail" in body
        assert "Invalid section" in body["detail"]

    def test_task_not_found_returns_404(self, client, admin_service, monkeypatch):
        """Test that TaskNotFoundError exceptions return 404 Not Found."""
        # Mock the service method to raise a TaskNotFoundError
        def failing_get_task(task_id):
            raise TaskNotFoundError(f"Task {task_id} not found")

        monkeypatch.setattr(admin_service, "get_task", failing_get_task)

        response = client.get("/api/v1/admin/tasks/nonexistent")

        # Should return 404 for TaskNotFoundError
        assert response.status_code == status.HTTP_404_NOT_FOUND

        body = response.json()
        assert "detail" in body
        assert "not found" in body["detail"].lower()

    def test_reset_configuration_error_returns_400(self, client, admin_service, monkeypatch):
        """Test that ConfigurationError from reset_configuration returns 400 Bad Request."""
        # Mock the service method to raise a ConfigurationError
        def failing_reset_configuration():
            raise ConfigurationError("Failed to reset configuration: Invalid default settings")

        monkeypatch.setattr(admin_service, "reset_configuration", failing_reset_configuration)

        response = client.post("/api/v1/admin/configuration/reset")

        # Should return 400 for ConfigurationError
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        body = response.json()
        assert "detail" in body
        assert "Failed to reset configuration" in body["detail"]
