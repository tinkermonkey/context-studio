"""
One SQLite transaction across repository calls (TransactionScope port).

Repositories open a session per method (`with self.session_factory() as
session: ... session.commit()`). Built on a `SharedSessionFactory`, they keep
doing so outside a scope; inside `atomic()` every session they open is the
scope's one session, their commits only flush, and the scope commits once at
the end or rolls everything back if the block raises. No repository method
changes.

The scope starts with BEGIN IMMEDIATE, so its reads and writes see one
consistent database and it holds the write lock from the start (other writers
wait up to busy_timeout). Use it on file databases: with an in-memory
StaticPool database every session shares one connection, so a session outside
the scope that commits would commit the scope's work too.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from sqlalchemy.orm import Session, sessionmaker


class _JoinedSession:
    """The scope's session as a repository method sees it: commit flushes, close is a no-op."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> "_JoinedSession":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def close(self) -> None:
        return None

    def commit(self) -> None:
        self._session.flush()
        # Database-level cascades (ON DELETE CASCADE / SET NULL) don't touch the
        # identity map; expire it so later reads in the scope see the database.
        self._session.expire_all()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)


class SharedSessionFactory:
    """
    A sessionmaker that hands out the open scope's session while
    `SqliteTransactionScope.atomic()` runs (in this thread or task), and a new
    session otherwise.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory
        self._current: ContextVar[Session | None] = ContextVar(
            f"shared_session_{id(self)}", default=None
        )

    def __call__(self, **kwargs: Any) -> Any:
        session = self._current.get()
        if session is None:
            return self._factory(**kwargs)
        return _JoinedSession(session)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._factory, name)

    @contextmanager
    def scope(self) -> Iterator[None]:
        if self._current.get() is not None:
            yield  # nested: join the outer scope
            return
        session = self._factory()
        token = self._current.set(session)
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            yield
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            self._current.reset(token)
            session.close()


class SqliteTransactionScope:
    """TransactionScope over the repositories built on one SharedSessionFactory."""

    def __init__(self, factory: SharedSessionFactory) -> None:
        self._factory = factory

    def atomic(self):  # type: ignore[no-untyped-def]
        return self._factory.scope()
