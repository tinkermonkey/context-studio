"""Metrics and monitoring for schema.org operations."""

import os
import time
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from utils.logger import get_logger

logger = get_logger(__name__)

# Configuration for metrics logging verbosity
METRICS_LOGGING_ENABLED = os.getenv("SCHEMA_ORG_METRICS_LOGGING", "true").lower() == "true"


@dataclass
class ImportMetrics:
    """Metrics for schema.org import operations."""

    duration_seconds: float
    entity_count: int
    property_count: int
    embedding_failures: int = 0
    retry_counts: int = 0
    download_duration_seconds: float = 0.0
    parse_duration_seconds: float = 0.0
    populate_duration_seconds: float = 0.0
    total_embeddings_generated: int = 0
    peak_memory_mb: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging."""
        return asdict(self)

    def log(self) -> None:
        """Log metrics to the logger."""
        if METRICS_LOGGING_ENABLED:
            logger.info(
                "Schema.org import metrics: duration=%.2fs, entities=%d, properties=%d, "
                "embeddings=%d, failures=%d, retries=%d, peak_memory=%.2fMB",
                self.duration_seconds,
                self.entity_count,
                self.property_count,
                self.total_embeddings_generated,
                self.embedding_failures,
                self.retry_counts,
                self.peak_memory_mb or 0.0
            )


@dataclass
class SearchMetrics:
    """Metrics for schema.org search operations."""

    query_time_ms: float
    result_count: int
    search_type: str  # "text", "semantic", or "combined"
    threshold: Optional[float] = None
    limit: int = 20

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging."""
        return asdict(self)

    def log(self) -> None:
        """Log metrics to the logger."""
        if METRICS_LOGGING_ENABLED:
            logger.debug(
                "Schema.org search metrics: type=%s, query_time=%.2fms, results=%d, limit=%d",
                self.search_type,
                self.query_time_ms,
                self.result_count,
                self.limit
            )


class MetricsTracker:
    """Context manager for tracking operation metrics.

    Thread-safe for concurrent operation tracking.
    """

    _lock = threading.Lock()

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        with self._lock:
            self.start_time = time.perf_counter()
            logger.debug("Starting %s", self.operation_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with self._lock:
            self.end_time = time.perf_counter()
            duration = self.end_time - self.start_time

            if exc_type is None:
                logger.debug("%s completed in %.2fs", self.operation_name, duration)
            else:
                logger.warning("%s failed after %.2fs: %s", self.operation_name, duration, exc_val)

        return False  # Don't suppress exceptions

    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        with self._lock:
            if self.end_time is None:
                return time.perf_counter() - self.start_time
            return self.end_time - self.start_time
