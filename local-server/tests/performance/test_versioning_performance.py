"""Performance tests for version control and collaboration operations at various scales.

Tests measure changeset creation, proposal workflow, and change event recording
performance at multiple scales.
"""

import sys
import os
import time
import pytest
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.versioning.services import VersioningService
from domain.versioning.value_objects import ChangeOperation
from tests.fakes.fake_change_repository import FakeChangeRepository
from tests.fakes.fake_sync_target import FakeSyncTarget
from tests.fakes.fake_event_publisher import FakeEventPublisher


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
@pytest.mark.parametrize("num_changesets,max_time", [
    (10, 0.02),
    (50, 0.1),
    (100, 0.2),
])
def test_bulk_create_changesets(num_changesets: int, max_time: float) -> None:
    """Measure throughput of creating changesets."""
    service, _ = _setup_versioning_context()

    start = time.perf_counter()
    for i in range(num_changesets):
        service.create_changeset(
            name=f"Changeset_{i:03d}",
            description=f"Description for changeset {i}",
        )
    elapsed = time.perf_counter() - start

    print(f"\nBulk create changesets ({num_changesets} changesets): {elapsed:.4f}s ({num_changesets / elapsed:.1f} changesets/sec)")
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_changes,max_time", [
    (10, 0.02),
    (50, 0.1),
    (100, 0.25),
])
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

    print(f"\nBulk record changes ({num_changes} changes): {elapsed:.4f}s ({num_changes / elapsed:.1f} changes/sec)")
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_changesets,max_time", [
    (5, 0.01),
    (10, 0.05),
    (20, 0.1),
])
def test_proposal_workflow(num_changesets: int, max_time: float) -> None:
    """Measure throughput of proposal creation and approval workflow."""
    service, _ = _setup_versioning_context()

    # Create changesets
    changeset_ids = []
    for i in range(num_changesets):
        changeset = service.create_changeset(
            name=f"Changeset_{i:03d}",
            description=f"Description for changeset {i}",
        )
        changeset_ids.append(changeset.id)

    start = time.perf_counter()
    for changeset_id in changeset_ids:
        service.stage_changeset(changeset_id)
        proposal = service.submit_proposal(changeset_id)
        service.approve_proposal(proposal.id)
    elapsed = time.perf_counter() - start

    print(f"\nProposal workflow ({num_changesets} proposals): {elapsed:.4f}s ({num_changesets / elapsed:.1f} proposals/sec)")
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize("num_changes,max_time", [
    (10, 0.01),
    (50, 0.05),
    (100, 0.15),
])
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
