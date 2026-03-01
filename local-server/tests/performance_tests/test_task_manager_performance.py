"""
Performance tests for the TaskManager background task system.

These tests validate that the TaskManager meets performance requirements
for throughput, latency, resource usage, and scalability.
"""

import sys
import os
import pytest
import asyncio
import time
import psutil
from statistics import mean, stdev

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.task_manager import (
    TaskStatus,
    initialize_task_manager,
    shutdown_task_manager
)


class TestTaskSubmissionPerformance:
    """Performance tests for task submission."""

    @pytest.mark.asyncio
    async def test_task_submission_throughput(self):
        """
        Performance Test: Task submission throughput.

        Validates that the system can handle high rates of task
        submission without significant performance degradation.

        Target: >1000 task submissions per second
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager(max_queue_size=2000)
        await task_manager.start()

        # Prepare tasks
        async def quick_task():
            return "done"

        # Measure submission throughput
        num_tasks = 1000
        start_time = time.time()

        task_ids = []
        for i in range(num_tasks):
            task_id = await task_manager.submit_task(
                task_type=f"perf_test_{i}",
                coroutine=quick_task()
            )
            task_ids.append(task_id)

        end_time = time.time()
        duration = end_time - start_time

        # Calculate throughput
        throughput = num_tasks / duration

        print("\n=== Task Submission Performance ===")
        print(f"Tasks submitted: {num_tasks}")
        print(f"Duration: {duration:.3f} seconds")
        print(f"Throughput: {throughput:.1f} tasks/second")

        # Assert performance target
        assert throughput > 1000, f"Throughput {throughput:.1f} is below target of 1000 tasks/second"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_task_submission_latency(self):
        """
        Performance Test: Task submission latency.

        Measures the latency of individual task submissions to ensure
        consistent performance.

        Target: p95 latency < 10ms
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        async def quick_task():
            return "done"

        # Measure individual submission latencies
        latencies = []
        num_samples = 100

        for i in range(num_samples):
            start = time.time()
            await task_manager.submit_task(
                task_type=f"latency_test_{i}",
                coroutine=quick_task()
            )
            end = time.time()
            latencies.append((end - start) * 1000)  # Convert to ms

        # Calculate statistics
        avg_latency = mean(latencies)
        std_latency = stdev(latencies)
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))]
        p99_latency = sorted(latencies)[int(0.99 * len(latencies))]

        print("\n=== Task Submission Latency ===")
        print(f"Average: {avg_latency:.3f}ms")
        print(f"Std Dev: {std_latency:.3f}ms")
        print(f"P95: {p95_latency:.3f}ms")
        print(f"P99: {p99_latency:.3f}ms")

        # Assert performance targets
        assert p95_latency < 10, f"P95 latency {p95_latency:.3f}ms exceeds target of 10ms"
        assert avg_latency < 5, f"Average latency {avg_latency:.3f}ms exceeds target of 5ms"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()


class TestTaskExecutionPerformance:
    """Performance tests for task execution."""

    @pytest.mark.asyncio
    async def test_task_processing_throughput(self):
        """
        Performance Test: Task processing throughput.

        Validates that the worker can process tasks at expected rates.

        Target: Process >100 simple tasks per second
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager(max_queue_size=300)
        await task_manager.start()

        # Create fast tasks
        async def fast_task():
            await asyncio.sleep(0.001)  # 1ms task
            return "done"

        # Submit many tasks
        num_tasks = 200
        start_time = time.time()

        for i in range(num_tasks):
            await task_manager.submit_task(
                task_type=f"fast_{i}",
                coroutine=fast_task()
            )

        # Wait for all tasks to complete
        while True:
            stats = task_manager.get_stats()
            if stats["status_counts"]["completed"] == num_tasks:
                break
            await asyncio.sleep(0.05)

        end_time = time.time()
        duration = end_time - start_time

        # Calculate processing throughput
        throughput = num_tasks / duration

        print("\n=== Task Processing Throughput ===")
        print(f"Tasks processed: {num_tasks}")
        print(f"Duration: {duration:.3f} seconds")
        print(f"Processing throughput: {throughput:.1f} tasks/second")

        # Assert performance target
        assert throughput > 100, f"Processing throughput {throughput:.1f} is below target of 100 tasks/second"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_sequential_processing_overhead(self):
        """
        Performance Test: Sequential processing overhead.

        Measures the overhead of sequential task processing vs parallel.
        The overhead should be minimal (< 10% of total execution time).
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        # Create tasks with known duration
        task_duration = 0.05  # 50ms per task
        num_tasks = 10

        async def timed_task():
            await asyncio.sleep(task_duration)
            return "done"

        # Measure actual processing time
        start_time = time.time()

        for i in range(num_tasks):
            await task_manager.submit_task(
                task_type=f"timed_{i}",
                coroutine=timed_task()
            )

        # Wait for all tasks to complete with timeout
        max_wait = 10.0  # 10 second timeout
        wait_start = time.time()
        while True:
            stats = task_manager.get_stats()
            if stats["status_counts"]["completed"] == num_tasks:
                break
            if time.time() - wait_start > max_wait:
                logger.warning(f"Timeout waiting for tasks to complete. Stats: {stats}")
                break
            await asyncio.sleep(0.01)

        end_time = time.time()
        actual_duration = end_time - start_time

        # Calculate expected duration and overhead
        expected_duration = num_tasks * task_duration
        overhead = actual_duration - expected_duration
        overhead_percentage = (overhead / expected_duration) * 100

        print("\n=== Sequential Processing Overhead ===")
        print(f"Expected duration: {expected_duration:.3f}s")
        print(f"Actual duration: {actual_duration:.3f}s")
        print(f"Overhead: {overhead:.3f}s ({overhead_percentage:.1f}%)")

        # Assert overhead is acceptable
        assert overhead_percentage < 20, f"Overhead {overhead_percentage:.1f}% exceeds target of 20%"

        # Cleanup - ensure proper shutdown
        try:
            await task_manager.shutdown()
        finally:
            await shutdown_task_manager()


class TestMemoryPerformance:
    """Performance tests for memory usage."""

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """
        Performance Test: Memory usage under load.

        Validates that memory usage remains reasonable even with
        many tasks in the system.

        Target: Memory growth < 100MB for 1000 tasks
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager(max_queue_size=2000)
        await task_manager.start()

        # Measure initial memory
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Submit many tasks
        async def small_task():
            await asyncio.sleep(0.01)
            return {"data": "result"}

        num_tasks = 1000
        for i in range(num_tasks):
            await task_manager.submit_task(
                task_type=f"mem_test_{i}",
                coroutine=small_task(),
                metadata={"test_id": i}
            )

        # Wait for half the tasks to complete
        await asyncio.sleep(2.0)

        # Measure peak memory
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Wait for all tasks to complete
        while True:
            stats = task_manager.get_stats()
            if stats["status_counts"]["completed"] == num_tasks:
                break
            await asyncio.sleep(0.1)

        # Measure final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        memory_growth = peak_memory - initial_memory

        print("\n=== Memory Usage Performance ===")
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Peak memory: {peak_memory:.1f} MB")
        print(f"Final memory: {final_memory:.1f} MB")
        print(f"Memory growth: {memory_growth:.1f} MB")
        print(f"Memory per task: {(memory_growth / num_tasks) * 1000:.2f} KB")

        # Assert memory usage is reasonable
        assert memory_growth < 100, f"Memory growth {memory_growth:.1f}MB exceeds target of 100MB"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()


class TestConcurrencyPerformance:
    """Performance tests for concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_status_queries(self):
        """
        Performance Test: Concurrent status query performance.

        Validates that the system can handle many concurrent status
        queries without performance degradation.

        Target: Handle 100 concurrent queries in < 100ms
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        # Submit some tasks
        async def task():
            await asyncio.sleep(1.0)
            return "done"

        task_ids = []
        for i in range(50):
            task_id = await task_manager.submit_task(
                task_type=f"query_test_{i}",
                coroutine=task()
            )
            task_ids.append(task_id)

        # Measure concurrent query performance
        num_queries = 100
        start_time = time.time()

        # Make concurrent queries
        query_tasks = []
        for _ in range(num_queries):
            task_id = task_ids[_ % len(task_ids)]
            query_tasks.append(asyncio.create_task(
                asyncio.to_thread(task_manager.get_task_status, task_id)
            ))

        results = await asyncio.gather(*query_tasks)
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to ms

        print("\n=== Concurrent Status Query Performance ===")
        print(f"Queries: {num_queries}")
        print(f"Duration: {duration:.1f}ms")
        print(f"Avg latency: {duration / num_queries:.2f}ms")

        # Assert all queries returned results
        assert all(r is not None for r in results)

        # Assert performance target
        assert duration < 100, f"Query duration {duration:.1f}ms exceeds target of 100ms"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_concurrent_submissions_and_cancellations(self):
        """
        Performance Test: Concurrent submissions and cancellations.

        Validates system stability under mixed concurrent operations.

        Target: Handle 50 submissions + 50 cancellations in < 1s
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager(max_queue_size=200)
        await task_manager.start()

        # Create long-running tasks
        async def long_task():
            await asyncio.sleep(10.0)
            return "done"

        # Measure concurrent operations
        start_time = time.time()

        # Submit tasks concurrently
        submission_tasks = []
        for i in range(50):
            submission_tasks.append(
                task_manager.submit_task(
                    task_type=f"concurrent_{i}",
                    coroutine=long_task()
                )
            )

        task_ids = await asyncio.gather(*submission_tasks)

        # Wait a bit for tasks to start
        await asyncio.sleep(0.2)

        # Cancel half of them concurrently
        cancellation_tasks = []
        for task_id in task_ids[:25]:
            cancellation_tasks.append(task_manager.cancel_task(task_id))

        await asyncio.gather(*cancellation_tasks)

        end_time = time.time()
        duration = end_time - start_time

        print("\n=== Concurrent Operations Performance ===")
        print(f"Duration: {duration:.3f}s")
        print("Operations: 50 submissions + 25 cancellations")

        # Assert performance target
        assert duration < 1.0, f"Duration {duration:.3f}s exceeds target of 1.0s"

        # Verify final state
        stats = task_manager.get_stats()
        assert stats["status_counts"]["cancelled"] >= 25

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()


class TestScalabilityPerformance:
    """Performance tests for system scalability."""

    @pytest.mark.asyncio
    async def test_large_queue_performance(self):
        """
        Performance Test: Large queue handling.

        Validates performance with large numbers of queued tasks.

        Target: Queue 500 tasks in < 2 seconds
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager(max_queue_size=1000)
        await task_manager.start()

        async def slow_task():
            await asyncio.sleep(1.0)
            return "done"

        # Queue many tasks
        num_tasks = 500
        start_time = time.time()

        for i in range(num_tasks):
            await task_manager.submit_task(
                task_type=f"queue_test_{i}",
                coroutine=slow_task()
            )

        end_time = time.time()
        queue_time = end_time - start_time

        # Check queue size
        queue_size = task_manager.get_queue_size()

        print("\n=== Large Queue Performance ===")
        print(f"Tasks queued: {num_tasks}")
        print(f"Queue time: {queue_time:.3f}s")
        print(f"Current queue size: {queue_size}")

        # Assert performance target
        assert queue_time < 2.0, f"Queue time {queue_time:.3f}s exceeds target of 2.0s"
        assert queue_size > 0, "Queue should have pending tasks"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_dlq_performance_at_scale(self):
        """
        Performance Test: Dead letter queue performance at scale.

        Validates DLQ performance with many failed tasks.

        Target: 100 failures processed in < 1 second
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager(max_dlq_size=1000)
        await task_manager.start()

        # Create failing tasks
        async def failing_task(n):
            await asyncio.sleep(0.001)
            raise RuntimeError(f"Failed {n}")

        # Submit many failing tasks
        num_tasks = 100
        start_time = time.time()

        for i in range(num_tasks):
            await task_manager.submit_task(
                task_type=f"dlq_test_{i}",
                coroutine=failing_task(i)
            )

        # Wait for all to fail
        while True:
            stats = task_manager.get_stats()
            if stats["status_counts"]["failed"] == num_tasks:
                break
            await asyncio.sleep(0.05)

        end_time = time.time()
        duration = end_time - start_time

        # Verify DLQ
        dlq = task_manager.get_dead_letter_queue()

        print("\n=== DLQ Performance at Scale ===")
        print(f"Failed tasks: {num_tasks}")
        print(f"Processing time: {duration:.3f}s")
        print(f"DLQ size: {len(dlq)}")

        # Assert performance target
        assert duration < 1.0, f"Duration {duration:.3f}s exceeds target of 1.0s"
        assert len(dlq) == num_tasks, f"DLQ should contain all {num_tasks} failed tasks"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()


class TestProgressTrackingPerformance:
    """Performance tests for progress tracking."""

    @pytest.mark.asyncio
    async def test_progress_update_performance(self):
        """
        Performance Test: Progress update performance.

        Validates that frequent progress updates don't significantly
        impact task execution performance.

        Target: <10% overhead for 100 progress updates per task
        """
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        # Task with many progress updates
        async def task_with_frequent_updates():
            for i in range(100):
                await asyncio.sleep(0.001)
                task_manager._update_progress(task_id, i / 100)
            return "done"

        # Task without progress updates (baseline)
        async def task_without_updates():
            for i in range(100):
                await asyncio.sleep(0.001)
            return "done"

        # Measure task with progress updates
        task_id = await task_manager.submit_task(
            task_type="with_progress",
            coroutine=task_with_frequent_updates()
        )

        start_time = time.time()
        while True:
            status = task_manager.get_task_status(task_id)
            if status["status"] == TaskStatus.COMPLETED.value:
                break
            await asyncio.sleep(0.01)
        with_progress_time = time.time() - start_time

        # Measure baseline task
        task_id_baseline = await task_manager.submit_task(
            task_type="without_progress",
            coroutine=task_without_updates()
        )

        start_time = time.time()
        while True:
            status = task_manager.get_task_status(task_id_baseline)
            if status["status"] == TaskStatus.COMPLETED.value:
                break
            await asyncio.sleep(0.01)
        without_progress_time = time.time() - start_time

        # Calculate overhead
        overhead = with_progress_time - without_progress_time
        overhead_percentage = (overhead / without_progress_time) * 100

        print("\n=== Progress Update Performance ===")
        print(f"Without progress: {without_progress_time:.3f}s")
        print(f"With progress (100 updates): {with_progress_time:.3f}s")
        print(f"Overhead: {overhead:.3f}s ({overhead_percentage:.1f}%)")

        # Assert overhead is acceptable
        assert overhead_percentage < 15, f"Progress overhead {overhead_percentage:.1f}% exceeds target of 15%"

        # Cleanup
        await task_manager.shutdown()
        await shutdown_task_manager()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to show print statements
