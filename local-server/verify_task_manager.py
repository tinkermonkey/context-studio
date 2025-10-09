#!/usr/bin/env python3
"""
Standalone verification script for TaskManager implementation.
Tests basic functionality without requiring full test infrastructure.
"""

import asyncio
import sys
from services.task_manager import (
    TaskManager,
    BackgroundTask,
    TaskStatus,
    initialize_task_manager,
    shutdown_task_manager,
    get_task_manager
)


async def test_basic_functionality():
    """Test basic TaskManager functionality."""
    print("=" * 60)
    print("TaskManager Verification Script")
    print("=" * 60)

    # Test 1: Initialization
    print("\n[Test 1] TaskManager initialization...")
    task_manager = TaskManager(max_queue_size=50)
    assert task_manager.max_queue_size == 50
    assert task_manager.get_queue_size() == 0
    print("✓ TaskManager initialized successfully")

    # Test 2: Start worker
    print("\n[Test 2] Starting TaskManager worker...")
    await task_manager.start()
    assert task_manager._running is True
    print("✓ TaskManager worker started")

    # Test 3: Submit task
    print("\n[Test 3] Submitting a task...")
    async def simple_task():
        await asyncio.sleep(0.1)
        return "Task completed successfully"

    task_id = await task_manager.submit_task(
        task_type="verification_test",
        coroutine=simple_task(),
        metadata={"description": "Verification test task"}
    )
    print(f"✓ Task submitted with ID: {task_id}")

    # Test 4: Get task status (pending/running)
    print("\n[Test 4] Getting task status...")
    status = task_manager.get_task_status(task_id)
    assert status is not None
    assert status["task_id"] == task_id
    assert status["task_type"] == "verification_test"
    print(f"✓ Task status: {status['status']}")

    # Test 5: Wait for completion
    print("\n[Test 5] Waiting for task completion...")
    await asyncio.sleep(0.5)
    final_status = task_manager.get_task_status(task_id)
    assert final_status["status"] == "completed"
    assert final_status["result"] == "Task completed successfully"
    print(f"✓ Task completed: {final_status['result']}")

    # Test 6: Test failing task and dead letter queue
    print("\n[Test 6] Testing failed task and dead letter queue...")
    async def failing_task():
        raise ValueError("Intentional test error")

    failed_task_id = await task_manager.submit_task("test", failing_task())
    await asyncio.sleep(0.3)

    failed_status = task_manager.get_task_status(failed_task_id)
    assert failed_status["status"] == "failed"
    assert "Intentional test error" in failed_status["error"]

    dlq = task_manager.get_dead_letter_queue()
    assert len(dlq) >= 1
    print(f"✓ Failed task added to DLQ. DLQ size: {len(dlq)}")

    # Test 7: Test cancellation
    print("\n[Test 7] Testing task cancellation...")
    async def long_task():
        await asyncio.sleep(10)

    cancel_task_id = await task_manager.submit_task("test", long_task())
    await asyncio.sleep(0.2)  # Let it start
    cancelled = await task_manager.cancel_task(cancel_task_id)
    assert cancelled is True
    await asyncio.sleep(0.1)

    cancel_status = task_manager.get_task_status(cancel_task_id)
    assert cancel_status["status"] == "cancelled"
    print("✓ Task cancelled successfully")

    # Test 8: Get statistics
    print("\n[Test 8] Getting TaskManager statistics...")
    stats = task_manager.get_stats()
    print(f"  Total tasks: {stats['total_tasks']}")
    print(f"  Queue size: {stats['queue_size']}")
    print(f"  DLQ size: {stats['dead_letter_queue_size']}")
    print(f"  Status counts: {stats['status_counts']}")
    print("✓ Statistics retrieved successfully")

    # Test 9: Shutdown
    print("\n[Test 9] Shutting down TaskManager...")
    await task_manager.shutdown()
    assert task_manager._running is False
    print("✓ TaskManager shut down successfully")

    print("\n" + "=" * 60)
    print("All verification tests passed! ✓")
    print("=" * 60)


async def test_global_instance():
    """Test global task manager singleton."""
    print("\n[Bonus Test] Testing global TaskManager instance...")

    # Clean up any existing instance
    await shutdown_task_manager()

    # Initialize
    tm = initialize_task_manager(max_queue_size=75)
    await tm.start()

    # Get should return same instance
    tm2 = get_task_manager()
    assert tm is tm2
    print("✓ Global instance working correctly")

    # Submit a task
    async def test_task():
        return "global task result"

    task_id = await tm.submit_task("global_test", test_task())
    await asyncio.sleep(0.2)

    status = tm.get_task_status(task_id)
    assert status["status"] == "completed"
    print(f"✓ Global task completed: {status['result']}")

    # Cleanup
    await shutdown_task_manager()
    print("✓ Global instance cleaned up")


async def main():
    """Run all verification tests."""
    try:
        await test_basic_functionality()
        await test_global_instance()
        print("\n✅ All verification tests completed successfully!\n")
        return 0
    except Exception as e:
        print(f"\n❌ Verification failed: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
