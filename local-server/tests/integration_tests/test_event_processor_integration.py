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
        CREATE TABLE node_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            node_type TEXT NOT NULL,
            node_id TEXT NOT NULL,
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


def insert_event(conn, event_type, node_type, processed=0, ts=None, node_id=None):
    from datetime import datetime, timezone
    cur = conn.cursor()
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    if node_id is None:
        node_id = f"test-{node_type}-id"
    cur.execute(
        "INSERT INTO node_events (event_type, node_type, node_id, old_data, new_data, timestamp, processed) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_type, node_type, node_id, '{}', '{}', ts, processed)
    )
    conn.commit()


def test_integration_event_processor_end_to_end(temp_db, capsys):
    conn = sqlite3.connect(temp_db)
    # Insert a mix of events
    insert_event(conn, "create", "layer")
    insert_event(conn, "update", "domain")
    insert_event(conn, "delete", "term")
    insert_event(conn, "create", "node_link")
    insert_event(conn, "create", "unknown_node_type")  # negative case
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
    cur.execute("SELECT COUNT(*) FROM node_events WHERE processed=0")
    assert cur.fetchone()[0] == 0
    conn.close()

    # Check logs for correct handler calls and unknown entity warning
    log_contents = log_stream.getvalue()
    assert "Processing layer event: create" in log_contents
    assert "Processing domain event: update" in log_contents
    assert "Processing term event: delete" in log_contents
    assert "Processing node_link event: create" in log_contents
    assert "No handler for node_type: unknown_node_type" in log_contents


def test_integration_event_processor_cleanup(temp_db, capsys):
    conn = sqlite3.connect(temp_db)
    # Insert processed events, one old, one recent
    from datetime import datetime, timezone
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    insert_event(conn, "delete", "layer", processed=1, ts=old_ts)
    insert_event(conn, "update", "domain", processed=1)
    conn.close()

    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        processor.cleanup_old_events()
    finally:
        processor.stop()

    # Only the recent event should remain
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM node_events WHERE processed=1")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_integration_event_processor_large_batch(temp_db, capsys):
    conn = sqlite3.connect(temp_db)
    # Insert many events
    node_types = ["layer", "domain", "term", "node_link"]
    for i in range(50):
        node_type = node_types[i % len(node_types)]
        insert_event(conn, "create", node_type, node_id=f"test-{node_type}-{i}")
    conn.close()

    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        processor.start()
        time.sleep(0.5)  # Let it process multiple batches
    finally:
        processor.stop()

    # All events should be processed
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM node_events WHERE processed=0")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM node_events WHERE processed=1")
    assert cur.fetchone()[0] == 50
    conn.close()
