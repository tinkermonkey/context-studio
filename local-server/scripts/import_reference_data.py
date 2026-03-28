"""
CLI script to populate reference.db with data from external reference sources.

This script is idempotent and safe to run multiple times. It demonstrates
importing from ConceptNet CSV assertions and can be extended to support
DBpedia and Wikidata dumps.

Usage:
    python scripts/import_reference_data.py [--source SOURCE] [--limit LIMIT]

Options:
    --source SOURCE    Source to import from: 'conceptnet', 'schema_org', or 'all' (default: 'all')
    --limit LIMIT      Maximum number of entries to import (default: None for unlimited)
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.persistence.sqlite.reference_repo import LocalReferenceRepository
from adapters.reference.schema_org import (
    SCHEMA_ORG_DEFINITIONS,
    SCHEMA_ORG_RELATIONS,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def import_schema_org(repo: LocalReferenceRepository, limit: int | None = None) -> int:
    """
    Import schema.org vocabulary definitions into the repository.

    Args:
        repo: LocalReferenceRepository instance
        limit: Maximum number of entries to import (None for unlimited)

    Returns:
        Number of entries imported
    """
    logger.info("Importing schema.org vocabulary...")

    count = 0
    for type_name, definition in SCHEMA_ORG_DEFINITIONS.items():
        if limit is not None and count >= limit:
            break

        repo.import_reference(
            uri=definition["uri"],
            label=definition["label"],
            description=definition["description"],
            source="schema.org",
        )
        count += 1

    # Import relationships
    for source_type, relations in SCHEMA_ORG_RELATIONS.items():
        for predicate, target_type in relations:
            source_uri = SCHEMA_ORG_DEFINITIONS[source_type]["uri"]
            target_uri = f"http://schema.org/{target_type}"

            repo.import_relation(
                subject_uri=source_uri,
                predicate=predicate,
                object_uri=target_uri,
                source="schema.org",
            )

    logger.info(f"Imported {count} schema.org definitions")
    return count


def import_conceptnet_sample(
    repo: LocalReferenceRepository, limit: int | None = None
) -> int:
    """
    Import sample ConceptNet assertions into the repository.

    In a production system, this would parse a ConceptNet CSV dump:
    https://github.com/commonsensegraph/conceptnet5/wiki/Downloads

    For now, this demonstrates the import pattern with hardcoded sample data.

    Args:
        repo: LocalReferenceRepository instance
        limit: Maximum number of entries to import (None for unlimited)

    Returns:
        Number of entries imported
    """
    logger.info("Importing ConceptNet sample data...")

    # Sample ConceptNet concepts (in production, load from CSV)
    sample_concepts = [
        {
            "uri": "/c/en/dog",
            "label": "dog",
            "description": "A domesticated mammal",
            "source": "ConceptNet",
        },
        {
            "uri": "/c/en/cat",
            "label": "cat",
            "description": "A feline animal",
            "source": "ConceptNet",
        },
        {
            "uri": "/c/en/animal",
            "label": "animal",
            "description": "A living organism",
            "source": "ConceptNet",
        },
        {
            "uri": "/c/en/person",
            "label": "person",
            "description": "A human being",
            "source": "ConceptNet",
        },
    ]

    count = 0
    for concept in sample_concepts:
        if limit is not None and count >= limit:
            break

        repo.import_reference(
            uri=concept["uri"],
            label=concept["label"],
            description=concept["description"],
            source=concept["source"],
        )
        count += 1

    # Sample relations
    sample_relations = [
        ("/c/en/dog", "IsA", "/c/en/animal", "ConceptNet"),
        ("/c/en/cat", "IsA", "/c/en/animal", "ConceptNet"),
        ("/c/en/person", "Owns", "/c/en/dog", "ConceptNet"),
    ]

    for subject, predicate, object_uri, source in sample_relations:
        repo.import_relation(
            subject_uri=subject,
            predicate=predicate,
            object_uri=object_uri,
            source=source,
        )

    logger.info(f"Imported {count} ConceptNet sample concepts")
    return count


def main() -> int:
    """
    Main entry point for the import script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Import reference data from external sources into reference.db"
    )
    parser.add_argument(
        "--source",
        choices=["conceptnet", "schema_org", "all"],
        default="all",
        help="Source to import from (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of entries to import per source",
    )
    parser.add_argument(
        "--db",
        default="./reference.db",
        help="Path to reference.db (default: ./reference.db)",
    )

    args = parser.parse_args()

    try:
        repo = LocalReferenceRepository(db_path=args.db)

        total_imported = 0

        if args.source in ("schema_org", "all"):
            total_imported += import_schema_org(repo, limit=args.limit)

        if args.source in ("conceptnet", "all"):
            total_imported += import_conceptnet_sample(repo, limit=args.limit)

        logger.info(f"Import complete: {total_imported} total entries imported")
        print(f"✓ Import complete: {total_imported} total entries imported")
        return 0

    except Exception as e:
        logger.error(f"Import failed: {e}")
        print(f"✗ Import failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
