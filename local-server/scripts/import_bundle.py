"""
Load a Context Studio bundle (v0) into the workspace ontology.

A bundle describes another project's ontology (see domain/interchange/bundle.py
for the format). Loading is idempotent: run it again after the project's
bundle changes and only the differences are written. Every change is recorded
as a change event. Entities the bundle no longer contains are reported, never
deleted.

Usage (from local-server/, venv active):
    python scripts/import_bundle.py PATH/TO/project.bundle.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.individual_vector_index import (
    SqliteIndividualVectorIndex,
)
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from config import get_config_manager
from domain.interchange.bundle import (
    BundleError,
    BundleImportSummary,
    check_bundle_header,
    load_bundle,
)
from domain.ontology.events import (
    AttributeDefinitionCreated,
    AttributeDefinitionUpdated,
    ClassCreated,
    ClassMoved,
    ClassUpdated,
    IndividualCreated,
    IndividualUpdated,
    PropertyDefinitionCreated,
    PropertyDefinitionUpdated,
    RelationshipCreated,
    SchemeCreated,
    SchemeUpdated,
    TaxonomyCreated,
    TaxonomyUpdated,
)
from domain.ontology.exceptions import OntologyError
from domain.ontology.ports import EmbeddingService, OntologyRepository
from domain.ontology.services import OntologyService


def read_bundle(path: Path) -> dict:
    """Read a bundle file and check its header."""
    try:
        bundle = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise BundleError(f"Malformed JSON in {path}: {exc}") from exc
    check_bundle_header(bundle)
    return bundle


def build_import_service(
    session_factory: sessionmaker, embedding_service: EmbeddingService
) -> OntologyService:
    """OntologyService for a bulk load: changes recorded, vector indexing deferred."""
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(SQLiteChangeRepository(session_factory))
    for event, handler in (
        (TaxonomyCreated, recorder.on_taxonomy_created),
        (TaxonomyUpdated, recorder.on_taxonomy_updated),
        (SchemeCreated, recorder.on_scheme_created),
        (SchemeUpdated, recorder.on_scheme_updated),
        (ClassCreated, recorder.on_class_created),
        (ClassUpdated, recorder.on_class_updated),
        (ClassMoved, recorder.on_class_moved),
        (PropertyDefinitionCreated, recorder.on_property_definition_created),
        (PropertyDefinitionUpdated, recorder.on_property_definition_updated),
        (IndividualCreated, recorder.on_individual_created),
        (IndividualUpdated, recorder.on_individual_updated),
        (RelationshipCreated, recorder.on_relationship_created),
        (AttributeDefinitionCreated, recorder.on_attribute_definition_created),
        (AttributeDefinitionUpdated, recorder.on_attribute_definition_updated),
    ):
        publisher.subscribe(event, handler)
    return OntologyService(
        repository=cast(OntologyRepository, SQLiteOntologyRepository(session_factory)),
        embedding_service=embedding_service,
        event_publisher=publisher,
        schema_index=None,
        individual_index=None,
    )


def print_summary(summary: BundleImportSummary) -> None:
    """Print per-kind counts and any stale entities."""
    print(f"Source: {summary.source}")
    print(f"{'kind':<14} {'created':>8} {'updated':>8} {'unchanged':>10}")
    for kind, counts in summary.counts.items():
        print(f"{kind:<14} {counts.created:>8} {counts.updated:>8} {counts.unchanged:>10}")
    if summary.stale:
        print(
            f"Stale (in the workspace, no longer in the bundle; not deleted): {len(summary.stale)}"
        )
        for entry in summary.stale:
            print(f"  - {entry}")
    else:
        print("Stale: none")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to the bundle JSON file")
    args = parser.parse_args()

    try:
        bundle = read_bundle(args.bundle)
    except (OSError, BundleError) as exc:
        print(f"Cannot read bundle: {exc}", file=sys.stderr)
        return 1

    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()
    embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")
    service = build_import_service(session_factory, embedding_service)
    repo = cast(OntologyRepository, SQLiteOntologyRepository(session_factory))

    print(f"Loading bundle {args.bundle} into {settings.database.local_db_path} ...")
    try:
        summary = load_bundle(service, repo, bundle)
    except (BundleError, OntologyError, ValueError) as exc:
        # Writes before the failure stay applied (and recorded); fix the bundle and reload.
        print(f"Load failed: {exc}", file=sys.stderr)
        return 1
    print_summary(summary)

    if summary.changed:
        print("Reindexing individual and schema vector indexes ...")
        individuals = SqliteIndividualVectorIndex(
            session_factory, embedding_service
        ).reindex_all_individuals()
        schema = SqliteSchemaVectorIndex(session_factory, embedding_service).reindex_all()
        print(f"Indexed {individuals} individuals; reindexed {schema} schema entities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
