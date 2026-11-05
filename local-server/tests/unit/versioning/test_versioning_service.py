"""
Unit tests for the VersioningService domain service.

Tests the change history queries and sync operations using FakeChangeRepository.
"""

from datetime import datetime, timedelta, timezone

import pytest

from domain.versioning.entities import ChangeEvent
from domain.versioning.events import SyncCompleted
from domain.versioning.services import VersioningService
from domain.versioning.value_objects import ChangeOperation, SyncResult
from tests.fakes.fake_change_repository import FakeChangeRepository
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_sync_target import FakeSyncTarget

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def repo() -> FakeChangeRepository:
    """Create a fresh fake repository for each test."""
    return FakeChangeRepository()


@pytest.fixture
def sync_target() -> FakeSyncTarget:
    """Create a fresh fake sync target for each test."""
    return FakeSyncTarget()


@pytest.fixture
def event_publisher() -> FakeEventPublisher:
    """Create a fresh fake event publisher for each test."""
    return FakeEventPublisher()


@pytest.fixture
def service(
    repo: FakeChangeRepository,
    sync_target: FakeSyncTarget,
    event_publisher: FakeEventPublisher,
) -> VersioningService:
    """Create a VersioningService with fake dependencies."""
    return VersioningService(
        change_repo=repo,
        sync_target=sync_target,
        event_publisher=event_publisher,
    )


# ============================================================================
# Change History Query Tests
# ============================================================================


class TestChangeHistoryQueries:
    """Test change history query methods."""

    def test_get_change_history_empty(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history when no changes exist."""
        result = service.get_change_history()
        assert result.events == ()
        assert result.total == 0

    def test_get_change_history_all_events(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving all change events."""
        # Record some events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity2"},
        )

        result = service.get_change_history()
        assert len(result.events) == 2
        assert result.total == 2
        assert any(e.id == event_id_1 for e in result.events)
        assert any(e.id == event_id_2 for e in result.events)

    def test_get_change_history_filtered_by_entity(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history filtered by entity."""
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        repo.record_change(
            entity_id="entity2",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity2"},
        )

        result = service.get_change_history(entity_id="entity1")
        assert len(result.events) == 1
        assert result.total == 1
        assert result.events[0].entity_id == "entity1"

    def test_get_change_history_filtered_by_since(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test retrieving change history since a timestamp."""
        now = datetime.now(timezone.utc)
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        # This event is recorded with current time, so it will be after 'now'
        # Let's retrieve after a time before now
        since = now - timedelta(seconds=1)

        result = service.get_change_history(since=since)
        # The recorded event should be after 'since'
        assert len(result.events) > 0
        assert result.total > 0

    def test_get_change_history_respects_limit(
        self, service: VersioningService, repo: FakeChangeRepository
    ) -> None:
        """Test that change history respects the limit parameter."""
        for i in range(10):
            repo.record_change(
                entity_id=f"entity{i}",
                entity_type="class",
                operation=ChangeOperation.CREATE,
                new_state={"name": f"Entity{i}"},
            )

        result = service.get_change_history(limit=5)
        assert len(result.events) == 5
        assert result.total == 10


# ============================================================================
# Synchronization Tests
# ============================================================================


class TestSyncMethods:
    """Test sync methods (push/pull) with event slicing and transaction handling."""

    def test_push_changes_empty_returns_zero_pushed(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        sync_target: FakeSyncTarget,
    ) -> None:
        """Test push_changes with no unprocessed events returns 0 pushed."""
        result = service.push_changes()

        assert result.pushed == 0
        assert result.pushed_event_ids is None or len(result.pushed_event_ids) == 0
        assert len(result.errors) == 0

    def test_push_changes_marks_events_as_processed(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        sync_target: FakeSyncTarget,
        event_publisher: FakeEventPublisher,
    ) -> None:
        """Test push_changes marks successfully pushed events as processed."""
        # Record some unprocessed events
        event_id_1 = repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )
        event_id_2 = repo.record_change(
            entity_id="entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity2"},
        )

        # Push changes
        result = service.push_changes()

        # Verify push succeeded
        assert result.pushed == 2
        assert result.pushed_event_ids is not None
        assert event_id_1 in result.pushed_event_ids
        assert event_id_2 in result.pushed_event_ids
        assert len(result.errors) == 0

        # Verify events are marked as processed
        history = repo.get_changes()
        for change_event in history.events:
            if change_event.id in [event_id_1, event_id_2]:
                assert change_event.processed

        # Verify SyncCompleted event was published
        events = event_publisher.get_events_of_type(SyncCompleted)
        assert len(events) == 1
        event = events[0]
        assert event.direction == "push"
        assert event.events_count == 2

    def test_push_changes_respects_500_event_limit(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        sync_target: FakeSyncTarget,
    ) -> None:
        """Test push_changes slices events to 500 limit."""
        # Record 600 unprocessed events
        event_ids = []
        for i in range(600):
            event_id = repo.record_change(
                entity_id=f"entity{i}",
                entity_type="class",
                operation=ChangeOperation.CREATE,
                new_state={"name": f"Entity{i}"},
            )
            event_ids.append(event_id)

        # Push changes
        result = service.push_changes()

        # Should push only 500 (the limit)
        assert result.pushed == 500
        assert result.pushed_event_ids is not None
        assert len(result.pushed_event_ids) == 500

        # Verify 500 were marked processed, 100 remain unprocessed
        unprocessed_events = repo.get_unprocessed()
        assert len(unprocessed_events) == 100

    def test_push_changes_with_sync_target_not_configured(
        self, repo: FakeChangeRepository, event_publisher: FakeEventPublisher
    ) -> None:
        """Test push_changes when sync target is not configured."""
        sync_target = FakeSyncTarget(configured=False)
        service = VersioningService(
            change_repo=repo,
            sync_target=sync_target,
            event_publisher=event_publisher,
        )

        # Record an event
        repo.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity1"},
        )

        # Push should return error
        result = service.push_changes()

        assert result.pushed == 0
        assert len(result.errors) > 0
        # Event should not be marked as processed
        unprocessed = repo.get_unprocessed()
        assert len(unprocessed) == 1

    def test_pull_changes_empty_returns_zero_pulled(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        sync_target: FakeSyncTarget,
    ) -> None:
        """Test pull_changes with no remote events returns 0 pulled."""
        result = service.pull_changes()

        assert result.pulled == 0
        assert len(result.errors) == 0
        assert len(repo.get_changes().events) == 0

    def test_pull_changes_records_events_locally(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        sync_target: FakeSyncTarget,
        event_publisher: FakeEventPublisher,
    ) -> None:
        """Test pull_changes records remote events in local repository."""
        # Add remote events
        remote_event_1 = ChangeEvent(
            id="remote-1",
            entity_id="remote_entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity1"},
            timestamp=datetime.now(timezone.utc),
        )
        remote_event_2 = ChangeEvent(
            id="remote-2",
            entity_id="remote_entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity2"},
            timestamp=datetime.now(timezone.utc),
        )
        sync_target.add_remote_events([remote_event_1, remote_event_2])

        # Pull changes
        result = service.pull_changes()

        # Verify pull recorded events
        assert result.pulled == 2
        assert len(result.errors) == 0

        # Verify events are in repository
        history = repo.get_changes()
        assert len(history.events) == 2
        assert any(e.entity_id == "remote_entity1" for e in history.events)
        assert any(e.entity_id == "remote_entity2" for e in history.events)

        # Verify SyncCompleted event was published
        events = event_publisher.get_events_of_type(SyncCompleted)
        assert len(events) == 1
        event = events[0]
        assert event.direction == "pull"
        assert event.events_count == 2

    def test_pull_changes_stops_on_first_error(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        event_publisher: FakeEventPublisher,
    ) -> None:
        """Test pull_changes stops on first record error and logs partial success."""
        # Create a mock sync target that returns events
        remote_event = ChangeEvent(
            id="remote-1",
            entity_id="remote_entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity1"},
            timestamp=datetime.now(timezone.utc),
        )

        class FailingSyncTarget:
            def pull(self, since=None):
                return [remote_event]

            def push(self, events):
                now = datetime.now(timezone.utc)
                return SyncResult(pushed=0, pulled=0, errors=(), started_at=now, completed_at=now)

            def is_configured(self):
                return True

            def get_sync_status(self):
                from domain.versioning.value_objects import SyncStatus

                return SyncStatus(
                    last_pushed_at=None,
                    last_pulled_at=None,
                    unprocessed_count=0,
                    is_configured=True,
                )

        # Create a repository that fails on record_change by extending FakeChangeRepository
        class FailingRepository(FakeChangeRepository):
            def record_change(
                self,
                entity_id: str,
                entity_type: str,
                operation: ChangeOperation,
                new_state: dict,
                previous_state=None,
                user_id=None,
                change_reason=None,
                batch_run_id=None,
            ):
                raise RuntimeError("Database error")

        failing_repo = FailingRepository()
        service = VersioningService(
            change_repo=failing_repo,
            sync_target=FailingSyncTarget(),
            event_publisher=event_publisher,
        )

        result = service.pull_changes()

        # Should have error, zero pulled
        assert result.pulled == 0
        assert len(result.errors) > 0
        assert "Database error" in result.errors[0]

    def test_pull_changes_rolls_back_on_partial_failure(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        event_publisher: FakeEventPublisher,
    ) -> None:
        """Test pull_changes rolls back all recorded events when one fails mid-pull."""
        # Create remote events to be pulled
        remote_event_1 = ChangeEvent(
            id="remote-1",
            entity_id="remote_entity1",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity1"},
            timestamp=datetime.now(timezone.utc),
        )
        remote_event_2 = ChangeEvent(
            id="remote-2",
            entity_id="remote_entity2",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "RemoteEntity2"},
            timestamp=datetime.now(timezone.utc),
        )

        class PartialFailingSyncTarget:
            def pull(self, since=None):
                return [remote_event_1, remote_event_2]

            def push(self, events):
                now = datetime.now(timezone.utc)
                return SyncResult(pushed=0, pulled=0, errors=(), started_at=now, completed_at=now)

            def is_configured(self):
                return True

            def get_sync_status(self):
                from domain.versioning.value_objects import SyncStatus

                return SyncStatus(
                    last_pushed_at=None,
                    last_pulled_at=None,
                    unprocessed_count=0,
                    is_configured=True,
                )

        # Create a repository that succeeds once, then fails on second record_change
        class PartialFailingRepository(FakeChangeRepository):
            def __init__(self):
                super().__init__()
                self.record_change_count = 0

            def record_change(
                self,
                entity_id: str,
                entity_type: str,
                operation: ChangeOperation,
                new_state: dict,
                previous_state=None,
                user_id=None,
                change_reason=None,
                batch_run_id=None,
            ):
                self.record_change_count += 1
                if self.record_change_count > 1:
                    raise RuntimeError("Second record failed")
                # First call succeeds - call parent implementation
                return super().record_change(
                    entity_id,
                    entity_type,
                    operation,
                    new_state,
                    previous_state,
                    user_id,
                    change_reason,
                    batch_run_id,
                )

        failing_repo = PartialFailingRepository()
        service = VersioningService(
            change_repo=failing_repo,
            sync_target=PartialFailingSyncTarget(),
            event_publisher=event_publisher,
        )

        # Pull should fail after recording first event
        result = service.pull_changes()

        # Should have error
        assert len(result.errors) > 0
        assert "Second record failed" in result.errors[0]

        # Verify no events remain (first was recorded but then deleted during rollback)
        history = failing_repo.get_changes()
        assert len(history.events) == 0


# ============================================================================
# Sync Status Error Handling Tests
# ============================================================================


class TestSyncStatusErrorHandling:
    """Test get_sync_status error handling and graceful degradation."""

    def test_get_sync_status_count_unprocessed_error(
        self, sync_target: FakeSyncTarget, event_publisher: FakeEventPublisher
    ) -> None:
        """Test that count_unprocessed errors degrade to unprocessed_count=0."""

        class FailingCountRepository(FakeChangeRepository):
            def count_unprocessed(self) -> int:
                raise RuntimeError("Database connection failed")

        failing_repo = FailingCountRepository()
        service = VersioningService(
            change_repo=failing_repo,
            sync_target=sync_target,
            event_publisher=event_publisher,
        )

        status = service.get_sync_status()

        assert status.unprocessed_count == 0
        assert status.is_configured == sync_target.is_configured()
        assert status.is_degraded is True

    def test_get_sync_status_is_configured_error(
        self, repo: FakeChangeRepository, event_publisher: FakeEventPublisher
    ) -> None:
        """Test that is_configured errors degrade to is_configured=False and set
        is_degraded=True."""

        class FailingConfigSyncTarget(FakeSyncTarget):
            def is_configured(self) -> bool:
                raise OSError("Configuration file not accessible")

        failing_sync = FailingConfigSyncTarget()
        service = VersioningService(
            change_repo=repo,
            sync_target=failing_sync,
            event_publisher=event_publisher,
        )

        status = service.get_sync_status()

        assert status.is_configured is False
        assert status.unprocessed_count == repo.count_unprocessed()
        assert status.is_degraded is True

    def test_get_sync_status_both_errors(self, event_publisher: FakeEventPublisher) -> None:
        """Test that both count_unprocessed and is_configured errors degrade gracefully."""

        class FailingCountRepository(FakeChangeRepository):
            def count_unprocessed(self) -> int:
                raise RuntimeError("Database connection failed")

        class FailingConfigSyncTarget(FakeSyncTarget):
            def is_configured(self) -> bool:
                raise OSError("Configuration file not accessible")

        failing_repo = FailingCountRepository()
        failing_sync = FailingConfigSyncTarget()
        service = VersioningService(
            change_repo=failing_repo,
            sync_target=failing_sync,
            event_publisher=event_publisher,
        )

        status = service.get_sync_status()

        assert status.unprocessed_count == 0
        assert status.is_configured is False
        assert status.is_degraded is True

    def test_get_sync_status_success_path(
        self,
        service: VersioningService,
        repo: FakeChangeRepository,
        sync_target: FakeSyncTarget,
    ) -> None:
        """Test that get_sync_status returns correct values when no errors occur."""
        # Record a change to have an unprocessed event
        repo.record_change(
            entity_id="test-entity",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Test"},
        )

        status = service.get_sync_status()

        assert status.unprocessed_count == 1
        assert status.is_configured == sync_target.is_configured()
        assert status.is_degraded is False
