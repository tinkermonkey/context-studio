"""
Integration tests for migration cfbd1243dcc5 (create grounding_workflows / workflow_runs).

Tests verify, against real file-based SQLite databases migrated with Alembic:
- A fresh database at head has both tables and their indexes
- A database that already has the tables (create_all + stamp) upgrades as a
  no-op with its rows intact
- Downgrade followed by upgrade round-trips
"""

import os
import sqlite3
import sys

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.persistence.sqlite.models import GroundingWorkflow, WorkflowRun  # noqa: E402

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "../../adapters/persistence/sqlite/alembic.ini"
)
REVISION = "cfbd1243dcc5"
PREVIOUS_REVISION = "eae4e30702d2"

EXPECTED_INDEXES = {
    "ix_grounding_workflows_status",
    "ix_grounding_workflows_title",
    "ix_workflow_runs_status",
    "ix_workflow_runs_timestamp",
    "ix_workflow_runs_workflow_id",
}


def _alembic_config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _tables(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def _workflow_indexes(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name IN ('grounding_workflows', 'workflow_runs') "
            "AND name NOT LIKE 'sqlite_autoindex%'"
        ).fetchall()
    return {row[0] for row in rows}


def _insert_workflow_and_run(conn: sqlite3.Connection, workflow_id: str, run_id: str) -> None:
    conn.execute(
        "INSERT INTO grounding_workflows (id, title, source, class_scope, status, "
        "created_at, updated_at) VALUES (?, 'wf', 'dbpedia', '[]', 'inactive', "
        "'2026-01-01', '2026-01-01')",
        (workflow_id,),
    )
    conn.execute(
        "INSERT INTO workflow_runs (id, workflow_id, status, record_count, timestamp) "
        "VALUES (?, ?, 'running', 0, '2026-01-01')",
        (run_id, workflow_id),
    )


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "local.db")


class TestFreshDatabase:
    """A database migrated from scratch gets both workflow tables."""

    def test_tables_and_indexes_created(self, db_path):
        upgrade(_alembic_config(db_path), "head")

        assert {"grounding_workflows", "workflow_runs"} <= _tables(db_path)
        assert _workflow_indexes(db_path) == EXPECTED_INDEXES
        with sqlite3.connect(db_path) as conn:
            _insert_workflow_and_run(conn, "wf-1", "run-1")
            assert conn.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0] == 1
            with pytest.raises(sqlite3.IntegrityError, match="check_valid_run_status"):
                conn.execute(
                    "INSERT INTO workflow_runs (id, workflow_id, status, record_count, "
                    "timestamp) VALUES ('run-2', 'wf-1', 'bogus', 0, '2026-01-01')"
                )

    def test_downgrade_then_upgrade_round_trips(self, db_path):
        config = _alembic_config(db_path)
        upgrade(config, "head")

        downgrade(config, PREVIOUS_REVISION)
        assert not {"grounding_workflows", "workflow_runs"} & _tables(db_path)

        upgrade(config, "head")
        assert {"grounding_workflows", "workflow_runs"} <= _tables(db_path)
        assert _workflow_indexes(db_path) == EXPECTED_INDEXES


class TestPreexistingTables:
    """A create_all-built database that already has the tables upgrades as a no-op."""

    @pytest.fixture
    def preexisting_db(self, db_path):
        """Database at the previous head with the tables created from the models, plus rows."""
        upgrade(_alembic_config(db_path), PREVIOUS_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        GroundingWorkflow.__table__.create(engine)
        WorkflowRun.__table__.create(engine)
        engine.dispose()
        with sqlite3.connect(db_path) as conn:
            _insert_workflow_and_run(conn, "wf-1", "run-1")
        return db_path

    def test_upgrade_preserves_rows(self, preexisting_db):
        upgrade(_alembic_config(preexisting_db), "head")

        with sqlite3.connect(preexisting_db) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
                REVISION
            )
            assert conn.execute("SELECT id FROM grounding_workflows").fetchall() == [("wf-1",)]
            assert conn.execute("SELECT id, workflow_id FROM workflow_runs").fetchall() == [
                ("run-1", "wf-1")
            ]
        assert _workflow_indexes(preexisting_db) == EXPECTED_INDEXES
