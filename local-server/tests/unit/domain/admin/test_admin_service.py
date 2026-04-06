"""
Unit tests for the AdminService domain service.

These tests verify system health monitoring, configuration management,
and background task lifecycle in isolation using fake ports.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime, timezone

from domain.admin.services import AdminService
from domain.admin.entities import SystemHealth, AppConfiguration
from domain.admin.value_objects import (
    SystemHealthStatus,
    BackgroundTaskStatus,
    DatabaseHealth,
    ServiceMetrics,
    ComponentStatus,
    BackgroundTaskSummary,
    CREDENTIAL_FIELD_NAMES,
)
from domain.admin.exceptions import ConfigurationError, TaskNotFoundError
from tests.fakes.fake_metrics_collector import FakeMetricsCollector
from tests.fakes.fake_configuration_store import FakeConfigurationStore


class TestAdminServiceGranularHealthMethods:
    """Tests for granular health check delegation methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = FakeMetricsCollector()
        self.config_store = FakeConfigurationStore()
        self.service = AdminService(self.metrics, self.config_store)

    def test_get_database_health_delegation(self):
        """get_database_health delegates to metrics collector."""
        db_health = self.service.get_database_health()

        assert isinstance(db_health, DatabaseHealth)
        assert db_health.connected is True
        assert db_health.issues == []

    def test_get_service_metrics_delegation(self):
        """get_service_metrics delegates to metrics collector."""
        metrics = self.service.get_service_metrics()

        assert isinstance(metrics, ServiceMetrics)
        assert metrics.uptime_seconds == 0.0
        assert metrics.llm_providers_available == []

    def test_get_embedding_model_status_delegation(self):
        """get_embedding_model_status delegates to metrics collector."""
        status = self.service.get_embedding_model_status()

        assert isinstance(status, ComponentStatus)
        assert status.available is True

    def test_get_nlp_pipeline_status_delegation(self):
        """get_nlp_pipeline_status delegates to metrics collector."""
        status = self.service.get_nlp_pipeline_status()

        assert isinstance(status, ComponentStatus)
        assert status.available is True

    def test_get_background_task_summary_delegation(self):
        """get_background_task_summary delegates to metrics collector."""
        summary = self.service.get_background_task_summary()

        assert isinstance(summary, BackgroundTaskSummary)
        assert summary.total == 0


class TestAdminServiceCompositeHealthAggregation:
    """Tests for health status aggregation business rules."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config_store = FakeConfigurationStore()

    def test_check_health_healthy_when_all_components_ok(self):
        """Status is HEALTHY when all components are operational."""
        metrics = FakeMetricsCollector(
            database_health=DatabaseHealth(connected=True, issues=[]),
            service_metrics=ServiceMetrics(uptime_seconds=3600.0, llm_providers_available=["openai"]),
            embedding_status=ComponentStatus(available=True, details="Loaded"),
            nlp_status=ComponentStatus(available=True, details="Ready"),
            task_summary=BackgroundTaskSummary(total=0, by_status={}),
        )
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.status == SystemHealthStatus.HEALTHY
        assert health.issues == []

    def test_check_health_unhealthy_when_database_disconnected(self):
        """Status is UNHEALTHY when database is disconnected."""
        metrics = FakeMetricsCollector(
            database_health=DatabaseHealth(
                connected=False, issues=["Connection timeout"]
            ),
            service_metrics=ServiceMetrics(uptime_seconds=3600.0, llm_providers_available=["openai"]),
            embedding_status=ComponentStatus(available=True, details="Loaded"),
            nlp_status=ComponentStatus(available=True, details="Ready"),
            task_summary=BackgroundTaskSummary(total=0, by_status={}),
        )
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.status == SystemHealthStatus.UNHEALTHY
        assert health.database_connected is False

    def test_check_health_degraded_when_embedding_unavailable(self):
        """Status is DEGRADED when embedding model is unavailable."""
        metrics = FakeMetricsCollector(
            database_health=DatabaseHealth(connected=True, issues=[]),
            service_metrics=ServiceMetrics(uptime_seconds=3600.0, llm_providers_available=["openai"]),
            embedding_status=ComponentStatus(available=False, details="Model not loaded"),
            nlp_status=ComponentStatus(available=True, details="Ready"),
            task_summary=BackgroundTaskSummary(total=0, by_status={}),
        )
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.status == SystemHealthStatus.DEGRADED
        assert health.embedding_model_loaded is False
        assert any("Embedding model" in issue for issue in health.issues)

    def test_check_health_degraded_when_nlp_unavailable(self):
        """Status is DEGRADED when NLP pipeline is unavailable."""
        metrics = FakeMetricsCollector(
            database_health=DatabaseHealth(connected=True, issues=[]),
            service_metrics=ServiceMetrics(uptime_seconds=3600.0, llm_providers_available=["openai"]),
            embedding_status=ComponentStatus(available=True, details="Loaded"),
            nlp_status=ComponentStatus(available=False, details="Pipeline not ready"),
            task_summary=BackgroundTaskSummary(total=0, by_status={}),
        )
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.status == SystemHealthStatus.DEGRADED
        assert health.nlp_pipeline_ready is False
        assert any("NLP pipeline" in issue for issue in health.issues)

    def test_check_health_degraded_when_database_has_issues(self):
        """Status is DEGRADED when database reports issues."""
        metrics = FakeMetricsCollector(
            database_health=DatabaseHealth(
                connected=True, issues=["Slow queries detected"]
            ),
            service_metrics=ServiceMetrics(uptime_seconds=3600.0, llm_providers_available=["openai"]),
            embedding_status=ComponentStatus(available=True, details="Loaded"),
            nlp_status=ComponentStatus(available=True, details="Ready"),
            task_summary=BackgroundTaskSummary(total=0, by_status={}),
        )
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.status == SystemHealthStatus.DEGRADED
        assert "Slow queries detected" in health.issues

    def test_check_health_aggregates_all_component_data(self):
        """check_health aggregates data from all components."""
        metrics = FakeMetricsCollector(
            database_health=DatabaseHealth(connected=True, issues=[]),
            service_metrics=ServiceMetrics(uptime_seconds=7200.0, llm_providers_available=["openai", "anthropic"]),
            embedding_status=ComponentStatus(available=True, details="Loaded"),
            nlp_status=ComponentStatus(available=True, details="Ready"),
            task_summary=BackgroundTaskSummary(total=0, by_status={}),
        )
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.database_connected is True
        assert health.nlp_pipeline_ready is True
        assert health.embedding_model_loaded is True
        assert health.llm_providers_available == ["openai", "anthropic"]
        assert health.uptime_seconds == 7200.0


class TestAdminServiceHealthMonitoring:
    """Tests for system health monitoring functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = FakeMetricsCollector()
        self.config_store = FakeConfigurationStore()
        self.service = AdminService(self.metrics, self.config_store)

    def test_check_health_returns_healthy_status(self):
        """Check health returns healthy status from metrics collector."""
        health = self.service.check_health()

        assert health.status == SystemHealthStatus.HEALTHY
        assert health.database_connected is True
        assert health.nlp_pipeline_ready is True
        assert health.embedding_model_loaded is True
        assert health.llm_providers_available == []
        assert health.uptime_seconds == 0.0
        assert health.checked_at is not None
        assert health.issues == []


class TestAdminServiceConfigurationReset:
    """Tests for configuration reset functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = FakeMetricsCollector()
        self.config_store = FakeConfigurationStore()
        self.service = AdminService(self.metrics, self.config_store)

    def test_reset_configuration_clears_non_credential_fields(self):
        """Reset configuration removes non-credential fields."""
        initial = AppConfiguration(
            sections={
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4",
                    "openai_api_key": "sk-secret-key",
                    "temperature": 0.7,
                },
                "database": {"path": "/tmp/test.db"},
            }
        )
        config_store = FakeConfigurationStore(initial_config=initial)
        service = AdminService(self.metrics, config_store)

        reset_config = service.reset_configuration()

        assert "provider" not in reset_config.sections["llm"]
        assert "model" not in reset_config.sections["llm"]
        assert "temperature" not in reset_config.sections["llm"]
        assert "path" not in reset_config.sections["database"]

    def test_reset_configuration_preserves_credentials(self):
        """Reset configuration preserves credential fields."""
        initial = AppConfiguration(
            sections={
                "llm": {
                    "provider": "openai",
                    "openai_api_key": "sk-secret-key",
                    "anthropic_api_key": "sk-ant-secret",
                },
                "database": {"path": "/tmp/test.db"},
                "sync": {
                    "s3_access_key": "access-key",
                    "s3_secret_key": "secret-key",
                },
            }
        )
        config_store = FakeConfigurationStore(initial_config=initial)
        service = AdminService(self.metrics, config_store)

        reset_config = service.reset_configuration()

        assert reset_config.sections["llm"]["openai_api_key"] == "sk-secret-key"
        assert reset_config.sections["llm"]["anthropic_api_key"] == "sk-ant-secret"
        assert reset_config.sections["sync"]["s3_access_key"] == "access-key"
        assert reset_config.sections["sync"]["s3_secret_key"] == "secret-key"

    def test_reset_configuration_uses_credential_field_names_constant(self):
        """Reset configuration uses CREDENTIAL_FIELD_NAMES to determine which fields to preserve."""
        # Create config with both credential fields (in CREDENTIAL_FIELD_NAMES) and non-credential fields
        initial = AppConfiguration(
            sections={
                "llm": {
                    "provider": "openai",  # Non-credential field
                    "model": "gpt-4",  # Non-credential field
                    "openai_api_key": "sk-secret",  # Credential field
                    "anthropic_api_key": "sk-ant",  # Credential field
                },
                "sync": {
                    "bucket": "my-bucket",  # Non-credential field
                    "s3_access_key": "access-key",  # Credential field
                    "s3_secret_key": "secret-key",  # Credential field
                },
            }
        )
        config_store = FakeConfigurationStore(initial_config=initial)
        service = AdminService(self.metrics, config_store)

        # Reset configuration
        reset_config = service.reset_configuration()

        # Verify non-credential fields are cleared
        assert "provider" not in reset_config.sections["llm"]
        assert "model" not in reset_config.sections["llm"]
        assert "bucket" not in reset_config.sections["sync"]

        # Verify credential fields (in CREDENTIAL_FIELD_NAMES) are preserved
        assert reset_config.sections["llm"]["openai_api_key"] == "sk-secret"
        assert reset_config.sections["llm"]["anthropic_api_key"] == "sk-ant"
        assert reset_config.sections["sync"]["s3_access_key"] == "access-key"
        assert reset_config.sections["sync"]["s3_secret_key"] == "secret-key"

    def test_reset_configuration_delegatesto_config_store(self):
        """Reset configuration delegates to ConfigurationStore.reset_to_defaults()."""
        config_store = FakeConfigurationStore()
        service = AdminService(self.metrics, config_store)

        result = service.reset_configuration()

        assert isinstance(result, AppConfiguration)
        assert "llm" in result.sections
        assert "database" in result.sections

    def test_reset_configuration_persists_changes(self):
        """Reset configuration persists the reset state."""
        initial = AppConfiguration(
            sections={
                "llm": {
                    "provider": "openai",
                    "openai_api_key": "sk-secret",
                },
                "database": {"path": "/tmp/test.db"},
            }
        )
        config_store = FakeConfigurationStore(initial_config=initial)
        service = AdminService(self.metrics, config_store)

        service.reset_configuration()
        loaded = service.get_configuration()

        assert "provider" not in loaded.sections["llm"]
        assert loaded.sections["llm"]["openai_api_key"] == "sk-secret"


class TestAdminServiceConfigurationManagement:
    """Tests for configuration management functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = FakeMetricsCollector()
        self.config_store = FakeConfigurationStore()
        self.service = AdminService(self.metrics, self.config_store)

    def test_get_configuration_returns_current_config(self):
        """Get configuration returns the current configuration."""
        config = self.service.get_configuration()

        assert isinstance(config, AppConfiguration)
        assert "llm" in config.sections
        assert "database" in config.sections

    def test_get_configuration_with_custom_sections(self):
        """Get configuration returns custom sections if provided."""
        initial = AppConfiguration(
            sections={
                "llm": {"provider": "openai", "model": "gpt-4"},
                "database": {"path": "/tmp/test.db"},
            }
        )
        config_store = FakeConfigurationStore(initial_config=initial)
        service = AdminService(self.metrics, config_store)

        config = service.get_configuration()

        assert config.sections["llm"]["provider"] == "openai"
        assert config.sections["llm"]["model"] == "gpt-4"
        assert config.sections["database"]["path"] == "/tmp/test.db"

    def test_update_configuration_updates_existing_section(self):
        """Update configuration modifies an existing section."""
        config = self.service.update_configuration(
            "llm", {"provider": "anthropic", "model": "claude-opus"}
        )

        assert config.sections["llm"]["provider"] == "anthropic"
        assert config.sections["llm"]["model"] == "claude-opus"

    def test_update_configuration_persists_changes(self):
        """Update configuration persists changes to the store."""
        self.service.update_configuration("llm", {"temperature": 0.7})
        loaded = self.service.get_configuration()

        assert loaded.sections["llm"]["temperature"] == 0.7

    def test_update_configuration_preserves_other_sections(self):
        """Update configuration does not affect other sections."""
        self.service.update_configuration(
            "database", {"max_connections": 50}
        )
        config = self.service.get_configuration()

        assert "llm" in config.sections
        assert config.sections["database"]["max_connections"] == 50

    def test_update_configuration_raises_error_for_unknown_section(self):
        """Update configuration raises ConfigurationError for unknown section."""
        with pytest.raises(ConfigurationError) as exc_info:
            self.service.update_configuration("unknown_section", {})

        assert "Unknown config section: unknown_section" in str(exc_info.value)

    def test_update_configuration_merges_updates(self):
        """Update configuration merges updates with existing values."""
        self.service.update_configuration("llm", {"provider": "openai"})
        self.service.update_configuration("llm", {"model": "gpt-4"})
        config = self.service.get_configuration()

        assert config.sections["llm"]["provider"] == "openai"
        assert config.sections["llm"]["model"] == "gpt-4"


class TestAdminServiceTaskManagement:
    """Tests for background task lifecycle management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = FakeMetricsCollector()
        self.config_store = FakeConfigurationStore()
        self.service = AdminService(self.metrics, self.config_store)

    def test_register_task_creates_task_with_pending_status(self):
        """Register task creates a task with pending status."""
        task = self.service.register_task("extract-data")

        assert task.id is not None
        assert task.name == "extract-data"
        assert task.status == BackgroundTaskStatus.PENDING
        assert task.created_at is not None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.error is None
        assert task.result is None

    def test_register_task_with_unique_ids(self):
        """Register task creates tasks with unique IDs."""
        task1 = self.service.register_task("task1")
        task2 = self.service.register_task("task2")

        assert task1.id != task2.id

    def test_get_task_returns_registered_task(self):
        """Get task retrieves a previously registered task."""
        registered = self.service.register_task("process-embeddings")
        retrieved = self.service.get_task(registered.id)

        assert retrieved.id == registered.id
        assert retrieved.name == "process-embeddings"
        assert retrieved.status == BackgroundTaskStatus.PENDING

    def test_get_task_raises_error_for_unknown_id(self):
        """Get task raises TaskNotFoundError for unknown ID."""
        with pytest.raises(TaskNotFoundError) as exc_info:
            self.service.get_task("nonexistent-id")

        assert "Task nonexistent-id not found" in str(exc_info.value)

    def test_list_tasks_returns_all_registered_tasks(self):
        """List tasks returns all registered tasks."""
        task1 = self.service.register_task("task1")
        task2 = self.service.register_task("task2")
        task3 = self.service.register_task("task3")

        tasks = self.service.list_tasks()

        assert len(tasks) == 3
        task_ids = {t.id for t in tasks}
        assert task1.id in task_ids
        assert task2.id in task_ids
        assert task3.id in task_ids

    def test_list_tasks_returns_empty_list_initially(self):
        """List tasks returns empty list when no tasks registered."""
        tasks = self.service.list_tasks()

        assert tasks == []

    def test_update_task_status_to_running(self):
        """Update task status to running sets started_at."""
        task = self.service.register_task("long-running")
        before = datetime.now(timezone.utc)

        updated = self.service.update_task_status(task.id, BackgroundTaskStatus.RUNNING)

        after = datetime.now(timezone.utc)
        assert updated.status == BackgroundTaskStatus.RUNNING
        assert updated.started_at is not None
        assert before <= updated.started_at <= after

    def test_update_task_status_to_completed(self):
        """Update task status to completed sets completed_at and result."""
        task = self.service.register_task("data-processing")
        before = datetime.now(timezone.utc)

        updated = self.service.update_task_status(
            task.id, BackgroundTaskStatus.COMPLETED, result={"processed": 100}
        )

        after = datetime.now(timezone.utc)
        assert updated.status == BackgroundTaskStatus.COMPLETED
        assert updated.completed_at is not None
        assert before <= updated.completed_at <= after
        assert updated.result == {"processed": 100}
        assert updated.error is None

    def test_update_task_status_to_failed(self):
        """Update task status to failed sets completed_at and error."""
        task = self.service.register_task("failing-task")
        before = datetime.now(timezone.utc)

        updated = self.service.update_task_status(
            task.id, BackgroundTaskStatus.FAILED, error="Connection timeout"
        )

        after = datetime.now(timezone.utc)
        assert updated.status == BackgroundTaskStatus.FAILED
        assert updated.completed_at is not None
        assert before <= updated.completed_at <= after
        assert updated.error == "Connection timeout"
        assert updated.result is None

    def test_update_task_status_raises_error_for_unknown_task(self):
        """Update task status raises TaskNotFoundError for unknown task."""
        with pytest.raises(TaskNotFoundError) as exc_info:
            self.service.update_task_status("nonexistent", "running")

        assert "Task nonexistent not found" in str(exc_info.value)

    def test_update_task_status_preserves_in_memory_state(self):
        """Update task status updates the task in-memory."""
        task = self.service.register_task("state-test")
        self.service.update_task_status(task.id, "running")
        retrieved = self.service.get_task(task.id)

        assert retrieved.status == "running"
        assert retrieved.started_at is not None

    def test_task_lifecycle_pending_to_running_to_completed(self):
        """Full task lifecycle: pending → running → completed."""
        task = self.service.register_task("full-lifecycle")
        assert task.status == BackgroundTaskStatus.PENDING

        running = self.service.update_task_status(task.id, BackgroundTaskStatus.RUNNING)
        assert running.status == BackgroundTaskStatus.RUNNING
        assert running.started_at is not None

        completed = self.service.update_task_status(
            task.id, BackgroundTaskStatus.COMPLETED, result={"status": "success"}
        )
        assert completed.status == BackgroundTaskStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.result == {"status": "success"}
