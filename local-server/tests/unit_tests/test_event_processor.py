import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import time
import pytest
from utils.event_processor import EventProcessor
from database.utils import get_current_engine
from database.enums import RecordType
from sqlalchemy import text
from datetime import datetime, timezone, timedelta


def insert_event_via_sqlalchemy(event_type, record_type, processed=0, ts=None, record_id=None):
    """Insert an event using SQLAlchemy engine (same as EventProcessor uses)"""
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    if record_id is None:
        record_id = f"test-{record_type.replace('_', '-')}-id"
    
    # Create JSON data
    new_data = f'{{"title": "Test {record_type}"}}'
    old_data = f'{{"title": "Old Test {record_type}"}}' if event_type == "update" else None
    
    engine = get_current_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO change_events 
            (event_type, record_type, record_id, old_data, new_data, timestamp, processed) 
            VALUES (:event_type, :record_type, :record_id, :old_data, :new_data, :ts, :processed)
        """), {
            "event_type": event_type,
            "record_type": record_type,
            "record_id": record_id,
            "old_data": old_data,
            "new_data": new_data,
            "ts": ts,
            "processed": processed
        })
        conn.commit()


def get_event_count_via_sqlalchemy(processed=None):
    """Get count of events using SQLAlchemy (same as EventProcessor uses)"""
    if processed is not None:
        query = "SELECT COUNT(*) FROM change_events WHERE processed = :processed"
        params = {"processed": processed}
    else:
        query = "SELECT COUNT(*) FROM change_events"
        params = {}
    
    engine = get_current_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return result.scalar()


def cleanup_events():
    """Clean up test events"""
    engine = get_current_engine()
    with engine.connect() as conn:
        # Check if table exists first
        table_check = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='change_events'
        """)).fetchone()
        
        if table_check:
            # Clean up events where the JSON contains test- IDs
            conn.execute(text("""
                DELETE FROM change_events 
                WHERE (new_data LIKE '%test-%' OR old_data LIKE '%test-%')
            """))
            conn.commit()


@pytest.fixture(autouse=True)
def cleanup_test_events(shared_app):
    """Automatically cleanup test events before and after each test"""
    cleanup_events()  # Clean up before test
    yield
    cleanup_events()  # Clean up after test


def test_event_processor_processes_events(shared_app):
    """Test that EventProcessor processes events for all record types."""
    # Insert unprocessed events for each record type
    for record_type in ["structure_node", "structure_node_link", "predicate"]:
        insert_event_via_sqlalchemy("create", record_type)

    print("[TEST] Starting test_event_processor_processes_events")
    
    # Get the database URL from the current engine
    from database.utils import get_current_engine
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    try:
        processor.start()
        print("[TEST] EventProcessor started")
        time.sleep(0.2)  # Allow processor to run
        print("[TEST] Slept 0.2s, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")

    # All events should be marked processed
    unprocessed_count = get_event_count_via_sqlalchemy(processed=0)
    assert unprocessed_count == 0


def test_event_processor_handles_all_record_types(shared_app):
    """Test that EventProcessor handles structure_node, structure_node_link, and predicate events."""
    print("[TEST] Starting test_event_processor_handles_all_record_types")
    
    # Insert events for all record types
    for record_type in ["structure_node", "structure_node_link", "predicate"]:
        insert_event_via_sqlalchemy("create", record_type)
    
    # Get the database URL from the current engine
    from database.utils import get_current_engine
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    
    # Capture logs to verify handlers are called
    import logging
    import io
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        processor.start()
        print("[TEST] EventProcessor started")
        time.sleep(0.2)  # Allow processor to run
        print("[TEST] Slept 0.2s, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")
        logger.removeHandler(handler)
    
    # Verify that all record types were processed
    log_contents = log_stream.getvalue()
    assert "Processing structure_node event" in log_contents
    assert "Processing structure_node_link event" in log_contents  
    assert "Processing predicate event" in log_contents
    
    # All events should be marked processed
    unprocessed_count = get_event_count_via_sqlalchemy(processed=0)
    assert unprocessed_count == 0


def test_event_processor_handles_unknown_record_type(shared_app, capsys):
    """Test handling of unknown record types."""
    insert_event_via_sqlalchemy("create", "unknown_record_type")

    print("[TEST] Starting test_event_processor_handles_unknown_record_type")
    
    # Get the database URL from the current engine
    from database.utils import get_current_engine
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    import logging
    import io
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        processor.start()
        print("[TEST] EventProcessor started")
        time.sleep(0.15)
        print("[TEST] Slept 0.15s, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")
        logger.removeHandler(handler)

    # Should log a warning about unknown record_type
    log_contents = log_stream.getvalue()
    assert "Unknown record_type: unknown_record_type" in log_contents


def test_event_processor_cleanup_old_events(shared_app, capsys):
    """Test cleanup of old processed events."""
    # Get initial processed event count
    initial_processed_count = get_event_count_via_sqlalchemy(processed=1)
    
    # Insert processed event older than 48h (timezone-aware)
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    insert_event_via_sqlalchemy("delete", "structure_node", processed=1, ts=old_ts)
    # Insert recent processed event
    insert_event_via_sqlalchemy("delete", "structure_node", processed=1)

    print("[TEST] Starting test_event_processor_cleanup_old_events")
    
    # Verify we added 2 events
    pre_cleanup_count = get_event_count_via_sqlalchemy(processed=1)
    assert pre_cleanup_count == initial_processed_count + 2, f"Expected {initial_processed_count + 2} events, got {pre_cleanup_count}"
    
    # Get the database URL from the current engine
    from database.utils import get_current_engine
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    try:
        # Call cleanup directly (don't wait a day)
        processor.cleanup_old_events()
        print("[TEST] Called cleanup_old_events, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")
    
    # Only the recent event (plus any pre-existing events) should remain
    processed_count = get_event_count_via_sqlalchemy(processed=1)
    assert processed_count == initial_processed_count + 1, f"Expected {initial_processed_count + 1} events after cleanup, got {processed_count}"


def test_predicate_event_processing(shared_app):
    """Test processing of predicate-specific events."""
    print("[TEST] Starting test_predicate_event_processing")
    
    # Insert predicate events
    insert_event_via_sqlalchemy("create", "predicate", record_id="test-predicate-123")
    insert_event_via_sqlalchemy("update", "predicate", record_id="test-predicate-456")
    insert_event_via_sqlalchemy("delete", "predicate", record_id="test-predicate-789")
    
    # Get the database URL from the current engine
    from database.utils import get_current_engine
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    
    # Capture logs to verify predicate handler is called
    import logging
    import io
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        processor.start()
        print("[TEST] EventProcessor started")
        time.sleep(0.2)  # Allow processor to run
        print("[TEST] Slept 0.2s, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")
        logger.removeHandler(handler)
    
    # Verify that predicate events were processed
    log_contents = log_stream.getvalue()
    assert log_contents.count("Processing predicate event") == 3  # create, update, delete
    
    # All events should be marked processed
    unprocessed_count = get_event_count_via_sqlalchemy(processed=0)
    assert unprocessed_count == 0


def test_event_processor_thread_start_stop_idempotent(shared_app):
    print("[TEST] Starting test_event_processor_thread_start_stop_idempotent")
    
    # Get the database URL from the current engine
    from database.utils import get_current_engine
    engine = get_current_engine()
    database_url = str(engine.url)
    
    processor = EventProcessor(database_url=database_url, poll_interval=0.05, max_events=10)
    try:
        processor.start()
        print("[TEST] EventProcessor started (1)")
        processor.start()  # Should not start a second thread
        print("[TEST] EventProcessor started (2)")
        time.sleep(0.1)
        print("[TEST] Slept 0.1s, stopping EventProcessor")
    finally:
        processor.stop()
        processor.stop()  # Should not error
        print("[TEST] EventProcessor stopped")
