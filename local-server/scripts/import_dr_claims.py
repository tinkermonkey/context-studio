"""
Import DR's split claims and triage bench gold into the dr_spec taxonomy (#1521).

Reads DR's `claims.jsonl` (optionally xz-compressed) and `bench-gold.jsonl`,
maps DR spec ids to the workspace's entities, stores the claims (replacing
earlier imports by key) and records the gold as verdicts. Defaults to the
snapshots committed under tests/integration/fixtures/dr_triage/.

Usage (from local-server/, with the DR spec already imported):

    python scripts/import_dr_claims.py
    python scripts/import_dr_claims.py --claims PATH --gold PATH
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.interchange.dr_claims import import_dr_claims, read_jsonl
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from config import get_config_manager
from domain.versioning.claims import ClaimService

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "integration" / "fixtures" / "dr_triage"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--claims", type=Path, help="DR's claims.jsonl (default: the committed snapshot)"
    )
    parser.add_argument(
        "--gold",
        type=Path,
        help="DR's bench-gold.jsonl (default: the committed snapshot, only with its claims)",
    )
    parser.add_argument("--no-gold", action="store_true", help="Import claims only")
    args = parser.parse_args()
    if args.claims is None:
        args.claims = FIXTURES / "claims.jsonl.xz"
        if args.gold is None:
            # The snapshots are a pair; gold keys are positions in that split
            args.gold = FIXTURES / "bench-gold.jsonl"
    if args.no_gold:
        args.gold = None
    return args


def main() -> int:
    args = parse_args()
    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()
    repo = SQLiteOntologyRepository(session_factory)
    service = ClaimService(SQLiteClaimRepository(session_factory), repo)
    try:
        result = import_dr_claims(
            service, repo, read_jsonl(args.claims), read_jsonl(args.gold) if args.gold else []
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Claims stored: {result.claims}")
    print(
        f"References: {result.references}, {result.unresolved_references} unresolved"
        f" ({len(result.unresolved)} distinct DR ids matched no entity)"
    )
    for ref in result.unresolved:
        print(f"  - {ref}")
    if result.unresolved_subjects:
        print(f"Subjects that matched no class: {', '.join(result.unresolved_subjects)}")
    print(f"Verdicts from bench gold: {result.verdicts}")
    if result.gold_without_claim:
        print(f"Gold rows with no claim: {', '.join(result.gold_without_claim)}")
    if result.gold_on_changed_claims:
        print(
            "Gold not applied, the claim's text changed in this import: "
            + ", ".join(result.gold_on_changed_claims)
        )
    if result.gold_under_person_verdicts:
        print(
            "Gold not applied over a person's verdict: "
            + ", ".join(result.gold_under_person_verdicts)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
