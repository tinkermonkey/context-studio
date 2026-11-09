"""
Integration test for migration df5096c1a2ef (#1465): ontology entities gain a
derived flag, and rows that already exist read back as not derived.
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
REVISION = "df5096c1a2ef"
PREVIOUS_REVISION = "6f2ab6f75f48"


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: str) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [row[1] for row in conn.execute("PRAGMA table_info(ontology_entities)")]


def test_existing_entities_are_not_derived_and_downgrade_drops_the_column(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO ontology_entities (id, node_type, title, external_references,"
            " lexical_senses, data_properties, created_at, last_modified, version, status,"
            " is_indexed)"
            " VALUES ('t', 'taxonomy', 'T', '[]', '[]', '[]', '2026-01-01', '2026-01-01',"
            " 1, 'draft', 0)"
        )
    assert "derived" not in _columns(db)

    upgrade(config, REVISION)
    with sqlite3.connect(db) as conn:
        [(derived,)] = conn.execute("SELECT derived FROM ontology_entities").fetchall()
    assert derived == 0

    downgrade(config, PREVIOUS_REVISION)
    assert "derived" not in _columns(db)
