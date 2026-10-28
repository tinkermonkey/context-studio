"""
Integration test for migration 0cb067ec7265 (#1355): the approval_policies
table, against a real file-based SQLite database migrated with Alembic.
"""

import os
import sqlite3
import sys

from alembic.command import downgrade, upgrade
from alembic.config import Config

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "../../adapters/persistence/sqlite/alembic.ini"
)
REVISION = "0cb067ec7265"
PREVIOUS_REVISION = "8de28edb4953"


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


def test_upgrade_adds_the_table_and_downgrade_drops_it(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    assert _ddl(db, "approval_policies") is None

    upgrade(config, REVISION)
    ddl = _ddl(db, "approval_policies")
    assert ddl is not None
    assert "REFERENCES ontology_entities (id) ON DELETE CASCADE" in ddl
    assert "PRIMARY KEY (taxonomy_id)" in ddl

    downgrade(config, PREVIOUS_REVISION)
    assert _ddl(db, "approval_policies") is None
