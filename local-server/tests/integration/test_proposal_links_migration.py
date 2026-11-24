"""
Integration test for migration e4806276757a (#1624): proposal_links and proposal_operations.amended_at, amendments,
against a real file-based SQLite database migrated with Alembic.
"""

import sqlite3
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = str(Path(__file__).parent / "../../adapters/persistence/sqlite/alembic.ini")
REVISION = "e4806276757a"
PREVIOUS_REVISION = "7d858e111738"


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: str, table: str) -> dict[str, tuple[str, int, str]]:
    """{name: (type, notnull, default)} of the table's columns."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1]: (row[2], row[3], row[4]) for row in rows}


def _tables(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_upgrade_adds_links_and_amendments_and_downgrade_drops_them(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    assert "proposal_links" not in _tables(db)

    upgrade(config, REVISION)
    assert {"id", "source_proposal_id", "kind", "target_proposal_id", "created_at", "note"} == set(
        _columns(db, "proposal_links")
    )
    columns = _columns(db, "proposal_operations")
    assert columns["amended_at"][1] == 0
    assert columns["amendments"] == ("JSON", 1, "'[]'")

    downgrade(config, PREVIOUS_REVISION)
    assert "proposal_links" not in _tables(db)
    assert "amendments" not in _columns(db, "proposal_operations")
