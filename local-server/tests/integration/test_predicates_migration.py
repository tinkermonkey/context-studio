"""
Integration test for migration a042b463a6f2 (#1480): predicates become a per-taxonomy
catalog table, relationship types point at one, and canonical_predicate stops being
a column.

Seeds a small database at the previous revision with a DR taxonomy carrying its
catalog on the spec reference, a type with a domain class, a type known only
through its edges, and a type with no taxonomy at all.
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
REVISION = "a042b463a6f2"
PREVIOUS_REVISION = "7512875103f3"

DR_CATALOG = {
    "navigates-to": {
        "inverse": "navigated-from",
        "category": "behavioral",
        "description": "Moves the user to another element",
        "archimate_alignment": "triggering",
    },
    "accesses": {"inverse": "accessed-by", "category": "security", "description": "Reads"},
}
DR_REFS = [
    {
        "source": "documentation_robotics",
        "identifier": "spec",
        "uri": None,
        "metadata": {"spec_version": "0.10.0", "predicates": DR_CATALOG},
    }
]


def _config(db_path: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _entity(conn, entity_id, node_type, **columns):
    values = {
        "id": entity_id,
        "node_type": node_type,
        "title": entity_id,
        "external_references": "[]",
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
        _entity(
            conn, "dr", "taxonomy", identifier="dr_spec", external_references=json.dumps(DR_REFS)
        )
        _entity(conn, "demo", "taxonomy", identifier="tax_demo")
        _entity(conn, "dr-scheme", "concept_scheme", identifier="dr_scheme", taxonomy_id="dr")
        _entity(conn, "demo-scheme", "concept_scheme", identifier="demo_scheme", taxonomy_id="demo")
        for class_id, taxonomy_id, scheme_id in (
            ("dr-page", "dr", "dr-scheme"),
            ("dr-view", "dr", "dr-scheme"),
            ("demo-gene", "demo", "demo-scheme"),
            ("demo-protein", "demo", "demo-scheme"),
        ):
            _entity(
                conn,
                class_id,
                "class",
                identifier=class_id.replace("-", "_"),
                taxonomy_id=taxonomy_id,
                concept_scheme_id=scheme_id,
            )
        # DR type with a domain class and a catalog predicate
        _entity(
            conn,
            "type-nav",
            "property_definition",
            identifier="page_navigates_to_view",
            canonical_predicate="navigates-to",
            domain_class_id="dr-page",
            range_class_id="dr-view",
        )
        # DR type whose predicate isn't in the catalog: found or created
        _entity(
            conn,
            "type-extra",
            "property_definition",
            identifier="view_shows_page",
            canonical_predicate="shows",
            range_class_id="dr-page",
        )
        # Demo type with no canonical_predicate and no domain/range, but an edge
        _entity(conn, "type-encoded", "property_definition", identifier="encoded_by")
        conn.execute(
            "INSERT INTO relationships (id, source_id, target_id, property_definition_id,"
            " created_at, attributes)"
            " VALUES ('rel-1', 'demo-protein', 'demo-gene', 'type-encoded', '2026-01-01', '{}')"
        )
        # A type no taxonomy reaches
        _entity(conn, "type-orphan", "property_definition", identifier="orphan_type")


def _rows(db: str, sql: str) -> list[tuple]:
    with sqlite3.connect(db) as conn:
        return conn.execute(sql).fetchall()


def _columns(db: str) -> list[str]:
    return [row[1] for row in _rows(db, "PRAGMA table_info(ontology_entities)")]


def test_upgrade_builds_the_catalogs_and_downgrade_restores_them(tmp_path, capsys):
    db = str(tmp_path / "local.db")
    config = _config(db)
    upgrade(config, PREVIOUS_REVISION)
    _seed(db)

    upgrade(config, REVISION)

    assert "canonical_predicate" not in _columns(db)
    assert "orphan_type" in capsys.readouterr().out
    predicates = {
        (taxonomy_id, identifier): (description, json.loads(refs))
        for taxonomy_id, identifier, description, refs in _rows(
            db, "SELECT taxonomy_id, identifier, description, external_references FROM predicates"
        )
    }
    assert set(predicates) == {
        ("dr", "navigates-to"),
        ("dr", "accesses"),
        ("dr", "shows"),
        ("demo", "encoded_by"),
    }
    description, refs = predicates[("dr", "navigates-to")]
    assert description == "Moves the user to another element"
    assert refs == [
        {
            "source": "documentation_robotics",
            "identifier": "navigates-to",
            "uri": None,
            "metadata": {
                "inverse": "navigated-from",
                "category": "behavioral",
                "archimate_alignment": "triggering",
            },
        }
    ]
    assert predicates[("dr", "shows")] == (None, [])

    [(dr_refs,)] = _rows(db, "SELECT external_references FROM ontology_entities WHERE id = 'dr'")
    assert json.loads(dr_refs)[0]["metadata"] == {"spec_version": "0.10.0"}

    linked = dict(
        _rows(
            db,
            "SELECT pd.id, p.taxonomy_id || ':' || p.identifier FROM ontology_entities pd"
            " LEFT JOIN predicates p ON p.id = pd.predicate_id"
            " WHERE pd.node_type = 'property_definition'",
        )
    )
    assert linked == {
        "type-nav": "dr:navigates-to",
        "type-extra": "dr:shows",
        "type-encoded": "demo:encoded_by",
        "type-orphan": None,
    }
    assert _rows(db, "PRAGMA foreign_key_check") == []

    downgrade(config, PREVIOUS_REVISION)

    assert "predicate_id" not in _columns(db)
    assert _rows(db, "SELECT name FROM sqlite_master WHERE name = 'predicates'") == []
    assert dict(
        _rows(
            db,
            "SELECT id, canonical_predicate FROM ontology_entities"
            " WHERE node_type = 'property_definition'",
        )
    ) == {
        "type-nav": "navigates-to",
        "type-extra": "shows",
        "type-encoded": "encoded_by",
        "type-orphan": None,
    }
    [(dr_refs,)] = _rows(db, "SELECT external_references FROM ontology_entities WHERE id = 'dr'")
    assert json.loads(dr_refs) == DR_REFS

    upgrade(config, REVISION)
    assert len(_rows(db, "SELECT id FROM predicates")) == 4
