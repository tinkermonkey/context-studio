"""Insert the parent rows that foreign keys require in integration tests.

Foreign keys are enforced, so a pipeline run needs its ``batches`` row and a
change event tagged with a run needs its ``batch_runs`` row. These helpers
create those parents with a chosen id, so tests that assert on a literal id
keep working.
"""

from datetime import datetime, timezone
from typing import Callable, Optional, Union
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.persistence.sqlite.models import Batch

SessionSource = Union[Callable[[], Session], Session]


def create_batch_row(session_source: SessionSource, batch_id: Optional[str] = None) -> str:
    """Insert a pending ``batches`` row and return its id.

    Args:
        session_source: A session factory, or a Session the caller owns.
        batch_id: Id to use; a new UUID when omitted.
    """
    batch_id = batch_id or str(uuid4())
    now = datetime.now(timezone.utc)
    owns_session = callable(session_source)
    session = session_source() if owns_session else session_source
    try:
        session.add(Batch(id=batch_id, status="pending", created_at=now, last_updated=now))
        session.commit()
    finally:
        if owns_session:
            session.close()
    return batch_id


def create_batch_run_row(session_source: SessionSource, run_id: Optional[str] = None) -> str:
    """Insert a bare ``batch_runs`` row and return its id.

    For tests that record change events tagged with a run id but do not care
    about the run itself. ``change_events.batch_run_id`` references
    ``batch_runs.id``.

    Args:
        session_source: A session factory, or a Session the caller owns.
        run_id: Id to use; a new UUID when omitted.
    """
    run_id = run_id or str(uuid4())
    owns_session = callable(session_source)
    session = session_source() if owns_session else session_source
    try:
        session.execute(
            text(
                "INSERT INTO batch_runs (id, created_at, status, affected_entity_ids, run_type) "
                "VALUES (:id, :created_at, 'completed', '[]', 'import')"
            ),
            {"id": run_id, "created_at": datetime.now(timezone.utc)},
        )
        session.commit()
    finally:
        if owns_session:
            session.close()
    return run_id
