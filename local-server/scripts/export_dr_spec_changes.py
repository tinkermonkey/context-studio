#!/usr/bin/env python
"""
Write a decided change proposal's DR relationship-type and node-type changes
for DR's `cli/scripts/spec-enrich/cs-decisions-to-spec.ts`, which writes them
into `spec/schemas/relationships/**` and `spec/schemas/nodes/**`.

Works for any proposal on the DR spec, reflection plan or not: every applied
create, update and delete of a DR relationship type, and every applied
create, update, move and delete of a DR node type, with the values it
applied (format `cs-dr-spec-changes/1`; see `adapters/interchange/dr_spec_changes.py`).
A reverted proposal is refused. For a reflection plan, `export_dr_decisions.py`
still writes the seq-joined decisions DR's `proposal-import.ts` reads.

Order matters: export, land the change in DR's spec, then re-import the spec
(`import_dr_ontology.py`). A re-import before DR has the change sets the
relationship types back to what the spec says, attributes included.

Usage (from local-server/, venv active):
    python scripts/export_dr_spec_changes.py PROPOSAL_ID OUT.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.interchange.dr_spec_changes import spec_changes_for
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from config import get_config_manager
from domain.versioning.gold import DecisionFilter, by_operation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal_id", help="The change proposal's id")
    parser.add_argument("out", type=Path, help="Where to write the spec changes JSON")
    args = parser.parse_args()

    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()
    proposals = SQLiteChangeProposalRepository(session_factory)
    proposal = proposals.get(args.proposal_id)
    if proposal is None:
        print(f"No change proposal {args.proposal_id}", file=sys.stderr)
        return 1
    decisions = by_operation(
        proposals.list_decisions(DecisionFilter(proposal_id=proposal.id, include_superseded=True))
    )
    try:
        document = spec_changes_for(proposal, SQLiteOntologyRepository(session_factory), decisions)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    args.out.write_text(json.dumps(document, indent=2) + "\n")
    print(
        f"Wrote {len(document['changes'])} relationship type changes "
        f"({_counts(document['changes'])}) and {len(document['node_changes'])} node type "
        f"changes ({_counts(document['node_changes'])}) to {args.out}; "
        f"{len(document['skipped'])} operations skipped"
    )
    for item in document["skipped"]:
        print(f"  skipped seq {item['seq']}: {item['why']}")
    return 0


def _counts(changes: list[dict]) -> str:
    """'2 create, 1 delete': how many changes of each op."""
    counts: dict[str, int] = {}
    for change in changes:
        counts[change["op"]] = counts.get(change["op"], 0) + 1
    return ", ".join(f"{count} {op}" for op, count in sorted(counts.items())) or "none"


if __name__ == "__main__":
    raise SystemExit(main())
