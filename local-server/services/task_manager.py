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
from typing import Any, Dict, List, Optional, Awaitable, Protocol
from utils.logger import get_logger


logger = get_logger(__name__)


class ProgressCallback(Protocol):
    """Protocol for progress callback functions."""
    def __call__(self, task_id: str, progress: float) -> None:
        """
        Called when task progress updates.

        Args:
            task_id: The task identifier
            progress: Progress value from 0.0 to 1.0
        """
        ...


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
        # Filter out internal metadata keys (those starting with '_')
        public_metadata = {k: v for k, v in self.metadata.items() if not k.startswith('_')}

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
            "metadata": public_metadata
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

    def __init__(self, max_queue_size: int = 100, max_dlq_size: int = 1000, max_task_history: int = 10000):
        """
        Initialize the TaskManager.

        Args:
            max_queue_size: Maximum number of tasks in queue (default: 100)
            max_dlq_size: Maximum size of dead letter queue (default: 1000)
            max_task_history: Maximum number of completed tasks to keep in memory (default: 10000)
        """
        self.max_queue_size = max_queue_size
        self.max_dlq_size = max_dlq_size
        self.max_task_history = max_task_history
        self.task_queue: asyncio.Queue[BackgroundTask] = asyncio.Queue(maxsize=max_queue_size)
        self.tasks: Dict[str, BackgroundTask] = {}  # All tasks by ID
        self.dead_letter_queue: List[BackgroundTask] = []  # Failed tasks for analysis
        self._tasks_lock = asyncio.Lock()  # Protect concurrent access to tasks dict
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        logger.info(f"TaskManager initialized with max_queue_size={max_queue_size}, max_dlq_size={max_dlq_size}, max_task_history={max_task_history}")

    async def start(self):
        """
        Start the task manager worker.

        This method is idempotent and safe to call multiple times.
        Subsequent calls after the first will be no-ops.
        """
        if self._running:
            logger.debug("TaskManager is already running; ignoring duplicate start request")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("TaskManager worker started")

    async def shutdown(self, timeout: float = 5.0):
        """
        Shutdown the task manager gracefully.

        Args:
            timeout: Maximum time to wait for worker to finish (seconds)
        """
        if not self._running:
            return

        logger.info("Shutting down TaskManager...")
        self._running = False

        # Mark all pending/running tasks as cancelled first, before stopping worker
        # We iterate over a copy since we're modifying task state
        tasks_to_cancel = [
            task for task in list(self.tasks.values())
            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
        ]

        for task in tasks_to_cancel:
            await self._cancel_task_internal(task)

        # Cancel worker task and wait briefly for it to finish
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"Worker task did not finish within {timeout}s timeout during shutdown")
            except asyncio.CancelledError:
                # This is expected when we cancel the task
                pass
            except Exception as e:
                logger.error(f"Unexpected exception during worker shutdown: {type(e).__name__}: {e}")

        logger.info("TaskManager shutdown complete")

    async def submit_task(
        self,
        task_type: str,
        coroutine: Awaitable[Any],
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        timeout: Optional[float] = None
    ) -> str:
        """
        Submit a new task to the queue.

        Args:
            task_type: Type of task (e.g., 'predicate_discovery')
            coroutine: The async coroutine to execute
            metadata: Optional metadata about the task
            progress_callback: Optional callback for progress updates: callback(task_id, progress)
            timeout: Optional timeout in seconds for task execution

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

        # Store the coroutine, progress callback, and timeout in metadata for worker
        task.metadata['_coroutine'] = coroutine
        task.metadata['_progress_callback'] = progress_callback
        task.metadata['_timeout'] = timeout

        # Try to add to queue (raises QueueFull if at capacity)
        try:
            self.task_queue.put_nowait(task)
            async with self._tasks_lock:
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
            logger.debug(f"Cannot cancel task {task_id}: not found (may have been cleaned up)")
            return False

        if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            logger.debug(f"Cannot cancel task {task_id}: already in state {task.status.value}")
            return False

        await self._cancel_task_internal(task)
        return True

    async def _cancel_task_internal(self, task: BackgroundTask):
        """Internal method to cancel a task."""
        if task._asyncio_task and not task._asyncio_task.done():
            task._asyncio_task.cancel()
            try:
                # Use a short timeout to avoid hanging if task is unresponsive
                await asyncio.wait_for(task._asyncio_task, timeout=1.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                logger.warning(f"Task {task.task_id} cancellation timed out after 1.0s")
            except Exception as e:
                logger.warning(f"Exception during task {task.task_id} cancellation: {e}")

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
        if task and task.status == TaskStatus.RUNNING:
            task.progress = max(0.0, min(1.0, progress))  # Clamp to [0.0, 1.0]
            logger.debug(f"Task {task_id} progress: {task.progress:.2%}")

    def _cleanup_completed_tasks(self):
        """
        Remove old completed tasks from memory to prevent unbounded growth.

        Keeps the most recent completed/failed/cancelled tasks up to max_task_history.
        """
        if len(self.tasks) <= self.max_task_history:
            return

        # Sort by completion time, keeping most recent
        completed_tasks = [
            (task_id, task) for task_id, task in self.tasks.items()
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        ]

        if not completed_tasks:
            return

        # Sort by completed_at time (most recent last)
        completed_tasks.sort(key=lambda x: x[1].completed_at or datetime.now(timezone.utc))

        # Calculate how many to remove
        excess = len(self.tasks) - self.max_task_history
        tasks_to_remove = completed_tasks[:excess]

        for task_id, task in tasks_to_remove:
            del self.tasks[task_id]
            logger.debug(f"Cleaned up completed task {task_id} from memory")

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
                    # Periodically clean up old completed tasks
                    self._cleanup_completed_tasks()
                    continue

                # Process the task
                await self._process_task(task)

                # Clean up after processing
                self._cleanup_completed_tasks()

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

        # Extract coroutine, progress callback, and timeout from metadata
        coroutine = task.metadata.pop('_coroutine', None)
        progress_callback = task.metadata.pop('_progress_callback', None)
        timeout = task.metadata.pop('_timeout', None)

        if coroutine is None:
            logger.error(f"Task {task.task_id} has no coroutine to execute")
            task.status = TaskStatus.FAILED
            task.error = "No coroutine provided"
            task.completed_at = datetime.now(timezone.utc)
            self._add_to_dead_letter_queue(task)
            return

        # Create wrapper coroutine that supports progress callback
        async def execute_with_progress():
            # If progress callback provided, inject it into coroutine context
            if progress_callback:
                # Create a wrapped progress updater that calls both internal and external callbacks
                def progress_updater(progress: float):
                    self._update_progress(task.task_id, progress)
                    try:
                        progress_callback(task.task_id, progress)
                    except Exception as e:
                        logger.warning(f"Progress callback error for task {task.task_id}: {e}")

                # Execute the coroutine with progress support
                # Note: The actual implementation depends on how the coroutine accepts progress updates
                # For now, we assume the coroutine can access progress via callback
                return await coroutine
            else:
                return await coroutine

        # Wrap the coroutine in an asyncio task
        task._asyncio_task = asyncio.create_task(execute_with_progress())

        try:
            # Execute the task with optional timeout
            if timeout:
                result = await asyncio.wait_for(task._asyncio_task, timeout=timeout)
            else:
                result = await task._asyncio_task

            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.progress = 1.0
            task.completed_at = datetime.now(timezone.utc)
            logger.info(f"Task {task.task_id} completed successfully")

        except asyncio.TimeoutError:
            # Task timed out
            task.status = TaskStatus.FAILED
            task.error = f"Task timed out after {timeout} seconds"
            task.completed_at = datetime.now(timezone.utc)
            self._add_to_dead_letter_queue(task)
            logger.error(f"Task {task.task_id} timed out after {timeout} seconds")

        except asyncio.CancelledError:
            # Task was cancelled
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            logger.info(f"Task {task.task_id} was cancelled")
            # Re-raise to propagate cancellation to worker loop
            raise

        except Exception as e:
            # Task failed
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)

            # Add to dead letter queue for analysis
            self._add_to_dead_letter_queue(task)

            logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)

    def _add_to_dead_letter_queue(self, task: BackgroundTask):
        """
        Add a failed task to the dead letter queue with size limit enforcement.

        Args:
            task: The failed task to add
        """
        self.dead_letter_queue.append(task)

        # Enforce max DLQ size with FIFO eviction
        while len(self.dead_letter_queue) > self.max_dlq_size:
            evicted = self.dead_letter_queue.pop(0)
            logger.warning(
                f"Dead letter queue exceeded max size ({self.max_dlq_size}), "
                f"evicted oldest task: {evicted.task_id}"
            )

    def clear_dead_letter_queue(self):
        """Clear all tasks from the dead letter queue."""
        count = len(self.dead_letter_queue)
        self.dead_letter_queue.clear()
        logger.info(f"Cleared {count} tasks from dead letter queue")

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


def initialize_task_manager(max_queue_size: int = 100, max_dlq_size: int = 1000, max_task_history: int = 10000) -> TaskManager:
    """
    Initialize the global TaskManager instance.

    Args:
        max_queue_size: Maximum number of tasks in queue
        max_dlq_size: Maximum size of dead letter queue
        max_task_history: Maximum number of completed tasks to keep in memory

    Returns:
        The initialized TaskManager instance
    """
    global _task_manager
    if _task_manager is not None:
        if _task_manager._running:
            logger.warning("TaskManager is already running; returning existing instance")
        else:
            logger.debug("Reusing existing TaskManager instance")
        return _task_manager

    _task_manager = TaskManager(max_queue_size=max_queue_size, max_dlq_size=max_dlq_size, max_task_history=max_task_history)
    logger.info("Global TaskManager initialized")
    return _task_manager


async def shutdown_task_manager():
    """Shutdown the global TaskManager instance."""
    global _task_manager
    if _task_manager is not None:
        await _task_manager.shutdown()
        _task_manager = None
        logger.info("Global TaskManager shut down")
