#!/usr/bin/env python
"""
One-time, idempotent import of the Documentation Robotics (DR) spec into
Context Studio's ontology domain model.

Replaces the placeholder ontology with the full DR 12-layer ontology: one
Taxonomy, one ConceptScheme per layer, one Class per DR node schema, and one
PropertyDefinition per DR relationship schema. Reads only from
`{spec-dir}/schemas/{nodes,relationships}/` and `{spec-dir}/dist/manifest.json`
in the sibling `documentation_robotics` checkout — that spec is an external,
versioned dependency and is never copied into this repository.

Safe to re-run: entities are keyed on the preserved DR schema id, so importing
against the same or an updated spec version updates existing entities in
place instead of creating duplicates.

A successful import against a spec version not already recorded in
`experiments/ledger.jsonl` appends a `baseline_reset` checkpoint entry there
(see `experiments/ledger.py`). Per
`documentation/karpathy_loop_dr_ontology_design.md` §9, swapping the ontology
resets the Karpathy loop's incumbent baselines: this checkpoint is the
mechanism that scopes ledger reads (e.g. `rejected_hypotheses`) to entries
recorded since the import, so pre-import experiment results never judge
post-import ones. A spec-version upgrade is therefore always a deliberate,
baseline-resetting re-import — never an in-place, silent update.

Usage (from local-server/, venv active):
    python scripts/import_dr_ontology.py [--spec-dir PATH]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from config import get_config_manager
from domain.ontology.services import OntologyService
from domain.ontology.ports import OntologyRepository
from experiments.ledger import append_baseline_reset, latest_baseline_reset
from scripts.dr_ontology_loader import ImportSummary, import_dr_ontology

DR_ONTOLOGY_CONTEXT = "dr_spec"


def _current_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def record_baseline_reset_if_new(
    summary: ImportSummary, spec_dir: Path, ledger_path: Path | str | None = None
) -> bool:
    """
    Append a `baseline_reset` ledger entry for `summary.spec_version`, unless
    one is already recorded for it (re-running the import against an
    unchanged spec version is idempotent sync, not a new baseline event).

    Args:
        ledger_path: Defaults to `experiments/ledger.jsonl`. Override for testing.

    Returns:
        True if a new checkpoint was appended, False if one already existed.
    """
    existing = latest_baseline_reset(ontology_context=DR_ONTOLOGY_CONTEXT, ledger_path=ledger_path)
    if existing is not None and existing.get("spec_version") == summary.spec_version:
        return False

    reason = (
        f"DR ontology import from {spec_dir}: spec_version={summary.spec_version}, "
        f"taxonomies +{summary.taxonomies_created}/~{summary.taxonomies_updated}, "
        f"concept_schemes +{summary.concept_schemes_created}/~{summary.concept_schemes_updated}, "
        f"classes +{summary.classes_created}/~{summary.classes_updated}, "
        f"property_definitions +{summary.property_definitions_created}/~"
        f"{summary.property_definitions_updated}. Replaces the throwaway 3-class placeholder "
        "ontology (documentation/karpathy_loop_dr_ontology_design.md); per its §9 "
        "metric-gaming-defense rule this is a deliberate baseline reset, not an in-place update — "
        "ledger entries recorded before this checkpoint are not comparable to experiments run "
        "after it."
    )
    append_baseline_reset(
        reason=reason,
        ontology_context=DR_ONTOLOGY_CONTEXT,
        spec_version=summary.spec_version,
        base_commit=_current_git_commit(),
        ledger_path=ledger_path,
    )
    return True


# local-server/scripts/../.. == the context-studio repo root; parents[3] is
# that repo root's parent, where the DR spec is checked out as a sibling repo
# (not vendored into this one).
DEFAULT_SPEC_DIR = Path(__file__).resolve().parents[3] / "documentation_robotics" / "spec"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec-dir",
        type=Path,
        default=DEFAULT_SPEC_DIR,
        help=f"Path to the documentation_robotics spec checkout (default: {DEFAULT_SPEC_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec_dir = args.spec_dir.resolve()
    if not spec_dir.is_dir():
        print(f"Spec directory not found: {spec_dir}", file=sys.stderr)
        return 1

    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()

    ontology_repo = SQLiteOntologyRepository(session_factory)
    embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")

    # schema_index=None suppresses per-entity vector sync during creation;
    # reindex_all() below runs the embedding batch exactly once, at the end.
    ontology_service = OntologyService(
        repository=cast(OntologyRepository, ontology_repo),
        embedding_service=embedding_service,
        event_publisher=InProcessEventPublisher(),
        schema_index=None,
    )

    print(f"Importing DR ontology spec from {spec_dir} ...")
    summary = import_dr_ontology(ontology_service, cast(OntologyRepository, ontology_repo), spec_dir)

    print(f"Spec version: {summary.spec_version}")
    print(
        f"Taxonomies:            created={summary.taxonomies_created:4d}  "
        f"updated={summary.taxonomies_updated:4d}"
    )
    print(
        f"Concept schemes:       created={summary.concept_schemes_created:4d}  "
        f"updated={summary.concept_schemes_updated:4d}"
    )
    print(
        f"Classes:               created={summary.classes_created:4d}  "
        f"updated={summary.classes_updated:4d}"
    )
    print(
        f"Property definitions:  created={summary.property_definitions_created:4d}  "
        f"updated={summary.property_definitions_updated:4d}"
    )

    print("Reindexing schema vector index ...")
    vector_index = SqliteSchemaVectorIndex(session_factory, embedding_service)
    reindexed = vector_index.reindex_all()
    print(f"Reindexed {reindexed} schema entities.")

    if record_baseline_reset_if_new(summary, spec_dir):
        print(
            f"Recorded baseline-reset checkpoint for spec_version={summary.spec_version} in "
            "experiments/ledger.jsonl"
        )
    else:
        print(
            f"Baseline-reset checkpoint for spec_version={summary.spec_version} already "
            "recorded — skipped."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
