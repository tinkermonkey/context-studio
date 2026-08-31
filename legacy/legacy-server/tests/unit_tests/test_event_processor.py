import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from database.utils import get_current_engine
from sqlalchemy import text
from utils.event_processor import EventProcessor

# Mark all tests in this file for separate execution
pytestmark = pytest.mark.event_processor


def insert_event_via_sqlalchemy(
    event_type, record_type, processed=0, ts=None, record_id=None, test_session_id=None
):
    """Insert an event using SQLAlchemy engine (same as EventProcessor uses)"""
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    if record_id is None:
        # Generate unique UUID-based ID for each test run
        unique_id = str(uuid.uuid4())[:8]  # Short UUID for readability
        record_id = f"test-{record_type.replace('_', '-')}-{unique_id}"

    # Add test session ID to ensure proper cleanup
    if test_session_id:
        record_id = f"{test_session_id}-{record_id}"

    # Create JSON data with test session ID for comprehensive cleanup
    test_marker = f"test-session-{test_session_id}" if test_session_id else "test-data"
    new_data = f'{{"title": "Test {record_type}", "test_marker": "{test_marker}"}}'
    old_data = (
        f'{{"title": "Old Test {record_type}", "test_marker": "{test_marker}"}}'
        if event_type == "update"
        else None
    )

    engine = get_current_engine()
    if engine is None:
        # If no engine available, skip insertion (this can happen in full test suite context)
        return
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO change_events
            (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
            VALUES (:event_type, :record_type, :record_id, :old_data, :new_data, :ts, :processed)
        """),
            {
                "event_type": event_type,
                "record_type": record_type,
                "record_id": record_id,
                "old_data": old_data,
                "new_data": new_data,
                "ts": ts,
                "processed": processed,
            },
        )
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
    if engine is None:
        # If no engine available, return 0 (this can happen in full test suite context)
        return 0
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return result.scalar()


def cleanup_events(test_session_id=None):
    """Clean up test events comprehensively"""
    engine = get_current_engine()
    if engine is None:
        # If no engine available, skip cleanup (this can happen in full test suite context)
        return
    with engine.connect() as conn:
        # Check if table exists first
        table_check = conn.execute(text("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='change_events'
        """)).fetchone()

        if table_check:
            if test_session_id:
                # Clean up events for specific test session
                conn.execute(
                    text("""
                    DELETE FROM change_events
                    WHERE (record_id LIKE :session_pattern
                           OR new_data LIKE :json_pattern
                           OR old_data LIKE :json_pattern)
                """),
                    {
                        "session_pattern": f"{test_session_id}-%",
                        "json_pattern": f"%test-session-{test_session_id}%",
                    },
                )
            else:
                # Clean up all test events (fallback)
                conn.execute(text("""
                    DELETE FROM change_events
                    WHERE (record_id LIKE 'test-%'
                           OR new_data LIKE '%test-%'
                           OR old_data LIKE '%test-%'
                           OR new_data LIKE '%test-session-%'
                           OR old_data LIKE '%test-session-%')
                """))
            conn.commit()


@pytest.fixture(autouse=True)
def test_session_isolation(shared_app, request):
    """Provide test session isolation with unique ID and comprehensive cleanup"""
    app, engine, session_local = shared_app

    # Ensure current engine is set for database operations
    from database.utils import set_current_engine_for_testing

    set_current_engine_for_testing(engine, session_local)

    # Generate unique test session ID
    test_session_id = f"session-{str(uuid.uuid4())[:8]}"

    # Store in test node for access by test functions
    request.node.test_session_id = test_session_id

    # Clean up any existing test data before test
    cleanup_events()

    # CRITICAL: Stop any existing event processor from the shared app to prevent conflicts
    if hasattr(app.state, "event_processor") and app.state.event_processor:
        try:
            app.state.event_processor.stop()
            print(
                f"[ISOLATION] Stopped shared app event processor for test {request.node.name}"
            )
        except Exception as e:
            print(
                f"[ISOLATION] Warning: Could not stop shared app event processor: {e}"
            )

    yield test_session_id

    # Clean up this test session's data after test
    cleanup_events(test_session_id)

    # Final cleanup to ensure no residual data
    cleanup_events()


def test_event_processor_processes_events(shared_app, test_session_isolation, request):
    """Test that EventProcessor processes events for all record types."""
    test_session_id = request.node.test_session_id

    # Insert unprocessed events for each record type with unique test session ID
    for record_type in ["structure_node", "structure_node_link", "predicate"]:
        insert_event_via_sqlalchemy(
            "create", record_type, test_session_id=test_session_id
        )

    print("[TEST] Starting test_event_processor_processes_events")

    # Get the database URL from the current engine
    from database.utils import get_current_engine

    engine = get_current_engine()
    database_url = str(engine.url)

    # Create isolated EventProcessor with unique connection
    processor = EventProcessor(
        database_url=database_url,
        poll_interval=0.01,
        max_events=10,  # Faster polling for tests
    )
    try:
        processor.start()
        print(f"[TEST] EventProcessor started for session {test_session_id}")

        # Wait for processing with deterministic check instead of fixed sleep
        max_wait_time = 2.0  # Maximum wait time in seconds
        check_interval = 0.05  # Check every 50ms
        waited = 0

        while waited < max_wait_time:
            unprocessed = get_event_count_via_sqlalchemy(processed=0)
            if unprocessed == 0:
                print(f"[TEST] All events processed after {waited:.2f}s")
                break
            time.sleep(check_interval)
            waited += check_interval

        if waited >= max_wait_time:
            print(
                f"[TEST] Timeout after {max_wait_time}s, some events may be unprocessed"
            )

    finally:
        try:
            processor.stop()
            print(f"[TEST] EventProcessor stopped for session {test_session_id}")
        except Exception as e:
            print(f"[TEST] Warning: Error stopping EventProcessor: {e}")

        # Give a moment for cleanup
        time.sleep(0.01)

    # All events should be marked processed
    unprocessed_count = get_event_count_via_sqlalchemy(processed=0)
    assert unprocessed_count == 0


def test_event_processor_handles_all_record_types(
    shared_app, test_session_isolation, request
):
    """Test that EventProcessor handles structure_node, structure_node_link, and predicate events."""
    test_session_id = request.node.test_session_id
    print("[TEST] Starting test_event_processor_handles_all_record_types")

    # Insert events for all record types with unique test session ID
    for record_type in ["structure_node", "structure_node_link", "predicate"]:
        insert_event_via_sqlalchemy(
            "create", record_type, test_session_id=test_session_id
        )

    # Get the database URL from the current engine
    from database.utils import get_current_engine

    engine = get_current_engine()
    database_url = str(engine.url)

    processor = EventProcessor(
        database_url=database_url,
        poll_interval=0.01,
        max_events=10,  # Faster polling for tests
    )

    # Capture logs to verify handlers are called
    import io
    import logging

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        processor.start()
        print("[TEST] EventProcessor started")

        # Wait for processing with deterministic check
        max_wait_time = 2.0
        check_interval = 0.05
        waited = 0

        while waited < max_wait_time:
            unprocessed = get_event_count_via_sqlalchemy(processed=0)
            if unprocessed == 0:
                print(f"[TEST] All events processed after {waited:.2f}s")
                break
            time.sleep(check_interval)
            waited += check_interval

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


def test_event_processor_cleanup_old_events(
    shared_app, test_session_isolation, request, capsys
):
    """Test cleanup of old processed events."""
    test_session_id = request.node.test_session_id

    # Get initial processed event count
    initial_processed_count = get_event_count_via_sqlalchemy(processed=1)

    # Insert processed event older than 48h (timezone-aware)
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    insert_event_via_sqlalchemy(
        "delete",
        "structure_node",
        processed=1,
        ts=old_ts,
        test_session_id=test_session_id,
    )
    # Insert recent processed event
    insert_event_via_sqlalchemy(
        "delete", "structure_node", processed=1, test_session_id=test_session_id
    )

    print("[TEST] Starting test_event_processor_cleanup_old_events")

    # Verify we added 2 events
    pre_cleanup_count = get_event_count_via_sqlalchemy(processed=1)
    assert (
        pre_cleanup_count == initial_processed_count + 2
    ), f"Expected {initial_processed_count + 2} events, got {pre_cleanup_count}"

    # Get the database URL from the current engine
    from database.utils import get_current_engine

    engine = get_current_engine()
    database_url = str(engine.url)

    processor = EventProcessor(
        database_url=database_url, poll_interval=0.05, max_events=10
    )
    try:
        # Call cleanup directly (don't wait a day)
        processor.cleanup_old_events()
        print("[TEST] Called cleanup_old_events, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")

    # Only the recent event (plus any pre-existing events) should remain
    processed_count = get_event_count_via_sqlalchemy(processed=1)
    assert (
        processed_count == initial_processed_count + 1
    ), f"Expected {initial_processed_count + 1} events after cleanup, got {processed_count}"


def test_predicate_event_processing(shared_app, test_session_isolation, request):
    """Test processing of predicate-specific events."""
    test_session_id = request.node.test_session_id
    print("[TEST] Starting test_predicate_event_processing")

    # Insert predicate events with unique test session IDs
    insert_event_via_sqlalchemy(
        "create",
        "predicate",
        record_id=f"test-predicate-123-{str(uuid.uuid4())[:8]}",
        test_session_id=test_session_id,
    )
    insert_event_via_sqlalchemy(
        "update",
        "predicate",
        record_id=f"test-predicate-456-{str(uuid.uuid4())[:8]}",
        test_session_id=test_session_id,
    )
    insert_event_via_sqlalchemy(
        "delete",
        "predicate",
        record_id=f"test-predicate-789-{str(uuid.uuid4())[:8]}",
        test_session_id=test_session_id,
    )

    # Get the database URL from the current engine
    from database.utils import get_current_engine

    engine = get_current_engine()
    database_url = str(engine.url)

    processor = EventProcessor(
        database_url=database_url,
        poll_interval=0.01,
        max_events=10,  # Faster polling for tests
    )

    # Capture logs to verify predicate handler is called
    import io
    import logging

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        processor.start()
        print("[TEST] EventProcessor started")

        # Wait for processing with deterministic check
        max_wait_time = 2.0
        check_interval = 0.05
        waited = 0

        while waited < max_wait_time:
            unprocessed = get_event_count_via_sqlalchemy(processed=0)
            if unprocessed == 0:
                print(f"[TEST] All events processed after {waited:.2f}s")
                break
            time.sleep(check_interval)
            waited += check_interval

    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")
        logger.removeHandler(handler)

    # Verify that predicate events were processed
    log_contents = log_stream.getvalue()
    assert (
        log_contents.count("Processing predicate event") == 3
    )  # create, update, delete

    # All events should be marked processed
    unprocessed_count = get_event_count_via_sqlalchemy(processed=0)
    assert unprocessed_count == 0


def test_event_processor_thread_start_stop_idempotent(
    shared_app, test_session_isolation
):
    print("[TEST] Starting test_event_processor_thread_start_stop_idempotent")

    # Get the database URL from the current engine
    from database.utils import get_current_engine

    engine = get_current_engine()
    database_url = str(engine.url)

    processor = EventProcessor(
        database_url=database_url,
        poll_interval=0.01,
        max_events=10,  # Faster polling for tests
    )
    try:
        processor.start()
        print("[TEST] EventProcessor started (1)")
        processor.start()  # Should not start a second thread
        print("[TEST] EventProcessor started (2)")

        # Brief deterministic wait instead of fixed sleep
        time.sleep(0.1)
        print("[TEST] Waited 0.1s, stopping EventProcessor")
    finally:
        processor.stop()
        processor.stop()  # Should not error
        print("[TEST] EventProcessor stopped")
