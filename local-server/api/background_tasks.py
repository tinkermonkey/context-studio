"""
API endpoints for background task management.

This module provides REST API endpoints for managing background tasks,
including task submission, status retrieval, and cancellation.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from services.task_manager import get_task_manager
from utils.logger import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["background-tasks"])


# Response models
class TaskStatusResponse(BaseModel):
    """Response model for task status."""
    task_id: str
    task_type: str
    status: str
    progress: float = Field(ge=0.0, le=1.0)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskListResponse(BaseModel):
    """Response model for list of tasks."""
    tasks: List[TaskStatusResponse]
    total: int


class TaskStatsResponse(BaseModel):
    """Response model for task statistics."""
    total_tasks: int
    queue_size: int
    max_queue_size: int
    dead_letter_queue_size: int
    status_counts: Dict[str, int]
    is_running: bool


class CancelTaskResponse(BaseModel):
    """Response model for task cancellation."""
    task_id: str
    cancelled: bool
    message: str


# NOTE: Specific routes (with literal paths) must be defined BEFORE
# parameterized routes (with path parameters like {task_id}) to avoid conflicts

@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status_filter: Optional[str] = None,
    task_type: Optional[str] = None
):
    """
    List all background tasks with optional filtering.

    Args:
        status_filter: Optional status filter (pending, running, completed, failed, cancelled)
        task_type: Optional task type filter

    Returns:
        List of tasks matching the filters
    """
    try:
        task_manager = get_task_manager()
        all_tasks = task_manager.get_all_tasks()

        # Apply filters
        filtered_tasks = all_tasks

        if status_filter:
            status_filter_lower = status_filter.lower()
            filtered_tasks = [
                t for t in filtered_tasks
                if t['status'].lower() == status_filter_lower
            ]

        if task_type:
            filtered_tasks = [
                t for t in filtered_tasks
                if t['task_type'] == task_type
            ]

        return TaskListResponse(
            tasks=[TaskStatusResponse(**t) for t in filtered_tasks],
            total=len(filtered_tasks)
        )

    except RuntimeError as e:
        logger.error(f"TaskManager not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task management service not available"
        )
    except Exception as e:
        logger.error(f"Error listing tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/stats/summary", response_model=TaskStatsResponse)
async def get_task_stats():
    """
    Get task management statistics.

    Returns:
        Statistics about task manager and tasks
    """
    try:
        task_manager = get_task_manager()
        stats = task_manager.get_stats()

        return TaskStatsResponse(**stats)

    except RuntimeError as e:
        logger.error(f"TaskManager not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task management service not available"
        )
    except Exception as e:
        logger.error(f"Error getting task stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/dead-letter-queue", response_model=TaskListResponse)
async def get_dead_letter_queue():
    """
    Get all failed tasks from the dead letter queue.

    Returns:
        List of failed tasks requiring manual intervention
    """
    try:
        task_manager = get_task_manager()
        dead_letter_tasks = task_manager.get_dead_letter_queue()

        return TaskListResponse(
            tasks=[TaskStatusResponse(**t) for t in dead_letter_tasks],
            total=len(dead_letter_tasks)
        )

    except RuntimeError as e:
        logger.error(f"TaskManager not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task management service not available"
        )
    except Exception as e:
        logger.error(f"Error getting dead letter queue: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of a background task.

    Args:
        task_id: The unique task identifier

    Returns:
        Task status information

    Raises:
        HTTPException: 404 if task not found
    """
    try:
        task_manager = get_task_manager()
        task_status = task_manager.get_task_status(task_id)

        if task_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )

        return TaskStatusResponse(**task_status)

    except RuntimeError as e:
        logger.error(f"TaskManager not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task management service not available"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{task_id}", response_model=CancelTaskResponse)
async def cancel_task(task_id: str):
    """
    Cancel a running or pending background task.

    Args:
        task_id: The unique task identifier

    Returns:
        Cancellation result

    Raises:
        HTTPException: 404 if task not found, 400 if task cannot be cancelled
    """
    try:
        task_manager = get_task_manager()

        # Check if task exists
        task_status = task_manager.get_task_status(task_id)
        if task_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )

        # Check if task can be cancelled
        current_status = task_status['status']
        if current_status not in ['pending', 'running']:
            return CancelTaskResponse(
                task_id=task_id,
                cancelled=False,
                message=f"Task is in state '{current_status}' and cannot be cancelled"
            )

        # Cancel the task
        cancelled = await task_manager.cancel_task(task_id)

        return CancelTaskResponse(
            task_id=task_id,
            cancelled=cancelled,
            message="Task cancelled successfully" if cancelled else "Task cancellation failed"
        )

    except RuntimeError as e:
        logger.error(f"TaskManager not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task management service not available"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
