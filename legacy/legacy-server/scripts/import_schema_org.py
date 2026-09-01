#!/usr/bin/env python3
"""
Script to import Schema.org data using the refactored SchemaOrgImporter.

This script runs the complete Schema.org import pipeline:
1. Downloads Schema.org JSON-LD
2. Parses into Classes (entities) and Properties (predicates)
3. Generates embeddings for all items
4. Inserts Classes as ReferenceNodes
5. Inserts Properties as ExternalPredicates
6. Creates vec0 virtual table for semantic search
7. Extracts and inserts metadata relationships
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.schema_org_importer import SchemaOrgImporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main():
    """Run Schema.org import."""
    logger.info("=" * 80)
    logger.info("Starting Schema.org Import")
    logger.info("=" * 80)

    try:
        # Initialize config and manager
        config = ReferenceConfig()
        manager = ReferenceManager(config)

        logger.info(f"Database: {manager.db_path}")
        logger.info(f"Schema.org URL: {config.schema_org_api_url}")
        logger.info("")

        # Create importer
        importer = SchemaOrgImporter(config, manager)

        # Run import with default batch size (200)
        # You can adjust batch_size if needed: importer.import_schema_org(batch_size=500)
        result = importer.import_schema_org()

        # Print results
        logger.info("")
        logger.info("=" * 80)
        logger.info("Import Complete!")
        logger.info("=" * 80)
        logger.info(
            f"Entities imported: {result['entities_imported']} (stored as ReferenceNodes)"
        )
        logger.info(
            f"Properties imported: {result['properties_imported']} (stored as ExternalPredicates)"
        )
        logger.info(
            f"Links imported: {result['links_imported']} (subClassOf relationships)"
        )
        logger.info(f"Timestamp: {result['timestamp']}")
        logger.info("")
        logger.info("Next steps:")
        logger.info(
            "1. Test predicate discovery: curl -X POST 'http://localhost:8000/api/predicates/discover?sources=schema_org'"
        )
        logger.info(
            "2. View predicates in UI: Navigate to External Predicates tab and filter by 'schema.org'"
        )

        return 0

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        logger.error("")
        logger.error("Troubleshooting tips:")
        logger.error("- Check that the Schema.org URL is accessible")
        logger.error("- Verify database permissions")
        logger.error("- Check available disk space")
        logger.error("- Review the full error trace above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
