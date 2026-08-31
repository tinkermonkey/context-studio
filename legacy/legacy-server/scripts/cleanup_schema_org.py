# mypy: ignore-errors
#!/usr/bin/env python3
"""
Cleanup script to remove old Schema.org data before re-importing with refactored importer.

This script:
1. Deletes all Schema.org ReferenceNodes (old data)
2. Deletes all Schema.org ExternalPredicates (if any exist)
3. Deletes all Schema.org ReferenceLinks
4. Drops the vec table (will be recreated on import)

Run this before running the Schema.org import with the refactored importer.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.models import ExternalPredicate, ReferenceLink, ReferenceNode
from sqlalchemy import text
from utils.logger import get_logger

logger = get_logger(__name__)

SOURCE_NAME = "schema.org"


def cleanup_schema_org_data(db_path: str | None = None):
    """
    Clean up all Schema.org data from the database.

    Args:
        db_path: Optional path to database file. If None, uses default.
    """
    logger.info("Starting Schema.org data cleanup")

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path)

    try:
        # Count existing data
        node_count = (
            manager.session.query(ReferenceNode).filter_by(source=SOURCE_NAME).count()
        )
        predicate_count = (
            manager.session.query(ExternalPredicate)
            .filter_by(source=SOURCE_NAME)
            .count()
        )

        # Note: ReferenceLinks don't have a source field, but we can identify Schema.org links
        # by checking if they reference Schema.org nodes
        schema_node_ids = [
            n.id
            for n in manager.session.query(ReferenceNode.id)
            .filter_by(source=SOURCE_NAME)
            .all()
        ]
        link_count = 0
        if schema_node_ids:
            link_count = (
                manager.session.query(ReferenceLink)
                .filter(
                    (ReferenceLink.subject_node.in_(schema_node_ids))
                    | (ReferenceLink.object_node.in_(schema_node_ids))
                )
                .count()
            )

        logger.info(f"Found {node_count} Schema.org nodes")
        logger.info(f"Found {predicate_count} Schema.org predicates")
        logger.info(f"Found {link_count} Schema.org links")

        if node_count == 0 and predicate_count == 0 and link_count == 0:
            logger.info("No Schema.org data found. Nothing to clean up.")
            return

        # Delete links first (foreign key constraints)
        if link_count > 0:
            logger.info("Deleting Schema.org links...")
            manager.session.query(ReferenceLink).filter(
                (ReferenceLink.subject_node.in_(schema_node_ids))
                | (ReferenceLink.object_node.in_(schema_node_ids))
            ).delete(synchronize_session=False)
            manager.session.commit()
            logger.info(f"Deleted {link_count} links")

        # Delete nodes
        if node_count > 0:
            logger.info("Deleting Schema.org nodes...")
            manager.session.query(ReferenceNode).filter_by(source=SOURCE_NAME).delete()
            manager.session.commit()
            logger.info(f"Deleted {node_count} nodes")

        # Delete predicates
        if predicate_count > 0:
            logger.info("Deleting Schema.org predicates...")
            manager.session.query(ExternalPredicate).filter_by(
                source=SOURCE_NAME
            ).delete()
            manager.session.commit()
            logger.info(f"Deleted {predicate_count} predicates")

        # Drop vec table (will be recreated on import)
        try:
            logger.info("Dropping vec table...")
            manager.session.execute(text("DROP TABLE IF EXISTS reference_nodes_vec"))
            manager.session.commit()
            logger.info("Vec table dropped")
        except Exception as e:
            logger.warning(f"Failed to drop vec table (may not exist): {e}")
            manager.session.rollback()

        logger.info("✅ Schema.org data cleanup complete!")
        logger.info(
            "You can now run the Schema.org import with the refactored importer."
        )

    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        manager.session.rollback()
        raise
    finally:
        manager.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean up old Schema.org data")
    parser.add_argument(
        "--db-path",
        type=str,
        help="Path to database file (optional, uses default if not provided)",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    if not args.yes:
        print("⚠️  This will delete all Schema.org data from the database.")
        print("   - All Schema.org ReferenceNodes")
        print("   - All Schema.org ExternalPredicates")
        print("   - All Schema.org ReferenceLinks")
        print("   - The vec table")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            print("Cleanup cancelled.")
            sys.exit(0)

    try:
        cleanup_schema_org_data(args.db_path)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)
