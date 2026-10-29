#!/usr/bin/env python
"""
Write the decisions on a DR reflection-plan proposal for DR's
`proposal-import.ts --decisions`: a JSON array of
`{seq, op_id, status, fields?, reason, result_entity_id}`, one per operation,
joined to DR's plan by seq. `fields` appears on an operation a reviewer edited
before applying it: the applied triple `{predicate, source_spec_node_id,
destination_spec_node_id}`. Pending operations are written as "pending", which
DR skips. A reverted proposal is refused: none of its decisions stand.

Usage (from local-server/, venv active):
    python scripts/export_dr_decisions.py PROPOSAL_ID OUT.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from config import get_config_manager
from scripts.dr_reflection_plan import decisions_for


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal_id", help="The change proposal's id")
    parser.add_argument("out", type=Path, help="Where to write the decisions JSON")
    args = parser.parse_args()

    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    proposal = SQLiteChangeProposalRepository(db_manager.get_local_session_factory()).get(
        args.proposal_id
    )
    if proposal is None:
        print(f"No change proposal {args.proposal_id}", file=sys.stderr)
        return 1
    try:
        decisions = decisions_for(proposal)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    args.out.write_text(json.dumps(decisions, indent=2) + "\n")
    counts: dict[str, int] = {}
    for decision in decisions:
        counts[decision["status"]] = counts.get(decision["status"], 0) + 1
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    print(f"Wrote {len(decisions)} decisions ({summary}) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
