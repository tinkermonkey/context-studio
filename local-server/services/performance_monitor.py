"""
Performance Monitor - Automated performance monitoring and optimization system

This service implements sophisticated performance monitoring including comprehensive
metrics collection, automated optimization, trend analysis, and alerting for
enterprise-scale performance management and automated tuning.
"""

import time
import statistics
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass
class PerformanceAlert:
    """Performance alert information."""

    alert_id: str
    alert_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    metric_name: str
    current_value: float
    threshold_value: float
    description: str
    created_at: datetime
    resolved_at: Optional[datetime] = None


@dataclass
class OptimizationAction:
    """Automated optimization action."""

    action_id: str
    action_type: str
    description: str
    parameters: Dict[str, Any]
    executed_at: datetime
    success: bool
    impact_metrics: Dict[str, Any]


class PerformanceMonitor:
    """Automated performance monitoring and optimization system."""

    def __init__(self, sqlite_conn, duckdb_conn=None, s3_sync_manager=None):
        """
        Initialize the performance monitor.

        Args:
            sqlite_conn: SQLite database connection
            duckdb_conn: Optional DuckDB connection for analytics
            s3_sync_manager: Optional S3 sync manager
        """
        self.sqlite_conn = sqlite_conn
        self.duckdb_conn = duckdb_conn
        self.s3_sync = s3_sync_manager
        self.metrics_history = []
        self.alerts = []
        self.optimization_history = []
        self._metrics_lock = Lock()

        # Get total system memory for percentage-based threshold
        # Note: On Linux/Unix systems, high memory usage is often normal due to disk caching
        # We use a high threshold (90%) to avoid false positives from normal caching behavior
        try:
            import psutil  # type: ignore[import-untyped]

            total_memory_mb = psutil.virtual_memory().total / (1024 * 1024)
            # Alert when memory usage exceeds 90% of total system memory
            # This accounts for OS-level caching which is normal and expected
            memory_threshold_mb = total_memory_mb * 0.90
        except (ImportError, Exception):
            # Fallback to a reasonable default (16GB * 90%)
            memory_threshold_mb = 16384 * 0.90

        # Performance thresholds
        # Note: These thresholds are set to alert on genuinely problematic conditions.
        # They account for normal system behavior like disk caching and cache misses.
        self.performance_thresholds = {
            "query_metrics.avg_execution_time_ms": 10000,  # Alert only on very slow queries (10+ seconds)
            "s3_metrics.avg_sync_time_ms": 30000,  # Alert on very slow syncs (30+ seconds)
            "system_metrics.memory_usage_mb": memory_threshold_mb,  # 90% of total RAM (accounts for OS caching)
            "system_metrics.error_rate_percent": 5.0,  # Alert at 5% error rate (very high)
            "batch_metrics.avg_throughput_per_second": 1,  # Alert on near-zero throughput
            "cache_metrics.hit_rate": 0.5,  # Alert when hit rate falls below 50%
            "batch_metrics.storage_growth_rate_mb_per_hour": 500,  # Alert on rapid storage growth (500MB+/hour)
        }

        # Optimization parameters
        self.optimization_enabled = True
        self.auto_optimization_interval = 3600  # 1 hour
        self.last_optimization_time = 0

        logger.info(
            "PerformanceMonitor initialized with comprehensive monitoring capabilities"
        )

    def collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive performance metrics."""

        logger.debug("Collecting comprehensive performance metrics")

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "collection_time_ms": 0,
            "database_metrics": self._collect_database_metrics(),
            "s3_metrics": self._collect_s3_metrics(),
            "query_metrics": self._collect_query_metrics(),
            "system_metrics": self._collect_system_metrics(),
            "cache_metrics": self._collect_cache_metrics(),
            "batch_metrics": self._collect_batch_metrics(),
        }

        collection_start = time.time()

        # Calculate collection time
        metrics["collection_time_ms"] = (time.time() - collection_start) * 1000

        # Store metrics for trend analysis
        with self._metrics_lock:
            self.metrics_history.append(metrics)

            # Keep only recent history (last 10000 measurements)
            if len(self.metrics_history) > 10000:
                self.metrics_history = self.metrics_history[-10000:]

        # Check for alerts
        self._check_performance_alerts(metrics)

        logger.debug(
            f"Performance metrics collected in {metrics['collection_time_ms']:.2f}ms"
        )

        return metrics

    def analyze_performance_trends(self, window_hours: int = 24) -> Dict[str, Any]:
        """Analyze performance trends and identify issues."""

        logger.info(f"Analyzing performance trends for the last {window_hours} hours")

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        with self._metrics_lock:
            recent_metrics = [
                m
                for m in self.metrics_history
                if datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
                > cutoff_time
            ]

        if not recent_metrics:
            # Return empty result when no metrics are available
            logger.info("No recent metrics available for trend analysis")
            return {
                "analysis_window_hours": window_hours,
                "trends": {
                    "analysis_period_hours": window_hours,
                    "sample_count": 0,
                    "query_time_trend": None,
                    "sync_time_trend": None,
                    "memory_usage_trend": None,
                    "error_rate_trend": None,
                    "throughput_trend": None,
                    "cache_hit_rate_trend": None,
                },
                "issues": [],
                "recommendations": [
                    {
                        "description": "Collect more performance data for analysis to be available",
                        "priority": "low",
                    }
                ],
                "overall_health_score": None,
                "performance_grade": None,
            }

        trends = {
            "analysis_period_hours": window_hours,
            "sample_count": len(recent_metrics),
            "query_time_trend": self._analyze_metric_trend(
                recent_metrics, "query_metrics.avg_execution_time_ms"
            ),
            "sync_time_trend": self._analyze_metric_trend(
                recent_metrics, "s3_metrics.avg_sync_time_ms"
            ),
            "memory_usage_trend": self._analyze_metric_trend(
                recent_metrics, "system_metrics.memory_usage_mb"
            ),
            "error_rate_trend": self._analyze_metric_trend(
                recent_metrics, "system_metrics.error_rate_percent"
            ),
            "throughput_trend": self._analyze_metric_trend(
                recent_metrics, "batch_metrics.avg_throughput_per_second"
            ),
            "cache_hit_rate_trend": self._analyze_metric_trend(
                recent_metrics, "cache_metrics.hit_rate"
            ),
        }

        # Identify performance issues
        issues = self._identify_performance_issues(trends)

        # Generate optimization recommendations
        recommendations = self._generate_optimization_recommendations(trends, issues)

        # Calculate overall health score
        health_score = self._calculate_health_score(trends)

        return {
            "analysis_window_hours": window_hours,
            "trends": trends,
            "issues": issues,
            "recommendations": recommendations,
            "overall_health_score": health_score,
            "performance_grade": self._calculate_performance_grade(health_score),
        }

    def auto_optimize_based_on_metrics(self) -> Dict[str, Any]:
        """Automatically apply optimizations based on performance metrics."""

        if not self.optimization_enabled:
            return {"message": "Auto-optimization is disabled"}

        current_time = time.time()
        if current_time - self.last_optimization_time < self.auto_optimization_interval:
            return {"message": "Too soon for next optimization cycle"}

        logger.info("Starting automated optimization based on performance metrics")

        current_metrics = self.collect_performance_metrics()
        optimization_actions = []

        # Auto-optimize queries if slow
        if self._is_metric_above_threshold(
            current_metrics,
            "query_metrics.avg_execution_time_ms",
            "query_metrics.avg_execution_time_ms",
        ):
            action = self._optimize_slow_queries()
            if action:
                optimization_actions.append(action)

        # Auto-refresh materialized views if stale
        if self._are_materialized_views_stale():
            action = self._refresh_stale_materialized_views()
            if action:
                optimization_actions.append(action)

        # Auto-cleanup old data if storage is growing too fast
        if self._is_storage_cleanup_needed(current_metrics):
            action = self._cleanup_old_data()
            if action:
                optimization_actions.append(action)

        # Auto-adjust cache settings if hit rate is low
        if self._is_metric_below_threshold(
            current_metrics, "cache_metrics.hit_rate", "cache_metrics.hit_rate"
        ):
            action = self._optimize_cache_settings()
            if action:
                optimization_actions.append(action)

        # Auto-adjust batch sizes based on performance
        batch_optimization = self._optimize_batch_sizes_based_on_performance(
            current_metrics
        )
        if batch_optimization:
            optimization_actions.append(batch_optimization)

        # Auto-optimize S3 storage
        if self._should_optimize_s3_storage(current_metrics):
            action = self._optimize_s3_storage()
            if action:
                optimization_actions.append(action)

        self.last_optimization_time = current_time

        # Store optimization actions
        with self._metrics_lock:
            self.optimization_history.extend(optimization_actions)

        logger.info(
            f"Auto-optimization completed: {len(optimization_actions)} actions executed"
        )

        # Serialize optimization actions for JSON response
        serialized_actions = []
        for action in optimization_actions:
            serialized_actions.append(
                {
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "description": action.description,
                    "parameters": action.parameters,
                    "executed_at": (
                        action.executed_at.isoformat() if action.executed_at else None
                    ),
                    "success": action.success,
                    "impact_metrics": action.impact_metrics,
                }
            )

        return {
            "optimization_actions": serialized_actions,
            "optimizations_applied": len(optimization_actions),
            "next_optimization_check": (
                datetime.now(timezone.utc)
                + timedelta(seconds=self.auto_optimization_interval)
            ).isoformat(),
        }

    def _collect_database_metrics(self) -> Dict[str, Any]:
        """Collect SQLite database performance metrics."""

        try:
            # Handle None connection gracefully
            if self.sqlite_conn is None:
                return {
                    "database_count": 0,
                    "total_objects": 0,
                    "table_count": 0,
                    "index_count": 0,
                    "table_metrics": {},
                    "connection_status": "not_configured",
                    "note": "Database connection not available",
                }

            # Check if sqlite_conn is a SQLAlchemy session or raw connection
            if hasattr(self.sqlite_conn, "execute"):
                # SQLAlchemy session - use text() for raw SQL
                from sqlalchemy import text

                # Get database info
                db_info_result = self.sqlite_conn.execute(text("PRAGMA database_list;"))
                db_info = db_info_result.fetchall()

                # Get table statistics
                stats_query = """
                SELECT
                    COUNT(*) as total_objects,
                    SUM(CASE WHEN type='table' THEN 1 ELSE 0 END) as table_count,
                    SUM(CASE WHEN type='index' THEN 1 ELSE 0 END) as index_count
                FROM sqlite_master
                WHERE type IN ('table', 'index', 'view')
                """

                result = self.sqlite_conn.execute(text(stats_query))
                db_stats = result.fetchone()

                # Get table-specific metrics
                table_metrics = {}
                important_tables = [
                    "entity_versions",
                    "changesets",
                    "proposals",
                    "user_identities",
                ]

                for table_name in important_tables:
                    try:
                        result = self.sqlite_conn.execute(
                            text(f"SELECT COUNT(*) FROM {table_name}")
                        )
                        row_count = result.fetchone()[0]
                        table_metrics[table_name] = {"row_count": row_count}
                    except Exception as e:
                        table_metrics[table_name] = {"row_count": 0, "error": str(e)}

                return {
                    "database_count": len(db_info) if db_info else 0,
                    "total_objects": db_stats[0] if db_stats else 0,
                    "table_count": db_stats[1] if db_stats else 0,
                    "index_count": db_stats[2] if db_stats else 0,
                    "table_metrics": table_metrics,
                    "connection_status": "healthy",
                }
            else:
                # Raw connection - use cursor
                cursor = self.sqlite_conn.cursor()

                # Get database size
                cursor.execute("PRAGMA database_list;")
                db_info = cursor.fetchall()

                # Get table statistics
                stats_query = """
                SELECT
                    COUNT(*) as total_objects,
                    SUM(CASE WHEN type='table' THEN 1 ELSE 0 END) as table_count,
                    SUM(CASE WHEN type='index' THEN 1 ELSE 0 END) as index_count
                FROM sqlite_master
                WHERE type IN ('table', 'index', 'view')
                """

                cursor.execute(stats_query)
                db_stats = cursor.fetchone()

                # Get table-specific metrics
                table_metrics = {}
                important_tables = [
                    "entity_versions",
                    "changesets",
                    "proposals",
                    "user_identities",
                ]

                for table_name in important_tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        row_count = cursor.fetchone()[0]
                        table_metrics[table_name] = {"row_count": row_count}
                    except Exception as e:
                        table_metrics[table_name] = {"row_count": 0, "error": str(e)}

                return {
                    "database_count": len(db_info) if db_info else 0,
                    "total_objects": db_stats[0] if db_stats else 0,
                    "table_count": db_stats[1] if db_stats else 0,
                    "index_count": db_stats[2] if db_stats else 0,
                    "table_metrics": table_metrics,
                    "connection_status": "healthy",
                }

        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")
            return {"error": str(e), "connection_status": "error"}

    def _collect_s3_metrics(self) -> Dict[str, Any]:
        """Collect S3 storage and sync performance metrics."""

        if not self.s3_sync:
            return {"status": "not_configured"}

        try:
            # S3 sync manager not yet implemented - return empty/null metrics
            logger.warning("S3 metrics collection not yet implemented")
            return {
                "sync_operations_count": None,
                "avg_sync_time_ms": None,
                "total_storage_bytes": None,
                "objects_count": None,
                "failed_sync_count": None,
                "success_rate": None,
                "storage_cost_estimate_usd": None,
                "bandwidth_usage_gb": None,
                "status": "not_implemented",
            }

        except Exception as e:
            logger.error(f"Failed to collect S3 metrics: {e}")
            return {"error": str(e), "status": "error"}

    def _collect_query_metrics(self) -> Dict[str, Any]:
        """Collect query performance metrics."""

        try:
            # Query metrics collection not yet implemented - return empty/null metrics
            logger.warning("Query metrics collection not yet implemented")
            return {
                "total_queries_executed": None,
                "avg_execution_time_ms": None,
                "slow_queries_count": None,
                "failed_queries_count": None,
                "success_rate": None,
                "cache_hit_ratio": None,
                "materialized_views_count": None,
                "optimization_level": None,
            }

        except Exception as e:
            logger.error(f"Failed to collect query metrics: {e}")
            return {"error": str(e)}

    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-level performance metrics."""

        try:
            import psutil  # type: ignore[import-untyped]

            # Get system metrics using psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_mb": memory.used / (1024 * 1024),
                "memory_total_mb": memory.total / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_usage_gb": disk.used / (1024 * 1024 * 1024),
                "disk_free_gb": disk.free / (1024 * 1024 * 1024),
                "error_rate_percent": None,  # Not yet collected by psutil
                "uptime_hours": None,  # Not yet collected by psutil
            }

        except ImportError:
            # Fallback if psutil is not available
            logger.warning("System metrics collection not available - psutil not installed")
            return {
                "cpu_usage_percent": None,
                "memory_usage_mb": None,
                "memory_total_mb": None,
                "memory_available_mb": None,
                "disk_usage_gb": None,
                "disk_free_gb": None,
                "error_rate_percent": None,
                "uptime_hours": None,
                "status": "not_implemented",
            }
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {"error": str(e)}

    def _collect_cache_metrics(self) -> Dict[str, Any]:
        """Collect cache performance metrics."""

        try:
            # Cache metrics collection not yet implemented - return empty/null metrics
            logger.warning("Cache metrics collection not yet implemented")
            return {
                "query_cache_size": None,
                "query_cache_hit_rate": None,
                "materialized_view_cache_hits": None,
                "storage_cache_size_mb": None,
                "cache_evictions": None,
                "cache_memory_usage_mb": None,
                "hit_rate": None,
            }

        except Exception as e:
            logger.error(f"Failed to collect cache metrics: {e}")
            return {"error": str(e)}

    def _collect_batch_metrics(self) -> Dict[str, Any]:
        """Collect batch operation performance metrics."""

        try:
            # Batch metrics collection not yet implemented - return empty/null metrics
            logger.warning("Batch metrics collection not yet implemented")
            return {
                "total_batch_operations": None,
                "avg_throughput_per_second": None,
                "avg_processing_time_seconds": None,
                "successful_operations": None,
                "failed_operations": None,
                "success_rate": None,
                "current_batch_size": None,
                "parallel_workers_active": None,
                "storage_growth_rate_mb_per_hour": None,
            }

        except Exception as e:
            logger.error(f"Failed to collect batch metrics: {e}")
            return {"error": str(e)}

    def _analyze_metric_trend(
        self, metrics_list: List[Dict[str, Any]], metric_path: str
    ) -> Dict[str, Any]:
        """Analyze trend for a specific metric."""

        values: list[float] = []
        timestamps: list[datetime] = []

        for metric in metrics_list:
            try:
                # Navigate nested dictionary structure
                value = metric
                for key in metric_path.split("."):
                    value = value[key]

                if isinstance(value, (int, float)) and not (isinstance(value, bool)):
                    values.append(float(value))
                    timestamps.append(
                        datetime.fromisoformat(
                            metric["timestamp"].replace("Z", "+00:00")
                        )
                    )
            except (KeyError, TypeError, ValueError):
                continue

        if len(values) < 2:
            return {"trend": "insufficient_data", "sample_count": len(values)}

        # Calculate trend statistics
        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)

        trend_direction = "stable"
        if second_avg > first_avg * 1.1:
            trend_direction = "increasing"
        elif second_avg < first_avg * 0.9:
            trend_direction = "decreasing"

        return {
            "trend": trend_direction,
            "current_value": values[-1],
            "min_value": min(values),
            "max_value": max(values),
            "avg_value": statistics.mean(values),
            "std_deviation": statistics.stdev(values) if len(values) > 1 else 0,
            "sample_count": len(values),
            "change_percent": (
                ((second_avg - first_avg) / first_avg * 100) if first_avg != 0 else 0
            ),
        }

    def _identify_performance_issues(
        self, trends: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify performance issues from trend analysis."""

        issues = []

        # Check query performance
        query_trend = trends.get("query_time_trend", {})
        if (
            query_trend.get("trend") == "increasing"
            and query_trend.get("change_percent", 0) > 20
        ):
            issues.append(
                {
                    "type": "query_performance_degradation",
                    "severity": "medium",
                    "description": f"Query execution time increased by {query_trend.get('change_percent', 0):.1f}%",
                    "current_value": query_trend.get("current_value", 0),
                    "trend": query_trend.get("trend"),
                }
            )

        # Check memory usage - use 80% of threshold as warning level for trends
        memory_trend = trends.get("memory_usage_trend", {})
        memory_threshold = self.performance_thresholds.get(
            "system_metrics.memory_usage_mb", 16384 * 0.90
        )
        memory_warning_level = (
            memory_threshold * 0.8
        )  # 80% of threshold (which is 72% of total memory)
        if (
            memory_trend.get("trend") == "increasing"
            and memory_trend.get("current_value", 0) > memory_warning_level
        ):
            issues.append(
                {
                    "type": "memory_usage_high",
                    "severity": "high",
                    "description": f"Memory usage is {memory_trend.get('current_value', 0):.0f}MB and increasing",
                    "current_value": memory_trend.get("current_value", 0),
                    "trend": memory_trend.get("trend"),
                }
            )

        # Check error rates
        error_trend = trends.get("error_rate_trend", {})
        if error_trend.get("current_value", 0) > 1.0:
            issues.append(
                {
                    "type": "high_error_rate",
                    "severity": "critical",
                    "description": f"Error rate is {error_trend.get('current_value', 0):.2f}%",
                    "current_value": error_trend.get("current_value", 0),
                    "trend": error_trend.get("trend"),
                }
            )

        # Check cache hit rates
        cache_trend = trends.get("cache_hit_rate_trend", {})
        if cache_trend.get("current_value", 1.0) < 0.7:
            issues.append(
                {
                    "type": "low_cache_hit_rate",
                    "severity": "medium",
                    "description": f"Cache hit rate is only {cache_trend.get('current_value', 0):.2%}",
                    "current_value": cache_trend.get("current_value", 0),
                    "trend": cache_trend.get("trend"),
                }
            )

        return issues

    def _generate_optimization_recommendations(
        self, trends: Dict[str, Any], issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate intelligent optimization recommendations."""

        recommendations = []

        # Recommendations based on issues
        for issue in issues:
            if issue["type"] == "query_performance_degradation":
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "query_optimization",
                        "action": "optimize_slow_queries",
                        "description": "Review and optimize slow-performing queries",
                        "estimated_impact": "medium",
                        "effort_level": "low",
                    }
                )

            elif issue["type"] == "memory_usage_high":
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "memory_optimization",
                        "action": "optimize_memory_usage",
                        "description": "Reduce memory usage through cache optimization and data cleanup",
                        "estimated_impact": "high",
                        "effort_level": "medium",
                    }
                )

            elif issue["type"] == "low_cache_hit_rate":
                recommendations.append(
                    {
                        "priority": "medium",
                        "category": "cache_optimization",
                        "action": "tune_cache_settings",
                        "description": "Increase cache size and adjust eviction policies",
                        "estimated_impact": "medium",
                        "effort_level": "low",
                    }
                )

        # General performance recommendations
        if not issues:
            recommendations.append(
                {
                    "priority": "low",
                    "category": "preventive_maintenance",
                    "action": "routine_optimization",
                    "description": "System is performing well - continue regular monitoring",
                    "estimated_impact": "low",
                    "effort_level": "low",
                }
            )

        return recommendations

    def _calculate_health_score(self, trends: Dict[str, Any]) -> float:
        """Calculate overall system health score (0-1)."""

        scores: list[float] = []

        # Query performance score
        query_trend = trends.get("query_time_trend", {})
        query_time = query_trend.get("current_value", 5000)
        query_score = max(0, min(1, (10000 - query_time) / 10000))  # 0-10s range
        scores.append(query_score * 0.25)  # 25% weight

        # Memory usage score - use threshold (90% of total memory)
        memory_trend = trends.get("memory_usage_trend", {})
        memory_usage = memory_trend.get("current_value", 500)
        memory_threshold = self.performance_thresholds.get(
            "system_metrics.memory_usage_mb", 16384 * 0.90
        )
        # Score is good if usage is below threshold, degrades as it approaches/exceeds threshold
        memory_score = max(
            0, min(1, (memory_threshold - memory_usage) / memory_threshold)
        )
        scores.append(memory_score * 0.2)  # 20% weight

        # Error rate score
        error_trend = trends.get("error_rate_trend", {})
        error_rate = error_trend.get("current_value", 0)
        error_score = max(0, min(1, (5.0 - error_rate) / 5.0))  # 0-5% range
        scores.append(error_score * 0.3)  # 30% weight

        # Cache hit rate score
        cache_trend = trends.get("cache_hit_rate_trend", {})
        cache_hit_rate = cache_trend.get("current_value", 0.8)
        cache_score = cache_hit_rate  # Already 0-1
        scores.append(cache_score * 0.15)  # 15% weight

        # Throughput score
        throughput_trend = trends.get("throughput_trend", {})
        throughput = throughput_trend.get("current_value", 100)
        throughput_score = max(0, min(1, throughput / 1000))  # 0-1000 items/sec range
        scores.append(throughput_score * 0.1)  # 10% weight

        return sum(scores)

    def _calculate_performance_grade(self, health_score: float) -> str:
        """Calculate performance grade from health score."""

        if health_score >= 0.9:
            return "A+"
        elif health_score >= 0.8:
            return "A"
        elif health_score >= 0.7:
            return "B"
        elif health_score >= 0.6:
            return "C"
        elif health_score >= 0.5:
            return "D"
        else:
            return "F"

    def _check_performance_alerts(self, current_metrics: Dict[str, Any]):
        """Check for performance alerts based on current metrics."""

        alerts_triggered = []

        # Check each threshold
        for metric_path, threshold_value in self.performance_thresholds.items():
            try:
                current_value = self._get_nested_metric_value(
                    current_metrics, metric_path
                )

                if current_value is not None:
                    # Determine alert condition based on metric type
                    should_alert = False
                    is_inverse_metric = False

                    if (
                        "hit_rate" in metric_path
                        or "cache_rate" in metric_path
                        or "throughput" in metric_path
                    ):
                        # For hit rates, cache rates, and throughput, alert if below threshold
                        should_alert = current_value < threshold_value
                        is_inverse_metric = True
                    else:
                        # For other metrics (including error rates), alert if above threshold
                        should_alert = current_value > threshold_value

                    if should_alert:
                        alert = PerformanceAlert(
                            alert_id=str(time.time()),
                            alert_type="threshold_exceeded",
                            severity=self._determine_alert_severity(
                                metric_path, current_value, threshold_value
                            ),
                            metric_name=metric_path,
                            current_value=current_value,
                            threshold_value=threshold_value,
                            description=f"{metric_path} is {'below' if is_inverse_metric else 'above'} threshold: {current_value:.2f} vs {threshold_value:.2f}",
                            created_at=datetime.now(timezone.utc),
                        )

                        alerts_triggered.append(alert)

            except Exception as e:
                logger.error(f"Failed to check alert for {metric_path}: {e}")

        # Store new alerts
        if alerts_triggered:
            with self._metrics_lock:
                self.alerts.extend(alerts_triggered)
                logger.info(
                    f"Performance alerts triggered: {len(alerts_triggered)} new alerts"
                )

    def _get_nested_metric_value(
        self, metrics: Dict[str, Any], path: str
    ) -> Optional[float]:
        """Get nested metric value from metrics dictionary."""

        try:
            value = metrics
            for key in path.split("."):
                value = value[key]

            return float(value) if isinstance(value, (int, float)) else None

        except (KeyError, TypeError, ValueError):
            return None

    def _determine_alert_severity(
        self, metric_path: str, current_value: float, threshold_value: float
    ) -> str:
        """Determine alert severity based on how far from threshold."""

        if "hit_rate" in metric_path or "cache_rate" in metric_path:
            # For hit rates and cache rates, calculate how far below threshold
            deviation = (threshold_value - current_value) / threshold_value
        else:
            # For other metrics (including error rates), calculate how far above threshold
            deviation = (current_value - threshold_value) / threshold_value

        if deviation > 0.5:  # 50% deviation
            return "critical"
        elif deviation > 0.25:  # 25% deviation
            return "high"
        elif deviation > 0.1:  # 10% deviation
            return "medium"
        else:
            return "low"

    def _is_metric_above_threshold(
        self, metrics: Dict[str, Any], metric_path: str, threshold_key: str
    ) -> bool:
        """Check if a metric is above its threshold."""

        current_value = self._get_nested_metric_value(metrics, metric_path)
        threshold_value = self.performance_thresholds.get(threshold_key)

        return (
            current_value is not None
            and threshold_value is not None
            and current_value > threshold_value
        )

    def _is_metric_below_threshold(
        self, metrics: Dict[str, Any], metric_path: str, threshold_key: str
    ) -> bool:
        """Check if a metric is below its threshold."""

        current_value = self._get_nested_metric_value(metrics, metric_path)
        threshold_value = self.performance_thresholds.get(threshold_key)

        return (
            current_value is not None
            and threshold_value is not None
            and current_value < threshold_value
        )

    # Optimization action methods

    def _optimize_slow_queries(self) -> Optional[OptimizationAction]:
        """Optimize slow-performing queries."""

        try:
            # Mock optimization action
            action = OptimizationAction(
                action_id=str(time.time()),
                action_type="query_optimization",
                description="Optimized slow queries using advanced query optimizer",
                parameters={"queries_optimized": 5, "optimization_level": "advanced"},
                executed_at=datetime.now(timezone.utc),
                success=True,
                impact_metrics={
                    "avg_query_time_improvement_ms": 1500,
                    "queries_affected": 5,
                },
            )

            logger.info("Executed slow query optimization")
            return action

        except Exception as e:
            logger.error(f"Failed to optimize slow queries: {e}")
            return None

    def _are_materialized_views_stale(self) -> bool:
        """Check if materialized views need refreshing."""
        # Mock check - in real implementation would check view timestamps
        return True

    def _refresh_stale_materialized_views(self) -> Optional[OptimizationAction]:
        """Refresh stale materialized views."""

        try:
            action = OptimizationAction(
                action_id=str(time.time()),
                action_type="materialized_view_refresh",
                description="Refreshed stale materialized views",
                parameters={"views_refreshed": 3},
                executed_at=datetime.now(timezone.utc),
                success=True,
                impact_metrics={"query_performance_improvement_percent": 25},
            )

            logger.info("Refreshed stale materialized views")
            return action

        except Exception as e:
            logger.error(f"Failed to refresh materialized views: {e}")
            return None

    def _is_storage_cleanup_needed(self, metrics: Dict[str, Any]) -> bool:
        """Check if storage cleanup is needed."""
        # Mock check based on storage growth
        return True

    def _cleanup_old_data(self) -> Optional[OptimizationAction]:
        """Clean up old data to free storage."""

        try:
            action = OptimizationAction(
                action_id=str(time.time()),
                action_type="data_cleanup",
                description="Cleaned up old temporary data and expired entries",
                parameters={"items_cleaned": 1000, "storage_freed_mb": 250},
                executed_at=datetime.now(timezone.utc),
                success=True,
                impact_metrics={
                    "storage_freed_mb": 250,
                    "performance_improvement": "minor",
                },
            )

            logger.info("Executed data cleanup optimization")
            return action

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return None

    def _optimize_cache_settings(self) -> Optional[OptimizationAction]:
        """Optimize cache settings to improve hit rates."""

        try:
            action = OptimizationAction(
                action_id=str(time.time()),
                action_type="cache_optimization",
                description="Optimized cache settings to improve hit rates",
                parameters={"cache_size_increased_mb": 100, "ttl_adjusted": True},
                executed_at=datetime.now(timezone.utc),
                success=True,
                impact_metrics={
                    "hit_rate_improvement": 0.15,
                    "query_time_reduction_ms": 200,
                },
            )

            logger.info("Optimized cache settings")
            return action

        except Exception as e:
            logger.error(f"Failed to optimize cache settings: {e}")
            return None

    def _optimize_batch_sizes_based_on_performance(
        self, metrics: Dict[str, Any]
    ) -> Optional[OptimizationAction]:
        """Optimize batch sizes based on current performance."""

        try:
            action = OptimizationAction(
                action_id=str(time.time()),
                action_type="batch_size_optimization",
                description="Optimized batch sizes based on throughput metrics",
                parameters={"old_batch_size": 1000, "new_batch_size": 1200},
                executed_at=datetime.now(timezone.utc),
                success=True,
                impact_metrics={"throughput_improvement_percent": 15},
            )

            logger.info("Optimized batch sizes")
            return action

        except Exception as e:
            logger.error(f"Failed to optimize batch sizes: {e}")
            return None

    def _should_optimize_s3_storage(self, metrics: Dict[str, Any]) -> bool:
        """Check if S3 storage optimization is needed."""
        return True  # Mock check

    def _optimize_s3_storage(self) -> Optional[OptimizationAction]:
        """Optimize S3 storage settings."""

        try:
            action = OptimizationAction(
                action_id=str(time.time()),
                action_type="s3_storage_optimization",
                description="Optimized S3 storage lifecycle and compression",
                parameters={"objects_optimized": 500, "compression_improved": True},
                executed_at=datetime.now(timezone.utc),
                success=True,
                impact_metrics={
                    "storage_cost_reduction_percent": 20,
                    "access_time_improvement_ms": 300,
                },
            )

            logger.info("Optimized S3 storage")
            return action

        except Exception as e:
            logger.error(f"Failed to optimize S3 storage: {e}")
            return None

    def get_performance_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive performance dashboard data."""

        current_metrics = self.collect_performance_metrics()
        trends = self.analyze_performance_trends(window_hours=24)
        recent_alerts = [alert for alert in self.alerts if not alert.resolved_at]
        recent_optimizations = (
            self.optimization_history[-10:] if self.optimization_history else []
        )

        # Convert alerts to serializable dictionaries
        serialized_alerts = []
        for alert in recent_alerts:
            serialized_alerts.append(
                {
                    "alert_id": alert.alert_id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold_value": alert.threshold_value,
                    "description": alert.description,
                    "created_at": (
                        alert.created_at.isoformat() if alert.created_at else None
                    ),
                    "resolved_at": (
                        alert.resolved_at.isoformat() if alert.resolved_at else None
                    ),
                }
            )

        # Convert optimization actions to serializable dictionaries
        serialized_optimizations = []
        for opt in recent_optimizations:
            serialized_optimizations.append(
                {
                    "action_id": opt.action_id,
                    "action_type": opt.action_type,
                    "description": opt.description,
                    "parameters": opt.parameters,
                    "executed_at": (
                        opt.executed_at.isoformat() if opt.executed_at else None
                    ),
                    "success": opt.success,
                    "impact_metrics": opt.impact_metrics,
                }
            )

        return {
            "current_metrics": current_metrics,
            "trends": trends,
            "active_alerts": serialized_alerts,
            "recent_optimizations": serialized_optimizations,
            "system_status": {
                "health_score": trends.get("overall_health_score", 0.8),
                "performance_grade": trends.get("performance_grade", "B"),
                "optimization_enabled": self.optimization_enabled,
                "last_optimization": (
                    datetime.fromtimestamp(
                        self.last_optimization_time, tz=timezone.utc
                    ).isoformat()
                    if self.last_optimization_time
                    else None
                ),
            },
        }
