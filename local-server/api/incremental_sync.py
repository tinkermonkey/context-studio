"""
Incremental Sync API Endpoints

This module implements incremental synchronization API endpoints for efficient
large-scale data synchronization with partitioned queries and optimization.

Endpoints:
- POST /api/sync/incremental - Start incremental sync operation
- GET /api/sync/operations - List sync operations with filtering
- GET /api/sync/operations/{operation_id} - Get sync operation details
- POST /api/sync/operations/{operation_id}/cancel - Cancel running sync operation
- GET /api/sync/status - Get current sync system status
- GET /api/sync/performance - Get sync performance metrics
- POST /api/sync/optimize - Optimize sync configuration
- GET /api/sync/health - Get sync system health
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Path, BackgroundTasks
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from database.utils import get_db
from services.service_factory import get_incremental_sync_engine_via_factory
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/sync", tags=["incremental_sync"])


class IncrementalSyncRequest(BaseModel):
    """API model for incremental sync request."""
    since: datetime = Field(..., description="Start timestamp for sync (ISO format)")
    until: Optional[datetime] = Field(None, description="End timestamp for sync (ISO format)")
    entity_types: Optional[List[str]] = Field(None, description="Specific entity types to sync")
    sync_strategy: str = Field("auto", description="Sync strategy: auto, parallel, sequential")
    batch_size: int = Field(1000, ge=100, le=10000, description="Batch size for processing")
    max_parallel_workers: int = Field(4, ge=1, le=20, description="Max parallel workers")


class SyncOperationOut(BaseModel):
    """API model for sync operation output."""
    id: str
    sync_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    since_timestamp: datetime
    until_timestamp: Optional[datetime]
    entity_types: Optional[List[str]]
    synced_changes: int
    new_entities: int
    updated_entities: int
    errors: Optional[List[str]]
    metadata: Optional[Dict[str, Any]]


class SyncStatusOut(BaseModel):
    """API model for sync system status."""
    active_operations: int
    queued_operations: int
    total_operations_today: int
    last_successful_sync: Optional[datetime]
    system_load_percent: float
    available_workers: int
    sync_health_score: float


class SyncPerformanceOut(BaseModel):
    """API model for sync performance metrics."""
    avg_sync_time_minutes: float
    throughput_changes_per_minute: float
    success_rate_percent: float
    error_rate_percent: float
    peak_performance_hour: Optional[int]
    bottleneck_analysis: Dict[str, Any]


class SyncHealthOut(BaseModel):
    """API model for sync system health."""
    status: str
    s3_connectivity: bool
    database_connectivity: bool
    worker_pool_health: bool
    last_health_check: datetime
    performance_grade: str
    recommended_actions: List[str]


class OptimizationRequest(BaseModel):
    """API model for sync optimization request."""
    target_throughput: Optional[float] = Field(None, description="Target throughput in changes/minute")
    max_batch_size: Optional[int] = Field(None, ge=100, le=50000)
    optimize_for: str = Field("balanced", description="Optimization target: speed, memory, balanced")
    enable_auto_tuning: bool = Field(True, description="Enable automatic parameter tuning")


class OptimizationResultOut(BaseModel):
    """API model for optimization result."""
    optimized_parameters: Dict[str, Any]
    expected_improvement_percent: float
    recommendation_summary: str
    applied_changes: List[str]


def get_incremental_sync_engine(db: Session = Depends(get_db)):
    """Get IncrementalSyncEngine instance via service factory."""
    return get_incremental_sync_engine_via_factory(db)


# Core Sync Operations

@router.post("/incremental", response_model=SyncOperationOut)
def start_incremental_sync(
    request: IncrementalSyncRequest,
    background_tasks: BackgroundTasks,
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Start a new incremental synchronization operation."""
    try:
        # Validate timestamp range
        if request.until and request.since >= request.until:
            raise HTTPException(status_code=400, detail="'since' timestamp must be before 'until' timestamp")
        
        # Start sync operation (runs in background)
        operation = sync_engine.sync_incremental(
            since=request.since,
            until=request.until,
            entity_types=request.entity_types,
            sync_strategy=request.sync_strategy,
            batch_size=request.batch_size,
            max_parallel_workers=request.max_parallel_workers
        )
        
        return SyncOperationOut.model_validate(operation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start incremental sync: {str(e)}")


@router.get("/operations", response_model=List[SyncOperationOut])
def list_sync_operations(
    sync_type: Optional[str] = Query(None, description="Filter by sync type"),
    status: Optional[str] = Query(None, description="Filter by status (completed, running, failed)"),
    since: Optional[datetime] = Query(None, description="List operations since timestamp"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of operations to return"),
    offset: int = Query(0, ge=0, description="Number of operations to skip"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """List sync operations with optional filtering."""
    try:
        operations = sync_engine.list_sync_operations(
            sync_type=sync_type,
            status=status,
            since=since,
            limit=limit,
            offset=offset
        )
        return [SyncOperationOut.model_validate(op) for op in operations]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sync operations: {str(e)}")


@router.get("/operations/{operation_id}", response_model=SyncOperationOut)
def get_sync_operation(
    operation_id: str = Path(..., description="Sync operation ID"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Get detailed information about a specific sync operation."""
    try:
        operation = sync_engine.get_sync_operation(operation_id)
        if not operation:
            raise HTTPException(status_code=404, detail=f"Sync operation {operation_id} not found")
        return SyncOperationOut.model_validate(operation)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync operation: {str(e)}")


@router.post("/operations/{operation_id}/cancel")
def cancel_sync_operation(
    operation_id: str = Path(..., description="Sync operation ID to cancel"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Cancel a running sync operation."""
    try:
        success = sync_engine.cancel_sync_operation(operation_id)
        if not success:
            raise HTTPException(status_code=400, detail="Cannot cancel sync operation - may not be running")
        return {"message": f"Sync operation {operation_id} cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel sync operation: {str(e)}")


# Sync System Status and Monitoring

@router.get("/status", response_model=SyncStatusOut)
def get_sync_status(
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Get current sync system status and activity."""
    try:
        status = sync_engine.get_sync_system_status()
        return SyncStatusOut.model_validate(status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.get("/performance", response_model=SyncPerformanceOut)
def get_sync_performance_metrics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Get comprehensive sync performance metrics."""
    try:
        performance = sync_engine.get_sync_performance_metrics(days=days)
        return SyncPerformanceOut.model_validate(performance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync performance: {str(e)}")


@router.get("/health", response_model=SyncHealthOut)
def get_sync_health(
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Get sync system health and diagnostics."""
    try:
        health = sync_engine.get_sync_system_health()
        return SyncHealthOut.model_validate(health)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync health: {str(e)}")


# Optimization and Performance Tuning

@router.post("/optimize", response_model=OptimizationResultOut)
def optimize_sync_configuration(
    request: OptimizationRequest,
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Optimize sync configuration for better performance."""
    try:
        optimization_result = sync_engine.optimize_sync_configuration(
            target_throughput=request.target_throughput,
            max_batch_size=request.max_batch_size,
            optimize_for=request.optimize_for,
            enable_auto_tuning=request.enable_auto_tuning
        )
        return OptimizationResultOut.model_validate(optimization_result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to optimize sync configuration: {str(e)}")


@router.get("/recommendations")
def get_sync_recommendations(
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Get performance recommendations for sync operations."""
    try:
        recommendations = sync_engine.get_performance_recommendations()
        return {"recommendations": recommendations, "generated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


# Advanced Sync Features

@router.post("/full-resync")
def trigger_full_resync(
    entity_types: Optional[List[str]] = Query(None, description="Specific entity types to resync"),
    force: bool = Query(False, description="Force resync even if recent sync exists"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Trigger a full data resynchronization."""
    try:
        operation = sync_engine.trigger_full_resync(
            entity_types=entity_types,
            force=force
        )
        return {"message": "Full resync triggered", "operation_id": operation["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger full resync: {str(e)}")


@router.post("/validate-data")
def validate_sync_data_integrity(
    sample_size: int = Query(1000, ge=100, le=10000, description="Number of records to sample"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Validate data integrity between local and remote sources."""
    try:
        validation_result = sync_engine.validate_data_integrity(sample_size=sample_size)
        return {
            "validation_status": validation_result["status"],
            "integrity_score": validation_result["integrity_score"],
            "issues_found": validation_result["issues_found"],
            "sample_size": sample_size,
            "validated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate data integrity: {str(e)}")


@router.get("/partition-analytics")
def get_partition_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Get analytics about data partition performance."""
    try:
        analytics = sync_engine.get_partition_analytics(days=days)
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get partition analytics: {str(e)}")


# Batch and Scheduled Operations

@router.post("/schedule-sync")
def schedule_recurring_sync(
    cron_expression: str = Query(..., description="Cron expression for sync schedule"),
    sync_config: IncrementalSyncRequest = ...,
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Schedule recurring incremental sync operations."""
    try:
        schedule_id = sync_engine.schedule_recurring_sync(
            cron_expression=cron_expression,
            sync_config=sync_config.model_dump()
        )
        return {"message": "Sync scheduled successfully", "schedule_id": schedule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule sync: {str(e)}")


@router.get("/schedules")
def list_sync_schedules(
    active_only: bool = Query(True, description="Show only active schedules"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """List all scheduled sync operations."""
    try:
        schedules = sync_engine.list_sync_schedules(active_only=active_only)
        return {"schedules": schedules}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sync schedules: {str(e)}")


@router.delete("/schedules/{schedule_id}")
def cancel_sync_schedule(
    schedule_id: str = Path(..., description="Schedule ID to cancel"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Cancel a scheduled sync operation."""
    try:
        success = sync_engine.cancel_sync_schedule(schedule_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
        return {"message": f"Schedule {schedule_id} cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel schedule: {str(e)}")


# Emergency and Recovery Operations

@router.post("/emergency-stop")
def emergency_stop_all_sync(
    reason: str = Query(..., description="Reason for emergency stop"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Emergency stop all running sync operations."""
    try:
        stopped_count = sync_engine.emergency_stop_all_sync(reason=reason)
        return {
            "message": "Emergency stop executed",
            "stopped_operations": stopped_count,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute emergency stop: {str(e)}")


@router.post("/recovery/resume-failed")
def resume_failed_operations(
    max_retry_count: int = Query(3, ge=1, le=10, description="Maximum retry attempts"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Resume failed sync operations with retry logic."""
    try:
        resumed_operations = sync_engine.resume_failed_operations(max_retry_count=max_retry_count)
        return {
            "message": "Failed operations resumed",
            "resumed_count": len(resumed_operations),
            "operation_ids": resumed_operations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume operations: {str(e)}")


@router.get("/metrics/export")
def export_sync_metrics(
    format: str = Query("json", description="Export format: json, csv"),
    days: int = Query(30, ge=1, le=365, description="Number of days to export"),
    sync_engine = Depends(get_incremental_sync_engine)
):
    """Export sync metrics for external analysis."""
    from fastapi.responses import StreamingResponse
    import io
    import json
    
    try:
        metrics = sync_engine.export_sync_metrics(days=days, format=format)
        
        if format.lower() == "csv":
            import pandas as pd
            df = pd.DataFrame(metrics)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            
            return StreamingResponse(
                io.BytesIO(csv_buffer.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=sync_metrics_{days}days.csv"}
            )
        else:
            json_str = json.dumps(metrics, indent=2, default=str)
            return StreamingResponse(
                io.BytesIO(json_str.encode()),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=sync_metrics_{days}days.json"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export metrics: {str(e)}")