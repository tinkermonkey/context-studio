"""
Integration tests for the DuckDB sync adapter.

These tests verify that the DuckDBSyncAdapter correctly serializes and deserializes
change events using Parquet files with date partitioning.
"""

import sys
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import ChangeOperation, SyncResult
from adapters.sync.duckdb_sync import DuckDBSyncAdapter


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for Parquet files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def duckdb_adapter(temp_output_dir):
    """Create a DuckDB sync adapter instance."""
    return DuckDBSyncAdapter(output_dir=temp_output_dir)


@pytest.fixture
def sample_events():
    """Create sample change events for testing."""
    now = datetime.now(timezone.utc)
    return [
        ChangeEvent(
            id="event-1",
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "TestClass", "description": "A test class"},
            timestamp=now,
            user_id="user-1",
            change_reason="Initial creation",
            processed=False,
        ),
        ChangeEvent(
            id="event-2",
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "TestClass", "description": "Updated description"},
            previous_state={"name": "TestClass", "description": "A test class"},
            timestamp=now + timedelta(hours=1),
            user_id="user-1",
            change_reason="Description update",
            processed=False,
        ),
        ChangeEvent(
            id="event-3",
            entity_id="entity-2",
            entity_type="Property",
            operation=ChangeOperation.CREATE,
            new_state={"name": "property1", "domain": "entity-1"},
            timestamp=now + timedelta(days=1),
            user_id="user-2",
            change_reason="Added new property",
            processed=False,
        ),
    ]


class TestDuckDBSyncAdapterPush:
    """Tests for the push() method."""

    def test_push_empty_events(self, duckdb_adapter):
        """Test pushing an empty list of events."""
        result = duckdb_adapter.push([])

        assert isinstance(result, SyncResult)
        assert result.pushed == 0
        assert result.pulled == 0
        assert result.errors == ()
        assert result.pushed_event_ids == ()

    def test_push_single_event(self, duckdb_adapter, sample_events):
        """Test pushing a single event."""
        event = sample_events[0]

        result = duckdb_adapter.push([event])

        assert result.pushed == 1
        assert result.pulled == 0
        assert result.errors == ()
        assert event.id in result.pushed_event_ids

    def test_push_multiple_events(self, duckdb_adapter, sample_events):
        """Test pushing multiple events."""
        result = duckdb_adapter.push(sample_events)

        assert result.pushed == 3
        assert result.pulled == 0
        assert result.errors == ()
        assert len(result.pushed_event_ids) == 3
        assert all(event.id in result.pushed_event_ids for event in sample_events)

    def test_push_creates_date_partitioned_files(self, duckdb_adapter, sample_events):
        """Test that push creates properly partitioned Parquet files."""
        duckdb_adapter.push(sample_events)

        # Verify directory structure
        changes_dir = Path(duckdb_adapter._output_dir) / "changes"
        assert changes_dir.exists()

        # Verify date directories exist
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        tomorrow_date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        assert (changes_dir / date_str).exists()
        assert (changes_dir / tomorrow_date_str).exists()

        # Verify Parquet files exist in the date directories (UUID filenames)
        date_parquet_files = list((changes_dir / date_str).glob("*.parquet"))
        tomorrow_parquet_files = list((changes_dir / tomorrow_date_str).glob("*.parquet"))

        assert len(date_parquet_files) > 0, f"No Parquet files in {date_str} directory"
        assert len(tomorrow_parquet_files) > 0, f"No Parquet files in {tomorrow_date_str} directory"

    def test_push_events_with_complex_state(self, duckdb_adapter):
        """Test pushing events with complex nested state objects."""
        event = ChangeEvent(
            id="event-complex",
            entity_id="entity-complex",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={
                "name": "Complex",
                "nested": {"field1": "value1", "field2": [1, 2, 3]},
                "metadata": {"tags": ["tag1", "tag2"]},
            },
            timestamp=datetime.now(timezone.utc),
            processed=False,
        )

        result = duckdb_adapter.push([event])

        assert result.pushed == 1
        assert event.id in result.pushed_event_ids

    def test_push_events_without_optional_fields(self, duckdb_adapter):
        """Test pushing events with minimal fields."""
        event = ChangeEvent(
            id="event-minimal",
            entity_id="entity-minimal",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Minimal"},
            timestamp=datetime.now(timezone.utc),
        )

        result = duckdb_adapter.push([event])

        assert result.pushed == 1
        assert event.id in result.pushed_event_ids


class TestDuckDBSyncAdapterPull:
    """Tests for the pull() method."""

    def test_pull_empty_directory(self, duckdb_adapter):
        """Test pulling from an empty sync directory."""
        events = duckdb_adapter.pull()

        assert isinstance(events, list)
        assert len(events) == 0

    def test_pull_single_event(self, duckdb_adapter, sample_events):
        """Test pulling a single event."""
        event = sample_events[0]
        duckdb_adapter.push([event])

        pulled = duckdb_adapter.pull()

        assert len(pulled) == 1
        assert pulled[0].id == event.id
        assert pulled[0].entity_id == event.entity_id
        assert pulled[0].entity_type == event.entity_type
        assert pulled[0].operation == event.operation
        assert pulled[0].new_state == event.new_state

    def test_pull_multiple_events(self, duckdb_adapter, sample_events):
        """Test pulling multiple events."""
        duckdb_adapter.push(sample_events)

        pulled = duckdb_adapter.pull()

        assert len(pulled) == 3
        pulled_ids = {event.id for event in pulled}
        expected_ids = {event.id for event in sample_events}
        assert pulled_ids == expected_ids

    def test_pull_filters_by_date(self, duckdb_adapter, sample_events):
        """Test that pull filters events by date using since parameter."""
        duckdb_adapter.push(sample_events)

        # Pull only events from the day after the first event
        # event-1 and event-2 are on the same day, event-3 is 1 day later
        # We filter to include only events on the day of event-3 or later
        since = sample_events[0].timestamp + timedelta(hours=12)
        pulled = duckdb_adapter.pull(since=since)

        # Should get event-3 (on the next day)
        assert len(pulled) == 1
        assert pulled[0].id == sample_events[2].id

    def test_pull_deduplicates_events(self, duckdb_adapter, sample_events):
        """Test that pull deduplicates events by ID across multiple Parquet files."""
        event = sample_events[0]

        # Push the same event twice in separate calls to create duplicate Parquet files
        # This simulates the case where the same event appears in multiple files
        duckdb_adapter.push([event])
        duckdb_adapter.push([event])

        pulled = duckdb_adapter.pull()

        # Should only get one copy of the event, proving deduplication works
        assert len(pulled) == 1
        assert pulled[0].id == event.id

    def test_pull_preserves_event_state(self, duckdb_adapter):
        """Test that pull preserves all event fields."""
        event = ChangeEvent(
            id="event-state",
            entity_id="entity-state",
            entity_type="Class",
            operation=ChangeOperation.UPDATE,
            new_state={"name": "New", "version": 2},
            previous_state={"name": "Old", "version": 1},
            timestamp=datetime.now(timezone.utc),
            user_id="user-test",
            change_reason="Testing state preservation",
            processed=True,
        )

        duckdb_adapter.push([event])
        pulled = duckdb_adapter.pull()

        assert len(pulled) == 1
        pulled_event = pulled[0]
        assert pulled_event.id == event.id
        assert pulled_event.entity_id == event.entity_id
        assert pulled_event.entity_type == event.entity_type
        assert pulled_event.operation == event.operation
        assert pulled_event.new_state == event.new_state
        assert pulled_event.previous_state == event.previous_state
        assert pulled_event.user_id == event.user_id
        assert pulled_event.change_reason == event.change_reason
        assert pulled_event.processed == event.processed

    def test_pull_with_null_optional_fields(self, duckdb_adapter):
        """Test pulling events with null optional fields."""
        event = ChangeEvent(
            id="event-nulls",
            entity_id="entity-nulls",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "WithNulls"},
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            change_reason=None,
            previous_state=None,
            processed=False,
        )

        duckdb_adapter.push([event])
        pulled = duckdb_adapter.pull()

        assert len(pulled) == 1
        pulled_event = pulled[0]
        assert pulled_event.user_id is None
        assert pulled_event.change_reason is None
        assert pulled_event.previous_state is None


class TestDuckDBSyncAdapterRoundTrip:
    """Integration tests for complete push/pull round trips."""

    def test_round_trip_preserves_events(self, duckdb_adapter, sample_events):
        """Test that events survive a complete push/pull round trip."""
        # Push events
        push_result = duckdb_adapter.push(sample_events)
        assert push_result.pushed == 3

        # Pull events
        pulled = duckdb_adapter.pull()
        assert len(pulled) == 3

        # Verify each event was preserved
        pulled_map = {event.id: event for event in pulled}
        for original in sample_events:
            pulled_event = pulled_map[original.id]
            assert pulled_event.entity_id == original.entity_id
            assert pulled_event.entity_type == original.entity_type
            assert pulled_event.operation == original.operation
            assert pulled_event.new_state == original.new_state
            assert pulled_event.previous_state == original.previous_state
            assert pulled_event.user_id == original.user_id
            assert pulled_event.change_reason == original.change_reason

    def test_round_trip_with_subsequent_pushes(self, duckdb_adapter, sample_events):
        """Test multiple push operations and pulling all accumulated events."""
        # First push
        duckdb_adapter.push(sample_events[:2])

        # Second push
        duckdb_adapter.push(sample_events[2:])

        # Pull all
        pulled = duckdb_adapter.pull()

        assert len(pulled) == 3
        pulled_ids = {event.id for event in pulled}
        expected_ids = {event.id for event in sample_events}
        assert pulled_ids == expected_ids

    def test_round_trip_with_date_filtering(self, duckdb_adapter, sample_events):
        """Test round trip with date-based filtering."""
        # Push all events
        duckdb_adapter.push(sample_events)

        # Pull only recent events (from the next day onwards)
        filter_date = sample_events[0].timestamp + timedelta(hours=12)
        pulled = duckdb_adapter.pull(since=filter_date)

        # Should get only event-3 (which is on the next day)
        assert len(pulled) == 1
        assert pulled[0].id == sample_events[2].id


class TestDuckDBSyncAdapterConfiguration:
    """Tests for adapter configuration and initialization."""

    def test_adapter_initialization(self, temp_output_dir):
        """Test that adapter initializes correctly."""
        adapter = DuckDBSyncAdapter(output_dir=temp_output_dir)

        assert adapter.is_configured()
        assert (Path(temp_output_dir) / "changes").exists()

    def test_adapter_creates_missing_directory(self, temp_output_dir):
        """Test that adapter creates output directory if it doesn't exist."""
        nonexistent_dir = os.path.join(temp_output_dir, "new", "nested", "dir")
        adapter = DuckDBSyncAdapter(output_dir=nonexistent_dir)

        assert adapter.is_configured()
        assert Path(nonexistent_dir).exists()

    def test_is_configured_returns_true_after_successful_init(self, duckdb_adapter):
        """Test that is_configured() returns True after successful initialization."""
        assert duckdb_adapter.is_configured() is True

    def test_adapter_with_relative_path(self):
        """Test that adapter works with relative paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save current directory
            original_cwd = os.getcwd()
            try:
                # Change to temp directory
                os.chdir(temp_dir)

                # Create adapter with relative path
                adapter = DuckDBSyncAdapter(output_dir="./sync_data")

                assert adapter.is_configured()
                assert Path("./sync_data/changes").exists()
            finally:
                # Restore original directory
                os.chdir(original_cwd)
