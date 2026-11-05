"""Performance tests for version control and collaboration operations at various scales.

Tests measure change event recording and change history query
performance at multiple scales.
"""

import time
from uuid import uuid4

import pytest

from domain.versioning.services import VersioningService
from domain.versioning.value_objects import ChangeOperation
from tests.fakes.fake_change_repository import FakeChangeRepository
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_sync_target import FakeSyncTarget


def _setup_versioning_context() -> tuple[VersioningService, FakeChangeRepository]:
    """Set up versioning service with fake dependencies.

    Returns:
        Tuple of (service, repository) for testing
    """
    repository = FakeChangeRepository()
    sync_target = FakeSyncTarget()
    event_publisher = FakeEventPublisher()
    service = VersioningService(repository, sync_target, event_publisher)
    return service, repository


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_changes,max_time",
    [
        (10, 0.02),
        (50, 0.1),
        (100, 0.25),
    ],
)
def test_bulk_record_changes(num_changes: int, max_time: float) -> None:
    """Measure throughput of recording change events."""
    _, repository = _setup_versioning_context()

    start = time.perf_counter()
    for i in range(num_changes):
        repository.record_change(
            entity_id=str(uuid4()),
            entity_type="TestEntity",
            operation=ChangeOperation.CREATE if i % 3 == 0 else ChangeOperation.UPDATE,
            new_state={"value": f"Entity {i}", "index": i},
            previous_state={"value": f"Entity {i-1}"} if i > 0 else None,
            change_reason=f"Change {i}",
        )
    elapsed = time.perf_counter() - start

    print(
        f"\nBulk record changes ({num_changes} changes): {elapsed:.4f}s"
        f" ({num_changes / elapsed:.1f} changes/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_changes,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.15),
    ],
)
def test_get_change_history(num_changes: int, max_time: float) -> None:
    """Measure time to retrieve change history."""
    _, repository = _setup_versioning_context()

    entity_id = str(uuid4())
    for i in range(num_changes):
        repository.record_change(
            entity_id=entity_id,
            entity_type="TestEntity",
            operation=ChangeOperation.CREATE if i == 0 else ChangeOperation.UPDATE,
            new_state={"value": f"Value {i}", "index": i},
            previous_state={"value": f"Value {i-1}"} if i > 0 else None,
            change_reason=f"Update {i}",
        )

    start = time.perf_counter()
    history = repository.get_changes(entity_id=entity_id, limit=num_changes + 100)
    elapsed = time.perf_counter() - start

    print(f"\nGet change history ({num_changes} changes): {elapsed:.4f}s")
    assert len(history.events) > 0
    assert elapsed < max_time
