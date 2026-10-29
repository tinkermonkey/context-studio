"""
Import a Context Studio bundle (v0) into the workspace as a change proposal.

A bundle describes another project's ontology (see domain/interchange/bundle.py
for the format). The bundle is planned against the workspace and the plan
proposed (source=bundle) for review: nothing changes until operations are
applied. The taxonomy's approval policy applies what it allows; --apply also
applies every other non-breaking operation. Breaking operations, such as
deleting what the bundle no longer contains, always wait for review. A bundle
that matches the workspace proposes nothing.

Usage (from local-server/, venv active):
    python scripts/import_bundle.py PATH/TO/project.bundle.json [--apply | --dry-run]
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.approval_policy_repo import SQLiteApprovalPolicyRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.individual_vector_index import (
    SqliteIndividualVectorIndex,
)
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from config import get_config_manager
from domain.interchange.bundle import BundleError, check_bundle_header
from domain.ontology.exceptions import OntologyError
from domain.ontology.ports import EmbeddingService, OntologyRepository
from domain.ontology.services import OntologyService
from domain.versioning.bundle_import import BundleImportResult, BundleImportService
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationStatus
from domain.versioning.revert_service import RevertService


def read_bundle(path: Path) -> dict:
    """Read a bundle file and check its header."""
    try:
        bundle = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise BundleError(f"Malformed JSON in {path}: {exc}") from exc
    check_bundle_header(bundle)
    return bundle


def build_bundle_importer(
    session_factory: sessionmaker, embedding_service: EmbeddingService
) -> BundleImportService:
    """
    A BundleImportService wired as in app.py, for a bulk import: every change is
    recorded (so a proposal can be reverted, atomically) and vector indexing is
    deferred to one reindex afterwards.
    """
    shared = SharedSessionFactory(session_factory)
    repo = cast(OntologyRepository, SQLiteOntologyRepository(shared))
    change_repo = SQLiteChangeRepository(shared)
    publisher = InProcessEventPublisher()
    ChangeEventRecorder(change_repo).subscribe_ontology_events(publisher)
    ontology = OntologyService(
        repository=repo,
        embedding_service=embedding_service,
        event_publisher=publisher,
        schema_index=None,
        individual_index=None,
    )
    proposals = ProposalService(
        SQLiteChangeProposalRepository(shared),
        ontology,
        repo,
        RevertService(change_repo, repo, transaction_scope=SqliteTransactionScope(shared)),
        approval_policies=SQLiteApprovalPolicyRepository(shared),
    )
    return BundleImportService(proposals, ontology, repo)


def print_result(result: BundleImportResult) -> None:
    """Print per-kind counts, the proposal and where its operations stand."""
    plan = result.plan
    print(f"Source: {plan.source}")
    if result.taxonomy_created:
        verb = "would be created" if result.dry_run else "created"
        print(f"Taxonomy {plan.taxonomy['identifier']!r} {verb}")
    print(f"{'kind':<14} {'create':>8} {'update':>8} {'delete':>8} {'unchanged':>10}")
    for kind, counts in plan.counts.items():
        print(
            f"{kind:<14} {counts.created:>8} {counts.updated:>8} {counts.deleted:>8}"
            f" {counts.unchanged:>10}"
        )
    if plan.deletes:
        print(f"Deletes proposed (breaking; they wait for review): {len(plan.deletes)}")
        for entry in plan.deletes:
            print(f"  - {entry}")
    proposal = result.proposal
    if not plan.operations:
        print("No changes: the workspace matches the bundle; nothing proposed.")
    elif proposal is None:
        print(f"Dry run: {len(plan.operations)} operations planned (not validated: new taxonomy).")
    else:
        label = "Dry run (not stored)" if result.dry_run else f"Proposal {proposal.id}"
        print(f"{label}: {proposal.title}")
        outcomes = Counter(f"{o.status.value} ({o.scope.value})" for o in proposal.operations)
        for key, count in sorted(outcomes.items()):
            print(f"  {count:5d}  {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to the bundle JSON file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="Also apply every non-breaking operation"
    )
    mode.add_argument(
        "--dry-run", action="store_true", help="Plan and validate only; store nothing"
    )
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
    importer = build_bundle_importer(session_factory, embedding_service)

    print(f"Importing bundle {args.bundle} into {settings.database.local_db_path} ...")
    try:
        result = importer.import_bundle(
            bundle, apply=args.apply, dry_run=args.dry_run, file_name=args.bundle.name
        )
    except ProposalValidationError as exc:
        print(f"Not proposed; {len(exc.errors)} operations are invalid:", file=sys.stderr)
        for error in exc.errors:
            seq = f"seq {error.seq}" if error.seq is not None else "proposal"
            print(f"  - {seq}: {error.code}: {error.message}", file=sys.stderr)
        return 1
    except (BundleError, OntologyError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print_result(result)

    applied = result.proposal is not None and any(
        o.status is OperationStatus.APPLIED for o in result.proposal.operations
    )
    if applied and not result.dry_run:
        print("Reindexing individual and schema vector indexes ...")
        individuals = SqliteIndividualVectorIndex(
            session_factory, embedding_service
        ).reindex_all_individuals()
        schema = SqliteSchemaVectorIndex(session_factory, embedding_service).reindex_all()
        print(f"Indexed {individuals} individuals; reindexed {schema} schema entities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
