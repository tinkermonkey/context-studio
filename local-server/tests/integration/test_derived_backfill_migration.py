"""
Integration test for migration b2cd90812677: classes and relationship types whose
reference metadata carries the legacy `derived: true` (House's convention before
#1465) get the derived column set; nothing else changes.
"""

import json
import os
import sqlite3
import sys

from alembic.command import downgrade, upgrade
from alembic.config import Config

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "../../adapters/persistence/sqlite/alembic.ini"
)
REVISION = "b2cd90812677"
PREVIOUS_REVISION = "d8b3aea1f6bf"


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _reference(metadata):
    entry = {"source": "house", "identifier": "x", "uri": None}
    if metadata is not None:
        entry["metadata"] = metadata
    return json.dumps([entry])


def _insert(conn, entity_id, node_type, references):
    conn.execute(
        "INSERT INTO ontology_entities (id, node_type, title, external_references,"
        " lexical_senses, data_properties, created_at, last_modified, version, status,"
        " is_indexed)"
        " VALUES (?, ?, ?, ?, '[]', '[]', '2026-01-01', '2026-01-01', 1, 'draft', 0)",
        (entity_id, node_type, entity_id, references),
    )


def _derived(db_path):
    with sqlite3.connect(db_path) as conn:
        return dict(conn.execute("SELECT id, derived FROM ontology_entities"))


def test_legacy_metadata_flag_backfills_classes_and_relationship_types_only(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    with sqlite3.connect(db) as conn:
        _insert(conn, "kit", "class", _reference({"derived": True}))
        _insert(conn, "has_kit", "property_definition", _reference({"derived": True}))
        _insert(conn, "plain", "class", _reference({"derived": False}))
        _insert(conn, "no_metadata", "class", _reference(None))
        _insert(conn, "no_references", "property_definition", "[]")
        _insert(conn, "text_reference", "class", json.dumps(["not an object"]))
        _insert(conn, "taxonomy", "taxonomy", _reference({"derived": True}))

    upgrade(config, REVISION)
    assert _derived(db) == {
        "kit": 1,
        "has_kit": 1,
        "plain": 0,
        "no_metadata": 0,
        "no_references": 0,
        "text_reference": 0,
        "taxonomy": 0,
    }
    with sqlite3.connect(db) as conn:
        [(references,)] = conn.execute(
            "SELECT external_references FROM ontology_entities WHERE id = 'kit'"
        ).fetchall()
    assert json.loads(references)[0]["metadata"] == {"derived": True}

    downgrade(config, PREVIOUS_REVISION)
    assert _derived(db)["kit"] == 1
