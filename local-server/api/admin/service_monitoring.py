"""
Administrative API endpoints for Service Factory monitoring (Phase 2)

This module provides administrative endpoints to monitor service factory performance,  # noqa: E501
cache statistics, and system health for Phase 2 implementation.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from datetime import datetime

from services.service_factory import get_service_factory, ServiceFactory
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/services", tags=["Service Administration"])


def get_admin_service_factory() -> ServiceFactory:
    """Dependency to get service factory for administrative operations."""
    return get_service_factory()


@router.get("/stats", summary="Get comprehensive service factory statistics")
async def get_service_factory_stats(
    factory: ServiceFactory = Depends(get_admin_service_factory),
) -> Dict[str, Any]:
    """
    Get comprehensive statistics about the service factory including:
    - Cache hit rates
    - Service creation metrics
    - Performance data
    - Cache entry details
    """
    try:
        stats = factory.get_cache_stats()
        logger.info(
            f"Service factory stats requested - {stats['total_cache_entries']} entries"
        )  # noqa: E501
        return stats
    except Exception as e:
        logger.error(f"Error getting service factory stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get service factory stats: {str(e)}"
        )  # noqa: E501


@router.get("/performance", summary="Get performance summary")
async def get_service_factory_performance(
    factory: ServiceFactory = Depends(get_admin_service_factory),
) -> Dict[str, Any]:
    """
    Get a concise performance summary for quick monitoring:
    - Overall cache hit rate
    - Best and worst performing services
    - Total services created
    """
    try:
        performance = factory.get_performance_summary()
        hit_rate = performance["overall_cache_hit_rate_percent"]
        logger.debug(
            f"Service factory performance summary: {hit_rate:.1f}% hit rate"
        )  # noqa: E501
        return performance
    except Exception as e:
        logger.error(f"Error getting service factory performance: {e}")
        msg = f"Failed to get service factory performance: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@router.get("/health", summary="Get service factory health status")
async def get_service_factory_health(
    factory: ServiceFactory = Depends(get_admin_service_factory),
) -> Dict[str, Any]:
    """
    Get health status of the service factory:
    - Overall health status
    - Identified issues
    - System metrics
    """
    try:
        health = factory.get_health_status()

        if health["status"] != "healthy":
            logger.warning(
                f"Service factory health issues detected: {health['issues']}"
            )  # noqa: E501

        return health
    except Exception as e:
        logger.error(f"Error getting service factory health: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get service factory health: {str(e)}"
        )  # noqa: E501


@router.post("/cache/clear", summary="Clear service factory cache")
async def clear_service_factory_cache(
    factory: ServiceFactory = Depends(get_admin_service_factory),
) -> Dict[str, Any]:
    """
    Clear all cached service entries and reset metrics.
    Use with caution - this will force recreation of all services.
    """
    try:
        stats_before = factory.get_cache_stats()
        entries_before = stats_before["total_cache_entries"]

        factory.clear_cache()

        logger.info(
            f"Service factory cache cleared - removed {entries_before} entries"
        )  # noqa: E501

        return {
            "status": "success",
            "message": f"Cache cleared successfully - removed {entries_before} entries",  # noqa: E501
            "entries_cleared": entries_before,
            "cleared_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error clearing service factory cache: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to clear service factory cache: {str(e)}"
        )  # noqa: E501


@router.post(
    "/cache/cleanup", summary="Force cleanup of expired cache entries"
)  # noqa: E501
async def cleanup_service_factory_cache(
    factory: ServiceFactory = Depends(get_admin_service_factory),
) -> Dict[str, Any]:
    """
    Force cleanup of expired cache entries.
    This is normally done automatically but can be triggered manually.
    """
    try:
        expired_count = factory.force_cleanup()

        logger.info(
            f"Service factory cache cleanup completed - removed {expired_count} expired entries"
        )  # noqa: E501

        return {
            "status": "success",
            "message": "Cache cleanup completed",
            "expired_entries_removed": expired_count,
            "cleaned_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error during service factory cache cleanup: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cleanup service factory cache: {str(e)}"
        )  # noqa: E501


@router.get(
    "/metrics/{service_type}", summary="Get metrics for specific service type"
)  # noqa: E501
async def get_service_type_metrics(
    service_type: str, factory: ServiceFactory = Depends(get_admin_service_factory)
) -> Dict[str, Any]:
    """
    Get detailed metrics for a specific service type.

    Args:
        service_type: The service type to get metrics for (e.g., 'node_service', 'llm_service')  # noqa: E501
    """
    try:
        stats = factory.get_cache_stats()

        if service_type not in stats["service_metrics"]:
            available = list(stats["service_metrics"].keys())
            raise HTTPException(
                status_code=404,
                detail=f"Service type '{service_type}' not found. Available types: {available}",  # noqa: E501
            )

        service_metrics = stats["service_metrics"][service_type]

        # Add cache entry details for this service type
        cache_entries = {
            key: entry
            for key, entry in stats["cache_entries"].items()
            if key.startswith(service_type) or key == service_type
        }

        return {
            "service_type": service_type,
            "metrics": service_metrics,
            "cache_entries": cache_entries,
            "cache_entry_count": len(cache_entries),
            "retrieved_at": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting metrics for service type {service_type}: {e}"
        )  # noqa: E501
        raise HTTPException(
            status_code=500, detail=f"Failed to get metrics for service type: {str(e)}"
        )  # noqa: E501


@router.get("/dashboard", summary="Get monitoring dashboard data")
async def get_service_factory_dashboard(
    factory: ServiceFactory = Depends(get_admin_service_factory),
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data combining stats, performance, and health.
    Perfect for monitoring dashboards and operational visibility.
    """
    try:
        stats = factory.get_cache_stats()
        performance = factory.get_performance_summary()
        health = factory.get_health_status()

        # Calculate some additional dashboard metrics
        service_metrics = stats["service_metrics"]
        total_requests = sum(
            m["cache_hits"] + m["cache_misses"] for m in service_metrics.values()
        )

        most_used_service = max(
            service_metrics.items(),
            key=lambda x: x[1]["total_created"],
            default=(None, {"total_created": 0}),
        )

        return {
            "factory_info": {
                "factory_id": stats["factory_id"],
                "cache_ttl_seconds": stats["cache_ttl_seconds"],
                "total_cache_entries": stats["total_cache_entries"],
            },
            "performance": {
                "overall_hit_rate_percent": performance[
                    "overall_cache_hit_rate_percent"
                ],  # noqa: E501
                "total_services_created": performance[
                    "total_services_created"
                ],  # noqa: E501
                "total_requests": total_requests,
            },
            "health": {
                "status": health["status"],
                "issues": health["issues"],
                "cache_size": health["cache_size"],
            },
            "top_services": {
                "most_used": {
                    "type": most_used_service[0],
                    "created_count": most_used_service[1]["total_created"],
                },
                "best_performance": performance["best_performing_service"],
                "worst_performance": performance["worst_performing_service"],
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error generating service factory dashboard: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate dashboard data: {str(e)}"
        )  # noqa: E501
