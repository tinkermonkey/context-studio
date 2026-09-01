"""API endpoints for LLM traceability and selection tracking."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from llm.execution_tracker import ExecutionTracker
from llm.models import (
    ExecutionHistoryResponse,
    FlavorAnalyticsResponse,
    PipelineType,
    RecordSelectionRequest,
    SelectionResponse,
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/llm", tags=["LLM Traceability"])


@router.post("/record-selection", response_model=SelectionResponse)
async def record_selection(request: RecordSelectionRequest):
    """Record when a user selects an LLM suggestion."""

    try:
        tracker = ExecutionTracker()
        selection_id = tracker.record_selection(request)

        return SelectionResponse(
            success=True,
            selection_id=selection_id,
            message="Selection recorded successfully",
        )

    except ValueError as e:
        logger.debug(f"Invalid selection request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error recording selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record selection",
        )


@router.get("/execution-analytics")
async def get_execution_analytics(
    pipeline_type: PipelineType | None = None, days_back: int = 30
) -> dict[str, Any]:
    """Get analytics for LLM executions."""

    try:
        tracker = ExecutionTracker()
        analytics = tracker.get_execution_analytics(pipeline_type, days_back)

        return {
            "success": True,
            "data": analytics,
            "filters": {
                "pipeline_type": (
                    pipeline_type.value if pipeline_type else "all"
                ),
                "days_back": days_back,
            },
        }

    except Exception as e:
        logger.error(f"Error getting execution analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution analytics",
        )


@router.get("/execution-details/{execution_id}")
async def get_execution_details(execution_id: str) -> dict[str, Any]:
    """Get detailed information about a specific execution."""

    try:
        tracker = ExecutionTracker()
        details = tracker.get_execution_details(execution_id)

        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found",
            )

        return {"success": True, "data": details}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution details",
        )


@router.get("/execution-history", response_model=ExecutionHistoryResponse)
async def get_execution_history(
    flavor_id: str = Query(
        ..., description="Flavor ID to get execution history for"
    ),
    limit: int = Query(
        100, description="Maximum number of executions to return"
    ),
) -> ExecutionHistoryResponse:
    """Get execution history for a specific flavor."""

    try:
        tracker = ExecutionTracker()
        history = tracker.get_flavor_execution_history(flavor_id, limit)

        if "error" in history:
            raise Exception(history["error"])

        return ExecutionHistoryResponse(
            executions=history["executions"],
            total_count=history["total_count"],
            flavor_id=history["flavor_id"],
        )

    except ValueError as e:
        logger.debug(f"Invalid execution history request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution history",
        )


@router.get(
    "/flavor-analytics/{flavor_id}", response_model=FlavorAnalyticsResponse
)
async def get_flavor_analytics(
    flavor_id: str,
    days_back: int = Query(30, description="Number of days of data to include"),
) -> FlavorAnalyticsResponse:
    """Get analytics for a specific flavor."""

    try:
        tracker = ExecutionTracker()
        analytics_data = tracker.get_flavor_analytics(flavor_id, days_back)

        if "error" in analytics_data:
            raise Exception(analytics_data["error"])

        return FlavorAnalyticsResponse(
            flavor_id=analytics_data["flavor_id"],
            analytics=analytics_data["analytics"],
            time_range_days=analytics_data["time_range_days"],
        )

    except ValueError as e:
        logger.debug(f"Invalid flavor analytics request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting flavor analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get flavor analytics",
        )


@router.get("/health")
async def traceability_health() -> dict[str, Any]:
    """Health check endpoint for LLM traceability service."""

    try:
        tracker = ExecutionTracker()
        # Test basic functionality by getting analytics
        analytics = tracker.get_execution_analytics(days_back=1)

        return {
            "status": "healthy",
            "service": "llm_traceability",
            "database_accessible": "error" not in analytics,
            "timestamp": "2024-01-01T00:00:00Z",  # Would use actual timestamp in production
        }

    except Exception as e:
        logger.error(f"Traceability health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM traceability service unhealthy",
        )
