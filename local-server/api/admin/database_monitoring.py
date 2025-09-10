"""
Phase 3: Enhanced Database Manager Administrative Monitoring

This module provides comprehensive monitoring and management endpoints for the
Enhanced Database Manager with optimized connection pooling and performance tracking.

Features:
- Database connection pool monitoring
- Environment-aware performance metrics
- Health check and diagnostics
- Connection lifecycle management
- Resource utilization reporting
- Performance recommendations
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime

from database.utils import (
    get_database_manager,
    PoolConfiguration,
    ConnectionMetrics
)

router = APIRouter()


@router.get("/admin/database/health", summary="Enhanced Database Health Check")
async def get_database_health() -> Dict[str, Any]:
    """Get comprehensive health status of the enhanced database manager."""
    try:
        manager = get_database_manager()
        health_status = manager.perform_health_check()
        return health_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/admin/database/performance", summary="Database Performance Metrics")
async def get_database_performance_metrics() -> Dict[str, Any]:
    """Get detailed performance metrics from the enhanced database manager."""
    try:
        manager = get_database_manager()
        return manager.get_performance_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Performance metrics failed: {str(e)}")


@router.get("/admin/database/engines", summary="Database Engines Status")
async def get_database_engines_status() -> Dict[str, Any]:
    """Get status information for all database engines."""
    try:
        manager = get_database_manager()
        health = manager.perform_health_check()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_engines": len(manager._engines),
            "engines": health["engines"],
            "active_connections": manager.metrics.active_connections,
            "peak_connections": manager.metrics.peak_connections,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engines status failed: {str(e)}")


@router.get("/admin/database/metrics", summary="Connection Metrics Summary")
async def get_connection_metrics() -> Dict[str, Any]:
    """Get detailed connection metrics and statistics."""
    try:
        manager = get_database_manager()
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": manager._get_metrics_summary(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")


@router.post("/admin/database/optimize", summary="Optimize Database for Workload")
async def optimize_database_for_workload(
    workload_type: str = "mixed"
) -> Dict[str, Any]:
    """
    Optimize database configuration for specific workload types.
    
    Supported workload types:
    - mixed: General purpose workload
    - read_heavy: Optimized for read operations
    - write_heavy: Optimized for write operations  
    - analytics: Optimized for analytical queries
    """
    try:
        valid_workloads = ["mixed", "read_heavy", "write_heavy", "analytics"]
        if workload_type not in valid_workloads:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid workload type. Must be one of: {', '.join(valid_workloads)}"
            )
        
        manager = get_database_manager()
        result = manager.optimize_for_workload(workload_type)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.get("/admin/database/recommendations", summary="Performance Recommendations")
async def get_performance_recommendations() -> Dict[str, Any]:
    """Get AI-generated performance recommendations based on current metrics."""
    try:
        manager = get_database_manager()
        metrics = manager._get_metrics_summary()
        recommendations = manager._generate_performance_recommendations()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "current_metrics": metrics,
            "recommendations": recommendations,
            "health_score": _calculate_health_score(metrics)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendations failed: {str(e)}")


@router.post("/admin/database/reset-metrics", summary="Reset Performance Metrics")
async def reset_performance_metrics() -> Dict[str, Any]:
    """Reset all performance metrics counters."""
    try:
        manager = get_database_manager()
        old_metrics = manager._get_metrics_summary()
        manager.metrics.reset()
        
        return {
            "status": "success",
            "message": "Performance metrics reset successfully",
            "timestamp": datetime.now().isoformat(),
            "previous_metrics": old_metrics,
            "reset_metrics": manager._get_metrics_summary()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics reset failed: {str(e)}")


@router.get("/admin/database/environment", summary="Database Environment Configuration")
async def get_environment_configuration() -> Dict[str, Any]:
    """Get current database environment configuration and optimizations."""
    try:
        manager = get_database_manager()
        
        # Sample database URL for strategy analysis
        from config import get_settings
        settings = get_settings()
        database_url = settings.database.default_url
        
        optimal_strategy = manager.get_optimal_pool_strategy(database_url)
        pool_config = manager.get_pool_configuration(database_url)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "optimal_pool_strategy": optimal_strategy.value,
            "pool_configuration": {
                "pool_size": pool_config.pool_size,
                "max_overflow": pool_config.max_overflow,
                "pool_timeout": pool_config.pool_timeout,
                "pool_recycle": pool_config.pool_recycle,
                "pool_pre_ping": pool_config.pool_pre_ping,
            },
            "database_url_type": "sqlite" if database_url.startswith("sqlite://") else "external",
            "is_memory_db": ":memory:" in database_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Environment config failed: {str(e)}")


@router.post("/admin/database/create-engine", summary="Create Optimized Engine")
async def create_optimized_database_engine(
    engine_id: str,
    database_url: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new optimized database engine with specified configuration."""
    try:
        manager = get_database_manager()
        
        # Use default database URL if not provided
        if database_url is None:
            from config import get_settings
            settings = get_settings()
            database_url = settings.database.default_url
        
        # Create the engine
        engine = manager.create_optimized_engine(database_url, engine_id)
        
        return {
            "status": "success",
            "message": f"Engine '{engine_id}' created successfully",
            "timestamp": datetime.now().isoformat(),
            "engine_id": engine_id,
            "database_url": database_url,
            "pool_info": _get_engine_pool_info(engine)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine creation failed: {str(e)}")


@router.delete("/admin/database/cleanup", summary="Cleanup Database Resources")
async def cleanup_database_resources() -> Dict[str, Any]:
    """Clean up all database resources and reset the manager."""
    try:
        manager = get_database_manager()
        engines_count = len(manager._engines)
        active_connections = manager.metrics.active_connections
        
        # Perform cleanup
        manager.cleanup_resources()
        
        return {
            "status": "success",
            "message": "Database resources cleaned up successfully",
            "timestamp": datetime.now().isoformat(),
            "engines_disposed": engines_count,
            "connections_closed": active_connections,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/admin/database/dashboard", summary="Enhanced Database Dashboard")
async def get_database_dashboard() -> Dict[str, Any]:
    """Get comprehensive dashboard data for the enhanced database manager."""
    try:
        manager = get_database_manager()
        health = manager.perform_health_check()
        metrics = manager._get_metrics_summary()
        recommendations = manager._generate_performance_recommendations()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "dashboard_info": {
                "manager_id": id(manager),
                "uptime_seconds": metrics["uptime_seconds"],
                "health_score": _calculate_health_score(metrics)
            },
            "health_status": health,
            "performance_metrics": metrics,
            "recommendations": recommendations,
            "engines_summary": {
                "total_engines": len(manager._engines),
                "healthy_engines": sum(1 for engine_health in health["engines"].values() 
                                     if engine_health["status"] == "healthy"),
                "warning_engines": sum(1 for engine_health in health["engines"].values() 
                                     if engine_health["status"] == "warning"),
                "error_engines": sum(1 for engine_health in health["engines"].values() 
                                   if engine_health["status"] == "error"),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard data failed: {str(e)}")


# Helper functions
def _calculate_health_score(metrics: Dict[str, Any]) -> float:
    """Calculate a health score based on performance metrics."""
    score = 100.0
    
    # Penalize for errors
    if metrics["connection_errors"] > 0:
        error_penalty = min(50, metrics["connection_errors"] * 5)
        score -= error_penalty
    
    # Penalize for high response times
    if metrics["avg_connection_time_ms"] > 100:
        time_penalty = min(20, (metrics["avg_connection_time_ms"] - 100) / 10)
        score -= time_penalty
    
    # Penalize for low pool efficiency
    if metrics["pool_efficiency_percent"] < 80:
        efficiency_penalty = (80 - metrics["pool_efficiency_percent"]) / 4
        score -= efficiency_penalty
    
    # Penalize for high query times
    if metrics["avg_query_time_ms"] > 50:
        query_penalty = min(10, (metrics["avg_query_time_ms"] - 50) / 10)
        score -= query_penalty
    
    return max(0.0, score)


def _get_engine_pool_info(engine) -> Dict[str, Any]:
    """Extract pool information from an engine."""
    try:
        pool = engine.pool
        return {
            "pool_class": pool.__class__.__name__,
            "size": getattr(pool, 'size', lambda: 'N/A')(),
            "checked_in": getattr(pool, 'checkedin', lambda: 'N/A')(),
            "checked_out": getattr(pool, 'checkedout', lambda: 'N/A')(),
            "overflow": getattr(pool, 'overflow', lambda: 'N/A')(),
            "invalid": getattr(pool, 'invalid', lambda: 'N/A')(),
        }
    except Exception:
        return {"pool_info": "unavailable"}
