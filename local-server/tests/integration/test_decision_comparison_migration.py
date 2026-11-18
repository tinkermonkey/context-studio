"""
Integration test for migration effca9e04889 (#1615): proposal_decisions.comparison,
against a real file-based SQLite database migrated with Alembic.
"""

import sqlite3
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = str(Path(__file__).parent / "../../adapters/persistence/sqlite/alembic.ini")
REVISION = "effca9e04889"
PREVIOUS_REVISION = "b1e44fd1bc4a"


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: str, table: str) -> dict[str, tuple[str, int]]:
    """{name: (type, notnull)} of the table's columns."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1]: (row[2], row[3]) for row in rows}


def test_upgrade_adds_a_nullable_comparison_column_and_downgrade_drops_it(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    assert "comparison" not in _columns(db, "proposal_decisions")

    upgrade(config, REVISION)
    assert _columns(db, "proposal_decisions")["comparison"] == ("JSON", 0)

    downgrade(config, PREVIOUS_REVISION)
    assert "comparison" not in _columns(db, "proposal_decisions")
