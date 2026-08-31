"""
Utility functions for analyzing proxy monitoring data.
"""

from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


def analyze_proxy_health(stats: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze proxy monitoring stats and return health summary with alerts.

    Args:
        stats: Full monitoring stats from proxy

    Returns:
        Analysis summary with health status and alerts
    """
    analysis: dict[str, Any] = {
        "overall_health": "healthy",
        "alerts": [],
        "recommendations": [],
        "summary": {},
    }

    try:
        # Analyze cache performance
        if stats.get("cache"):
            cache = stats["cache"]
            if isinstance(cache, dict):
                hit_rate = cache.get("hit_rate", 0)

                analysis["summary"]["cache_hit_rate"] = hit_rate

                if hit_rate < 0.5:
                    analysis["alerts"].append(
                        {
                            "level": "warning",
                            "type": "cache_performance",
                            "message": f"Low cache hit rate: {hit_rate:.1%}",
                            "recommendation": "Consider adjusting TTL settings or cache size",
                        }
                    )
                    analysis["overall_health"] = "degraded"
                elif hit_rate > 0.8:
                    analysis["summary"]["cache_status"] = "excellent"

                # Check for excessive evictions
                evicted = cache.get("evicted_entries", 0)
                total = cache.get("total_entries", 1)
                eviction_rate = evicted / total if total > 0 else 0

                if eviction_rate > 0.1:
                    analysis["alerts"].append(
                        {
                            "level": "warning",
                            "type": "cache_eviction",
                            "message": f"High eviction rate: {eviction_rate:.1%}",
                            "recommendation": "Consider increasing cache size or adjusting TTL",
                        }
                    )

        # Analyze upstream performance
        if stats.get("upstream"):
            upstream = stats["upstream"]
            if isinstance(upstream, dict):
                overall = upstream.get("overall", {})

                error_rate = (
                    overall.get("error_rate", 0)
                    if isinstance(overall, dict)
                    else 0
                )
                avg_response_time = (
                    overall.get("avg_response_time_ms", 0)
                    if isinstance(overall, dict)
                    else 0
                )

                analysis["summary"]["upstream_error_rate"] = error_rate
                analysis["summary"]["avg_response_time_ms"] = avg_response_time

                if error_rate > 0.1:
                    analysis["alerts"].append(
                        {
                            "level": "critical",
                            "type": "upstream_errors",
                            "message": f"High upstream error rate: {error_rate:.1%}",
                            "recommendation": "Check upstream API health and throttling settings",
                        }
                    )
                    analysis["overall_health"] = "unhealthy"

                if avg_response_time > 1000:
                    analysis["alerts"].append(
                        {
                            "level": "warning",
                            "type": "slow_response",
                            "message": f"Slow upstream responses: {avg_response_time:.0f}ms",
                            "recommendation": "Monitor upstream API performance",
                        }
                    )

        # Analyze throttling status
        if stats.get("throttling"):
            throttling = stats["throttling"]
            if isinstance(throttling, dict):
                throttle_state = throttling.get("throttle_state", {})

                throttled_domains: list[str] = []
                if isinstance(throttle_state, dict):
                    throttled_domains = [
                        domain
                        for domain, state in throttle_state.items()
                        if isinstance(state, dict)
                        and state.get("is_throttled", False)
                    ]

                if throttled_domains:
                    analysis["alerts"].append(
                        {
                            "level": "info",
                            "type": "throttling_active",
                            "message": f"Throttling active for domains: {', '.join(throttled_domains)}",
                            "recommendation": "Normal operation - throttling is protecting upstream APIs",
                        }
                    )

                analysis["summary"]["throttled_domains"] = throttled_domains

        # Analyze proxy health
        if stats.get("proxy_health"):
            health = stats["proxy_health"]
            if isinstance(health, dict):
                uptime = health.get("uptime_seconds", 0)
                recent_errors = health.get("recent_errors", [])

                analysis["summary"]["uptime_hours"] = uptime / 3600
                analysis["summary"]["recent_error_count"] = (
                    len(recent_errors)
                    if isinstance(recent_errors, list)
                    else 0
                )

                if recent_errors and isinstance(recent_errors, list):
                    analysis["alerts"].append(
                        {
                            "level": "warning",
                            "type": "recent_errors",
                            "message": f"{len(recent_errors)} recent errors detected",
                            "recommendation": "Review error logs for patterns",
                        }
                    )

    except Exception as e:
        logger.error(f"Error analyzing monitoring stats: {e}")
        analysis["alerts"].append(
            {
                "level": "error",
                "type": "analysis_error",
                "message": f"Failed to analyze stats: {e!s}",
                "recommendation": "Check monitoring data format",
            }
        )
        analysis["overall_health"] = "unknown"

    return analysis


def get_performance_summary(stats: dict[str, Any]) -> dict[str, Any]:
    """
    Extract key performance metrics for quick overview.

    Args:
        stats: Full monitoring stats from proxy

    Returns:
        Summary of key performance indicators
    """
    summary: dict[str, Any] = {
        "timestamp": stats.get("timestamp"),
        "metrics": {},
    }

    try:
        # Cache metrics
        if stats.get("cache"):
            cache = stats["cache"]
            if isinstance(cache, dict):
                summary["metrics"]["cache"] = {
                    "hit_rate": cache.get("hit_rate", 0),
                    "total_entries": cache.get("total_entries", 0),
                    "size_mb": round(
                        cache.get("cache_size_bytes", 0) / 1024 / 1024, 2
                    ),
                }

        # Upstream metrics
        if stats.get("upstream"):
            upstream = stats["upstream"]
            if isinstance(upstream, dict):
                overall = upstream.get("overall", {})
                if isinstance(overall, dict):
                    summary["metrics"]["upstream"] = {
                        "success_rate": overall.get("success_rate", 0),
                        "avg_response_time_ms": overall.get(
                            "avg_response_time_ms", 0
                        ),
                        "requests_per_hour": overall.get(
                            "requests_per_hour", 0
                        ),
                    }

        # Database metrics
        if stats.get("database"):
            db = stats["database"]
            if isinstance(db, dict):
                summary["metrics"]["database"] = {
                    "health": db.get("db_health", "unknown"),
                    "size_mb": round(
                        db.get("db_file_size_bytes", 0) / 1024 / 1024, 2
                    ),
                }

        # Proxy metrics
        if stats.get("proxy_health"):
            health = stats["proxy_health"]
            if isinstance(health, dict):
                summary["metrics"]["proxy"] = {
                    "uptime_hours": round(
                        health.get("uptime_seconds", 0) / 3600, 1
                    ),
                    "active_threads": health.get("active_threads", 0),
                }

    except Exception as e:
        logger.error(f"Error creating performance summary: {e}")
        summary["error"] = str(e)

    return summary
