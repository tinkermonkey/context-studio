"""
Integration test for migration a61cfa4aa3d7 (#1484): the old `datasets` table
(importable database files) is replaced by datasets over a taxonomy's schema,
each taxonomy with individuals gets a dataset `default` holding them, and every
individual must have a dataset from then on.
"""

import os
import sqlite3
import sys

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "../../adapters/persistence/sqlite/alembic.ini"
)
REVISION = "a61cfa4aa3d7"
PREVIOUS_REVISION = "7512875103f3"

_ENTITY_COLUMNS = (
    "id, node_type, title, taxonomy_id, concept_scheme_id, external_references,"
    " lexical_senses, data_properties, created_at, last_modified, version, status, is_indexed"
)


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: str, table: str) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _insert_entity(conn, entity_id, node_type, taxonomy_id=None, scheme_id=None):
    conn.execute(
        f"INSERT INTO ontology_entities ({_ENTITY_COLUMNS}) VALUES"
        " (?, ?, ?, ?, ?, '[]', '[]', '[]', '2026-01-01', '2026-01-01', 1, 'draft', 0)",
        (entity_id, node_type, entity_id.upper(), taxonomy_id, scheme_id),
    )


def _seed(db_path: str) -> None:
    """Two taxonomies with individuals, one without."""
    with sqlite3.connect(db_path) as conn:
        for tax in ("dr", "life", "empty"):
            _insert_entity(conn, tax, "taxonomy")
            _insert_entity(conn, f"{tax}-scheme", "concept_scheme", tax)
            _insert_entity(conn, f"{tax}-class", "class", tax, f"{tax}-scheme")
        for ind, tax in (("api", "dr"), ("gateway", "dr"), ("neuron", "life")):
            _insert_entity(conn, ind, "individual")
            conn.execute(
                "INSERT INTO individual_classes (individual_id, class_id, position)"
                " VALUES (?, ?, 0)",
                (ind, f"{tax}-class"),
            )


def test_individuals_land_in_a_default_dataset_per_taxonomy(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    _seed(db)

    upgrade(config, REVISION)

    with sqlite3.connect(db) as conn:
        datasets = dict(
            conn.execute("SELECT taxonomy_id, id FROM datasets WHERE identifier = 'default'")
        )
        placed = dict(
            conn.execute(
                "SELECT id, dataset_id FROM ontology_entities WHERE node_type = 'individual'"
            )
        )
        schema_rows = conn.execute(
            "SELECT count(*) FROM ontology_entities"
            " WHERE node_type != 'individual' AND dataset_id IS NOT NULL"
        ).fetchone()[0]
    assert set(datasets) == {"dr", "life"}
    assert placed == {
        "api": datasets["dr"],
        "gateway": datasets["dr"],
        "neuron": datasets["life"],
    }
    assert schema_rows == 0


def test_an_individual_without_a_dataset_is_refused_after_upgrade(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, REVISION)

    with sqlite3.connect(db) as conn, pytest.raises(sqlite3.IntegrityError, match="dataset"):
        _insert_entity(conn, "loose", "individual")


def test_downgrade_restores_the_old_table_and_drops_the_column(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    _seed(db)
    upgrade(config, REVISION)

    downgrade(config, PREVIOUS_REVISION)

    assert "dataset_id" not in _columns(db, "ontology_entities")
    assert "filename" in _columns(db, "datasets")
    with sqlite3.connect(db) as conn:
        individuals = conn.execute(
            "SELECT count(*) FROM ontology_entities WHERE node_type = 'individual'"
        ).fetchone()[0]
    assert individuals == 3


def test_an_individual_spanning_two_taxonomies_stops_the_upgrade(tmp_path):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    _seed(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO individual_classes (individual_id, class_id, position)"
            " VALUES ('api', 'life-class', 1)"
        )

    with pytest.raises(RuntimeError, match="more than one taxonomy"):
        upgrade(config, REVISION)
