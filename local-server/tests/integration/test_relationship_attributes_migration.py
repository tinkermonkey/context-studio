"""
Integration test for migration 86bcab10d611 (#1365): relationships gain an
attributes JSON column, and rows that already exist read back as {}.
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
REVISION = "86bcab10d611"
PREVIOUS_REVISION = "0cb067ec7265"


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: str) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [row[1] for row in conn.execute("PRAGMA table_info(relationships)")]


def test_existing_relationships_get_empty_attributes_and_downgrade_drops_the_column(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    # Foreign keys are off on a plain sqlite3 connection, so the ends need no rows.
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO relationships (id, source_id, target_id, property_definition_id,"
            " created_at) VALUES ('r', 'a', 'b', 'p', '2026-01-01')"
        )
    assert "attributes" not in _columns(db)

    upgrade(config, REVISION)
    with sqlite3.connect(db) as conn:
        [(attributes,)] = conn.execute("SELECT attributes FROM relationships").fetchall()
    assert attributes == "{}"

    downgrade(config, PREVIOUS_REVISION)
    assert "attributes" not in _columns(db)
