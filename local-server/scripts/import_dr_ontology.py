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

The first import writes the taxonomy directly. Once it exists, a re-run is a
re-import (#1464): it compares the spec with the taxonomy, matched by DR id
(following node types DR moved to another layer), and proposes what differs
as one change proposal for review instead of writing anything; with
--dry-run it only reports the drift. The app offers the same re-import over
REST and MCP (`adapters/interchange/dr_drift.py`).

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
    python scripts/import_dr_ontology.py [--spec-dir PATH] [--dry-run]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.interchange.dr_drift import DrDriftPlanner
from adapters.interchange.dr_relationships import DR_TAXONOMY_IDENTIFIER, DrRelationshipRules
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from config import get_config_manager
from domain.ontology.entities import AttributeDefinition, PropertyDefinition
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.versioning.drift import DriftError, DriftImportService, DriftResult
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.ports import ChangeProposalRepository
from domain.versioning.proposal_service import ProposalService
from domain.versioning.revert_service import RevertService
from experiments.ledger import append_baseline_reset, latest_baseline_reset
from scripts.dr_ontology_loader import (
    ImportSummary,
    PruneFailed,
    describe_stale,
    find_prune_blockers,
    import_dr_ontology,
    prune_stale,
)

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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Re-import: report the drift between the spec and the taxonomy; store nothing",
    )
    return parser.parse_args()


def reimport(
    session_factory: Any,
    ontology_service: OntologyService,
    repo: OntologyRepository,
    spec_dir: Path,
    dry_run: bool,
) -> int:
    """Propose (or with dry_run, report) the drift between the spec and the taxonomy."""
    proposals = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology_service,
        repo,
        RevertService(SQLiteChangeRepository(session_factory), repo),
        apply_rules=[DrRelationshipRules(repo)],
    )
    service = DriftImportService(proposals, ontology_service, DrDriftPlanner(repo))
    try:
        result = service.reimport(str(spec_dir), dry_run=dry_run)
    except (DriftError, ProposalValidationError) as exc:
        print(f"Re-import refused: {exc}", file=sys.stderr)
        return 1
    for line in describe_drift(result):
        print(line)
    return 0


def describe_drift(result: DriftResult) -> list[str]:
    """A drift result as lines of text."""
    revision = result.plan.source_revision
    lines = [
        f"Spec revision: {revision.spec_version if revision else '?'}"
        f" @ {(revision.commit if revision else None) or '?'}",
        f"Drift: {len(result.plan.entries)} entities differ",
    ]
    for entry in result.plan.entries:
        fields = f" ({', '.join(sorted(entry.fields))})" if entry.fields else ""
        lines.append(f"  {entry.change:6s} {entry.kind:9s} {entry.source_id}{fields}")
    if result.proposal is None:
        lines.append("No drift: nothing to propose.")
    elif result.dry_run:
        lines.append(
            f"Dry run: {len(result.proposal.operations)} operations validated; nothing stored."
        )
    else:
        lines.append(
            f"Proposed as {result.proposal.id} ({len(result.proposal.operations)} operations);"
            " review it in the app."
        )
    return lines


def report_and_prune(
    summary: ImportSummary,
    service: OntologyService,
    repo: OntologyRepository,
    proposals: ChangeProposalRepository,
    prune: bool,
) -> bool:
    """
    List the stale entities; with `prune`, delete them all, or none if any is in use.

    Returns False when pruning was refused because something uses a stale entity,
    or a delete was refused partway (the deleted and not-deleted ones are listed).
    """
    if not summary.stale:
        print("Stale: none")
        return True
    if not prune:
        print(
            "Stale (from an earlier import, not in this spec; not deleted, re-run with "
            f"--prune to delete): {len(summary.stale)}"
        )
        for entry in summary.stale:
            print(f"  - {entry}")
        return True

    blockers = find_prune_blockers(repo, proposals, summary.stale_entities)
    if blockers:
        print(
            f"Prune refused, nothing deleted: {len(blockers)} use(s) of the "
            f"{len(summary.stale)} stale entities:",
            file=sys.stderr,
        )
        for stale, user in blockers:
            print(f"  - {stale} <- used by {user}", file=sys.stderr)
        return False

    try:
        deleted = prune_stale(service, summary.stale_entities)
    except PruneFailed as exc:
        deleted_ids = {entity.id for entity in exc.deleted}
        print(f"Prune stopped: {exc}", file=sys.stderr)
        print(f"Deleted ({len(exc.deleted)}):", file=sys.stderr)
        for entity in exc.deleted:
            print(f"  - {describe_stale(entity)}", file=sys.stderr)
        not_deleted = [e for e in summary.stale_entities if e.id not in deleted_ids]
        print(f"Not deleted ({len(not_deleted)}):", file=sys.stderr)
        for entity in not_deleted:
            print(f"  - {describe_stale(entity)}", file=sys.stderr)
        return False

    properties = sum(isinstance(entity, PropertyDefinition) for entity in deleted)
    attributes = sum(isinstance(entity, AttributeDefinition) for entity in deleted)
    print(
        f"Pruned {len(deleted)} stale entities: {properties} property definition(s), "
        f"{attributes} attribute definition(s), {len(deleted) - properties - attributes} class(es)"
    )
    for entity in deleted:
        print(f"  - {describe_stale(entity)}")
    return True


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
    event_publisher = InProcessEventPublisher()
    ontology_service = OntologyService(
        repository=cast(OntologyRepository, ontology_repo),
        embedding_service=embedding_service,
        event_publisher=event_publisher,
        schema_index=None,
    )

    if ontology_repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER) is not None:
        print(f"Re-importing DR spec from {spec_dir} as a drift proposal ...")
        ChangeEventRecorder(SQLiteChangeRepository(session_factory)).subscribe_ontology_events(
            event_publisher
        )
        return reimport(
            session_factory,
            ontology_service,
            cast(OntologyRepository, ontology_repo),
            spec_dir,
            args.dry_run,
        )
    if args.dry_run:
        print("Nothing to compare: the DR spec hasn't been imported yet.", file=sys.stderr)
        return 1

    print(f"Importing DR ontology spec from {spec_dir} ...")
    summary = import_dr_ontology(
        ontology_service, cast(OntologyRepository, ontology_repo), spec_dir
    )

    print(f"Spec version: {summary.spec_version}")
    if summary.source_revision is not None:
        print(
            f"Source revision: {summary.source_revision.repo or '?'}"
            f" @ {summary.source_revision.commit or '?'} (taxonomy marked mirrored)"
        )
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
    print(
        f"Attribute definitions: created={summary.attribute_definitions_created:4d}  "
        f"updated={summary.attribute_definitions_updated:4d}"
    )

    if summary.charter_found:
        print("Design charter: taxonomy vision and summary set from DESIGN_CHARTER.md")
    else:
        print("Design charter: none in this spec; existing vision and summary left as they were")
    prune_ok = report_and_prune(
        summary,
        ontology_service,
        cast(OntologyRepository, ontology_repo),
        SQLiteChangeProposalRepository(session_factory),
        False,
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

    return 0 if prune_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
