"""
Performance monitoring utilities for tracking operation execution times.

This module provides utilities to monitor and alert on performance metrics
to ensure acceptance criteria are met.
"""

import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric for an operation."""
    operation: str
    execution_time_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)


class PerformanceMonitor:
    """
    Performance monitoring system for tracking operation execution times.

    This system:
    - Records execution times for operations
    - Tracks performance metrics with statistics
    - Alerts when thresholds are exceeded
    - Provides performance reports
    """

    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self.thresholds: Dict[str, float] = {}
        self.alert_callbacks: List[Callable] = []

    def record_metric(
        self,
        operation: str,
        execution_time_ms: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a performance metric.

        Args:
            operation: Name of the operation
            execution_time_ms: Execution time in milliseconds
            metadata: Optional metadata about the operation

        Example:
            >>> monitor = PerformanceMonitor()
            >>> monitor.set_threshold("mapping_update", 100.0)
            >>> monitor.record_metric("mapping_update", 85.5)
        """
        metric = PerformanceMetric(
            operation=operation,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {}
        )

        self.metrics[operation].append(metric)

        # Check threshold
        if operation in self.thresholds:
            threshold = self.thresholds[operation]
            if execution_time_ms > threshold:
                self._alert_threshold_exceeded(metric, threshold)

        logger.debug(
            f"Performance metric recorded: {operation} took {execution_time_ms:.2f}ms"
        )

    def set_threshold(self, operation: str, threshold_ms: float) -> None:
        """
        Set performance threshold for an operation.

        Args:
            operation: Name of the operation
            threshold_ms: Threshold in milliseconds

        Example:
            >>> monitor.set_threshold("mapping_update", 100.0)
            >>> monitor.set_threshold("audit_log_creation", 20.0)
        """
        self.thresholds[operation] = threshold_ms
        logger.info(f"Performance threshold set: {operation} = {threshold_ms}ms")

    def register_alert_callback(self, callback: Callable[[PerformanceMetric, float], None]) -> None:
        """
        Register a callback to be invoked when threshold is exceeded.

        Args:
            callback: Function to call with (metric, threshold) when exceeded

        Example:
            >>> def alert_handler(metric, threshold):
            ...     print(f"ALERT: {metric.operation} exceeded {threshold}ms")
            >>> monitor.register_alert_callback(alert_handler)
        """
        self.alert_callbacks.append(callback)

    def _alert_threshold_exceeded(self, metric: PerformanceMetric, threshold: float) -> None:
        """Alert that a threshold was exceeded."""
        logger.warning(
            f"Performance threshold exceeded: {metric.operation} took "
            f"{metric.execution_time_ms:.2f}ms (threshold: {threshold}ms)"
        )

        for callback in self.alert_callbacks:
            try:
                callback(metric, threshold)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def get_statistics(self, operation: str) -> Optional[Dict]:
        """
        Get performance statistics for an operation.

        Args:
            operation: Name of the operation

        Returns:
            Dictionary with statistics or None if no data

        Example:
            >>> stats = monitor.get_statistics("mapping_update")
            >>> print(f"Average: {stats['avg']:.2f}ms")
        """
        if operation not in self.metrics or not self.metrics[operation]:
            return None

        times = [m.execution_time_ms for m in self.metrics[operation]]
        times_sorted = sorted(times)

        count = len(times)
        p50_index = int(count * 0.50)
        p95_index = int(count * 0.95)
        p99_index = int(count * 0.99)

        return {
            "operation": operation,
            "count": count,
            "min": min(times),
            "max": max(times),
            "avg": sum(times) / count,
            "p50": times_sorted[p50_index] if count > 0 else 0,
            "p95": times_sorted[p95_index] if count > 0 else 0,
            "p99": times_sorted[p99_index] if count > 0 else 0,
            "threshold": self.thresholds.get(operation),
            "threshold_violations": sum(1 for t in times if operation in self.thresholds and t > self.thresholds[operation])
        }

    def get_all_statistics(self) -> Dict[str, Dict]:
        """
        Get performance statistics for all operations.

        Returns:
            Dictionary mapping operation names to their statistics

        Example:
            >>> all_stats = monitor.get_all_statistics()
            >>> for op, stats in all_stats.items():
            ...     print(f"{op}: avg={stats['avg']:.2f}ms")
        """
        return {
            operation: self.get_statistics(operation)
            for operation in self.metrics.keys()
            if self.get_statistics(operation) is not None
        }

    def clear_metrics(self, operation: Optional[str] = None) -> None:
        """
        Clear recorded metrics.

        Args:
            operation: Optional operation name to clear (clears all if None)

        Example:
            >>> monitor.clear_metrics("mapping_update")  # Clear specific operation
            >>> monitor.clear_metrics()  # Clear all operations
        """
        if operation:
            if operation in self.metrics:
                del self.metrics[operation]
                logger.info(f"Cleared metrics for operation: {operation}")
        else:
            self.metrics.clear()
            logger.info("Cleared all metrics")


# Global performance monitor instance
_global_monitor = PerformanceMonitor()


# Configure standard thresholds based on acceptance criteria
_global_monitor.set_threshold("mapping_update", 100.0)  # PT-MAP-001
_global_monitor.set_threshold("batch_creation_10", 500.0)  # PT-MAP-002
_global_monitor.set_threshold("concurrent_update_p95", 200.0)  # PT-MAP-003
_global_monitor.set_threshold("transaction_rollback", 50.0)  # PT-MAP-004
_global_monitor.set_threshold("audit_log_creation", 20.0)  # PT-MAP-005


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return _global_monitor


def record_operation_time(operation: str, execution_time_ms: float, metadata: Optional[Dict] = None) -> None:
    """
    Record an operation execution time.

    This is a convenience function that uses the global monitor.

    Args:
        operation: Name of the operation
        execution_time_ms: Execution time in milliseconds
        metadata: Optional metadata

    Example:
        >>> record_operation_time("mapping_update", 85.5, {"predicate_id": "123"})
    """
    _global_monitor.record_metric(operation, execution_time_ms, metadata)


class PerformanceTimer:
    """
    Context manager for timing operations.

    Example:
        >>> with PerformanceTimer("mapping_update") as timer:
        ...     # Perform operation
        ...     update_mapping()
        ...     timer.metadata["predicate_id"] = "123"
        # Automatically records metric on exit
    """

    def __init__(self, operation: str, monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize performance timer.

        Args:
            operation: Name of the operation to time
            monitor: Optional monitor instance (uses global if None)
        """
        self.operation = operation
        self.monitor = monitor or _global_monitor
        self.start_time: Optional[float] = None
        self.metadata: Dict = {}

    def __enter__(self):
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and record metric."""
        if self.start_time:
            elapsed_ms = (time.perf_counter() - self.start_time) * 1000
            self.monitor.record_metric(self.operation, elapsed_ms, self.metadata)
        return False  # Don't suppress exceptions
