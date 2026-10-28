"""
Integration test for migration a0e7f093e345: ontology_entities.class_id and
structural_property_id are indexed, so the reference lookups a revert makes
before each delete don't scan the table.
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
REVISION = "a0e7f093e345"
PREVIOUS_REVISION = "8de28edb4953"
INDEXES = {"ix_ontology_entities_class_id", "ix_ontology_entities_structural_property_id"}


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _indexes(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ontology_entities'"
        ).fetchall()
    return {name for (name,) in rows}


def test_upgrade_adds_and_downgrade_drops_the_reference_indexes(tmp_path):
    db = str(tmp_path / "local.db")
    upgrade(_config(db), PREVIOUS_REVISION)
    assert not INDEXES & _indexes(db)

    upgrade(_config(db), REVISION)
    assert INDEXES <= _indexes(db)

    downgrade(_config(db), PREVIOUS_REVISION)
    assert not INDEXES & _indexes(db)
