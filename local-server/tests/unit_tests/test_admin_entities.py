"""
Unit tests for admin domain entities.

Tests validate invariant enforcement, enum usage, and immutability of
system health, background task, and application configuration entities.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import types
import pytest

from domain.admin.entities import SystemHealth, BackgroundTask, AppConfiguration
from domain.admin.enums import (
    SystemHealthStatus,
    BackgroundTaskStatus,
    BackgroundTaskType,
    LogLevel
)


class TestSystemHealthStatus:
    """Tests for SystemHealthStatus enum."""

    def test_system_health_status_values(self):
        """Test that SystemHealthStatus has all expected values."""
        assert SystemHealthStatus.HEALTHY.value == "healthy"
        assert SystemHealthStatus.DEGRADED.value == "degraded"
        assert SystemHealthStatus.UNHEALTHY.value == "unhealthy"


class TestBackgroundTaskStatus:
    """Tests for BackgroundTaskStatus enum."""

    def test_background_task_status_values(self):
        """Test that BackgroundTaskStatus has all expected values."""
        assert BackgroundTaskStatus.PENDING.value == "pending"
        assert BackgroundTaskStatus.RUNNING.value == "running"
        assert BackgroundTaskStatus.COMPLETED.value == "completed"
        assert BackgroundTaskStatus.FAILED.value == "failed"


class TestBackgroundTaskType:
    """Tests for BackgroundTaskType enum."""

    def test_background_task_type_values(self):
        """Test that BackgroundTaskType has all expected values."""
        assert BackgroundTaskType.SYNC.value == "sync"
        assert BackgroundTaskType.EMBEDDING.value == "embedding"
        assert BackgroundTaskType.EXPORT.value == "export"
        assert BackgroundTaskType.IMPORT.value == "import"
        assert BackgroundTaskType.MAINTENANCE.value == "maintenance"
        assert BackgroundTaskType.BACKUP.value == "backup"


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_level_values(self):
        """Test that LogLevel has all expected values."""
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.CRITICAL.value == "critical"


class TestSystemHealth:
    """Tests for SystemHealth entity."""

    def test_valid_system_health_healthy(self):
        """Test creating a healthy system health entity."""
        health = SystemHealth(
            status=SystemHealthStatus.HEALTHY,
            database_ok=True,
            embedding_service_ok=True,
            details=types.MappingProxyType({"uptime": "99.9%"})
        )
        assert health.status == SystemHealthStatus.HEALTHY
        assert health.database_ok is True
        assert health.embedding_service_ok is True

    def test_valid_system_health_degraded(self):
        """Test creating a degraded system health entity."""
        health = SystemHealth(
            status=SystemHealthStatus.DEGRADED,
            database_ok=True,
            embedding_service_ok=False,
            details=types.MappingProxyType({"issue": "embedding service slow"})
        )
        assert health.status == SystemHealthStatus.DEGRADED
        assert health.embedding_service_ok is False

    def test_system_health_with_dict_details_raises_error(self):
        """Test that plain dict details raises TypeError."""
        with pytest.raises(TypeError, match="details must be a MappingProxyType"):
            SystemHealth(
                status=SystemHealthStatus.HEALTHY,
                database_ok=True,
                embedding_service_ok=True,
                details={"uptime": "99.9%"}
            )

    def test_system_health_details_immutable(self):
        """Test that details are immutable."""
        health = SystemHealth(
            status=SystemHealthStatus.HEALTHY,
            database_ok=True,
            embedding_service_ok=True,
            details=types.MappingProxyType({"uptime": "99.9%"})
        )
        with pytest.raises(TypeError):
            health.details["uptime"] = "99.5%"

    def test_system_health_invalid_status(self):
        """Test that non-enum status raises TypeError."""
        with pytest.raises(TypeError, match="status must be a SystemHealthStatus enum"):
            SystemHealth(
                status="healthy",  # String instead of enum
                database_ok=True,
                embedding_service_ok=True
            )

    def test_system_health_invalid_database_ok(self):
        """Test that non-boolean database_ok raises TypeError."""
        with pytest.raises(TypeError, match="database_ok must be a boolean"):
            SystemHealth(
                status=SystemHealthStatus.HEALTHY,
                database_ok="true",  # String instead of boolean
                embedding_service_ok=True
            )

    def test_system_health_invalid_embedding_service_ok(self):
        """Test that non-boolean embedding_service_ok raises TypeError."""
        with pytest.raises(TypeError, match="embedding_service_ok must be a boolean"):
            SystemHealth(
                status=SystemHealthStatus.HEALTHY,
                database_ok=True,
                embedding_service_ok=1  # Integer instead of boolean
            )


class TestBackgroundTask:
    """Tests for BackgroundTask entity."""

    def test_valid_background_task_pending(self):
        """Test creating a valid pending background task."""
        task = BackgroundTask(
            id="task-1",
            task_type=BackgroundTaskType.SYNC,
            status=BackgroundTaskStatus.PENDING,
            progress=0.0,
            created_at="2025-03-06T00:00:00Z",
            completed_at=None,
            error=None
        )
        assert task.id == "task-1"
        assert task.task_type == BackgroundTaskType.SYNC
        assert task.status == BackgroundTaskStatus.PENDING
        assert task.progress == 0.0

    def test_valid_background_task_running(self):
        """Test creating a running background task."""
        task = BackgroundTask(
            id="task-1",
            task_type=BackgroundTaskType.EMBEDDING,
            status=BackgroundTaskStatus.RUNNING,
            progress=0.5,
            created_at="2025-03-06T00:00:00Z",
            completed_at=None,
            error=None
        )
        assert task.task_type == BackgroundTaskType.EMBEDDING
        assert task.progress == 0.5

    def test_valid_background_task_completed(self):
        """Test creating a completed background task."""
        task = BackgroundTask(
            id="task-1",
            task_type=BackgroundTaskType.EXPORT,
            status=BackgroundTaskStatus.COMPLETED,
            progress=1.0,
            created_at="2025-03-06T00:00:00Z",
            completed_at="2025-03-06T00:05:00Z",
            error=None
        )
        assert task.status == BackgroundTaskStatus.COMPLETED
        assert task.progress == 1.0
        assert task.completed_at == "2025-03-06T00:05:00Z"

    def test_valid_background_task_failed(self):
        """Test creating a failed background task."""
        task = BackgroundTask(
            id="task-1",
            task_type=BackgroundTaskType.IMPORT,
            status=BackgroundTaskStatus.FAILED,
            progress=0.3,
            created_at="2025-03-06T00:00:00Z",
            completed_at="2025-03-06T00:01:00Z",
            error="Import file not found"
        )
        assert task.status == BackgroundTaskStatus.FAILED
        assert task.error == "Import file not found"

    def test_background_task_progress_validation(self):
        """Test that progress must be between 0.0 and 1.0."""
        # Valid: 0.0
        task = BackgroundTask(
            id="task-1",
            task_type=BackgroundTaskType.SYNC,
            status=BackgroundTaskStatus.PENDING,
            progress=0.0,
            created_at="2025-03-06T00:00:00Z"
        )
        assert task.progress == 0.0

        # Valid: 1.0
        task = BackgroundTask(
            id="task-1",
            task_type=BackgroundTaskType.SYNC,
            status=BackgroundTaskStatus.COMPLETED,
            progress=1.0,
            created_at="2025-03-06T00:00:00Z"
        )
        assert task.progress == 1.0

        # Invalid: > 1.0
        with pytest.raises(ValueError, match="progress must be a number between 0.0 and 1.0"):
            BackgroundTask(
                id="task-1",
                task_type=BackgroundTaskType.SYNC,
                status=BackgroundTaskStatus.RUNNING,
                progress=1.5,
                created_at="2025-03-06T00:00:00Z"
            )

        # Invalid: < 0.0
        with pytest.raises(ValueError, match="progress must be a number between 0.0 and 1.0"):
            BackgroundTask(
                id="task-1",
                task_type=BackgroundTaskType.SYNC,
                status=BackgroundTaskStatus.PENDING,
                progress=-0.1,
                created_at="2025-03-06T00:00:00Z"
            )

        # Invalid: bool (even though bool is subclass of int)
        with pytest.raises(ValueError, match="progress must be a number between 0.0 and 1.0"):
            BackgroundTask(
                id="task-1",
                task_type=BackgroundTaskType.SYNC,
                status=BackgroundTaskStatus.PENDING,
                progress=True,
                created_at="2025-03-06T00:00:00Z"
            )

    def test_background_task_invalid_id(self):
        """Test that empty id raises ValueError."""
        with pytest.raises(ValueError, match="BackgroundTask id must be a non-empty string"):
            BackgroundTask(
                id="",
                task_type=BackgroundTaskType.SYNC,
                status=BackgroundTaskStatus.PENDING,
                progress=0.0,
                created_at="2025-03-06T00:00:00Z"
            )

    def test_background_task_invalid_task_type(self):
        """Test that non-enum task_type raises TypeError."""
        with pytest.raises(TypeError, match="task_type must be a BackgroundTaskType enum"):
            BackgroundTask(
                id="task-1",
                task_type="sync",  # String instead of enum
                status=BackgroundTaskStatus.PENDING,
                progress=0.0,
                created_at="2025-03-06T00:00:00Z"
            )

    def test_background_task_invalid_status(self):
        """Test that non-enum status raises TypeError."""
        with pytest.raises(TypeError, match="status must be a BackgroundTaskStatus enum"):
            BackgroundTask(
                id="task-1",
                task_type=BackgroundTaskType.SYNC,
                status="pending",  # String instead of enum
                progress=0.0,
                created_at="2025-03-06T00:00:00Z"
            )

    def test_background_task_invalid_created_at(self):
        """Test that empty created_at raises ValueError."""
        with pytest.raises(ValueError, match="BackgroundTask created_at must be a non-empty timestamp string"):
            BackgroundTask(
                id="task-1",
                task_type=BackgroundTaskType.SYNC,
                status=BackgroundTaskStatus.PENDING,
                progress=0.0,
                created_at=""
            )


class TestAppConfiguration:
    """Tests for AppConfiguration entity."""

    def test_valid_app_configuration(self):
        """Test creating a valid application configuration."""
        config = AppConfiguration(
            llm_provider="openai",
            embedding_model="text-embedding-3-small",
            database_path="/path/to/local.db",
            log_level=LogLevel.INFO,
            extra=types.MappingProxyType({"timeout": 30})
        )
        assert config.llm_provider == "openai"
        assert config.embedding_model == "text-embedding-3-small"
        assert config.database_path == "/path/to/local.db"
        assert config.log_level == LogLevel.INFO

    def test_app_configuration_all_log_levels(self):
        """Test application configuration with all log levels."""
        for log_level in LogLevel:
            config = AppConfiguration(
                llm_provider="anthropic",
                embedding_model="claude-embeddings",
                database_path="/db",
                log_level=log_level
            )
            assert config.log_level == log_level

    def test_app_configuration_with_dict_extra_raises_error(self):
        """Test that plain dict extra raises TypeError."""
        with pytest.raises(TypeError, match="extra must be a MappingProxyType"):
            AppConfiguration(
                llm_provider="openai",
                embedding_model="text-embedding-3-small",
                database_path="/path/to/local.db",
                log_level=LogLevel.DEBUG,
                extra={"timeout": 30, "retries": 3}
            )

    def test_app_configuration_extra_immutable(self):
        """Test that extra is immutable."""
        config = AppConfiguration(
            llm_provider="openai",
            embedding_model="text-embedding-3-small",
            database_path="/path/to/local.db",
            log_level=LogLevel.INFO,
            extra=types.MappingProxyType({"timeout": 30})
        )
        with pytest.raises(TypeError):
            config.extra["timeout"] = 60

    def test_app_configuration_invalid_llm_provider(self):
        """Test that empty llm_provider raises ValueError."""
        with pytest.raises(ValueError, match="llm_provider must be a non-empty string"):
            AppConfiguration(
                llm_provider="",
                embedding_model="text-embedding-3-small",
                database_path="/path/to/local.db",
                log_level=LogLevel.INFO
            )

    def test_app_configuration_invalid_embedding_model(self):
        """Test that empty embedding_model raises ValueError."""
        with pytest.raises(ValueError, match="embedding_model must be a non-empty string"):
            AppConfiguration(
                llm_provider="openai",
                embedding_model="",
                database_path="/path/to/local.db",
                log_level=LogLevel.INFO
            )

    def test_app_configuration_invalid_database_path(self):
        """Test that empty database_path raises ValueError."""
        with pytest.raises(ValueError, match="database_path must be a non-empty string"):
            AppConfiguration(
                llm_provider="openai",
                embedding_model="text-embedding-3-small",
                database_path="",
                log_level=LogLevel.INFO
            )

    def test_app_configuration_invalid_log_level(self):
        """Test that non-enum log_level raises TypeError."""
        with pytest.raises(TypeError, match="log_level must be a LogLevel enum"):
            AppConfiguration(
                llm_provider="openai",
                embedding_model="text-embedding-3-small",
                database_path="/path/to/local.db",
                log_level="info"  # String instead of enum
            )
