"""
Background task management system using asyncio.

This module implements the asyncio-based background task management system
for long-running operations like discovery and mapping tasks. It provides
task queuing, progress tracking, cancellation support, and dead letter queue
for failed tasks.

Design based on ADR-005: Background Processing with Asyncio.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable
from utils.logger import get_logger


logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """
    Represents a background task with its metadata and state.

    Attributes:
        task_id: Unique identifier for the task
        task_type: Type of task (e.g., 'predicate_discovery', 'mapping_operation')
        status: Current status of the task
        progress: Progress indicator (0.0 to 1.0)
        result: Result data when task completes successfully
        error: Error message if task fails
        created_at: Timestamp when task was created
        started_at: Timestamp when task execution started
        completed_at: Timestamp when task completed/failed/cancelled
        metadata: Additional task-specific metadata
    """
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Internal asyncio task handle (not serialized)
    _asyncio_task: Optional[asyncio.Task] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata
        }


class TaskManager:
    """
    Manages background tasks using asyncio.

    Features:
    - Task queue with configurable max size (default: 100)
    - Progress tracking via callbacks
    - Task cancellation support
    - Dead letter queue for failed tasks
    - Sequential task processing to control resource usage

    Usage:
        task_manager = TaskManager()
        await task_manager.start()

        task_id = await task_manager.submit_task(
            task_type="discovery",
            coroutine=my_async_function(),
            metadata={"description": "Discover predicates"}
        )

        status = task_manager.get_task_status(task_id)
        await task_manager.cancel_task(task_id)
        await task_manager.shutdown()
    """

    def __init__(self, max_queue_size: int = 100):
        """
        Initialize the TaskManager.

        Args:
            max_queue_size: Maximum number of tasks in queue (default: 100)
        """
        self.max_queue_size = max_queue_size
        self.task_queue: asyncio.Queue[BackgroundTask] = asyncio.Queue(maxsize=max_queue_size)
        self.tasks: Dict[str, BackgroundTask] = {}  # All tasks by ID
        self.dead_letter_queue: List[BackgroundTask] = []  # Failed tasks for analysis
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        logger.info(f"TaskManager initialized with max_queue_size={max_queue_size}")

    async def start(self):
        """Start the task manager worker."""
        if self._running:
            logger.warning("TaskManager is already running")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("TaskManager worker started")

    async def shutdown(self, timeout: float = 10.0):
        """
        Shutdown the task manager gracefully.

        Args:
            timeout: Maximum time to wait for worker to finish (seconds)
        """
        if not self._running:
            return

        logger.info("Shutting down TaskManager...")
        self._running = False

        # Cancel worker task
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Worker task did not finish within timeout")
            except asyncio.CancelledError:
                pass

        # Cancel all pending/running tasks
        for task in self.tasks.values():
            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                await self._cancel_task_internal(task)

        logger.info("TaskManager shutdown complete")

    async def submit_task(
        self,
        task_type: str,
        coroutine: Awaitable[Any],
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """
        Submit a new task to the queue.

        Args:
            task_type: Type of task (e.g., 'predicate_discovery')
            coroutine: The async coroutine to execute
            metadata: Optional metadata about the task
            progress_callback: Optional callback for progress updates: callback(task_id, progress)

        Returns:
            task_id: Unique identifier for the submitted task

        Raises:
            asyncio.QueueFull: If queue is at maximum capacity
        """
        task_id = str(uuid.uuid4())

        task = BackgroundTask(
            task_id=task_id,
            task_type=task_type,
            metadata=metadata or {}
        )

        # Store the coroutine and progress callback in metadata for worker
        task.metadata['_coroutine'] = coroutine
        task.metadata['_progress_callback'] = progress_callback

        # Try to add to queue (raises QueueFull if at capacity)
        try:
            self.task_queue.put_nowait(task)
            self.tasks[task_id] = task
            logger.info(f"Task {task_id} ({task_type}) submitted to queue")
            return task_id
        except asyncio.QueueFull:
            logger.error(f"Task queue is full (max={self.max_queue_size}), cannot submit task")
            raise

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a task.

        Args:
            task_id: The task identifier

        Returns:
            Task status dictionary or None if task not found
        """
        task = self.tasks.get(task_id)
        if task is None:
            return None
        return task.to_dict()

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or pending task.

        Args:
            task_id: The task identifier

        Returns:
            True if task was cancelled, False if task not found or already completed
        """
        task = self.tasks.get(task_id)
        if task is None:
            logger.warning(f"Cannot cancel task {task_id}: not found")
            return False

        if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            logger.warning(f"Cannot cancel task {task_id}: already in state {task.status.value}")
            return False

        await self._cancel_task_internal(task)
        return True

    async def _cancel_task_internal(self, task: BackgroundTask):
        """Internal method to cancel a task."""
        if task._asyncio_task and not task._asyncio_task.done():
            task._asyncio_task.cancel()
            try:
                await task._asyncio_task
            except asyncio.CancelledError:
                pass

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)
        logger.info(f"Task {task.task_id} cancelled")

    def _update_progress(self, task_id: str, progress: float):
        """
        Update task progress.

        Args:
            task_id: The task identifier
            progress: Progress value (0.0 to 1.0)
        """
        task = self.tasks.get(task_id)
        if task:
            task.progress = max(0.0, min(1.0, progress))  # Clamp to [0.0, 1.0]
            logger.debug(f"Task {task_id} progress: {task.progress:.2%}")

    async def _worker(self):
        """
        Worker coroutine that processes tasks from the queue sequentially.

        This worker ensures only one task runs at a time to control resource usage.
        """
        logger.info("TaskManager worker loop started")

        while self._running:
            try:
                # Wait for a task with timeout to check _running flag periodically
                try:
                    task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Process the task
                await self._process_task(task)

            except asyncio.CancelledError:
                logger.info("Worker received cancellation")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)

        logger.info("TaskManager worker loop exited")

    async def _process_task(self, task: BackgroundTask):
        """
        Process a single task.

        Args:
            task: The BackgroundTask to process
        """
        logger.info(f"Processing task {task.task_id} ({task.task_type})")

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        # Extract coroutine and progress callback from metadata
        coroutine = task.metadata.pop('_coroutine', None)
        progress_callback = task.metadata.pop('_progress_callback', None)

        if coroutine is None:
            logger.error(f"Task {task.task_id} has no coroutine to execute")
            task.status = TaskStatus.FAILED
            task.error = "No coroutine provided"
            task.completed_at = datetime.now(timezone.utc)
            self.dead_letter_queue.append(task)
            return

        # Wrap the coroutine in an asyncio task
        task._asyncio_task = asyncio.create_task(coroutine)

        try:
            # Execute the task
            result = await task._asyncio_task

            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.progress = 1.0
            task.completed_at = datetime.now(timezone.utc)
            logger.info(f"Task {task.task_id} completed successfully")

        except asyncio.CancelledError:
            # Task was cancelled
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            logger.info(f"Task {task.task_id} was cancelled")

        except Exception as e:
            # Task failed
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)

            # Add to dead letter queue for analysis
            self.dead_letter_queue.append(task)

            logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get status of all tasks.

        Returns:
            List of task status dictionaries
        """
        return [task.to_dict() for task in self.tasks.values()]

    def get_dead_letter_queue(self) -> List[Dict[str, Any]]:
        """
        Get all failed tasks from the dead letter queue.

        Returns:
            List of failed task status dictionaries
        """
        return [task.to_dict() for task in self.dead_letter_queue]

    def get_queue_size(self) -> int:
        """Get current number of pending tasks in queue."""
        return self.task_queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get TaskManager statistics.

        Returns:
            Dictionary with stats about tasks
        """
        status_counts = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }

        for task in self.tasks.values():
            status_counts[task.status.value] += 1

        return {
            "total_tasks": len(self.tasks),
            "queue_size": self.get_queue_size(),
            "max_queue_size": self.max_queue_size,
            "dead_letter_queue_size": len(self.dead_letter_queue),
            "status_counts": status_counts,
            "is_running": self._running
        }


# Global task manager instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """
    Get the global TaskManager instance.

    Returns:
        The global TaskManager instance

    Raises:
        RuntimeError: If task manager has not been initialized
    """
    global _task_manager
    if _task_manager is None:
        raise RuntimeError("TaskManager not initialized. Call initialize_task_manager() first.")
    return _task_manager


def initialize_task_manager(max_queue_size: int = 100) -> TaskManager:
    """
    Initialize the global TaskManager instance.

    Args:
        max_queue_size: Maximum number of tasks in queue

    Returns:
        The initialized TaskManager instance
    """
    global _task_manager
    if _task_manager is not None:
        logger.warning("TaskManager already initialized")
        return _task_manager

    _task_manager = TaskManager(max_queue_size=max_queue_size)
    logger.info("Global TaskManager initialized")
    return _task_manager


async def shutdown_task_manager():
    """Shutdown the global TaskManager instance."""
    global _task_manager
    if _task_manager is not None:
        await _task_manager.shutdown()
        _task_manager = None
        logger.info("Global TaskManager shut down")
