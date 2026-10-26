"""
Integration tests for migration 8de28edb4953 (#1353): change-proposal tables
and dropping the batch_runs run_type CHECK, against real file-based SQLite
databases migrated with Alembic.
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

from alembic.command import downgrade, upgrade
from alembic.config import Config

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "../../adapters/persistence/sqlite/alembic.ini"
)
REVISION = "8de28edb4953"
PREVIOUS_REVISION = "ae41ea8d5adc"


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _ddl(db_path: str, table: str) -> str | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    return row[0] if row else None


def _insert_run(conn: sqlite3.Connection, run_id: str, run_type: str) -> None:
    conn.execute(
        "INSERT INTO batch_runs (id, created_at, status, affected_entity_ids, run_type) "
        "VALUES (?, ?, 'open', '[]', ?)",
        (run_id, datetime.now(timezone.utc).isoformat(), run_type),
    )


def test_upgrade_drops_the_check_and_adds_the_proposal_tables(tmp_path):
    db = str(tmp_path / "local.db")
    upgrade(_config(db), PREVIOUS_REVISION)
    with sqlite3.connect(db) as conn:
        _insert_run(conn, "import-run", "import")

    upgrade(_config(db), REVISION)

    assert "check_valid_run_type" not in _ddl(db, "batch_runs")
    assert "fk_batch_runs_batch_id" in _ddl(db, "batch_runs")
    assert _ddl(db, "change_proposals") and _ddl(db, "proposal_operations")
    with sqlite3.connect(db) as conn:
        _insert_run(conn, "p1", "proposal")
        conn.execute(
            "INSERT INTO change_proposals (id, taxonomy_id, title, source) "
            "VALUES ('p1', 't1', 'T', 'mcp')"
        )
        assert conn.execute("SELECT COUNT(*) FROM batch_runs").fetchone()[0] == 2


def test_downgrade_removes_proposals_and_restores_the_check(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, REVISION)
    with sqlite3.connect(db) as conn:
        _insert_run(conn, "import-run", "import")
        _insert_run(conn, "p1", "proposal")

    downgrade(config, PREVIOUS_REVISION)

    assert "CONSTRAINT check_valid_run_type CHECK" in _ddl(db, "batch_runs")
    assert _ddl(db, "change_proposals") is None
    with sqlite3.connect(db) as conn:
        runs = [r[0] for r in conn.execute("SELECT id FROM batch_runs")]
    assert runs == ["import-run"]

    upgrade(config, REVISION)
    assert "check_valid_run_type" not in _ddl(db, "batch_runs")
