#!/usr/bin/env python
"""
Idempotent import of a Documentation Robotics (DR) model as individuals and
relationships under the `dr_spec` taxonomy.

Requires the DR spec ontology to be imported first (`import_dr_ontology.py`).
Reads `{viewer-dir}/documentation-robotics/model/` — by default Context
Studio's own DR model checked into this repository. One Individual per model
element, typed to the matching `dr_spec` Class; one Relationship per
`relationships.yaml` entry, typed to the matching PropertyDefinition. Elements
or relationships that do not resolve against the ontology are skipped and
reported.

Safe to re-run: individuals are keyed on the preserved DR element path, so a
re-run updates them in place. Writes go through OntologyService with the
change-event recorder subscribed; vector indexes are rebuilt once at the end.
Stop (or restart) a running server around the import so its in-memory graph
cache picks up the new individuals.

Usage (from local-server/, venv active):
    python scripts/import_dr_model.py [--viewer-dir PATH]
"""

import argparse
import os
import sys
from collections import Counter
from pathlib import Path
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from config import get_config_manager
from domain.ontology.events import IndividualCreated, IndividualUpdated, RelationshipCreated
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from scripts.dr_model_loader import ModelImportSummary, import_dr_model

# local-server/scripts/../.. == the context-studio repo root, which holds
# documentation-robotics/model/.
DEFAULT_VIEWER_DIR = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer-dir",
        type=Path,
        default=DEFAULT_VIEWER_DIR,
        help=(
            "Directory containing documentation-robotics/model/ " f"(default: {DEFAULT_VIEWER_DIR})"
        ),
    )
    return parser.parse_args()


def print_summary(summary: ModelImportSummary) -> None:
    """Print per-layer counts, then skipped entries grouped by reason."""
    print(f"Model spec version: {summary.model_spec_version}")
    header = (
        f"{'layer':<12} {'ind+':>5} {'ind~':>5} {'ind=':>5} {'ind-':>5} "
        f"{'rel+':>5} {'rel=':>5} {'rel-':>5}"
    )
    print(header)
    print("-" * len(header))
    totals = [0] * 7
    for layer in sorted(summary.layers):
        counts = summary.layers[layer]
        row = [
            counts.individuals_created,
            counts.individuals_updated,
            counts.individuals_unchanged,
            counts.individuals_skipped,
            counts.relationships_created,
            counts.relationships_unchanged,
            counts.relationships_skipped,
        ]
        totals = [total + value for total, value in zip(totals, row)]
        print(f"{layer:<12} " + " ".join(f"{value:>5}" for value in row))
    print("-" * len(header))
    print(f"{'total':<12} " + " ".join(f"{value:>5}" for value in totals))
    print("(+ created, ~ updated, = unchanged, - skipped; relationships by source layer)")

    if not summary.skipped:
        print("Skipped: none")
        return
    print(f"Skipped ({len(summary.skipped)}):")
    by_reason = Counter((record.kind, record.reason) for record in summary.skipped)
    for (kind, reason), count in sorted(by_reason.items()):
        print(f"  {count:4d}  {kind:<12} {reason}")


def main() -> int:
    args = parse_args()
    viewer_dir = args.viewer_dir.resolve()

    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()

    ontology_repo = SQLiteOntologyRepository(session_factory)
    embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")

    event_publisher = InProcessEventPublisher()
    change_recorder = ChangeEventRecorder(SQLiteChangeRepository(session_factory))
    event_publisher.subscribe(IndividualCreated, change_recorder.on_individual_created)
    event_publisher.subscribe(IndividualUpdated, change_recorder.on_individual_updated)
    event_publisher.subscribe(RelationshipCreated, change_recorder.on_relationship_created)

    # Both indexes None suppresses per-entity embedding during the import;
    # they are rebuilt once, in batch, below.
    ontology_service = OntologyService(
        repository=cast(OntologyRepository, ontology_repo),
        embedding_service=embedding_service,
        event_publisher=event_publisher,
        schema_index=None,
        individual_index=None,
    )

    print(f"Importing DR model from {viewer_dir} ...")
    try:
        summary = import_dr_model(
            ontology_service, cast(OntologyRepository, ontology_repo), viewer_dir
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print_summary(summary)

    print("Reindexing individual and schema vector indexes ...")
    individuals_indexed = SqliteIndividualVectorIndex(
        session_factory, embedding_service
    ).reindex_all_individuals()
    schema_indexed = SqliteSchemaVectorIndex(session_factory, embedding_service).reindex_all()
    print(f"Indexed {individuals_indexed} individuals; reindexed {schema_indexed} schema entities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
