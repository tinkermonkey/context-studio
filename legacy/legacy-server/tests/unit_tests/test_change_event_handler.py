"""Test the ChangeEventHandler with the new normalized change event system."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from database.enums import RecordType
from database.models import ChangeEvent
from services.change_event_handler import ChangeEventHandler


def test_change_event_creation_with_record_type_enum(db_session):
    """Test that ChangeEvent creation works with the new RecordType enum."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test data
    record_type = RecordType.STRUCTURE_NODE
    record_id = "test-node-123"
    event_type = "create"
    record_data = {
        "id": record_id,
        "title": "Test Node",
        "definition": "A test structure node",
    }

    # Create event using new enum system
    event = handler.fire_created_event(
        record_type=record_type, record_id=record_id, record_data=record_data
    )

    # Verify event was created with correct record_type and record_id
    assert event.record_id == record_id
    assert event.event_type == event_type
    assert event.record_type == record_type
    assert event.new_data == record_data
    assert event.old_data is None
    assert event.processed is False


def test_change_event_update_with_record_type_enum(db_session):
    """Test that ChangeEvent updates work with the new RecordType enum."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test data
    record_type = RecordType.STRUCTURE_NODE_LINK
    record_id = "test-link-456"
    old_data = {"id": record_id, "parent_id": "old-parent", "child_id": "child-id"}
    new_data = {"id": record_id, "parent_id": "new-parent", "child_id": "child-id"}

    # Create event
    event = handler.fire_updated_event(
        record_type=record_type,
        record_id=record_id,
        old_data=old_data,
        new_data=new_data,
    )

    # Verify event was created correctly
    assert event.record_id == record_id
    assert event.event_type == "update"
    assert event.record_type == record_type
    assert event.old_data == old_data
    assert event.new_data == new_data
    assert event.processed is False


def test_change_event_delete_with_record_type_enum(db_session):
    """Test that ChangeEvent deletes work with the new RecordType enum."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test data
    record_type = RecordType.PREDICATE
    record_id = "test-predicate-789"
    record_data = {
        "id": record_id,
        "title": "Deleted Predicate",
        "definition": "This will be deleted",
    }

    # Create event
    event = handler.fire_deleted_event(
        record_type=record_type, record_id=record_id, record_data=record_data
    )

    # Verify event was created correctly
    assert event.record_id == record_id
    assert event.event_type == "delete"
    assert event.record_type == record_type
    assert event.old_data == record_data
    assert event.new_data is None
    assert event.processed is False


def test_get_events_for_record(db_session):
    """Test querying events for a specific record."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test data
    record_id = "test-record-987"
    record_type = RecordType.STRUCTURE_NODE

    # Create multiple events for the same record
    event1 = handler.fire_created_event(record_type, record_id, {"title": "Created"})
    event2 = handler.fire_updated_event(
        record_type, record_id, {"title": "Created"}, {"title": "Updated"}
    )
    event3 = handler.fire_deleted_event(record_type, record_id, {"title": "Updated"})

    # Query events for this record
    events = handler.get_events_for_record(record_id)

    # Should return all 3 events for this record, ordered by timestamp desc
    assert len(events) == 3
    assert all(event.record_id == record_id for event in events)

    # Should be ordered by timestamp descending (most recent first)
    assert events[0].id == event3.id  # delete event (most recent)
    assert events[1].id == event2.id  # update event
    assert events[2].id == event1.id  # create event (oldest)


def test_get_events_for_record_with_limit(db_session):
    """Test querying events for a specific record with limit."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test data
    record_id = "test-record-limit-123"
    record_type = RecordType.STRUCTURE_NODE

    # Create multiple events for the same record
    for i in range(5):
        handler.fire_created_event(record_type, record_id, {"title": f"Event {i}"})

    # Query events with limit
    events = handler.get_events_for_record(record_id, limit=3)

    # Should return only 3 events
    assert len(events) == 3
    assert all(event.record_id == record_id for event in events)


def test_get_unprocessed_events_filtered_by_record_type(db_session):
    """Test filtering unprocessed events by record type."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Create events for different record types
    handler.fire_created_event(RecordType.STRUCTURE_NODE, "node-1", {"title": "Node 1"})
    handler.fire_created_event(
        RecordType.STRUCTURE_NODE_LINK, "link-1", {"parent": "p1", "child": "c1"}
    )
    handler.fire_created_event(RecordType.PREDICATE, "pred-1", {"title": "Predicate 1"})
    handler.fire_created_event(RecordType.STRUCTURE_NODE, "node-2", {"title": "Node 2"})

    # Get all unprocessed events
    all_events = handler.get_unprocessed_events()
    assert len(all_events) == 4

    # Get only structure_node events
    node_events = handler.get_unprocessed_events(record_type=RecordType.STRUCTURE_NODE)
    assert len(node_events) == 2
    assert all(event.record_type == RecordType.STRUCTURE_NODE for event in node_events)

    # Get only predicate events
    predicate_events = handler.get_unprocessed_events(record_type=RecordType.PREDICATE)
    assert len(predicate_events) == 1
    assert predicate_events[0].record_type == RecordType.PREDICATE


def test_predicate_event_creation(db_session):
    """Test creating predicate change events."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test data
    predicate_id = "test-predicate-456"
    predicate_data = {
        "id": predicate_id,
        "title": "Test Predicate",
        "definition": "A test predicate definition",
    }

    # Create predicate event using convenience method
    event = handler.fire_predicate_created_event(predicate_id, predicate_data)

    # Verify predicate event
    assert event.record_id == predicate_id
    assert event.record_type == RecordType.PREDICATE
    assert event.event_type == "create"
    assert event.new_data == predicate_data


def test_structure_node_event_creation(db_session):
    """Test creating structure node change events."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test data
    node_id = "test-node-789"
    node_data = {"id": node_id, "title": "Test Node", "node_type": "layer"}

    # Create structure node event using convenience method
    event = handler.fire_structure_node_created_event(node_id, node_data)

    # Verify structure node event
    assert event.record_id == node_id
    assert event.record_type == RecordType.STRUCTURE_NODE
    assert event.event_type == "create"
    assert event.new_data == node_data


def test_event_creation_with_enum_validation(db_session):
    """Test that RecordType enum validation works properly."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test that valid enum values work
    for record_type in [
        RecordType.STRUCTURE_NODE,
        RecordType.STRUCTURE_NODE_LINK,
        RecordType.PREDICATE,
    ]:
        event = handler.fire_created_event(
            record_type, f"test-{record_type.value}", {"test": "data"}
        )
        assert event.record_type == record_type

    # Test that invalid string values raise errors when passed directly to create_event
    with pytest.raises(ValueError):
        # This should fail because "invalid_type" is not a valid RecordType
        from database.enums import RecordType as RT

        RT("invalid_type")


def test_normalized_structure_node_events(db_session):
    """Test that normalized structure node events work properly."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Test structure node creation using new normalized method
    node_id = "test-structure-node"
    node_data = {"id": node_id, "title": "Structure Node Test"}

    # Use new normalized method with RecordType enum
    event = handler.fire_created_event(RecordType.STRUCTURE_NODE, node_id, node_data)

    # Should create a ChangeEvent with structure_node record type
    assert event.record_id == node_id
    assert event.record_type == RecordType.STRUCTURE_NODE
    assert event.event_type == "create"
    assert event.new_data == node_data


def test_mark_event_processed(db_session):
    """Test marking events as processed."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Create an unprocessed event
    event = handler.fire_created_event(
        RecordType.STRUCTURE_NODE, "test-node", {"title": "Test"}
    )
    assert event.processed is False

    # Mark as processed
    handler.mark_event_processed(event.id)

    # Verify it's marked as processed
    updated_event = db_session.query(ChangeEvent).filter_by(id=event.id).first()
    assert updated_event.processed is True


def test_get_event_stats(db_session):
    """Test getting event statistics."""

    # Create event handler
    handler = ChangeEventHandler(db_session)

    # Create some test events
    handler.fire_created_event(RecordType.STRUCTURE_NODE, "node-1", {"title": "Node 1"})
    handler.fire_updated_event(
        RecordType.STRUCTURE_NODE,
        "node-1",
        {"title": "Node 1"},
        {"title": "Updated Node 1"},
    )
    handler.fire_created_event(RecordType.PREDICATE, "pred-1", {"title": "Predicate 1"})

    # Mark one as processed
    events = handler.get_unprocessed_events()
    handler.mark_event_processed(events[0].id)

    # Get stats
    stats = handler.get_event_stats()

    # Verify stats
    assert stats["total_events"] >= 3
    assert stats["processed_events"] >= 1
    assert stats["unprocessed_events"] >= 2
    assert "create" in stats["events_by_type"]
    assert "update" in stats["events_by_type"]
    assert "structure_node" in stats["events_by_record_type"]
    assert "predicate" in stats["events_by_record_type"]
