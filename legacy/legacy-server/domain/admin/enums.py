"""
Domain value enums for the admin bounded context.

Enums represent domain concepts in the admin bounded context.
They are immutable and framework-free, depending only on Python stdlib.
"""

from enum import Enum


class SystemHealthStatus(str, Enum):
    """
    Enumeration of system health statuses.

    Attributes:
        HEALTHY: System is operating normally
        DEGRADED: System is functional but experiencing some issues
        UNHEALTHY: System is not functioning properly or experiencing critical issues
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BackgroundTaskStatus(str, Enum):
    """
    Enumeration of background task statuses.

    Attributes:
        PENDING: Task has been queued but not yet started
        RUNNING: Task is currently executing
        COMPLETED: Task completed successfully
        FAILED: Task failed with an error
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BackgroundTaskType(str, Enum):
    """
    Enumeration of background task types.

    Attributes:
        SYNC: Data synchronization task
        EMBEDDING: Embedding generation task
        EXPORT: Data export task
        IMPORT: Data import task
        MAINTENANCE: System maintenance task
        BACKUP: System backup task
    """

    SYNC = "sync"
    EMBEDDING = "embedding"
    EXPORT = "export"
    IMPORT = "import"
    MAINTENANCE = "maintenance"
    BACKUP = "backup"


class LogLevel(str, Enum):
    """
    Enumeration of logging levels.

    Attributes:
        DEBUG: Detailed information for debugging
        INFO: General informational messages
        WARNING: Warning messages for potentially problematic situations
        ERROR: Error messages for serious problems
        CRITICAL: Critical messages for very serious problems
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
