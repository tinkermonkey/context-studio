import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
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
    cur.execute(
        """
        CREATE TABLE change_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            record_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            old_data TEXT,
            new_data TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0
        );
    """
    )
    conn.commit()
    # Return SQLAlchemy URL format instead of file path
    yield f"sqlite:///{path}"
    os.remove(path)


def insert_event(db_url, record_type, event_type, processed=0, ts=None, record_id=None):
    from datetime import timezone
    import sqlite3

    # Extract file path from SQLAlchemy URL
    file_path = db_url.replace("sqlite:///", "")
    conn = sqlite3.connect(file_path)
    cur = conn.cursor()
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    if record_id is None:
        record_id = f"test-{record_type}-id"
    cur.execute(
        "INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_type, record_type, record_id, "{}", "{}", ts, processed),
    )
    conn.commit()
    conn.close()


def test_integration_event_processor_end_to_end(temp_db, capsys):
    # Insert a mix of events
    insert_event(temp_db, "structure_node", "create")
    insert_event(temp_db, "structure_node", "update")
    insert_event(temp_db, "structure_node", "delete")
    insert_event(temp_db, "structure_node_link", "create")
    insert_event(temp_db, "unknown_record_type", "create")  # negative case

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

        # Poll until all events are processed or timeout
        file_path = temp_db.replace("sqlite:///", "")
        timeout = time.time() + 2.0  # 2 second timeout
        while time.time() < timeout:
            conn = sqlite3.connect(file_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM change_events WHERE processed=0")
            unprocessed = cur.fetchone()[0]
            conn.close()

            if unprocessed == 0:
                break
            time.sleep(0.05)
    finally:
        processor.stop()
        logger.removeHandler(handler)

    # All events should be marked processed
    file_path = temp_db.replace("sqlite:///", "")
    conn = sqlite3.connect(file_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM change_events WHERE processed=0")
    assert cur.fetchone()[0] == 0
    conn.close()

    # Check logs for correct handler calls and unknown entity warning
    log_contents = log_stream.getvalue()
    assert "Processing structure_node event: create" in log_contents
    assert "Processing structure_node event: update" in log_contents
    assert "Processing structure_node event: delete" in log_contents
    assert "Processing structure_node_link event: create" in log_contents
    assert "[EventProcessor] Event 5 has invalid record_type 'unknown_record_type'. Valid types: ['structure_node', 'structure_node_link', 'predicate']. This event will be skipped." in log_contents


def test_integration_event_processor_cleanup(temp_db, capsys):
    # Insert processed events, one old, one recent
    from datetime import timezone

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    insert_event(temp_db, "structure_nodes", "delete", processed=1, ts=old_ts)
    insert_event(temp_db, "structure_nodes", "update", processed=1)

    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        processor.cleanup_old_events()
    finally:
        processor.stop()

    # Only the recent event should remain
    file_path = temp_db.replace("sqlite:///", "")
    conn = sqlite3.connect(file_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM change_events WHERE processed=1")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_integration_event_processor_large_batch(temp_db, capsys):
    # Insert many events
    record_types = ["structure_node", "structure_node_link", "predicate"]
    for i in range(50):
        record_type = record_types[i % len(record_types)]
        insert_event(
            temp_db, record_type, "create", record_id=f"test-{record_type}-{i}"
        )

    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        processor.start()

        # Poll until all events are processed or timeout
        file_path = temp_db.replace("sqlite:///", "")
        timeout = time.time() + 5.0  # 5 second timeout
        while time.time() < timeout:
            conn = sqlite3.connect(file_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM change_events WHERE processed=0")
            unprocessed = cur.fetchone()[0]
            conn.close()

            if unprocessed == 0:
                break
            time.sleep(0.05)
    finally:
        processor.stop()

    # All events should be processed
    file_path = temp_db.replace("sqlite:///", "")
    conn = sqlite3.connect(file_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM change_events WHERE processed=0")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM change_events WHERE processed=1")
    assert cur.fetchone()[0] == 50
    conn.close()
