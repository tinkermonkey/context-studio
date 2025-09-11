from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from database.utils import get_db
from services.service_factory import get_service_factory
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


@router.get("/status", response_model=SyncResponse)
async def get_sync_status(db: Session = Depends(get_db)) -> SyncResponse:
    """Get synchronization status."""

    try:
        service_factory = get_service_factory()
        sync_manager = service_factory.get_s3_sync_manager(db)

        status = sync_manager.get_sync_status()

        return SyncResponse(
            status="success", message="Sync status retrieved", data=status
        )

    except Exception as e:
        logger.error(f"Get sync status error: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


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
