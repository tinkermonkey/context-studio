"""
Unit tests for domain events in the Version Control & Collaboration bounded context.

Tests verify:
- ChangesetMerged event validation (merged_at timestamp required)
- SyncCompleted event validation (direction must be 'push'/'pull', completed_at required)
- Events are frozen (immutable)
- Auto-population of aggregate_id
"""

import sys
import os
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.versioning.events import ChangesetMerged, SyncCompleted
from domain.versioning.value_objects import SyncDirection


class TestChangesetMerged:
    """Tests for ChangesetMerged event."""

    def test_changeset_merged_instantiation(self):
        """ChangesetMerged can be instantiated with all required fields."""
        now = datetime.now(timezone.utc)
        event = ChangesetMerged(
            changeset_id="changeset-123",
            proposal_id="proposal-456",
            merged_at=now,
            events_applied=5,
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.changeset_id == "changeset-123"
        assert event.proposal_id == "proposal-456"
        assert event.merged_at == now
        assert event.events_applied == 5

    def test_changeset_merged_auto_populates_aggregate_id(self):
        """ChangesetMerged auto-populates aggregate_id from changeset_id."""
        now = datetime.now(timezone.utc)
        event = ChangesetMerged(
            changeset_id="changeset-789",
            proposal_id="proposal-999",
            merged_at=now,
            events_applied=3,
        )
        assert event.aggregate_id == "changeset-789"

    def test_changeset_merged_is_frozen(self):
        """ChangesetMerged instances are frozen."""
        now = datetime.now(timezone.utc)
        event = ChangesetMerged(
            changeset_id="changeset-123",
            proposal_id="proposal-456",
            merged_at=now,
            events_applied=5,
        )
        with pytest.raises(FrozenInstanceError):
            event.events_applied = 10

    def test_changeset_merged_rejects_none_merged_at(self):
        """ChangesetMerged raises ValueError if merged_at is None."""
        with pytest.raises(ValueError, match="ChangesetMerged event requires merged_at timestamp"):
            ChangesetMerged(
                changeset_id="changeset-123",
                proposal_id="proposal-456",
                merged_at=None,  # type: ignore
                events_applied=5,
            )

    def test_changeset_merged_accepts_zero_events_applied(self):
        """ChangesetMerged can have zero events_applied (edge case)."""
        now = datetime.now(timezone.utc)
        event = ChangesetMerged(
            changeset_id="changeset-123",
            proposal_id="proposal-456",
            merged_at=now,
            events_applied=0,
        )
        assert event.events_applied == 0

    def test_changeset_merged_rejects_empty_proposal_id(self):
        """ChangesetMerged raises ValueError if proposal_id is empty (parent validation)."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="Event field 'proposal_id' cannot be empty"):
            ChangesetMerged(
                changeset_id="changeset-123",
                proposal_id="",
                merged_at=now,
                events_applied=5,
            )


class TestSyncCompleted:
    """Tests for SyncCompleted event."""

    def test_sync_completed_push_instantiation(self):
        """SyncCompleted can be instantiated with direction='push' and all required fields."""
        now = datetime.now(timezone.utc)
        event = SyncCompleted(
            direction=SyncDirection.PUSH,
            events_count=10,
            completed_at=now,
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.direction == "push"
        assert event.events_count == 10
        assert event.completed_at == now

    def test_sync_completed_pull_instantiation(self):
        """SyncCompleted can be instantiated with direction='pull' and all required fields."""
        now = datetime.now(timezone.utc)
        event = SyncCompleted(
            direction=SyncDirection.PULL,
            events_count=7,
            completed_at=now,
        )
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.direction == "pull"
        assert event.events_count == 7
        assert event.completed_at == now

    def test_sync_completed_is_frozen(self):
        """SyncCompleted instances are frozen."""
        now = datetime.now(timezone.utc)
        event = SyncCompleted(
            direction=SyncDirection.PUSH,
            events_count=5,
            completed_at=now,
        )
        with pytest.raises(FrozenInstanceError):
            event.events_count = 10

    def test_sync_completed_with_valid_push_direction(self):
        """SyncCompleted can be instantiated with valid SyncDirection.PUSH."""
        now = datetime.now(timezone.utc)
        event = SyncCompleted(
            direction=SyncDirection.PUSH,
            events_count=5,
            completed_at=now,
        )
        assert event.direction == SyncDirection.PUSH

    def test_sync_completed_rejects_none_direction(self):
        """SyncCompleted raises ValueError if direction is None."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="SyncCompleted event requires direction"):
            SyncCompleted(
                direction=None,  # type: ignore
                events_count=5,
                completed_at=now,
            )

    def test_sync_completed_rejects_empty_direction(self):
        """SyncCompleted raises ValueError if direction is empty string (not a valid enum value)."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError):
            SyncCompleted(
                direction="",  # type: ignore
                events_count=5,
                completed_at=now,
            )

    def test_sync_completed_rejects_none_completed_at(self):
        """SyncCompleted raises ValueError if completed_at is None."""
        with pytest.raises(ValueError, match="SyncCompleted event requires completed_at timestamp"):
            SyncCompleted(
                direction=SyncDirection.PUSH,
                events_count=5,
                completed_at=None,  # type: ignore
            )

    def test_sync_completed_accepts_zero_events_count(self):
        """SyncCompleted can have zero events_count (no changes to sync)."""
        now = datetime.now(timezone.utc)
        event = SyncCompleted(
            direction=SyncDirection.PUSH,
            events_count=0,
            completed_at=now,
        )
        assert event.events_count == 0

    def test_sync_completed_with_valid_pull_direction(self):
        """SyncCompleted can be instantiated with valid SyncDirection.PULL."""
        now = datetime.now(timezone.utc)
        event = SyncCompleted(
            direction=SyncDirection.PULL,
            events_count=5,
            completed_at=now,
        )
        assert event.direction == SyncDirection.PULL

    def test_sync_completed_accepts_negative_events_count(self):
        """SyncCompleted allows negative events_count (unusual but technically valid)."""
        now = datetime.now(timezone.utc)
        event = SyncCompleted(
            direction=SyncDirection.PUSH,
            events_count=-1,
            completed_at=now,
        )
        assert event.events_count == -1


class TestEventImportability:
    """Tests that all versioning events can be imported from the module."""

    def test_versioning_events_importable(self):
        """ChangesetMerged and SyncCompleted are importable from domain.versioning.events."""
        events = [
            ChangesetMerged,
            SyncCompleted,
        ]
        for event_class in events:
            assert event_class is not None
            assert hasattr(event_class, "__dataclass_fields__")
