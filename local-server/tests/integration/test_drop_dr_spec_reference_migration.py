"""
Integration test for migration 76b182ca4cbb: the DR taxonomy's leftover
documentation_robotics/spec reference (only a stale spec_version since #1480) is
dropped, and every other reference is left as it is.
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
REVISION = "76b182ca4cbb"
PREVIOUS_REVISION = "3d7b38dca806"

SPEC_REF = {
    "source": "documentation_robotics",
    "identifier": "spec",
    "uri": None,
    "metadata": {"spec_version": "0.10.0"},
}
OTHER_DR_REF = {"source": "documentation_robotics", "identifier": "other", "uri": None}
WIKIDATA_REF = {
    "source": "wikidata",
    "identifier": "Q1",
    "uri": "https://www.wikidata.org/wiki/Q1",
    "metadata": {"label": "universe"},
}
# A class whose DR id happens to be "spec": only taxonomies lose the reference.
CLASS_REFS = [{"source": "documentation_robotics", "identifier": "spec", "uri": None}]


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _entity(conn, entity_id, node_type, refs, **columns):
    values = {
        "id": entity_id,
        "node_type": node_type,
        "title": entity_id,
        "identifier": entity_id,
        "external_references": json.dumps(refs),
        "lexical_senses": "[]",
        "data_properties": "[]",
        "created_at": "2026-01-01",
        "last_modified": "2026-01-01",
        "version": 1,
        "status": "draft",
        "is_indexed": 1,
        **columns,
    }
    names = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO ontology_entities ({names}) VALUES ({marks})", list(values.values()))


def _seed(db: str) -> None:
    with sqlite3.connect(db) as conn:
        _entity(conn, "dr", "taxonomy", [SPEC_REF, OTHER_DR_REF, WIKIDATA_REF])
        _entity(conn, "dr-only", "taxonomy", [SPEC_REF])
        _entity(conn, "house", "taxonomy", [WIKIDATA_REF])
        _entity(conn, "plain", "taxonomy", [])
        _entity(conn, "dr-scheme", "concept_scheme", [], taxonomy_id="dr")
        _entity(
            conn,
            "dr-class",
            "class",
            CLASS_REFS,
            taxonomy_id="dr",
            concept_scheme_id="dr-scheme",
        )


def _refs(db: str) -> dict[str, list[dict]]:
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT id, external_references FROM ontology_entities").fetchall()
    return {entity_id: json.loads(raw) for entity_id, raw in rows}


def test_upgrade_drops_only_the_dr_spec_reference(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    _seed(db)

    upgrade(config, REVISION)

    assert _refs(db) == {
        "dr": [OTHER_DR_REF, WIKIDATA_REF],
        "dr-only": [],
        "house": [WIKIDATA_REF],
        "plain": [],
        "dr-scheme": [],
        "dr-class": CLASS_REFS,
    }


def test_downgrade_is_a_no_op(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    _seed(db)
    upgrade(config, REVISION)
    after_upgrade = _refs(db)

    downgrade(config, PREVIOUS_REVISION)

    assert _refs(db) == after_upgrade
