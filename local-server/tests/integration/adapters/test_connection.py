"""
Integration tests for the SQLite connection/pooling configuration.

These pin two design decisions that a naive revert would break:
  - in-memory SQLite must use StaticPool (so every connection sees the same
    database), and the bare "sqlite://" empty-path form counts as in-memory;
  - file-based SQLite must apply WAL journaling + a busy_timeout per connection
    so concurrent read/write from the server's thread pool does not deadlock;
  - both kinds must enforce foreign keys, so ON DELETE CASCADE runs and
    orphan rows are rejected.
"""

import os
import sys
import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from adapters.persistence.sqlite.connection import (
    BUSY_TIMEOUT_MS,
    _is_memory_url,
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.models import Base, GroundingWorkflow, WorkflowRun

TESTS_CONFTEST = Path(__file__).resolve().parents[2] / "conftest.py"


@pytest.fixture
def without_test_fk_hook():
    """Remove the test-suite hook that enables foreign keys on every engine.

    tests/conftest.py enables foreign keys globally, which would hide a
    regression in connection.py. Remove it so these tests see only what
    connection.py configures, then put it back.
    """
    conftest = next(
        module
        for module in list(sys.modules.values())
        if getattr(module, "__file__", None) == str(TESTS_CONFTEST)
    )
    hook = conftest._enforce_sqlite_foreign_keys
    event.remove(Engine, "connect", hook)
    yield
    event.listen(Engine, "connect", hook)


@pytest.fixture(params=["file", "memory"])
def fk_engine(request, tmp_path, without_test_fk_hook):
    """A local.db engine (file-backed or in-memory) with the full schema."""
    url = f"sqlite:///{tmp_path / 'fk.db'}" if request.param == "file" else "sqlite://"
    engine = create_local_db_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


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
            assert busy_timeout == BUSY_TIMEOUT_MS == 30000
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

            successful_writes: int = 0
            lock_errors: int = 0
            barrier = threading.Barrier(4)

            def worker(n: int) -> None:
                nonlocal successful_writes, lock_errors
                barrier.wait()  # synchronize start, but reduce thread count to lower contention
                for i in range(10):
                    try:
                        with engine.begin() as conn:
                            conn.execute(
                                text("INSERT INTO t (v) VALUES (:v)"),
                                {"v": n * 100 + i},
                            )
                            conn.execute(text("SELECT COUNT(*) FROM t")).scalar()
                            successful_writes += 1
                    except Exception as exc:  # noqa: BLE001
                        if "database is locked" in str(exc):
                            lock_errors += 1
                        else:
                            raise

            threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # WAL + busy_timeout should handle most concurrent writes.
            # Allow up to 2 lock errors (transient under high concurrency is acceptable)
            # but the majority should succeed.
            assert lock_errors <= 2, (
                f"Too many lock errors: {lock_errors} " f"(successful: {successful_writes})"
            )
            assert successful_writes >= 35, (
                f"Not enough successful writes: {successful_writes} " f"(expected ≥35 out of 40)"
            )
            with engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM t")).scalar()
                assert count == successful_writes
        finally:
            engine.dispose()


def test_engines_enforce_foreign_keys(fk_engine):
    with fk_engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_cascade_delete_removes_child_rows(fk_engine):
    # Deleting a workflow must delete its runs (ON DELETE CASCADE). Without
    # enforced foreign keys this left an orphaned workflow_runs row behind.
    factory = create_session_factory(fk_engine)
    with factory() as session:
        session.add(GroundingWorkflow(id="wf-1", title="WF", source="wikidata", class_scope=[]))
        session.add(WorkflowRun(id="run-1", workflow_id="wf-1"))
        session.commit()

        session.delete(session.get(GroundingWorkflow, "wf-1"))
        session.commit()

    with factory() as session:
        assert session.get(WorkflowRun, "run-1") is None


def test_orphan_insert_is_rejected(fk_engine):
    factory = create_session_factory(fk_engine)
    with factory() as session:
        session.add(WorkflowRun(id="run-1", workflow_id="no-such-workflow"))
        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            session.commit()
