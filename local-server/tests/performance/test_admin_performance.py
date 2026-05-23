"""Performance tests for system administration operations.

Tests measure health check execution, configuration management,
and background task lifecycle operations.
"""

import time

import pytest

from domain.admin.services import AdminService
from domain.admin.value_objects import BackgroundTaskStatus
from tests.fakes.fake_configuration_store import FakeConfigurationStore
from tests.fakes.fake_metrics_collector import FakeMetricsCollector


def _setup_admin_context() -> AdminService:
    """Set up admin service with fake dependencies.

    Returns:
        AdminService instance for testing
    """
    metrics_collector = FakeMetricsCollector()
    config_store = FakeConfigurationStore()
    service = AdminService(metrics_collector, config_store)
    return service


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_checks,max_time",
    [
        (10, 0.05),
        (50, 0.25),
        (100, 0.5),
    ],
)
def test_bulk_health_checks(num_checks: int, max_time: float) -> None:
    """Measure throughput of health check execution."""
    service = _setup_admin_context()

    start = time.perf_counter()
    for _ in range(num_checks):
        service.check_health()
    elapsed = time.perf_counter() - start

    print(
        f"\nBulk health checks ({num_checks} checks): {elapsed:.4f}s"
        f" ({num_checks / elapsed:.1f} checks/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_checks,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_database_health_checks(num_checks: int, max_time: float) -> None:
    """Measure time to check database health."""
    service = _setup_admin_context()

    start = time.perf_counter()
    for _ in range(num_checks):
        service.get_database_health()
    elapsed = time.perf_counter() - start

    print(
        f"\nDatabase health checks ({num_checks} checks): {elapsed:.4f}s"
        f" ({num_checks / elapsed:.1f} checks/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_checks,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_service_metrics_retrieval(num_checks: int, max_time: float) -> None:
    """Measure time to retrieve service metrics."""
    service = _setup_admin_context()

    start = time.perf_counter()
    for _ in range(num_checks):
        service.get_service_metrics()
    elapsed = time.perf_counter() - start

    print(
        f"\nService metrics retrieval ({num_checks} calls): {elapsed:.4f}s"
        f" ({num_checks / elapsed:.1f} calls/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_tasks,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_bulk_register_tasks(num_tasks: int, max_time: float) -> None:
    """Measure throughput of registering background tasks."""
    service = _setup_admin_context()

    start = time.perf_counter()
    for i in range(num_tasks):
        service.register_task(f"Task_{i:03d}")
    elapsed = time.perf_counter() - start

    print(
        f"\nRegister background tasks ({num_tasks} tasks): {elapsed:.4f}s"
        f" ({num_tasks / elapsed:.1f} tasks/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_tasks,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_list_tasks(num_tasks: int, max_time: float) -> None:
    """Measure time to list all background tasks."""
    service = _setup_admin_context()

    # Register tasks
    for i in range(num_tasks):
        service.register_task(f"Task_{i:03d}")

    start = time.perf_counter()
    tasks = service.list_tasks()
    elapsed = time.perf_counter() - start

    print(f"\nList background tasks ({num_tasks} tasks): {elapsed:.4f}s")
    assert len(tasks) == num_tasks
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_updates,max_time",
    [
        (10, 0.02),
        (50, 0.1),
        (100, 0.2),
    ],
)
def test_update_task_status(num_updates: int, max_time: float) -> None:
    """Measure throughput of updating task status."""
    service = _setup_admin_context()

    # Register tasks
    task_ids = []
    for i in range(num_updates):
        task = service.register_task(f"Task_{i:03d}")
        task_ids.append(task.id)

    start = time.perf_counter()
    statuses = [
        BackgroundTaskStatus.RUNNING,
        BackgroundTaskStatus.COMPLETED,
        BackgroundTaskStatus.FAILED,
    ]
    for i, task_id in enumerate(task_ids):
        status = statuses[i % len(statuses)]
        service.update_task_status(task_id, status)
    elapsed = time.perf_counter() - start

    print(
        f"\nUpdate task status ({num_updates} updates): {elapsed:.4f}s"
        f" ({num_updates / elapsed:.1f} updates/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_updates,max_time",
    [
        (10, 0.05),
        (50, 0.25),
        (100, 0.5),
    ],
)
def test_bulk_configuration_updates(num_updates: int, max_time: float) -> None:
    """Measure throughput of configuration updates."""
    service = _setup_admin_context()

    start = time.perf_counter()
    for i in range(num_updates):
        service.update_configuration(section="embedding", updates={"model_name": f"model-{i % 3}"})
    elapsed = time.perf_counter() - start

    print(
        f"\nBulk configuration updates ({num_updates} updates): {elapsed:.4f}s"
        f" ({num_updates / elapsed:.1f} updates/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_retrievals,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_get_configuration(num_retrievals: int, max_time: float) -> None:
    """Measure time to retrieve configuration."""
    service = _setup_admin_context()

    start = time.perf_counter()
    for _ in range(num_retrievals):
        service.get_configuration()
    elapsed = time.perf_counter() - start

    print(
        f"\nGet configuration ({num_retrievals} calls): {elapsed:.4f}s"
        f" ({num_retrievals / elapsed:.1f} calls/sec)"
    )
    assert elapsed < max_time
