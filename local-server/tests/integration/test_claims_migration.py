"""
Integration test for migration 036cabe45eb0 (#1518): the claims table, against a
real file-based SQLite database migrated with Alembic.
"""

import sqlite3
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = str(Path(__file__).parent / "../../adapters/persistence/sqlite/alembic.ini")
REVISION = "036cabe45eb0"
PREVIOUS_REVISION = "fc64b1c76476"


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
    assert _ddl(db, "claims") is None

    upgrade(config, REVISION)
    ddl = _ddl(db, "claims")
    assert ddl is not None
    assert "REFERENCES ontology_entities (id) ON DELETE CASCADE" in ddl
    assert 'CONSTRAINT uq_claim_taxonomy_key UNIQUE (taxonomy_id, "key")' in ddl

    downgrade(config, PREVIOUS_REVISION)
    assert _ddl(db, "claims") is None
