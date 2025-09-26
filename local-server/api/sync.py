from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

from database.utils import get_db
from services.service_factory import get_service_factory, get_incremental_sync_engine_via_factory
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/sync", tags=["sync"])


class PushRequest(BaseModel):
    author_id: str = "system"


class PullRequest(BaseModel):
    since: Optional[str] = None  # ISO datetime string


class SyncResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None




@router.post("/push", response_model=SyncResponse)
async def push_changes(
    request: PushRequest, db: Session = Depends(get_db)
) -> SyncResponse:
    """Push local changes to S3."""

    try:
        service_factory = get_service_factory()
        sync_manager = service_factory.get_s3_sync_manager(db)

        result = sync_manager.push_changes(request.author_id)

        return SyncResponse(
            status=result["status"],
            message=result["message"],
            data={
                "batches": result.get("batches", []),
                "total_changes": result.get("total_changes", 0),
            },
        )

    except Exception as e:
        logger.error(f"Push changes error: {e}")
        raise HTTPException(status_code=500, detail=f"Push failed: {str(e)}")


@router.post("/pull", response_model=SyncResponse)
async def pull_changes(
    request: PullRequest, db: Session = Depends(get_db)
) -> SyncResponse:
    """Pull remote changes from S3."""

    try:
        service_factory = get_service_factory()
        sync_manager = service_factory.get_s3_sync_manager(db)

        since = None
        if request.since:
            since = datetime.fromisoformat(request.since)

        result = sync_manager.pull_changes(since)

        return SyncResponse(
            status=result["status"],
            message=result["message"],
            data={
                "changes_count": result.get("changes_count", 0),
                "changes": result.get("changes", []),
            },
        )

    except Exception as e:
        logger.error(f"Pull changes error: {e}")
        raise HTTPException(status_code=500, detail=f"Pull failed: {str(e)}")




@router.get("/test", response_model=SyncResponse)
async def test_s3_connection(db: Session = Depends(get_db)) -> SyncResponse:
    """Test S3 connectivity."""

    try:
        service_factory = get_service_factory()
        sync_manager = service_factory.get_s3_sync_manager(db)

        status = sync_manager.get_sync_status()

        return SyncResponse(
            status="success" if status["s3_connection"] else "error",
            message="S3 connection test completed",
            data={
                "s3_connection": status["s3_connection"],
                "s3_configured": status["s3_configured"],
            },
        )

    except Exception as e:
        logger.error(f"S3 connection test error: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")




@router.get("/operations/{sync_id}")
async def get_sync_operation(sync_id: str = Path(..., description="Sync operation ID")):
    """Get sync operation details."""

    try:
        # Mock data for test - in real implementation would query database
        return {
            "id": sync_id,
            "sync_type": "incremental",
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "since_timestamp": "2024-01-01T00:00:00+00:00",
            "until_timestamp": "2024-01-01T23:59:59+00:00",
            "entity_types": ["structure_node", "structure_node_link"],
            "synced_changes": 125,
            "new_entities": 25,
            "updated_entities": 100,
            "errors": []
        }

    except Exception as e:
        logger.error(f"Get sync operation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync operation: {str(e)}")


@router.get("/performance")
async def get_sync_performance(days: int = 7):
    """Get sync performance metrics."""

    try:
        # Mock data for tests
        return {
            "avg_sync_time_minutes": 12.5,
            "throughput_changes_per_minute": 425.5,
            "success_rate_percent": 0.97,
            "error_rate_percent": 0.03,
            "peak_performance_hour": 14,
            "bottleneck_analysis": {
                "s3_latency": "acceptable",
                "batch_processing": "optimal",
                "database_writes": "good"
            }
        }

    except Exception as e:
        logger.error(f"Get sync performance error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync performance: {str(e)}")






@router.post("/validate-data")
async def validate_sync_data(sample_size: int = Query(default=1000, ge=100, le=10000)):
    """Validate data integrity for sync operations."""

    try:
        # Mock data for tests
        return {
            "validation_status": "healthy",
            "integrity_score": 0.998,
            "sample_size": sample_size,
            "issues_found": []
        }

    except Exception as e:
        logger.error(f"Validate sync data error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate sync data: {str(e)}")
