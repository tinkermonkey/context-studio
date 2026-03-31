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
from domain.admin.exceptions import ConfigurationError, TaskNotFoundError
from tests.fakes.fake_metrics_collector import FakeMetricsCollector
from tests.fakes.fake_configuration_store import FakeConfigurationStore


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

        assert health.status == "healthy"
        assert health.database_connected is True
        assert health.nlp_pipeline_ready is True
        assert health.embedding_model_loaded is True
        assert health.llm_providers_available == []
        assert health.uptime_seconds == 0.0
        assert health.checked_at is not None
        assert health.issues == []

    def test_check_health_with_degraded_status(self):
        """Check health can return degraded status."""
        degraded_health = SystemHealth(
            status="degraded",
            database_connected=True,
            nlp_pipeline_ready=False,
            embedding_model_loaded=True,
            llm_providers_available=["openai"],
            uptime_seconds=3600.0,
            checked_at=datetime.now(timezone.utc),
            issues=["NLP pipeline not responding"],
        )
        metrics = FakeMetricsCollector(health=degraded_health)
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.status == "degraded"
        assert health.nlp_pipeline_ready is False
        assert health.issues == ["NLP pipeline not responding"]

    def test_check_health_with_unhealthy_status(self):
        """Check health can return unhealthy status."""
        unhealthy_health = SystemHealth(
            status="unhealthy",
            database_connected=False,
            nlp_pipeline_ready=False,
            embedding_model_loaded=False,
            llm_providers_available=[],
            uptime_seconds=0.0,
            checked_at=datetime.now(timezone.utc),
            issues=["Database disconnected", "No LLM providers available"],
        )
        metrics = FakeMetricsCollector(health=unhealthy_health)
        service = AdminService(metrics, self.config_store)

        health = service.check_health()

        assert health.status == "unhealthy"
        assert health.database_connected is False
        assert len(health.issues) == 2


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
        assert task.status == "pending"
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
        assert retrieved.status == "pending"

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

        updated = self.service.update_task_status(task.id, "running")

        after = datetime.now(timezone.utc)
        assert updated.status == "running"
        assert updated.started_at is not None
        assert before <= updated.started_at <= after

    def test_update_task_status_to_completed(self):
        """Update task status to completed sets completed_at and result."""
        task = self.service.register_task("data-processing")
        before = datetime.now(timezone.utc)

        updated = self.service.update_task_status(
            task.id, "completed", result={"processed": 100}
        )

        after = datetime.now(timezone.utc)
        assert updated.status == "completed"
        assert updated.completed_at is not None
        assert before <= updated.completed_at <= after
        assert updated.result == {"processed": 100}
        assert updated.error is None

    def test_update_task_status_to_failed(self):
        """Update task status to failed sets completed_at and error."""
        task = self.service.register_task("failing-task")
        before = datetime.now(timezone.utc)

        updated = self.service.update_task_status(
            task.id, "failed", error="Connection timeout"
        )

        after = datetime.now(timezone.utc)
        assert updated.status == "failed"
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
        assert task.status == "pending"

        running = self.service.update_task_status(task.id, "running")
        assert running.status == "running"
        assert running.started_at is not None

        completed = self.service.update_task_status(
            task.id, "completed", result={"status": "success"}
        )
        assert completed.status == "completed"
        assert completed.completed_at is not None
        assert completed.result == {"status": "success"}
