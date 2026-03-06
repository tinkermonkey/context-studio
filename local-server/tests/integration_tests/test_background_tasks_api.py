"""
Integration tests for the background tasks API endpoints.

Tests cover:
- API endpoint functionality
- Task lifecycle via API
- Error handling and edge cases
- Dead letter queue API
- Statistics API
"""

import sys
import os
import pytest
import asyncio
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # noqa: E501

from app import create_app  # noqa: E402
from services.task_manager import initialize_task_manager, shutdown_task_manager  # noqa: E402, E501


@pytest.fixture
async def app_with_task_manager():
    """Create a FastAPI app with TaskManager initialized."""
    # Clean up any existing task manager
    await shutdown_task_manager()

    # Initialize task manager
    task_manager = initialize_task_manager(max_queue_size=50)
    await task_manager.start()

    # Create app
    app = create_app()

    # Import and include the background_tasks router
    from api import background_tasks
    app.include_router(background_tasks.router)

    yield app

    # Cleanup
    await shutdown_task_manager()


@pytest.fixture
def client(app_with_task_manager):
    """Create a test client."""
    return TestClient(app_with_task_manager)


class TestTaskStatusAPI:
    """Tests for GET /api/tasks/{task_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_status_success(self):
        """Test getting status of an existing task."""
        # Initialize task manager
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        # Create app with router
        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit a task
        async def simple_task():
            await asyncio.sleep(0.1)
            return "result"

        task_id = await task_manager.submit_task("test", simple_task())

        # Get task status via API
        response = client.get(f"/api/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["task_type"] == "test"
        assert data["status"] in ["pending", "running", "completed"]

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self):
        """Test getting status of non-existent task."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        response = client.get("/api/tasks/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_get_task_status_completed(self):
        """Test getting status of completed task."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        async def quick_task():
            return "success"

        task_id = await task_manager.submit_task("test", quick_task())

        # Wait for completion
        await asyncio.sleep(0.3)

        response = client.get(f"/api/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] == "success"
        assert data["progress"] == 1.0

        await shutdown_task_manager()


class TestCancelTaskAPI:
    """Tests for DELETE /api/tasks/{task_id} endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_running_task(self):
        """Test cancelling a running task via API."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        async def long_task():
            await asyncio.sleep(10)

        task_id = await task_manager.submit_task("test", long_task())

        # Wait for task to start
        await asyncio.sleep(0.2)

        # Cancel via API
        response = client.delete(f"/api/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["cancelled"] is True

        # Verify task is cancelled
        await asyncio.sleep(0.1)
        status = task_manager.get_task_status(task_id)
        assert status["status"] == "cancelled"

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self):
        """Test that completed tasks cannot be cancelled."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        async def quick_task():
            return "done"

        task_id = await task_manager.submit_task("test", quick_task())

        # Wait for completion
        await asyncio.sleep(0.3)

        # Try to cancel
        response = client.delete(f"/api/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] is False
        assert "completed" in data["message"]

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        """Test cancelling a non-existent task."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        response = client.delete("/api/tasks/nonexistent-id")

        assert response.status_code == 404

        await shutdown_task_manager()


class TestListTasksAPI:
    """Tests for GET /api/tasks endpoint."""

    @pytest.mark.asyncio
    async def test_list_all_tasks(self):
        """Test listing all tasks."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit multiple tasks
        async def simple_task():
            return "done"

        for i in range(3):
            await task_manager.submit_task(f"test-{i}", simple_task())

        response = client.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["tasks"]) == 3

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_status(self):
        """Test listing tasks filtered by status."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit tasks
        async def quick_task():
            return "done"

        async def slow_task():
            await asyncio.sleep(10)

        # Submit and complete some tasks
        await task_manager.submit_task("test", quick_task())
        await asyncio.sleep(0.3)  # Wait for completion

        # Submit long running task
        await task_manager.submit_task("test", slow_task())

        # Filter by completed
        response = client.get("/api/tasks?status_filter=completed")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for task in data["tasks"]:
            assert task["status"] == "completed"

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_type(self):
        """Test listing tasks filtered by type."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        async def simple_task():
            return "done"

        # Submit tasks of different types
        await task_manager.submit_task("discovery", simple_task())
        await task_manager.submit_task("mapping", simple_task())
        await task_manager.submit_task("discovery", simple_task())

        # Filter by type
        response = client.get("/api/tasks?task_type=discovery")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for task in data["tasks"]:
            assert task["task_type"] == "discovery"

        await shutdown_task_manager()


class TestTaskStatsAPI:
    """Tests for GET /api/tasks/stats/summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_stats(self):
        """Test getting task statistics."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager(max_queue_size=50)
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit some tasks
        async def simple_task():
            return "done"

        async def failing_task():
            raise ValueError("error")

        await task_manager.submit_task("test", simple_task())
        await task_manager.submit_task("test", failing_task())

        # Wait for processing
        await asyncio.sleep(0.3)

        response = client.get("/api/tasks/stats/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 2
        assert data["max_queue_size"] == 50
        assert data["is_running"] is True
        assert "status_counts" in data

        await shutdown_task_manager()


class TestDeadLetterQueueAPI:
    """Tests for GET /api/tasks/dead-letter-queue endpoint."""

    @pytest.mark.asyncio
    async def test_get_dead_letter_queue(self):
        """Test getting failed tasks from dead letter queue."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit failing tasks
        async def failing_task(msg):
            raise RuntimeError(msg)

        await task_manager.submit_task("test", failing_task("Error 1"))
        await task_manager.submit_task("test", failing_task("Error 2"))

        # Wait for tasks to fail
        await asyncio.sleep(0.3)

        response = client.get("/api/tasks/dead-letter-queue")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["tasks"]) == 2
        for task in data["tasks"]:
            assert task["status"] == "failed"
            assert task["error"] is not None

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_dead_letter_queue_empty(self):
        """Test dead letter queue when no tasks have failed."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit successful task
        async def success_task():
            return "success"

        await task_manager.submit_task("test", success_task())
        await asyncio.sleep(0.2)

        response = client.get("/api/tasks/dead-letter-queue")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["tasks"]) == 0

        await shutdown_task_manager()


class TestErrorHandling:
    """Tests for API error handling."""

    @pytest.mark.asyncio
    async def test_api_when_task_manager_not_initialized(self):
        """Test API endpoints when TaskManager is not initialized."""
        # Ensure task manager is not initialized
        await shutdown_task_manager()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Try to get task status
        response = client.get("/api/tasks/some-id")
        assert response.status_code == 503
        assert "not available" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self):
        """Test handling concurrent API requests."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit multiple tasks
        async def simple_task():
            await asyncio.sleep(0.05)
            return "done"

        task_ids = []
        for _ in range(5):
            task_id = await task_manager.submit_task("test", simple_task())
            task_ids.append(task_id)

        # Make concurrent API requests
        responses = [client.get(f"/api/tasks/{tid}") for tid in task_ids]

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200

        await shutdown_task_manager()


class TestCompleteTaskLifecycle:
    """Integration tests for complete task lifecycle."""

    @pytest.mark.asyncio
    async def test_submit_monitor_complete_workflow(self):
        """Test complete workflow: submit → monitor → complete."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit task
        async def progressive_task():
            await asyncio.sleep(0.1)
            return {"result": "data"}

        task_id = await task_manager.submit_task(
            "discovery",
            progressive_task(),
            metadata={"description": "Test discovery"}
        )

        # Monitor task
        response1 = client.get(f"/api/tasks/{task_id}")
        assert response1.status_code == 200
        task1 = response1.json()
        assert task1["status"] in ["pending", "running"]

        # Wait for completion
        await asyncio.sleep(0.3)

        # Check completed state
        response2 = client.get(f"/api/tasks/{task_id}")
        assert response2.status_code == 200
        task2 = response2.json()
        assert task2["status"] == "completed"
        assert task2["result"] == {"result": "data"}
        assert task2["metadata"]["description"] == "Test discovery"

        # Verify in task list
        response3 = client.get("/api/tasks")
        assert response3.status_code == 200
        tasks = response3.json()["tasks"]
        assert any(t["task_id"] == task_id for t in tasks)

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_submit_cancel_workflow(self):
        """Test workflow: submit → cancel."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit long-running task
        async def long_task():
            await asyncio.sleep(10)

        task_id = await task_manager.submit_task("test", long_task())

        # Wait for task to start
        await asyncio.sleep(0.2)

        # Cancel task
        cancel_response = client.delete(f"/api/tasks/{task_id}")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["cancelled"] is True

        # Verify cancelled status
        await asyncio.sleep(0.1)
        status_response = client.get(f"/api/tasks/{task_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "cancelled"

        await shutdown_task_manager()

    @pytest.mark.asyncio
    async def test_failure_to_dead_letter_queue_workflow(self):
        """Test workflow: submit → fail → DLQ."""
        await shutdown_task_manager()
        task_manager = initialize_task_manager()
        await task_manager.start()

        from fastapi import FastAPI
        from api import background_tasks
        app = FastAPI()
        app.include_router(background_tasks.router)
        client = TestClient(app)

        # Submit failing task
        async def failing_task():
            raise ValueError("Intentional failure")

        task_id = await task_manager.submit_task("test", failing_task())

        # Wait for failure
        await asyncio.sleep(0.3)

        # Check failed status
        status_response = client.get(f"/api/tasks/{task_id}")
        assert status_response.status_code == 200
        task_data = status_response.json()
        assert task_data["status"] == "failed"
        assert "Intentional failure" in task_data["error"]

        # Check DLQ
        dlq_response = client.get("/api/tasks/dead-letter-queue")
        assert dlq_response.status_code == 200
        dlq_data = dlq_response.json()
        assert dlq_data["total"] >= 1
        assert any(t["task_id"] == task_id for t in dlq_data["tasks"])

        await shutdown_task_manager()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
