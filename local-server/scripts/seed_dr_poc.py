#!/usr/bin/env python
"""
Stand up the DR POC on an explicit (typically fresh, scratch) database.

Chains the existing steps against the DB paths given on the command line,
never the ones in config.json / CONFIG_PATH:

1. Alembic migrations for local.db and operations.db (scripts/run_migrations.py)
2. The DR spec ontology import (the loader behind scripts/import_dr_ontology.py)
   from the sibling documentation_robotics spec checkout, as taxonomy `dr_spec`
3. The DR model import (the loader behind scripts/import_dr_model.py) of
   documentation-robotics/model/ as individuals and relationships
4. Vector reindex (schema entities + individuals), so recognition can match
   extracted mentions against the imported individuals
5. Count verification against the import summaries

Unlike scripts/import_dr_ontology.py, this does NOT append a baseline_reset
entry to experiments/ledger.jsonl: a demo/E2E database is throwaway and must not
move the Karpathy-loop baselines.

Optionally writes a config.json for the app pointing at the seeded DBs
(`--write-config`), copying every other setting (LLM keys, models) from
`--base-config`, so the demo is: seed, then
`CONFIG_PATH=<that config> python app.py`, then open /app/pipelines/review.

Usage (from local-server/, venv active):
    python scripts/seed_dr_poc.py --db-dir /tmp/dr-poc \
        [--spec-dir PATH] [--viewer-dir PATH] \
        [--write-config /tmp/dr-poc/config.json] [--base-config ./config.json]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from domain.ontology.ports import OntologyRepository
from scripts.dr_model_loader import import_dr_model
from scripts.dr_ontology_loader import import_dr_ontology
from scripts.import_dr_model import DEFAULT_VIEWER_DIR, build_import_service, print_summary
from scripts.import_dr_ontology import DEFAULT_SPEC_DIR, DR_ONTOLOGY_CONTEXT
from scripts.run_migrations import run_migrations

EMBEDDING_MODEL = "all-MiniLM-L12-v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Directory for local.db and operations.db (created if missing)",
    )
    parser.add_argument("--spec-dir", type=Path, default=DEFAULT_SPEC_DIR)
    parser.add_argument("--viewer-dir", type=Path, default=DEFAULT_VIEWER_DIR)
    parser.add_argument(
        "--write-config",
        type=Path,
        default=None,
        help="Write an app config.json pointing at the seeded DBs to this path",
    )
    parser.add_argument(
        "--base-config",
        type=Path,
        default=Path("./config.json"),
        help="Config whose other settings (LLM keys, server) --write-config copies",
    )
    return parser.parse_args()


def migrate(local_db: Path, operations_db: Path) -> None:
    """Bring both databases to head; raise on failure."""
    for database, url_kwarg, path in (
        ("local", "local_db_url", local_db),
        ("operations", "operations_db_url", operations_db),
    ):
        print(f"Migrating {database}: {path}")
        code = run_migrations(database, ["upgrade", "head"], **{url_kwarg: f"sqlite:///{path}"})
        if code != 0:
            raise SystemExit(f"Migration of {database} failed (exit {code})")


def write_config(target: Path, base: Path, local_db: Path, operations_db: Path) -> None:
    """Copy `base` (if present) with database paths pointed at the seeded DBs."""
    config = json.loads(base.read_text()) if base.is_file() else {}
    config.setdefault("database", {})
    config["database"]["local_db_path"] = str(local_db)
    config["database"]["operations_db_path"] = str(operations_db)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Wrote app config: {target} (based on {base if base.is_file() else 'defaults'})")


def main() -> int:
    args = parse_args()
    db_dir = args.db_dir.resolve()
    db_dir.mkdir(parents=True, exist_ok=True)
    local_db = db_dir / "local.db"
    operations_db = db_dir / "operations.db"
    spec_dir = args.spec_dir.resolve()
    viewer_dir = args.viewer_dir.resolve()
    if not spec_dir.is_dir():
        print(f"Spec directory not found: {spec_dir}", file=sys.stderr)
        return 1

    migrate(local_db, operations_db)

    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{local_db}",
        operations_db_url=f"sqlite:///{operations_db}",
    )
    session_factory = db_manager.get_local_session_factory()
    ontology_repo = SQLiteOntologyRepository(session_factory)
    repo = cast(OntologyRepository, ontology_repo)
    embedding_service = SentenceTransformerEmbedding(model_name=EMBEDDING_MODEL)

    # Per-entity indexing off; the indexes are rebuilt in batch below.
    ontology_service = build_import_service(session_factory, embedding_service)

    print(f"Importing DR ontology spec from {spec_dir} ...")
    ontology = import_dr_ontology(ontology_service, repo, spec_dir)
    print(
        f"Spec {ontology.spec_version}: schemes +{ontology.concept_schemes_created}"
        f"/~{ontology.concept_schemes_updated}, classes +{ontology.classes_created}"
        f"/~{ontology.classes_updated}, properties +{ontology.property_definitions_created}"
        f"/~{ontology.property_definitions_updated}"
    )

    print(f"Importing DR model from {viewer_dir} ...")
    try:
        model = import_dr_model(ontology_service, repo, viewer_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Model import failed: {exc}", file=sys.stderr)
        return 1
    print_summary(model)

    print("Reindexing schema and individual vector indexes ...")
    schema_indexed = SqliteSchemaVectorIndex(session_factory, embedding_service).reindex_all()
    individuals_indexed = SqliteIndividualVectorIndex(
        session_factory, embedding_service
    ).reindex_all_individuals()

    # ---- Verify -------------------------------------------------------------
    layers = model.layers.values()
    imported_individuals = sum(
        c.individuals_created + c.individuals_updated + c.individuals_unchanged for c in layers
    )
    imported_relationships = sum(c.relationships_created + c.relationships_unchanged for c in layers)
    source_elements = imported_individuals + sum(c.individuals_skipped for c in layers)
    source_relationships = imported_relationships + sum(c.relationships_skipped for c in layers)

    imported_schemes = ontology.concept_schemes_created + ontology.concept_schemes_updated
    taxonomy = ontology_repo.get_by_identifier(DR_ONTOLOGY_CONTEXT)
    schemes = ontology_repo.count_concept_schemes(taxonomy_id=taxonomy.id) if taxonomy else 0
    db_individuals = len(ontology_repo.list_individuals(limit=None))
    db_relationships = ontology_repo.count_relationships()

    checks = [
        (f"taxonomy '{DR_ONTOLOGY_CONTEXT}' exists", taxonomy is not None),
        (
            f"concept schemes (layers) in DB ({schemes}) == imported ({imported_schemes}) > 0",
            0 < imported_schemes == schemes,
        ),
        (
            f"individuals in DB ({db_individuals}) >= imported ({imported_individuals}) > 0",
            0 < imported_individuals <= db_individuals,
        ),
        (
            f"relationships in DB ({db_relationships}) >= imported ({imported_relationships}) > 0",
            0 < imported_relationships <= db_relationships,
        ),
        (
            f"individuals indexed ({individuals_indexed}) >= imported ({imported_individuals})",
            individuals_indexed >= imported_individuals,
        ),
        (f"schema entities indexed ({schema_indexed}) > 0", schema_indexed > 0),
    ]
    print()
    print(
        f"Model source: {source_elements} elements, {source_relationships} relationships "
        f"({len(model.skipped)} skipped against spec {ontology.spec_version})"
    )
    failed = 0
    for label, ok in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {label}")
        failed += 0 if ok else 1

    if args.write_config:
        write_config(args.write_config.resolve(), args.base_config, local_db, operations_db)

    if failed:
        print(f"{failed} check(s) failed", file=sys.stderr)
        return 1
    print(f"DR POC seeded in {db_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
