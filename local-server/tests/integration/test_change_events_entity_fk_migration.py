"""
Integration tests for migration a170a80121f2 (drop the stale change_events.entity_id FK).

- A migrated database loses the entity_id -> ontology_entities FK, keeps the
  batch_run_id FK, its rows and the model's indexes
- A database whose change_events never had that FK is left untouched
"""

import os
import sqlite3
import sys

import pytest
from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.persistence.sqlite.models import ChangeEvent  # noqa: E402

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "../../adapters/persistence/sqlite/alembic.ini"
)
REVISION = "a170a80121f2"
PREVIOUS_REVISION = "cfbd1243dcc5"

EXPECTED_INDEXES = {
    "ix_change_events_entity_id",
    "ix_change_events_operation",
    "ix_change_events_timestamp",
    "ix_change_events_changeset_id",
    "ix_change_events_batch_run_id",
    "idx_entity_id_timestamp",
    "idx_processed",
    "idx_batch_run_id",
}


def _alembic_config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _foreign_keys(conn: sqlite3.Connection) -> set[tuple[str, str, str]]:
    """(from column, parent table, on_delete) for each FK on change_events."""
    rows = conn.execute("PRAGMA foreign_key_list(change_events)").fetchall()
    return {(row[3], row[2], row[6]) for row in rows}


def _indexes(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='change_events' "
        "AND name NOT LIKE 'sqlite_autoindex%'"
    ).fetchall()
    return {row[0] for row in rows}


def _insert_event(conn: sqlite3.Connection, event_id: str) -> None:
    conn.execute(
        "INSERT INTO change_events (id, entity_id, entity_type, operation, new_state, "
        "timestamp, processed) VALUES (?, 'not-an-entity', 'relationship', 'create', '{}', "
        "'2026-01-01', 0)",
        (event_id,),
    )


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "local.db")


class TestMigratedDatabase:
    """A database built by migrations carries the stale FK until this revision."""

    def test_upgrade_drops_entity_id_fk_and_keeps_rows(self, db_path):
        config = _alembic_config(db_path)
        upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(db_path) as conn:
            assert ("entity_id", "ontology_entities", "CASCADE") in _foreign_keys(conn)
            _insert_event(conn, "event-1")  # foreign keys are off on this connection

        upgrade(config, REVISION)

        with sqlite3.connect(db_path) as conn:
            assert _foreign_keys(conn) == {("batch_run_id", "batch_runs", "SET NULL")}
            assert _indexes(conn) == EXPECTED_INDEXES
            assert conn.execute("SELECT id FROM change_events").fetchall() == [("event-1",)]
            conn.execute("PRAGMA foreign_keys=ON")
            _insert_event(conn, "event-2")  # entity_id no longer has to be an entity


class TestDatabaseWithoutStaleFk:
    """A change_events table built from the model is left as it is."""

    def test_upgrade_is_a_no_op(self, db_path):
        config = _alembic_config(db_path)
        upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE change_events")
        engine = create_engine(f"sqlite:///{db_path}")
        ChangeEvent.__table__.create(engine)
        engine.dispose()
        with sqlite3.connect(db_path) as conn:
            ddl_before = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='change_events'"
            ).fetchone()[0]

        upgrade(config, REVISION)

        with sqlite3.connect(db_path) as conn:
            ddl_after = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='change_events'"
            ).fetchone()[0]
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
                REVISION
            )
        assert ddl_after == ddl_before
