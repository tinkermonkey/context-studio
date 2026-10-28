#!/usr/bin/env python
"""
Propose a Documentation Robotics reflection plan (`dr-reflection-plan/1`) as a
change proposal on the `dr_spec` taxonomy, for review in Context Studio.

Requires the DR spec ontology (`import_dr_ontology.py`). Nothing in the
ontology changes: the operations wait as pending until someone applies or
rejects them. Operations that don't resolve against the workspace (an unknown
relationship id or spec node) are listed and nothing is proposed. Export the
decisions afterwards with `export_dr_decisions.py`.

Usage (from local-server/, venv active):
    python scripts/import_dr_reflection_plan.py PLAN.json
"""

import argparse
import os
import sys
from pathlib import Path
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from config import get_config_manager
from domain.ontology.ports import EmbeddingService, OntologyRepository
from domain.ontology.services import OntologyService
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.revert_service import RevertService
from scripts.dr_reflection_plan import PlanError, import_reflection_plan, read_plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="Path to the dr-reflection-plan/1 JSON file")
    args = parser.parse_args()

    try:
        plan = read_plan(args.plan)
    except (OSError, ValueError) as exc:
        print(f"Cannot read plan: {exc}", file=sys.stderr)
        return 1

    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()
    repo = cast(OntologyRepository, SQLiteOntologyRepository(session_factory))
    # Proposing only reads the ontology; no embedding model is needed.
    service = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        OntologyService(repo, cast(EmbeddingService, None), InProcessEventPublisher()),
        repo,
        RevertService(SQLiteChangeRepository(session_factory), repo),
    )

    try:
        proposal = import_reflection_plan(plan, service, repo)
    except PlanError as exc:
        print(f"Not proposed; {len(exc.problems)} operations don't resolve:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    except ProposalValidationError as exc:
        print(f"Not proposed; {len(exc.errors)} operations are invalid:", file=sys.stderr)
        for error in exc.errors:
            seq = f"seq {error.seq}" if error.seq is not None else "proposal"
            print(f"  - {seq}: {error.code}: {error.message}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for operation in proposal.operations:
        key = f"{operation.op.value} ({operation.scope.value})"
        counts[key] = counts.get(key, 0) + 1
    print(f"Proposed {proposal.id}: {proposal.title}")
    for key, count in sorted(counts.items()):
        print(f"  {count:4d}  {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
