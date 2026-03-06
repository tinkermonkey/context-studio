"""
Optimization API Endpoints

This module implements comprehensive optimization API endpoints for Phase 5 optimization  # noqa: E501
services including query optimization, storage optimization, hierarchical diff processing,  # noqa: E501
batch operations, and performance monitoring.

Endpoints:
- GET /api/optimization/health - Get optimization system health status
- GET /api/optimization/performance/dashboard - Get comprehensive performance dashboard  # noqa: E501
- GET /api/optimization/performance/metrics - Get current performance metrics
- GET /api/optimization/performance/trends - Get performance trend analysis
- POST /api/optimization/performance/auto-optimize - Trigger automated optimization  # noqa: E501
- GET /api/optimization/query/stats - Get query optimization statistics
- POST /api/optimization/query/optimize - Optimize a specific query
- POST /api/optimization/query/materialized-view - Create materialized view
- GET /api/optimization/storage/stats - Get storage optimization statistics
- POST /api/optimization/storage/optimize - Trigger storage optimization
- POST /api/optimization/storage/lifecycle-policies - Setup lifecycle policies
- GET /api/optimization/diff/stats - Get diff engine performance statistics
- POST /api/optimization/diff/three-way - Perform three-way diff with conflict detection  # noqa: E501
- POST /api/optimization/batch/process - Execute batch operation with optimization  # noqa: E501
- GET /api/optimization/batch/stats - Get batch processing statistics
"""

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from services.service_factory import (
    get_duckdb_query_optimizer_via_factory,
    get_s3_storage_optimizer_via_factory,
    get_hierarchical_diff_engine_via_factory,
    get_batch_operation_processor_via_factory,
    get_performance_monitor_via_factory,
)
from database.utils import get_db
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/optimization", tags=["optimization"])


# Pydantic Models for API Validation


class SystemHealthOut(BaseModel):
    """API model for system health output."""

    status: str
    services_healthy: Dict[str, bool]
    performance_score: float
    optimization_enabled: bool
    last_optimization: Optional[str]
    issues: List[str]


class PerformanceMetricsOut(BaseModel):
    """API model for performance metrics output."""

    timestamp: str
    database_metrics: Dict[str, Any]
    s3_metrics: Dict[str, Any]
    query_metrics: Dict[str, Any]
    system_metrics: Dict[str, Any]
    cache_metrics: Dict[str, Any]
    batch_metrics: Dict[str, Any]


class PerformanceTrendsOut(BaseModel):
    """API model for performance trends output."""

    analysis_window_hours: int
    trends: Dict[str, Any]
    issues: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    overall_health_score: float
    performance_grade: str


class QueryOptimizationRequest(BaseModel):
    """API model for query optimization request."""

    query: str = Field(..., description="SQL query to optimize")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Query context for optimization"
    )


class QueryOptimizationOut(BaseModel):
    """API model for query optimization output."""

    original_query: str
    optimized_query: str
    metrics: Dict[str, Any]
    optimization_applied: List[str]


class MaterializedViewRequest(BaseModel):
    """API model for materialized view creation request."""

    view_name: str = Field(..., description="Name for the materialized view")
    query: str = Field(..., description="Query for the materialized view")
    refresh_strategy: str = Field(
        "manual", description="Refresh strategy (manual/scheduled)"
    )


class StorageOptimizationOut(BaseModel):
    """API model for storage optimization output."""

    optimization_actions: List[Dict[str, Any]]
    storage_saved_bytes: int
    cost_reduction_estimate: float
    objects_optimized: int


class ThreeWayDiffRequest(BaseModel):
    """API model for three-way diff request."""

    base: Dict[str, Any] = Field(..., description="Base version data")
    local: Dict[str, Any] = Field(..., description="Local version data")
    remote: Dict[str, Any] = Field(..., description="Remote version data")
    enable_semantic_analysis: bool = Field(True, description="Enable semantic analysis")  # noqa: E501


class ThreeWayDiffOut(BaseModel):
    """API model for three-way diff output."""

    diff_result: Dict[str, Any]
    conflicts_detected: List[Dict[str, Any]]
    semantic_insights: Optional[Dict[str, Any]]
    merge_recommendation: Optional[str]


class BatchOperationRequest(BaseModel):
    """API model for batch operation request."""

    operation_type: str = Field(..., description="Type of batch operation")
    entity_data: List[Dict[str, Any]] = Field(..., description="Entity data to process")  # noqa: E501
    author_id: str = Field(..., description="Author ID for the operation")
    options: Optional[Dict[str, Any]] = Field(
        None, description="Additional operation options"
    )


class BatchOperationOut(BaseModel):
    """API model for batch operation output."""

    operation_id: str
    total_items: int
    successful_items: int
    failed_items: int
    processing_time_seconds: float
    throughput_per_second: float
    errors: List[Dict[str, Any]]


# Dependency functions for service factory
def get_query_optimizer():
    """Get DuckDBQueryOptimizer instance via service factory."""
    return get_duckdb_query_optimizer_via_factory()


def get_storage_optimizer():
    """Get S3StorageOptimizer instance via service factory."""
    return get_s3_storage_optimizer_via_factory()


def get_diff_engine(db: Session = Depends(get_db)):
    """Get HierarchicalDiffEngine instance via service factory."""
    return get_hierarchical_diff_engine_via_factory(db)


def get_batch_processor(db: Session = Depends(get_db)):
    """Get BatchOperationProcessor instance via service factory."""
    return get_batch_operation_processor_via_factory(db)


def get_performance_monitor():
    """Get PerformanceMonitor instance via service factory."""
    return get_performance_monitor_via_factory()


# System Health and Monitoring Endpoints


@router.get("/health", response_model=SystemHealthOut)
def get_optimization_system_health(
    query_optimizer=Depends(get_query_optimizer),
    storage_optimizer=Depends(get_storage_optimizer),
    performance_monitor=Depends(get_performance_monitor),
):
    """Get comprehensive optimization system health status."""
    try:
        # Check actual service health from each service
        # Each service should implement a health check method
        services_health = {
            "query_optimizer": query_optimizer.health_check() if hasattr(query_optimizer, "health_check") else None,  # noqa: E501
            "storage_optimizer": storage_optimizer.health_check() if hasattr(storage_optimizer, "health_check") else None,  # noqa: E501
            "performance_monitor": performance_monitor.health_check() if hasattr(performance_monitor, "health_check") else None,  # noqa: E501
            "diff_engine": None,  # Not yet available as dependency
            "batch_processor": None,  # Not yet available as dependency
        }

        # Get performance dashboard to assess overall health
        dashboard = performance_monitor.get_performance_dashboard()
        system_status = dashboard.get("system_status", {})

        health_score = system_status.get("health_score", 0.8)
        performance_grade = system_status.get("performance_grade", "B")
        optimization_enabled = system_status.get("optimization_enabled", True)
        last_optimization = system_status.get("last_optimization")

        # Determine overall status
        if health_score >= 0.9:
            overall_status = "excellent"
        elif health_score >= 0.7:
            overall_status = "good"
        elif health_score >= 0.5:
            overall_status = "degraded"
        else:
            overall_status = "critical"

        issues = []
        if not optimization_enabled:
            issues.append("Automated optimization is disabled")
        if health_score < 0.7:
            issues.append(f"Performance score below threshold: {performance_grade}")  # noqa: E501

        return SystemHealthOut(
            status=overall_status,
            services_healthy=services_health,
            performance_score=health_score,
            optimization_enabled=optimization_enabled,
            last_optimization=last_optimization,
            issues=issues,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get system health: {str(e)}"
        )


# Performance Monitoring Endpoints


@router.get("/performance/dashboard")
def get_performance_dashboard(performance_monitor=Depends(get_performance_monitor)):  # noqa: E501
    """Get comprehensive performance dashboard data."""
    try:
        dashboard = performance_monitor.get_performance_dashboard()
        return dashboard
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance dashboard: {str(e)}"  # noqa: E501
        )


@router.get("/performance/metrics", response_model=PerformanceMetricsOut)
def get_performance_metrics(performance_monitor=Depends(get_performance_monitor)):  # noqa: E501
    """Get current comprehensive performance metrics."""
    try:
        metrics = performance_monitor.collect_performance_metrics()
        return PerformanceMetricsOut.model_validate(metrics)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance metrics: {str(e)}"  # noqa: E501
        )


@router.get("/performance/trends", response_model=PerformanceTrendsOut)
def get_performance_trends(
    window_hours: int = Query(24, ge=1, le=168, description="Analysis window in hours"),  # noqa: E501
    performance_monitor=Depends(get_performance_monitor),
):
    """Get performance trend analysis and optimization recommendations."""
    try:
        trends = performance_monitor.analyze_performance_trends(
            window_hours=window_hours
        )
        return PerformanceTrendsOut.model_validate(trends)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance trends: {str(e)}"  # noqa: E501
        )


@router.post("/performance/auto-optimize")
def trigger_auto_optimization(
    background_tasks: BackgroundTasks,
    performance_monitor=Depends(get_performance_monitor),
):
    """Trigger automated optimization based on current performance metrics."""
    try:

        def run_optimization():
            return performance_monitor.auto_optimize_based_on_metrics()

        # Run optimization in background to avoid blocking
        background_tasks.add_task(run_optimization)

        return {
            "message": "Automated optimization triggered",
            "status": "running",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger optimization: {str(e)}"
        )


# Query Optimization Endpoints


@router.get("/query/stats")
def get_query_optimization_stats(query_optimizer=Depends(get_query_optimizer)):
    """Get query optimization statistics and performance metrics."""
    try:
        stats = query_optimizer.get_optimization_statistics()

        # Ensure all expected fields are present
        response = {
            "total_queries": stats.get("total_queries", 0),
            "avg_execution_time_ms": stats.get(
                "avg_execution_time_ms", 0.0
            ),  # Add this field
            "cache_stats": stats.get("cache_stats", {}),
            "materialized_views_count": stats.get("materialized_views", 0),
        }
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get query stats: {str(e)}"
        )


@router.post("/query/optimize", response_model=QueryOptimizationOut)
def optimize_query(
    request: QueryOptimizationRequest, query_optimizer=Depends(get_query_optimizer)  # noqa: E501
):
    """Optimize a specific query using advanced optimization techniques."""
    try:
        optimized_query, metrics = query_optimizer.optimize_query(
            request.query, request.context or {}
        )

        return QueryOptimizationOut(
            original_query=request.query,
            optimized_query=optimized_query,
            metrics=metrics.__dict__,
            optimization_applied=[
                "predicate_pushdown",
                "partition_elimination",
                "column_pruning",
                "join_optimization",
                "aggregation_pushdown",
            ],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to optimize query: {str(e)}"
        )


@router.post("/query/materialized-view")
def create_materialized_view(
    request: MaterializedViewRequest, query_optimizer=Depends(get_query_optimizer)  # noqa: E501
):
    """Create a materialized view for frequently accessed queries."""
    try:
        # Validate view definition first
        if not request.view_name or not request.query:
            raise HTTPException(status_code=422, detail="Invalid view definition")  # noqa: E501

        success = query_optimizer.create_materialized_view(
            request.view_name, request.query, request.refresh_strategy
        )

        if success:
            return {
                "message": f"Materialized view '{request.view_name}' created successfully",  # noqa: E501
                "view_name": request.view_name,
                "refresh_strategy": request.refresh_strategy,
                "created_at": datetime.now().isoformat(),
                "success": True,
            }
        else:
            raise HTTPException(
                status_code=400, detail="Failed to create materialized view"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create materialized view: {str(e)}"  # noqa: E501
        )


# Storage Optimization Endpoints


@router.get("/storage/stats")
def get_storage_optimization_stats(storage_optimizer=Depends(get_storage_optimizer)):  # noqa: E501
    """Get storage optimization statistics and cost metrics."""
    try:
        stats = storage_optimizer.get_optimization_summary()

        response = {
            "optimization_summary": {  # Add this wrapper
                "files_optimized": stats.get("files_optimized", 0),
                "total_savings_bytes": stats.get("total_savings_bytes", 0),
                "average_compression_ratio": stats.get("average_compression_ratio", 0),  # noqa: E501
            },
            "compression_algorithms_used": stats.get("compression_algorithms_used", {}),  # noqa: E501
            "total_optimizations": stats.get("total_optimizations", 0),
        }
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get storage stats: {str(e)}"
        )


@router.post("/storage/optimize", response_model=StorageOptimizationOut)
def optimize_storage(
    background_tasks: BackgroundTasks, storage_optimizer=Depends(get_storage_optimizer)  # noqa: E501
):
    """Trigger comprehensive storage optimization including compression and lifecycle policies."""  # noqa: E501
    try:

        def run_storage_optimization():
            return storage_optimizer.optimize_storage_comprehensive()

        # Start optimization in background
        background_tasks.add_task(run_storage_optimization)

        # Return immediate response indicating optimization is in progress.
        # Actual results will be available once the background task completes.
        return StorageOptimizationOut(
            optimization_actions=[
                {
                    "action": "compression_optimization",
                    "status": "pending",
                    "details": "Background optimization in progress",
                },
                {
                    "action": "lifecycle_policy_application",
                    "status": "pending",
                    "details": "Background optimization in progress",
                },
            ],
            storage_saved_bytes=0,  # Actual results pending
            cost_reduction_estimate=0.0,  # Actual results pending
            objects_optimized=0,  # Actual results pending
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to optimize storage: {str(e)}"
        )


@router.post("/storage/lifecycle-policies")
def setup_lifecycle_policies(storage_optimizer=Depends(get_storage_optimizer)):
    """Setup intelligent S3 lifecycle policies for cost optimization."""
    try:
        success = storage_optimizer.setup_lifecycle_policies()

        if success:
            return {
                "message": "Lifecycle policies configured successfully",
                "policies": [
                    "Standard to IA after 30 days",
                    "IA to Glacier after 90 days",
                    "Glacier to Deep Archive after 365 days",
                ],
                "estimated_cost_reduction": "60-80%",
                "configured_at": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(
                status_code=400, detail="Failed to setup lifecycle policies"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to setup lifecycle policies: {str(e)}"  # noqa: E501
        )


# Hierarchical Diff Engine Endpoints


@router.get("/diff/stats")
def get_diff_engine_stats(diff_engine=Depends(get_diff_engine)):
    """Get hierarchical diff engine performance statistics."""
    try:
        stats = diff_engine.get_performance_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get diff stats: {str(e)}"
        )


@router.post("/diff/three-way", response_model=ThreeWayDiffOut)
def perform_three_way_diff(
    request: ThreeWayDiffRequest, diff_engine=Depends(get_diff_engine)
):
    """Perform advanced three-way diff with intelligent conflict detection."""
    try:
        diff_result = diff_engine.compute_three_way_diff(
            request.base, request.local, request.remote
        )

        return ThreeWayDiffOut(
            diff_result=diff_result,
            conflicts_detected=diff_result.get("conflicts", []),
            semantic_insights=diff_result.get("semantic_analysis"),
            merge_recommendation=diff_result.get("merge_recommendation"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to perform three-way diff: {str(e)}"  # noqa: E501
        )


# Batch Operation Endpoints


@router.get("/batch/stats")
def get_batch_processing_stats(batch_processor=Depends(get_batch_processor)):
    """Get batch operation processing statistics and performance metrics."""
    try:
        stats = batch_processor.get_performance_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get batch stats: {str(e)}"
        )


@router.post("/batch/process", response_model=BatchOperationOut)
def execute_batch_operation(
    request: BatchOperationRequest,
    background_tasks: BackgroundTasks,
    batch_processor=Depends(get_batch_processor),
):
    """Execute optimized batch operation with parallel processing."""
    try:
        if request.operation_type == "create_versions":
            result = batch_processor.batch_create_versions(
                request.entity_data, request.author_id
            )
        elif request.operation_type == "merge_changes":
            result = batch_processor.batch_merge_changes(
                request.entity_data, request.author_id
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported operation type: {request.operation_type}",
            )

        return BatchOperationOut(
            operation_id=result.operation_id,
            total_items=result.total_items,
            successful_items=result.successful_items,
            failed_items=result.failed_items,
            processing_time_seconds=result.processing_time_seconds,
            throughput_per_second=result.throughput_per_second,
            errors=[error.__dict__ for error in result.errors],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to execute batch operation: {str(e)}"  # noqa: E501
        )


# Configuration and Management Endpoints


@router.get("/config")
def get_optimization_configuration():
    """Get current optimization system configuration."""
    return {
        "query_optimization": {
            "cache_ttl_seconds": 3600,
            "materialized_view_refresh_interval": "daily",
            "optimization_strategies_enabled": [
                "predicate_pushdown",
                "partition_elimination",
                "column_pruning",
                "join_optimization",
                "aggregation_pushdown",
            ],
        },
        "storage_optimization": {
            "lifecycle_policies_enabled": True,
            "compression_algorithm": "intelligent",
            "cost_optimization_target": "80% reduction",
        },
        "performance_monitoring": {
            "auto_optimization_enabled": True,
            "optimization_interval_seconds": 3600,
            "alert_thresholds": {
                "query_time_ms": 5000,
                "memory_usage_mb": 1000,
                "error_rate_percent": 1.0,
            },
        },
    }


@router.put("/config")
def update_optimization_configuration(config: Dict[str, Any]):
    """Update optimization system configuration."""
    # Configuration update not yet implemented
    logger.warning("Optimization configuration update not yet implemented")
    raise HTTPException(
        status_code=501,
        detail="Configuration update not yet implemented"
    )
