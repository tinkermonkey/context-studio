"""
Export a workspace taxonomy as a Context Studio bundle (v0).

The inverse of scripts/import_bundle.py (see domain/interchange/bundle.py for
the format): loading the exported bundle back into the same workspace changes
nothing. Read-only.

Usage (from local-server/, venv active):
    python scripts/export_bundle.py TAXONOMY [--source SOURCE] [--output PATH]

TAXONOMY is the taxonomy's identifier or id. SOURCE defaults to the taxonomy's
identifier. Without --output the bundle is written to stdout.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from config import get_config_manager
from domain.interchange.bundle import BundleError, BundleExporter
from domain.ontology.entities import Taxonomy
from domain.ontology.ports import OntologyRepository


def taxonomy_id_for(repo: OntologyRepository, taxonomy: str) -> str:
    """Resolve a taxonomy identifier to its id; anything else is taken as an id."""
    entity = repo.get_by_identifier(taxonomy)
    return entity.id if isinstance(entity, Taxonomy) else taxonomy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("taxonomy", help="Taxonomy identifier or id")
    parser.add_argument("--source", help="Bundle source (default: the taxonomy identifier)")
    parser.add_argument("--output", type=Path, help="Write the bundle here instead of stdout")
    args = parser.parse_args()

    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    repo = cast(
        OntologyRepository, SQLiteOntologyRepository(db_manager.get_local_session_factory())
    )
    try:
        bundle = BundleExporter(repo).export(taxonomy_id_for(repo, args.taxonomy), args.source)
    except BundleError as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text)
        print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
