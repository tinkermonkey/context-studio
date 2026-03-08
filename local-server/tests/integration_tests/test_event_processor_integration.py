import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: E501
)
import sqlite3  # noqa: E402
import time  # noqa: E402
import tempfile  # noqa: E402
import pytest  # noqa: E402
from utils.event_processor import EventProcessor  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from sqlalchemy import text  # noqa: E402
from database.utils import get_database_manager  # noqa: E402


@pytest.fixture
def temp_db():
    from database.utils import get_database_manager

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
    conn.close()

    # Return SQLAlchemy URL format and generate a unique engine_id for this test
    db_url = f"sqlite:///{path}"
    engine_id = f"test_db_{id(path)}"

    # Clear any old engines from DatabaseManager for this engine_id
    db_manager = get_database_manager()
    if engine_id in db_manager._engines:
        try:
            db_manager._engines[engine_id].dispose()
        except Exception:
            pass
        del db_manager._engines[engine_id]
        if engine_id in db_manager._session_locals:
            del db_manager._session_locals[engine_id]

    yield {"url": db_url, "engine_id": engine_id}

    # Cleanup
    try:
        if engine_id in db_manager._engines:
            db_manager._engines[engine_id].dispose()
            del db_manager._engines[engine_id]
        if engine_id in db_manager._session_locals:
            del db_manager._session_locals[engine_id]
    except Exception:
        pass

    try:
        os.remove(path)
    except Exception:
        pass


def insert_event(db_url, engine_id, record_type, event_type, processed=0, ts=None, record_id=None):  # noqa: E501
    from datetime import timezone

    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    if record_id is None:
        record_id = f"test-{record_type}-id"

    # Use DatabaseManager with SQLAlchemy for consistent connection handling
    db_manager = get_database_manager()

    with db_manager.get_session(engine_id, db_url) as db:
        db.execute(
            text(
                "INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed) VALUES (:event_type, :record_type, :record_id, :old_data, :new_data, :timestamp, :processed)"  # noqa: E501
            ),
            {
                "event_type": event_type,
                "record_type": record_type,
                "record_id": record_id,
                "old_data": "{}",
                "new_data": "{}",
                "timestamp": ts,
                "processed": processed,
            },
        )


def test_integration_event_processor_end_to_end(temp_db, capsys):
    # Insert a mix of events
    db_url = temp_db["url"]
    engine_id = temp_db["engine_id"]

    insert_event(db_url, engine_id, "structure_node", "create")
    insert_event(db_url, engine_id, "structure_node", "update")
    insert_event(db_url, engine_id, "structure_node", "delete")
    insert_event(db_url, engine_id, "structure_node_link", "create")
    insert_event(db_url, engine_id, "unknown_record_type", "create")  # negative case

    import logging
    import io

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("utils.event_processor")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    db_manager = get_database_manager()

    try:
        processor = EventProcessor(db_url, poll_interval=0.05, max_events=10)
        processor.start()

        # Poll until all events are processed or timeout
        timeout = time.time() + 2.0  # 2 second timeout
        while time.time() < timeout:
            with db_manager.get_session(engine_id, db_url) as db:
                result = db.execute(
                    text("SELECT COUNT(*) FROM change_events WHERE processed=0")
                ).fetchone()
                unprocessed = result[0] if result else 0

            if unprocessed == 0:
                break
            time.sleep(0.05)
    finally:
        processor.stop()
        logger.removeHandler(handler)

    # All events should be marked processed
    with db_manager.get_session(engine_id, db_url) as db:
        result = db.execute(
            text("SELECT COUNT(*) FROM change_events WHERE processed=0")
        ).fetchone()
        assert (result[0] if result else 0) == 0

    # Check logs for correct handler calls and unknown entity warning
    log_contents = log_stream.getvalue()
    assert "Processing structure_node event: create" in log_contents
    assert "Processing structure_node event: update" in log_contents
    assert "Processing structure_node event: delete" in log_contents
    assert "Processing structure_node_link event: create" in log_contents
    assert "[EventProcessor] Event 5 has invalid record_type 'unknown_record_type'. Valid types: ['structure_node', 'structure_node_link', 'predicate']. This event will be skipped." in log_contents  # noqa: E501


def test_integration_event_processor_cleanup(temp_db, capsys):
    # Insert processed events, one old, one recent
    from datetime import timezone

    db_url = temp_db["url"]
    engine_id = temp_db["engine_id"]

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    insert_event(db_url, engine_id, "structure_nodes", "delete", processed=1, ts=old_ts)
    insert_event(db_url, engine_id, "structure_nodes", "update", processed=1)

    db_manager = get_database_manager()

    processor = EventProcessor(db_url, poll_interval=0.05, max_events=10)
    try:
        processor.cleanup_old_events()
    finally:
        processor.stop()

    # Only the recent event should remain
    with db_manager.get_session(engine_id, db_url) as db:
        result = db.execute(
            text("SELECT COUNT(*) FROM change_events WHERE processed=1")
        ).fetchone()
        assert (result[0] if result else 0) == 1


def test_integration_event_processor_large_batch(temp_db, capsys):
    # Insert many events
    db_url = temp_db["url"]
    engine_id = temp_db["engine_id"]

    record_types = ["structure_node", "structure_node_link", "predicate"]
    for i in range(50):
        record_type = record_types[i % len(record_types)]
        insert_event(
            db_url, engine_id, record_type, "create", record_id=f"test-{record_type}-{i}"
        )

    db_manager = get_database_manager()

    processor = EventProcessor(db_url, poll_interval=0.05, max_events=10)
    try:
        processor.start()

        # Poll until all events are processed or timeout
        timeout = time.time() + 5.0  # 5 second timeout
        while time.time() < timeout:
            with db_manager.get_session(engine_id, db_url) as db:
                result = db.execute(
                    text("SELECT COUNT(*) FROM change_events WHERE processed=0")
                ).fetchone()
                unprocessed = result[0] if result else 0

            if unprocessed == 0:
                break
            time.sleep(0.05)
    finally:
        processor.stop()

    # All events should be processed
    with db_manager.get_session(engine_id, db_url) as db:
        result = db.execute(
            text("SELECT COUNT(*) FROM change_events WHERE processed=0")
        ).fetchone()
        assert (result[0] if result else 0) == 0
        result = db.execute(
            text("SELECT COUNT(*) FROM change_events WHERE processed=1")
        ).fetchone()
        assert (result[0] if result else 0) == 50
