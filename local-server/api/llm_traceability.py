"""API endpoints for LLM traceability and selection tracking."""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional

from llm.execution_tracker import ExecutionTracker
from llm.models import RecordSelectionRequest, SelectionResponse, PipelineType
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
            message="Selection recorded successfully"
        )
        
    except ValueError as e:
        logger.warning(f"Invalid selection request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error recording selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record selection"
        )


@router.get("/execution-analytics")
async def get_execution_analytics(
    pipeline_type: Optional[PipelineType] = None,
    days_back: int = 30
) -> Dict[str, Any]:
    """Get analytics for LLM executions."""
    
    try:
        tracker = ExecutionTracker()
        analytics = tracker.get_execution_analytics(pipeline_type, days_back)
        
        return {
            "success": True,
            "data": analytics,
            "filters": {
                "pipeline_type": pipeline_type.value if pipeline_type else "all",
                "days_back": days_back
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting execution analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution analytics"
        )


@router.get("/execution-history/{execution_id}")
async def get_execution_details(execution_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific execution."""
    
    try:
        tracker = ExecutionTracker()
        details = tracker.get_execution_details(execution_id)
        
        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found"
            )
        
        return {
            "success": True,
            "data": details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution details"
        )


@router.get("/health")
async def traceability_health() -> Dict[str, Any]:
    """Health check endpoint for LLM traceability service."""
    
    try:
        tracker = ExecutionTracker()
        # Test basic functionality by getting analytics
        analytics = tracker.get_execution_analytics(days_back=1)
        
        return {
            "status": "healthy",
            "service": "llm_traceability",
            "database_accessible": "error" not in analytics,
            "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp in production
        }
        
    except Exception as e:
        logger.error(f"Traceability health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM traceability service unhealthy"
        )