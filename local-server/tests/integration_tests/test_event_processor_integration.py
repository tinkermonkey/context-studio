import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import sqlite3
import time
import tempfile
import pytest
from utils.event_processor import EventProcessor
from datetime import datetime, timedelta

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE graph_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            old_data TEXT,
            new_data TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0
        );
    """
    )
    conn.commit()
    yield path
    os.remove(path)


def insert_event(conn, event_type, entity_type, processed=0, ts=None):
    from datetime import datetime, timezone
    cur = conn.cursor()
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    cur.execute(
        "INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed) VALUES (?, ?, ?, ?, ?, ?)",
        (event_type, entity_type, '{}', '{}', ts, processed)
    )
    conn.commit()


def test_integration_event_processor_end_to_end(temp_db, capsys):
    conn = sqlite3.connect(temp_db)
    # Insert a mix of events
    insert_event(conn, "create", "layer")
    insert_event(conn, "update", "domain")
    insert_event(conn, "delete", "term")
    insert_event(conn, "create", "term_relationship")
    insert_event(conn, "create", "unknown_entity")  # negative case
    conn.close()

    import logging
    import io
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
        processor.start()
        time.sleep(0.3)
    finally:
        processor.stop()
        logger.removeHandler(handler)

    # All events should be marked processed
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM graph_events WHERE processed=0")
    assert cur.fetchone()[0] == 0
    conn.close()

    # Check logs for correct handler calls and unknown entity warning
    log_contents = log_stream.getvalue()
    assert "Processing layer event: create" in log_contents
    assert "Processing domain event: update" in log_contents
    assert "Processing term event: delete" in log_contents
    assert "Processing term_relationship event: create" in log_contents
    assert "No handler for entity_type: unknown_entity" in log_contents


def test_integration_event_processor_cleanup(temp_db, capsys):
    conn = sqlite3.connect(temp_db)
    # Insert processed events, one old, one recent
    from datetime import datetime, timezone
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    insert_event(conn, "delete", "layer", processed=1, ts=old_ts)
    insert_event(conn, "delete", "layer", processed=1)
    conn.close()

    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        processor.cleanup_old_events()
    finally:
        processor.stop()
    # Only the recent event should remain
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM graph_events WHERE processed=1")
    count = cur.fetchone()[0]
    assert count == 1
    conn.close()


def test_integration_event_processor_thread_safety(temp_db):
    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        processor.start()
        processor.start()  # Should not start a second thread
        time.sleep(0.1)
    finally:
        processor.stop()
        processor.stop()  # Should not error
