"""Integration tests for the SQLite transaction scope (persistence/sqlite/transaction.py)."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import threading
import time

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.transaction import (
    SharedSessionFactory,
    SqliteTransactionScope,
    TransactionAbortedError,
)
from domain.ontology.entities import Taxonomy


@pytest.fixture()
def parts(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    shared = SharedSessionFactory(sessionmaker(bind=engine))
    yield SQLiteOntologyRepository(session_factory=shared), shared, SqliteTransactionScope(shared)
    engine.dispose()


def taxonomy(n: int) -> Taxonomy:
    return Taxonomy(id=f"t{n}", title=f"T{n}", identifier=f"tax_{n}")


def test_writes_in_a_scope_commit_together(parts):
    repo, _, scope = parts
    with scope.atomic():
        repo.save_taxonomy(taxonomy(1))
        with scope.atomic():  # nested: joins
            repo.save_taxonomy(taxonomy(2))
        assert repo.get_taxonomy("t1") is not None  # visible inside the scope
    assert repo.get_taxonomy("t1") is not None and repo.get_taxonomy("t2") is not None


def test_an_exception_rolls_every_write_back(parts):
    repo, _, scope = parts
    with pytest.raises(RuntimeError):
        with scope.atomic():
            repo.save_taxonomy(taxonomy(1))
            raise RuntimeError("boom")
    assert repo.get_taxonomy("t1") is None


def test_a_rollback_inside_the_scope_refuses_to_commit_even_if_caught(parts):
    """A repository's own rollback ends the scope's transaction; carrying on keeps nothing."""
    repo, shared, scope = parts
    with pytest.raises(TransactionAbortedError):
        with scope.atomic():
            repo.save_taxonomy(taxonomy(1))
            with shared() as session:
                session.rollback()  # what a repository does on an IntegrityError
            repo.save_taxonomy(taxonomy(2))
    assert repo.get_taxonomy("t1") is None
    assert repo.get_taxonomy("t2") is None


@pytest.mark.slow
def test_a_writer_waits_through_a_scope_held_longer_than_five_seconds(parts):
    """Another thread's write waits for the scope's lock (busy_timeout) and then succeeds."""
    repo, shared, scope = parts
    other_repo = SQLiteOntologyRepository(session_factory=sessionmaker(bind=shared.kw["bind"]))
    lock_held = threading.Event()
    outcome: dict = {}

    def write() -> None:
        lock_held.wait()
        started = time.monotonic()
        try:
            other_repo.save_taxonomy(taxonomy(2))
            outcome["ok"] = True
        except Exception as exc:  # noqa: BLE001 - reported by the assertion below
            outcome["error"] = exc
        outcome["waited"] = time.monotonic() - started

    writer = threading.Thread(target=write)
    writer.start()
    with scope.atomic():
        repo.save_taxonomy(taxonomy(1))
        lock_held.set()
        time.sleep(6)
    writer.join(timeout=60)

    assert outcome.get("ok"), outcome
    assert outcome["waited"] >= 5
    assert repo.get_taxonomy("t1") is not None and repo.get_taxonomy("t2") is not None
