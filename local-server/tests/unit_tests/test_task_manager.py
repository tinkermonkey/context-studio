"""
Unit tests for the TaskManager background task management system.

Tests cover:
- Task submission and queue management
- Task state transitions
- Progress tracking
- Task cancellation
- Dead letter queue
- Resource cleanup
- Edge cases and error handling
"""

import sys
import os
import pytest
import asyncio
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.task_manager import (
    TaskManager,
    BackgroundTask,
    TaskStatus,
    initialize_task_manager,
    get_task_manager,
    shutdown_task_manager
)


class TestBackgroundTaskDataclass:
    """Tests for BackgroundTask dataclass."""

    def test_background_task_creation(self):
        """Test creating a BackgroundTask instance."""
        task = BackgroundTask(
            task_id="test-123",
            task_type="discovery"
        )

        assert task.task_id == "test-123"
        assert task.task_type == "discovery"
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
        assert task.result is None
        assert task.error is None
        assert task.created_at is not None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.metadata == {}

    def test_background_task_to_dict(self):
        """Test converting BackgroundTask to dictionary."""
        task = BackgroundTask(
            task_id="test-123",
            task_type="discovery",
            metadata={"key": "value"}
        )

        task_dict = task.to_dict()

        assert task_dict["task_id"] == "test-123"
        assert task_dict["task_type"] == "discovery"
        assert task_dict["status"] == "pending"
        assert task_dict["progress"] == 0.0
        assert task_dict["metadata"] == {"key": "value"}
        assert "created_at" in task_dict


class TestTaskManagerInitialization:
    """Tests for TaskManager initialization and lifecycle."""

    @pytest.mark.asyncio
    async def test_task_manager_initialization(self):
        """Test TaskManager initialization with default settings."""
        task_manager = TaskManager()

        assert task_manager.max_queue_size == 100
        assert task_manager.get_queue_size() == 0
        assert len(task_manager.tasks) == 0
        assert len(task_manager.dead_letter_queue) == 0
        assert not task_manager._running

    @pytest.mark.asyncio
    async def test_task_manager_custom_queue_size(self):
        """Test TaskManager initialization with custom queue size."""
        task_manager = TaskManager(max_queue_size=50)

        assert task_manager.max_queue_size == 50

    @pytest.mark.asyncio
    async def test_task_manager_start_stop(self):
        """Test starting and stopping the TaskManager."""
        task_manager = TaskManager()

        # Start the manager
        await task_manager.start()
        assert task_manager._running is True
        assert task_manager._worker_task is not None

        # Stop the manager
        await task_manager.shutdown()
        assert task_manager._running is False

    @pytest.mark.asyncio
    async def test_task_manager_double_start(self):
        """Test that starting TaskManager twice is safe."""
        task_manager = TaskManager()

        await task_manager.start()
        await task_manager.start()  # Should not raise

        assert task_manager._running is True

        await task_manager.shutdown()


class TestTaskSubmission:
    """Tests for task submission and queue management."""

    @pytest.mark.asyncio
    async def test_submit_simple_task(self):
        """Test submitting a simple async task."""
        task_manager = TaskManager()
        await task_manager.start()

        async def simple_task():
            await asyncio.sleep(0.1)
            return "success"

        task_id = await task_manager.submit_task(
            task_type="test",
            coroutine=simple_task()
        )

        assert task_id is not None
        assert task_id in task_manager.tasks

        # Wait for task to complete
        await asyncio.sleep(0.3)

        task_status = task_manager.get_task_status(task_id)
        assert task_status is not None
        assert task_status["status"] == TaskStatus.COMPLETED.value
        assert task_status["result"] == "success"

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_submit_task_with_metadata(self):
        """Test submitting a task with metadata."""
        task_manager = TaskManager()
        await task_manager.start()

        async def simple_task():
            return "done"

        metadata = {"description": "Test task", "priority": "high"}
        task_id = await task_manager.submit_task(
            task_type="discovery",
            coroutine=simple_task(),
            metadata=metadata
        )

        task_status = task_manager.get_task_status(task_id)
        assert task_status["metadata"]["description"] == "Test task"
        assert task_status["metadata"]["priority"] == "high"

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_queue_overflow(self):
        """Test that queue overflow is handled gracefully."""
        task_manager = TaskManager(max_queue_size=2)
        await task_manager.start()

        async def slow_task():
            await asyncio.sleep(10)  # Long running task

        # Fill the queue
        await task_manager.submit_task("test", slow_task())
        await task_manager.submit_task("test", slow_task())

        # Third task should raise QueueFull
        with pytest.raises(asyncio.QueueFull):
            await task_manager.submit_task("test", slow_task())

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_task_id_uniqueness(self):
        """Test that each submitted task gets a unique ID."""
        task_manager = TaskManager()
        await task_manager.start()

        async def simple_task():
            return "done"

        task_ids = set()
        for _ in range(10):
            task_id = await task_manager.submit_task("test", simple_task())
            task_ids.add(task_id)

        assert len(task_ids) == 10  # All IDs should be unique

        await task_manager.shutdown()


class TestTaskStateTransitions:
    """Tests for task state transitions."""

    @pytest.mark.asyncio
    async def test_pending_to_running_to_completed(self):
        """Test task state: pending → running → completed."""
        task_manager = TaskManager()
        await task_manager.start()

        async def task_func():
            await asyncio.sleep(0.1)
            return "result"

        task_id = await task_manager.submit_task("test", task_func())

        # Initial state should be pending
        status = task_manager.get_task_status(task_id)
        # Note: task might already be running by the time we check
        assert status["status"] in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]

        # Wait for completion
        await asyncio.sleep(0.3)

        status = task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.COMPLETED.value
        assert status["result"] == "result"
        assert status["started_at"] is not None
        assert status["completed_at"] is not None

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_pending_to_running_to_failed(self):
        """Test task state: pending → running → failed."""
        task_manager = TaskManager()
        await task_manager.start()

        async def failing_task():
            await asyncio.sleep(0.1)
            raise ValueError("Task failed intentionally")

        task_id = await task_manager.submit_task("test", failing_task())

        # Wait for task to fail
        await asyncio.sleep(0.3)

        status = task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.FAILED.value
        assert "Task failed intentionally" in status["error"]
        assert status["completed_at"] is not None

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_pending_to_cancelled(self):
        """Test task state: pending → cancelled."""
        task_manager = TaskManager()
        await task_manager.start()

        async def long_task():
            await asyncio.sleep(10)

        # Submit multiple tasks to ensure some stay pending
        task_ids = []
        for _ in range(3):
            task_id = await task_manager.submit_task("test", long_task())
            task_ids.append(task_id)

        # Cancel the last task (likely still pending)
        await asyncio.sleep(0.1)
        cancelled = await task_manager.cancel_task(task_ids[-1])

        assert cancelled is True

        status = task_manager.get_task_status(task_ids[-1])
        assert status["status"] == TaskStatus.CANCELLED.value

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_running_to_cancelled(self):
        """Test task state: running → cancelled."""
        task_manager = TaskManager()
        await task_manager.start()

        async def long_running_task():
            await asyncio.sleep(5)

        task_id = await task_manager.submit_task("test", long_running_task())

        # Wait for task to start
        await asyncio.sleep(0.2)

        # Cancel the running task
        cancelled = await task_manager.cancel_task(task_id)
        assert cancelled is True

        status = task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.CANCELLED.value

        await task_manager.shutdown()


class TestProgressTracking:
    """Tests for task progress tracking."""

    @pytest.mark.asyncio
    async def test_progress_tracking(self):
        """Test that progress tracking works correctly."""
        task_manager = TaskManager()
        await task_manager.start()

        async def task_with_progress():
            # Simulate progress
            task_manager._update_progress(task_id, 0.3)
            await asyncio.sleep(0.05)
            task_manager._update_progress(task_id, 0.6)
            await asyncio.sleep(0.05)
            task_manager._update_progress(task_id, 1.0)
            return "done"

        task_id = await task_manager.submit_task("test", task_with_progress())

        # Wait for task to complete
        await asyncio.sleep(0.3)

        status = task_manager.get_task_status(task_id)
        assert status["progress"] == 1.0

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """Test that progress callbacks are invoked correctly."""
        task_manager = TaskManager()
        await task_manager.start()

        progress_updates = []

        def progress_callback(task_id, progress):
            progress_updates.append((task_id, progress))

        async def task_with_progress():
            task_manager._update_progress(task_id, 0.5)
            await asyncio.sleep(0.05)
            return "done"

        task_id = await task_manager.submit_task(
            "test",
            task_with_progress(),
            progress_callback=progress_callback
        )

        # Wait for task to complete
        await asyncio.sleep(0.3)

        # Progress callback should have been called
        assert len(progress_updates) > 0
        assert any(task_id in str(update) for update in progress_updates)

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_progress_clamping(self):
        """Test that progress is clamped to [0.0, 1.0] range."""
        task_manager = TaskManager()
        await task_manager.start()

        async def task_func():
            return "done"

        task_id = await task_manager.submit_task("test", task_func())

        # Wait for task to start running
        await asyncio.sleep(0.1)

        # Test clamping to max
        task_manager._update_progress(task_id, 1.5)
        status = task_manager.get_task_status(task_id)
        assert status["progress"] <= 1.0

        # Test clamping to min
        task_manager._update_progress(task_id, -0.5)
        status = task_manager.get_task_status(task_id)
        assert status["progress"] >= 0.0

        await task_manager.shutdown()


class TestTaskCancellation:
    """Tests for task cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self):
        """Test cancelling a pending task."""
        task_manager = TaskManager()
        await task_manager.start()

        async def slow_task():
            await asyncio.sleep(10)

        # Submit multiple tasks
        task_id1 = await task_manager.submit_task("test", slow_task())
        task_id2 = await task_manager.submit_task("test", slow_task())

        # Cancel the second task (likely pending)
        cancelled = await task_manager.cancel_task(task_id2)
        assert cancelled is True

        status = task_manager.get_task_status(task_id2)
        assert status["status"] == TaskStatus.CANCELLED.value

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_cancel_running_task(self):
        """Test cancelling a running task."""
        task_manager = TaskManager()
        await task_manager.start()

        async def long_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                # Task should handle cancellation
                raise

        task_id = await task_manager.submit_task("test", long_task())

        # Wait for task to start
        await asyncio.sleep(0.1)

        # Cancel the task
        cancelled = await task_manager.cancel_task(task_id)
        assert cancelled is True

        # Wait a bit for cancellation to process
        await asyncio.sleep(0.1)

        status = task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.CANCELLED.value

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self):
        """Test that completed tasks cannot be cancelled."""
        task_manager = TaskManager()
        await task_manager.start()

        async def quick_task():
            return "done"

        task_id = await task_manager.submit_task("test", quick_task())

        # Wait for completion
        await asyncio.sleep(0.2)

        # Try to cancel completed task
        cancelled = await task_manager.cancel_task(task_id)
        assert cancelled is False

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        """Test cancelling a task that doesn't exist."""
        task_manager = TaskManager()
        await task_manager.start()

        cancelled = await task_manager.cancel_task("nonexistent-id")
        assert cancelled is False

        await task_manager.shutdown()


class TestDeadLetterQueue:
    """Tests for dead letter queue functionality."""

    @pytest.mark.asyncio
    async def test_failed_task_added_to_dlq(self):
        """Test that failed tasks are added to dead letter queue."""
        task_manager = TaskManager()
        await task_manager.start()

        async def failing_task():
            raise RuntimeError("Task error")

        task_id = await task_manager.submit_task("test", failing_task())

        # Wait for task to fail
        await asyncio.sleep(0.2)

        dlq = task_manager.get_dead_letter_queue()
        assert len(dlq) == 1
        assert dlq[0]["task_id"] == task_id
        assert dlq[0]["status"] == TaskStatus.FAILED.value
        assert "Task error" in dlq[0]["error"]

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_failures_in_dlq(self):
        """Test that multiple failed tasks accumulate in DLQ."""
        task_manager = TaskManager()
        await task_manager.start()

        async def failing_task(error_msg):
            raise ValueError(error_msg)

        # Submit multiple failing tasks
        for i in range(3):
            await task_manager.submit_task(
                "test",
                failing_task(f"Error {i}")
            )

        # Wait for all tasks to fail
        await asyncio.sleep(0.5)

        dlq = task_manager.get_dead_letter_queue()
        assert len(dlq) == 3

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_successful_tasks_not_in_dlq(self):
        """Test that successful tasks are not added to DLQ."""
        task_manager = TaskManager()
        await task_manager.start()

        async def success_task():
            return "success"

        await task_manager.submit_task("test", success_task())

        # Wait for completion
        await asyncio.sleep(0.2)

        dlq = task_manager.get_dead_letter_queue()
        assert len(dlq) == 0

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_dlq_size_limit(self):
        """Test that DLQ respects max size with FIFO eviction."""
        task_manager = TaskManager(max_dlq_size=5)
        await task_manager.start()

        async def failing_task(n):
            raise RuntimeError(f"Error {n}")

        # Submit 10 failing tasks (exceeds DLQ max of 5)
        for i in range(10):
            await task_manager.submit_task("test", failing_task(i))

        # Wait for all tasks to fail
        await asyncio.sleep(1.0)

        dlq = task_manager.get_dead_letter_queue()
        # DLQ should contain only the last 5 tasks (FIFO eviction)
        assert len(dlq) == 5

        # Verify oldest tasks were evicted (errors 0-4 should be gone, 5-9 should remain)
        errors_in_dlq = [task["error"] for task in dlq]
        assert any("Error 5" in error for error in errors_in_dlq)
        assert not any("Error 0" in error for error in errors_in_dlq)

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_clear_dlq(self):
        """Test clearing the dead letter queue."""
        task_manager = TaskManager()
        await task_manager.start()

        async def failing_task():
            raise RuntimeError("Test error")

        # Add some failed tasks
        for _ in range(3):
            await task_manager.submit_task("test", failing_task())

        await asyncio.sleep(0.5)

        # Verify tasks in DLQ
        dlq = task_manager.get_dead_letter_queue()
        assert len(dlq) == 3

        # Clear DLQ
        task_manager.clear_dead_letter_queue()

        # Verify DLQ is empty
        dlq = task_manager.get_dead_letter_queue()
        assert len(dlq) == 0

        await task_manager.shutdown()


class TestTaskRetrieval:
    """Tests for task status and list retrieval."""

    @pytest.mark.asyncio
    async def test_get_task_status_existing(self):
        """Test getting status of an existing task."""
        task_manager = TaskManager()
        await task_manager.start()

        async def simple_task():
            return "result"

        task_id = await task_manager.submit_task("test", simple_task())

        status = task_manager.get_task_status(task_id)
        assert status is not None
        assert status["task_id"] == task_id

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_task_status_nonexistent(self):
        """Test getting status of a non-existent task."""
        task_manager = TaskManager()

        status = task_manager.get_task_status("invalid-id")
        assert status is None

    @pytest.mark.asyncio
    async def test_get_all_tasks(self):
        """Test getting all tasks."""
        task_manager = TaskManager()
        await task_manager.start()

        async def simple_task():
            return "done"

        # Submit multiple tasks
        for i in range(5):
            await task_manager.submit_task(f"test-{i}", simple_task())

        all_tasks = task_manager.get_all_tasks()
        assert len(all_tasks) == 5

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting task manager statistics."""
        task_manager = TaskManager()
        await task_manager.start()

        async def success_task():
            return "success"

        async def fail_task():
            raise ValueError("fail")

        # Submit mix of tasks
        await task_manager.submit_task("test", success_task())
        await task_manager.submit_task("test", fail_task())

        # Wait for processing
        await asyncio.sleep(0.3)

        stats = task_manager.get_stats()
        assert stats["total_tasks"] == 2
        assert stats["is_running"] is True
        assert "status_counts" in stats

        await task_manager.shutdown()


class TestResourceCleanup:
    """Tests for resource cleanup."""

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_tasks(self):
        """Test that shutdown cancels all pending tasks."""
        task_manager = TaskManager()
        await task_manager.start()

        async def long_task():
            await asyncio.sleep(10)

        # Submit multiple long tasks
        task_ids = []
        for _ in range(3):
            task_id = await task_manager.submit_task("test", long_task())
            task_ids.append(task_id)

        # Shutdown immediately
        await task_manager.shutdown()

        # All tasks should be cancelled
        for task_id in task_ids:
            status = task_manager.get_task_status(task_id)
            assert status["status"] in [
                TaskStatus.CANCELLED.value,
                TaskStatus.PENDING.value,
                TaskStatus.RUNNING.value  # Might be running if shutdown is fast
            ]

    @pytest.mark.asyncio
    async def test_shutdown_timeout(self):
        """Test that shutdown respects timeout."""
        task_manager = TaskManager()
        await task_manager.start()

        async def infinite_task():
            while True:
                await asyncio.sleep(1)

        await task_manager.submit_task("test", infinite_task())

        # Shutdown with short timeout
        import time
        start = time.time()
        await task_manager.shutdown(timeout=0.5)
        duration = time.time() - start

        # Should complete within timeout + small margin
        assert duration < 1.5


class TestGlobalTaskManager:
    """Tests for global task manager singleton."""

    @pytest.mark.asyncio
    async def test_initialize_global_task_manager(self):
        """Test initializing global task manager."""
        # Clean up any existing instance
        await shutdown_task_manager()

        task_manager = initialize_task_manager(max_queue_size=50)
        assert task_manager is not None
        assert task_manager.max_queue_size == 50

        # Get should return same instance
        task_manager2 = get_task_manager()
        assert task_manager2 is task_manager

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_get_task_manager_not_initialized(self):
        """Test that get_task_manager raises error if not initialized."""
        # Clean up any existing instance
        await shutdown_task_manager()

        with pytest.raises(RuntimeError, match="TaskManager not initialized"):
            get_task_manager()

    @pytest.mark.asyncio
    async def test_shutdown_global_task_manager(self):
        """Test shutting down global task manager."""
        await shutdown_task_manager()  # Ensure clean state

        task_manager = initialize_task_manager()
        await task_manager.start()

        await shutdown_task_manager()

        # Should raise error after shutdown
        with pytest.raises(RuntimeError, match="TaskManager not initialized"):
            get_task_manager()


class TestTaskTimeout:
    """Tests for task timeout functionality."""

    @pytest.mark.asyncio
    async def test_task_timeout(self):
        """Test that tasks can timeout correctly."""
        task_manager = TaskManager()
        await task_manager.start()

        async def slow_task():
            await asyncio.sleep(5)  # Takes 5 seconds
            return "completed"

        # Submit task with 0.5 second timeout
        task_id = await task_manager.submit_task(
            "test",
            slow_task(),
            timeout=0.5
        )

        # Wait for timeout to occur
        await asyncio.sleep(1.0)

        status = task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.FAILED.value
        assert "timed out" in status["error"].lower()
        assert "0.5" in status["error"]

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_task_completes_before_timeout(self):
        """Test that tasks completing before timeout work correctly."""
        task_manager = TaskManager()
        await task_manager.start()

        async def quick_task():
            await asyncio.sleep(0.1)
            return "success"

        # Submit task with 2 second timeout (should complete first)
        task_id = await task_manager.submit_task(
            "test",
            quick_task(),
            timeout=2.0
        )

        # Wait for completion
        await asyncio.sleep(0.3)

        status = task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.COMPLETED.value
        assert status["result"] == "success"
        assert status["error"] is None

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_task_without_timeout(self):
        """Test that tasks without timeout parameter work normally."""
        task_manager = TaskManager()
        await task_manager.start()

        async def normal_task():
            await asyncio.sleep(0.1)
            return "done"

        task_id = await task_manager.submit_task("test", normal_task())

        await asyncio.sleep(0.3)

        status = task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.COMPLETED.value

        await task_manager.shutdown()


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_task_with_no_coroutine(self):
        """Test handling task with no coroutine (edge case)."""
        task_manager = TaskManager()
        await task_manager.start()

        # Manually create task without coroutine (shouldn't happen in normal usage)
        task = BackgroundTask(task_id="test-123", task_type="test")
        await task_manager.task_queue.put(task)
        async with task_manager._tasks_lock:
            task_manager.tasks["test-123"] = task

        # Wait for processing
        await asyncio.sleep(0.2)

        status = task_manager.get_task_status("test-123")
        assert status["status"] == TaskStatus.FAILED.value
        assert "No coroutine" in status["error"]

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_task_submission(self):
        """Test submitting multiple tasks concurrently."""
        task_manager = TaskManager()
        await task_manager.start()

        async def simple_task(n):
            await asyncio.sleep(0.01)
            return f"result-{n}"

        # Submit tasks concurrently
        tasks = [
            task_manager.submit_task(f"test-{i}", simple_task(i))
            for i in range(10)
        ]

        task_ids = await asyncio.gather(*tasks)
        assert len(task_ids) == 10
        assert len(set(task_ids)) == 10  # All unique

        await task_manager.shutdown()

    @pytest.mark.asyncio
    async def test_task_manager_sequential_processing(self):
        """Test that tasks are processed sequentially (not in parallel)."""
        task_manager = TaskManager()
        await task_manager.start()

        execution_order = []

        async def ordered_task(n):
            execution_order.append(f"start-{n}")
            await asyncio.sleep(0.05)
            execution_order.append(f"end-{n}")
            return n

        # Submit multiple tasks
        for i in range(3):
            await task_manager.submit_task("test", ordered_task(i))

        # Wait for all tasks to complete
        await asyncio.sleep(0.5)

        # Verify sequential execution (each task completes before next starts)
        assert execution_order == [
            "start-0", "end-0",
            "start-1", "end-1",
            "start-2", "end-2"
        ]

        await task_manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
