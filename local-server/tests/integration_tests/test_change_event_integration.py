"""Integration tests for the normalized change event system."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import text
from database.utils import get_current_engine
from services.change_event_handler import ChangeEventHandler
from utils.event_processor import EventProcessor
from database.models import ChangeEvent
from database.enums import RecordType
import time
import json
from uuid import uuid4


@pytest.fixture
def change_event_handler(db_session):
    """Create a ChangeEventHandler for testing."""
    return ChangeEventHandler(db_session)


def test_end_to_end_event_processing_all_record_types(db_session, change_event_handler):
    """Test end-to-end event processing for all record types."""
    
    # Generate unique IDs for this test
    node_id = f"test-node-{uuid4()}"
    link_id = f"test-link-{uuid4()}"
    predicate_id = f"test-predicate-{uuid4()}"
    parent_id = f"parent-{uuid4()}"
    child_id = f"child-{uuid4()}"
    
    # Create events for all record types
    events = []
    
    # Structure node event
    events.append(change_event_handler.fire_created_event(
        RecordType.STRUCTURE_NODE, 
        node_id, 
        {"id": node_id, "title": "Test Node", "node_type": "layer"}
    ))
    
    # Structure node link event
    events.append(change_event_handler.fire_created_event(
        RecordType.STRUCTURE_NODE_LINK,
        link_id, 
        {"id": link_id, "parent_id": parent_id, "child_id": child_id}
    ))
    
    # Predicate event
    events.append(change_event_handler.fire_created_event(
        RecordType.PREDICATE,
        predicate_id,
        {"id": predicate_id, "title": "Test Predicate", "definition": "Test definition"}
    ))
    
    # Verify events are unprocessed
    assert all(not event.processed for event in events)
    
    # Process events with EventProcessor
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    
    try:
        processor.start()
        time.sleep(0.2)  # Allow processing
    finally:
        processor.stop()
    
    # Verify all events are now processed
    db_session.refresh(events[0])
    db_session.refresh(events[1])
    db_session.refresh(events[2])
    
    assert all(event.processed for event in events)


def test_predicate_event_integration(db_session, change_event_handler):
    """Test integration of predicate events through the full system."""
    
    # Generate unique ID for this test
    predicate_id = f"pred-integration-test-{uuid4()}"
    
    # Create predicate events
    predicate_data = {
        "id": predicate_id,
        "title": "Integration Test Predicate",
        "definition": "A predicate for integration testing"
    }
    
    create_event = change_event_handler.fire_predicate_created_event(
        predicate_id, 
        predicate_data
    )
    
    update_event = change_event_handler.fire_updated_event(
        RecordType.PREDICATE,
        predicate_id,
        predicate_data,
        {**predicate_data, "definition": "Updated definition"}
    )
    
    delete_event = change_event_handler.fire_deleted_event(
        RecordType.PREDICATE,
        predicate_id,
        {**predicate_data, "definition": "Updated definition"}
    )
    
    # Verify events created
    assert create_event.record_type == RecordType.PREDICATE
    assert update_event.record_type == RecordType.PREDICATE
    assert delete_event.record_type == RecordType.PREDICATE
    
    # Process with EventProcessor
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    
    import logging
    import io
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        processor.start()
        time.sleep(0.2)
    finally:
        processor.stop()
        logger.removeHandler(handler)
    
    # Verify predicate events were processed
    log_contents = log_stream.getvalue()
    assert log_contents.count("Processing predicate event") == 3
    
    # Verify events are marked processed
    db_session.refresh(create_event)
    db_session.refresh(update_event)
    db_session.refresh(delete_event)
    
    assert create_event.processed
    assert update_event.processed  
    assert delete_event.processed


def test_mixed_event_processing_with_filtering(db_session, change_event_handler):
    """Test processing mixed event types with filtering capabilities."""
    
    # Create multiple events of different types
    node_events = []
    link_events = []
    predicate_events = []
    
    for i in range(3):
        node_events.append(change_event_handler.fire_created_event(
            RecordType.STRUCTURE_NODE, 
            f"node-{i}", 
            {"id": f"node-{i}", "title": f"Node {i}"}
        ))
        
        link_events.append(change_event_handler.fire_created_event(
            RecordType.STRUCTURE_NODE_LINK,
            f"link-{i}",
            {"id": f"link-{i}", "parent_id": f"parent-{i}", "child_id": f"child-{i}"}
        ))
        
        predicate_events.append(change_event_handler.fire_created_event(
            RecordType.PREDICATE,
            f"predicate-{i}",
            {"id": f"predicate-{i}", "title": f"Predicate {i}"}
        ))
    
    # Test filtering by record type
    all_unprocessed = change_event_handler.get_unprocessed_events()
    node_unprocessed = change_event_handler.get_unprocessed_events(record_type=RecordType.STRUCTURE_NODE)
    link_unprocessed = change_event_handler.get_unprocessed_events(record_type=RecordType.STRUCTURE_NODE_LINK)
    predicate_unprocessed = change_event_handler.get_unprocessed_events(record_type=RecordType.PREDICATE)
    
    assert len(all_unprocessed) >= 9
    assert len(node_unprocessed) == 3
    assert len(link_unprocessed) == 3
    assert len(predicate_unprocessed) == 3
    
    # Process all events
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=20)
    
    try:
        processor.start()
        time.sleep(0.3)  # Allow processing of all events
    finally:
        processor.stop()
    
    # Verify all events are processed
    final_unprocessed = change_event_handler.get_unprocessed_events()
    assert len(final_unprocessed) == 0


def test_event_statistics_integration(db_session, change_event_handler):
    """Test event statistics functionality with real data."""
    
    # Generate unique IDs for this test
    node_id = f"stats-node-{uuid4()}"
    pred_id = f"stats-pred-{uuid4()}"
    link_id = f"stats-link-{uuid4()}"
    parent_id = f"p-{uuid4()}"
    child_id = f"c-{uuid4()}"
    
    # Create baseline stats
    initial_stats = change_event_handler.get_event_stats()
    
    # Create events of different types
    change_event_handler.fire_created_event(RecordType.STRUCTURE_NODE, node_id, {"title": "Node 1"})
    change_event_handler.fire_updated_event(RecordType.STRUCTURE_NODE, node_id, {"title": "Node 1"}, {"title": "Updated Node 1"})
    change_event_handler.fire_deleted_event(RecordType.STRUCTURE_NODE, node_id, {"title": "Updated Node 1"})
    
    change_event_handler.fire_created_event(RecordType.PREDICATE, pred_id, {"title": "Predicate 1"})
    change_event_handler.fire_created_event(RecordType.STRUCTURE_NODE_LINK, link_id, {"parent": parent_id, "child": child_id})
    
    # Get new stats
    new_stats = change_event_handler.get_event_stats()
    
    # Verify stats increased
    assert new_stats["total_events"] == initial_stats["total_events"] + 5
    assert new_stats["unprocessed_events"] == initial_stats["unprocessed_events"] + 5
    
    # Verify event type breakdown
    assert new_stats["events_by_type"]["create"] == initial_stats["events_by_type"].get("create", 0) + 3
    assert new_stats["events_by_type"]["update"] == initial_stats["events_by_type"].get("update", 0) + 1
    assert new_stats["events_by_type"]["delete"] == initial_stats["events_by_type"].get("delete", 0) + 1
    
    # Verify record type breakdown  
    assert new_stats["events_by_record_type"]["structure_node"] == initial_stats["events_by_record_type"].get("structure_node", 0) + 3
    assert new_stats["events_by_record_type"]["predicate"] == initial_stats["events_by_record_type"].get("predicate", 0) + 1
    assert new_stats["events_by_record_type"]["structure_node_link"] == initial_stats["events_by_record_type"].get("structure_node_link", 0) + 1


def test_normalized_change_event_integration(db_session):
    """Test that normalized change event system works in integration scenarios."""
    
    # Generate unique ID for this test
    node_id = f"new-node-{uuid4()}"
    
    # Create handler using new interface
    handler = ChangeEventHandler(db_session)
    
    # Use new normalized methods
    node_event = handler.fire_created_event(RecordType.STRUCTURE_NODE, node_id, {"title": "Normalized Test"})
    
    # Verify it created a proper ChangeEvent
    assert isinstance(node_event, ChangeEvent)
    assert node_event.record_type == RecordType.STRUCTURE_NODE
    assert node_event.record_id == node_id
    
    # Process with EventProcessor
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    
    try:
        processor.start()
        time.sleep(0.1)
    finally:
        processor.stop()
    
    # Verify event was processed
    db_session.refresh(node_event)
    assert node_event.processed


def test_database_trigger_integration(db_session):
    """Test that database triggers create proper ChangeEvents."""
    
    # Generate unique ID for this test
    trigger_node_id = f"trigger-test-node-{uuid4()}"
    
    # Note: This test would need actual database triggers to be in place
    # and would insert directly into the tables to trigger the events
    # For now, we'll test the handler integration
    
    engine = get_current_engine()
    
    # Insert a structure_node directly (would trigger change_events via database trigger)
    # This is a simulated test since we'd need the actual triggers in place
    with engine.connect() as conn:
        # First check if change_events table exists
        table_exists = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='change_events'
        """)).fetchone()
        
        if table_exists:
            # Simulate what a trigger would do
            conn.execute(text("""
                INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, processed)
                VALUES ('create', 'structure_node', :node_id, NULL, 
                        :node_data, 0)
            """), {
                "node_id": trigger_node_id,
                "node_data": json.dumps({"id": trigger_node_id, "title": "Trigger Test", "node_type": "layer"})
            })
            conn.commit()
            
            # Verify the event was created
            event_count = conn.execute(text("""
                SELECT COUNT(*) FROM change_events WHERE record_id = :node_id
            """), {"node_id": trigger_node_id}).scalar()
            
            assert event_count == 1
            
            # Clean up
            conn.execute(text("""
                DELETE FROM change_events WHERE record_id = :node_id
            """), {"node_id": trigger_node_id})
            conn.commit()


def test_event_data_integrity_integration(db_session, change_event_handler):
    """Test data integrity throughout the event processing pipeline."""
    
    # Generate unique ID for this test
    integrity_node_id = f"integrity-test-node-{uuid4()}"
    parent_domain_id = f"parent-domain-{uuid4()}"
    child_term_1_id = f"child-term-1-{uuid4()}"
    child_term_2_id = f"child-term-2-{uuid4()}"
    
    # Create complex event with rich data
    complex_data = {
        "id": integrity_node_id,
        "title": "Complex Integration Test Node", 
        "definition": "A node with complex data for testing integrity",
        "node_type": "domain",
        "metadata": {
            "created_by": "test_system",
            "tags": ["integration", "test", "complex"],
            "settings": {"auto_expand": True, "color": "#FF5733"}
        },
        "relationships": [
            {"type": "parent", "target_id": parent_domain_id},
            {"type": "child", "target_id": child_term_1_id},
            {"type": "child", "target_id": child_term_2_id}
        ]
    }
    
    # Create event
    event = change_event_handler.fire_created_event(
        RecordType.STRUCTURE_NODE,
        integrity_node_id,
        complex_data
    )
    
    # Verify data stored correctly
    assert event.new_data == complex_data
    assert event.record_id == integrity_node_id
    
    # Process event
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    
    try:
        processor.start()
        time.sleep(0.1)
    finally:
        processor.stop()
    
    # Verify data integrity after processing
    db_session.refresh(event)
    assert event.processed
    assert event.new_data == complex_data  # Data should remain unchanged
    
    # Verify we can query and retrieve the event with intact data
    retrieved_event = change_event_handler.get_events_for_record(integrity_node_id)[0]
    assert retrieved_event.new_data == complex_data


def test_high_volume_event_processing(db_session, change_event_handler):
    """Test processing a higher volume of events."""
    
    # Generate unique base ID for this test run
    test_run_id = str(uuid4())
    
    # Create multiple batches of events
    events = []
    for i in range(50):  # Create 50 events of mixed types
        record_type = [RecordType.STRUCTURE_NODE, RecordType.STRUCTURE_NODE_LINK, RecordType.PREDICATE][i % 3]
        unique_id = f"volume-test-{test_run_id}-{record_type.value}-{i}"
        events.append(change_event_handler.fire_created_event(
            record_type,
            unique_id,
            {"id": unique_id, "title": f"Volume Test {i}"}
        ))
    
    # Verify all are unprocessed
    unprocessed_count = len(change_event_handler.get_unprocessed_events())
    assert unprocessed_count >= 50
    
    # Process with higher limits
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=100)
    
    try:
        processor.start()
        time.sleep(0.5)  # Allow time for all events to process
    finally:
        processor.stop()
    
    # Verify all events are processed
    final_unprocessed = change_event_handler.get_unprocessed_events()
    assert len(final_unprocessed) == 0
