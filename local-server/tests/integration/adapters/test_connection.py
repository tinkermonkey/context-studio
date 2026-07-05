"""
Integration tests for the SQLite connection/pooling configuration.

These pin two design decisions that a naive revert would break:
  - in-memory SQLite must use StaticPool (so every connection sees the same
    database), and the bare "sqlite://" empty-path form counts as in-memory;
  - file-based SQLite must apply WAL journaling + a busy_timeout per connection
    so concurrent read/write from the server's thread pool does not deadlock.
"""

import os
import sys
import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from adapters.persistence.sqlite.connection import (
    _is_memory_url,
    create_local_db_engine,
    create_session_factory,
)


@pytest.mark.parametrize(
    "url, expected",
    [
        ("sqlite:///:memory:", True),
        (":memory:", True),
        ("sqlite://", True),
        ("sqlite:///", True),
        ("sqlite:///file:foo?mode=memory&cache=shared&uri=true", True),
        ("sqlite:///./local.db", False),
        ("sqlite:////tmp/some/real/path.db", False),
    ],
)
def test_is_memory_url(url, expected):
    assert _is_memory_url(url) is expected


def test_file_engine_enables_wal_and_busy_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        url = f"sqlite:///{Path(tmpdir) / 'file.db'}"
        engine = create_local_db_engine(url)
        try:
            with engine.connect() as conn:
                journal_mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
                busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
            assert journal_mode.lower() == "wal"
            assert busy_timeout == 5000
        finally:
            engine.dispose()


def test_in_memory_engine_shares_database_across_sessions():
    # Bare empty-path form must route to StaticPool; a second session must see
    # data written by the first (would fail under QueuePool for :memory:).
    engine = create_local_db_engine("sqlite://")
    try:
        factory = create_session_factory(engine)

        with factory() as writer:
            writer.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
            writer.execute(text("INSERT INTO t (id, v) VALUES (1, 'hello')"))
            writer.commit()

        with factory() as reader:
            value = reader.execute(text("SELECT v FROM t WHERE id = 1")).scalar()
        assert value == "hello"
    finally:
        engine.dispose()


def test_file_engine_handles_concurrent_writes_without_locking():
    with tempfile.TemporaryDirectory() as tmpdir:
        url = f"sqlite:///{Path(tmpdir) / 'concurrent.db'}"
        engine = create_local_db_engine(url)
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER)"))

            errors: list[Exception] = []
            barrier = threading.Barrier(8)

            def worker(n: int) -> None:
                try:
                    barrier.wait()  # maximize overlap
                    for i in range(20):
                        with engine.begin() as conn:
                            conn.execute(
                                text("INSERT INTO t (v) VALUES (:v)"),
                                {"v": n * 100 + i},
                            )
                            conn.execute(text("SELECT COUNT(*) FROM t")).scalar()
                except Exception as exc:  # noqa: BLE001 - collected for assertion
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == [], f"concurrent access raised: {errors!r}"
            with engine.connect() as conn:
                assert conn.execute(text("SELECT COUNT(*) FROM t")).scalar() == 8 * 20
        finally:
            engine.dispose()
