import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import os
import sqlite3
import time
import tempfile
import pytest
from utils.event_processor import EventProcessor
from datetime import datetime, timedelta, timezone

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
    """)
    conn.commit()
    yield path
    os.remove(path)


def insert_event(conn, event_type, entity_type, processed=0, ts=None):
    cur = conn.cursor()
    # Use timezone-aware UTC datetime
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    cur.execute(
        "INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed) VALUES (?, ?, ?, ?, ?, ?)",
        (event_type, entity_type, '{}', '{}', ts, processed)
    )
    conn.commit()


def test_event_processor_processes_events(temp_db):
    conn = sqlite3.connect(temp_db)
    # Insert unprocessed events for each entity type
    for entity in ["layer", "domain", "term", "term_relationship"]:
        insert_event(conn, "create", entity)
    conn.close()

    print("[TEST] Starting test_event_processor_processes_events")
    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        processor.start()
        print("[TEST] EventProcessor started")
        time.sleep(0.2)  # Allow processor to run
        print("[TEST] Slept 0.2s, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")

    # All events should be marked processed
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM graph_events WHERE processed=0")
    assert cur.fetchone()[0] == 0
    conn.close()


def test_event_processor_handles_unknown_entity_type(temp_db, capsys):
    conn = sqlite3.connect(temp_db)
    insert_event(conn, "create", "unknown_entity")
    conn.close()

    print("[TEST] Starting test_event_processor_handles_unknown_entity_type")
    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
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

    # Should log a warning about unknown entity_type
    log_contents = log_stream.getvalue()
    assert "No handler for entity_type: unknown_entity" in log_contents


def test_event_processor_cleanup_old_events(temp_db, capsys):
    conn = sqlite3.connect(temp_db)
    # Insert processed event older than 48h (timezone-aware)
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    insert_event(conn, "delete", "layer", processed=1, ts=old_ts)
    # Insert recent processed event
    insert_event(conn, "delete", "layer", processed=1)
    conn.close()

    print("[TEST] Starting test_event_processor_cleanup_old_events")
    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
    try:
        # Call cleanup directly (don't wait a day)
        processor.cleanup_old_events()
        print("[TEST] Called cleanup_old_events, stopping EventProcessor")
    finally:
        processor.stop()
        print("[TEST] EventProcessor stopped")
    # Only the recent event should remain
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM graph_events WHERE processed=1")
    count = cur.fetchone()[0]
    assert count == 1
    conn.close()


def test_event_processor_thread_start_stop_idempotent(temp_db):
    print("[TEST] Starting test_event_processor_thread_start_stop_idempotent")
    processor = EventProcessor(temp_db, poll_interval=0.05, max_events=10)
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
