"""
Integration test for migration 7d858e111738 (#1628): change_proposals.review_only,
against a real file-based SQLite database migrated with Alembic.
"""

import sqlite3
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = str(Path(__file__).parent / "../../adapters/persistence/sqlite/alembic.ini")
REVISION = "7d858e111738"
PREVIOUS_REVISION = "effca9e04889"


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: str, table: str) -> dict[str, tuple[str, int, str]]:
    """{name: (type, notnull, default)} of the table's columns."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1]: (row[2], row[3], row[4]) for row in rows}


def test_upgrade_adds_review_only_false_by_default_and_downgrade_drops_it(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    assert "review_only" not in _columns(db, "change_proposals")
    with sqlite3.connect(db) as conn:  # a proposal stored before the column existed
        conn.execute(
            "INSERT INTO batch_runs (id, created_at, status, affected_entity_ids, run_type)"
            " VALUES ('p-old', '2026-11-01 00:00:00', 'open', '[]', 'proposal')"
        )
        conn.execute(
            "INSERT INTO change_proposals (id, taxonomy_id, title, source)"
            " VALUES ('p-old', 'tax-1', 'Before', 'mcp')"
        )

    upgrade(config, REVISION)
    assert _columns(db, "change_proposals")["review_only"] == ("BOOLEAN", 1, "0")
    with sqlite3.connect(db) as conn:
        (review_only,) = conn.execute(
            "SELECT review_only FROM change_proposals WHERE id = 'p-old'"
        ).fetchone()
    assert review_only == 0  # existing proposals are not review-only

    downgrade(config, PREVIOUS_REVISION)
    assert "review_only" not in _columns(db, "change_proposals")
