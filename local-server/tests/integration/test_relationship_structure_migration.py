"""
Integration test for migration 97ac937598aa (#1482): relationship-type structure
leaves reference metadata for columns, and edge properties become attribute
definitions owned by their relationship type.

Seeds a database at the previous revision with House-style types (min/max/
hierarchy/symmetric/edge_properties in their "house" reference metadata, one with
a key the lift leaves alone), DR-style types (cardinality in their
documentation_robotics reference, one with a value DR doesn't define) and a type
with no references, then upgrades, checks, downgrades and checks again.
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
REVISION = "97ac937598aa"
PREVIOUS_REVISION = "4e84e0aed52f"


def _house(identifier: str, **metadata) -> list[dict]:
    return [{"source": "house", "identifier": identifier, "uri": None, "metadata": metadata}]


def _dr(identifier: str, **metadata) -> list[dict]:
    return [
        {
            "source": "documentation_robotics",
            "identifier": identifier,
            "uri": None,
            "metadata": metadata,
        }
    ]


TYPES = {
    "kit-includes": _house(
        "house_kit_includes_tool",
        derived=True,
        min=0,
        max=None,
        hierarchy=False,
        symmetric=False,
        edge_properties=["quantity", "unit", "optional"],
    ),
    "sourced-from": _house(
        "house_resource_sourced_from_party",
        max=None,
        min=0,
        hierarchy=False,
        symmetric=False,
        edge_properties=["note", "preferred", "supplier_rank"],
    ),
    "part-of": _house("house_place_part_of_place", max=1, min=0, hierarchy=True, symmetric=False),
    "adjacent": _house(
        "house_place_adjacent_to_place", max=None, min=0, hierarchy=False, symmetric=True
    ),
    "located-in": _house(
        "house_item_located_in_place", max=1, min=1, hierarchy=False, symmetric=False
    ),
    "dr-mm": _dr("a.b", cardinality="many-to-many", strength="medium"),
    "dr-mo": _dr("a.c", cardinality="many-to-one", strength="high", evidence=["x"]),
    "dr-om": _dr("a.d", cardinality="one-to-many", strength="low"),
    "dr-oo": _dr("a.e", cardinality="one-to-one"),
    "dr-odd": _dr("a.f", cardinality="some-to-few", strength="low"),
    "plain": [],
}


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _seed(db: str) -> None:
    with sqlite3.connect(db) as conn:
        for type_id, refs in TYPES.items():
            conn.execute(
                "INSERT INTO ontology_entities (id, node_type, title, identifier,"
                " external_references, lexical_senses, data_properties, created_at,"
                " last_modified, version, status, is_indexed)"
                " VALUES (?, 'property_definition', ?, ?, ?, '[]', '[]', '2026-01-01',"
                " '2026-01-01', 1, 'draft', 1)",
                (type_id, type_id, type_id.replace("-", "_"), json.dumps(refs)),
            )


def _rows(db: str, sql: str) -> list[tuple]:
    with sqlite3.connect(db) as conn:
        return conn.execute(sql).fetchall()


def _metadata(db: str) -> dict[str, dict | None]:
    return {
        type_id: json.loads(refs)[0]["metadata"] if json.loads(refs) else None
        for type_id, refs in _rows(
            db,
            "SELECT id, external_references FROM ontology_entities"
            " WHERE node_type = 'property_definition'",
        )
    }


def test_upgrade_lifts_the_structure_and_downgrade_restores_it(tmp_path, capsys):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    _seed(db)

    upgrade(config, REVISION)

    out = capsys.readouterr().out
    assert "'some-to-few'" in out
    structure = {
        row[0]: row[1:]
        for row in _rows(
            db,
            "SELECT id, min_per_source, max_per_source, max_per_target, hierarchy, symmetric"
            " FROM ontology_entities WHERE node_type = 'property_definition'",
        )
    }
    assert structure == {
        "kit-includes": (0, None, None, 0, 0),
        "sourced-from": (0, None, None, 0, 0),
        "part-of": (0, 1, None, 1, 0),
        "adjacent": (0, None, None, 0, 1),
        "located-in": (1, 1, None, 0, 0),
        "dr-mm": (0, None, None, 0, 0),
        "dr-mo": (0, 1, None, 0, 0),
        "dr-om": (0, None, 1, 0, 0),
        "dr-oo": (0, 1, 1, 0, 0),
        "dr-odd": (0, None, None, 0, 0),
        "plain": (0, None, None, 0, 0),
    }

    attributes = _rows(
        db,
        "SELECT property_definition_id, class_id, identifier, title, datatype,"
        " allowed_values, sort_order, is_required, status FROM attribute_definitions"
        " ORDER BY property_definition_id, sort_order",
    )
    units = json.dumps(
        ["each", "pair", "dozen", "in", "ft", "yd", "mm", "cm", "m", "fl_oz"]
        + ["cup", "pt", "qt", "gal", "ml", "l", "oz", "lb", "g", "kg"]
    )
    assert [(*row[:5], json.loads(row[5]), *row[6:]) for row in attributes] == [
        ("kit-includes", None, "quantity", "quantity", "number", None, 0, 0, "draft"),
        ("kit-includes", None, "unit", "unit", "string", json.loads(units), 1, 0, "draft"),
        ("kit-includes", None, "optional", "optional", "boolean", None, 2, 0, "draft"),
        ("sourced-from", None, "note", "note", "string", None, 0, 0, "draft"),
        ("sourced-from", None, "preferred", "preferred", "boolean", None, 1, 0, "draft"),
        ("sourced-from", None, "supplier_rank", "supplier_rank", "string", None, 2, 0, "draft"),
    ]

    # The lifted keys are gone; what's left stays, and an emptied metadata is null
    assert _metadata(db) == {
        "kit-includes": {"derived": True},
        "sourced-from": None,
        "part-of": None,
        "adjacent": None,
        "located-in": None,
        "dr-mm": {"strength": "medium"},
        "dr-mo": {"strength": "high", "evidence": ["x"]},
        "dr-om": {"strength": "low"},
        "dr-oo": None,
        "dr-odd": {"cardinality": "some-to-few", "strength": "low"},
        "plain": None,
    }
    assert _rows(db, "PRAGMA foreign_key_check") == []

    downgrade(config, PREVIOUS_REVISION)

    columns = [row[1] for row in _rows(db, "PRAGMA table_info(ontology_entities)")]
    assert "min_per_source" not in columns and "symmetric" not in columns
    attribute_columns = [row[1] for row in _rows(db, "PRAGMA table_info(attribute_definitions)")]
    assert "property_definition_id" not in attribute_columns
    assert _rows(db, "SELECT COUNT(*) FROM attribute_definitions") == [(0,)]
    assert _metadata(db) == {
        type_id: refs[0]["metadata"] if refs else None for type_id, refs in TYPES.items()
    }

    upgrade(config, REVISION)
    assert _rows(db, "SELECT COUNT(*) FROM attribute_definitions") == [(6,)]
