"""
Integration test for migration 025e43bda199 (#1513): a class's operational
definition columns on ontology_entities, against a real file-based SQLite
database migrated with Alembic.
"""

import sqlite3
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = str(Path(__file__).parent / "../../adapters/persistence/sqlite/alembic.ini")
REVISION = "025e43bda199"
PREVIOUS_REVISION = "b03f04db2ea4"
COLUMNS = {"distinguish_from", "evidence_signals", "standard_reference"}


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(ontology_entities)")}


def test_upgrade_adds_the_columns_and_downgrade_drops_them(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    assert not COLUMNS & _columns(db)

    upgrade(config, REVISION)
    assert COLUMNS <= _columns(db)

    downgrade(config, PREVIOUS_REVISION)
    assert not COLUMNS & _columns(db)
