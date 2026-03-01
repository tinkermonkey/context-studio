#!/usr/bin/env python3
"""
Repair script for Migration 006 - fixes databases where migration 006 was marked as complete
but the data migration from legacy tables to structure_nodes failed.

This script:
1. Checks if migration 006 was completed
2. Verifies if legacy tables still exist
3. Re-runs the data migration if legacy tables have data but structure_nodes is empty
4. Does not modify the migration version (since 006 was already marked complete)
"""

import sys
import os
import sqlite3
import argparse
import logging

# Add the parent directory to the path so we can import from the project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
import importlib.util

# Import the migration module dynamically since it starts with a number
spec = importlib.util.spec_from_file_location("migration_006_nodes",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "database", "migrations", "versions", "006_nodes.py"))
migration_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration_module)
Migration006 = migration_module.Migration006

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_migration_status(db_path: str) -> bool:
    """Check if migration 006 is marked as complete."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Try different table names for migration tracking
            try:
                cursor.execute("SELECT version FROM schema_history WHERE version = 6")
                result = cursor.fetchone()
                return result is not None
            except sqlite3.OperationalError:
                # Fallback to older table name
                cursor.execute("SELECT version FROM migration_versions WHERE version = 6")
                result = cursor.fetchone()
                return result is not None
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        return False

def analyze_database(db_path: str) -> dict:
    """Analyze the database to understand the migration state."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check if legacy tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('layers', 'domains', 'terms')")
            legacy_tables = [row[0] for row in cursor.fetchall()]

            # Check if new tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('structure_nodes', 'structure_node_links')")
            new_tables = [row[0] for row in cursor.fetchall()]

            # Count records in legacy tables
            legacy_counts = {}
            for table in legacy_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                legacy_counts[table] = cursor.fetchone()[0]

            # Count records in new tables
            new_counts = {}
            for table in new_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                new_counts[table] = cursor.fetchone()[0]

            return {
                'legacy_tables': legacy_tables,
                'new_tables': new_tables,
                'legacy_counts': legacy_counts,
                'new_counts': new_counts
            }
    except Exception as e:
        logger.error(f"Error analyzing database: {e}")
        return {}

def needs_repair(analysis: dict) -> bool:
    """Determine if the database needs repair."""
    # Check if we have legacy data but missing structure_nodes data
    total_legacy = sum(analysis.get('legacy_counts', {}).values())
    structure_nodes_count = analysis.get('new_counts', {}).get('structure_nodes', 0)

    return total_legacy > 0 and structure_nodes_count == 0

def repair_database(db_path: str) -> bool:
    """Repair the database by re-running the data migration."""
    try:
        logger.info(f"Starting repair for database: {db_path}")

        # Create SQLAlchemy engine
        engine = create_engine(f"sqlite:///{db_path}")

        # Create migration instance
        migration = Migration006()

        with engine.connect() as connection:
            # Re-run only the data migration methods
            logger.info("Re-running data migration...")

            migration._migrate_layers_to_structure_nodes(connection)
            migration._migrate_domains_to_structure_nodes(connection)
            migration._migrate_terms_to_structure_nodes(connection)
            migration._migrate_term_relationships_to_structure_node_links(connection)

            # Populate vector embeddings if the table exists
            try:
                migration._populate_vector_embeddings(connection)
            except Exception as e:
                logger.warning(f"Vector embeddings population failed: {e}")

            # Validate the repair
            structure_nodes_count = connection.execute(text("SELECT COUNT(*) FROM structure_nodes")).scalar()
            structure_node_links_count = connection.execute(text("SELECT COUNT(*) FROM structure_node_links")).scalar()

            logger.info(f"Repair completed: {structure_nodes_count} structure_nodes, {structure_node_links_count} structure_node_links")

            # Commit the changes
            connection.commit()

        return True

    except Exception as e:
        logger.error(f"Error repairing database: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Repair Migration 006 data migration issues")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't make changes")
    parser.add_argument("--force", action="store_true", help="Force repair even if migration 006 wasn't completed")

    args = parser.parse_args()

    db_path = args.db_path

    # Check if database file exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        sys.exit(1)

    # Check migration status
    migration_complete = check_migration_status(db_path)
    logger.info(f"Migration 006 status: {'Complete' if migration_complete else 'Not complete'}")

    if not migration_complete and not args.force:
        logger.error("Migration 006 is not marked as complete. Use --force to repair anyway.")
        sys.exit(1)

    # Analyze the database
    analysis = analyze_database(db_path)
    if not analysis:
        logger.error("Failed to analyze database")
        sys.exit(1)

    logger.info(f"Legacy tables: {analysis['legacy_tables']}")
    logger.info(f"Legacy counts: {analysis['legacy_counts']}")
    logger.info(f"New tables: {analysis['new_tables']}")
    logger.info(f"New counts: {analysis['new_counts']}")

    # Check if repair is needed
    repair_needed = needs_repair(analysis)
    logger.info(f"Repair needed: {repair_needed}")

    if not repair_needed:
        logger.info("Database appears to be in good condition, no repair needed")
        sys.exit(0)

    if args.dry_run:
        logger.info("Dry run mode: Would repair this database")
        sys.exit(0)

    # Perform the repair
    success = repair_database(db_path)
    if success:
        logger.info("Repair completed successfully")
        sys.exit(0)
    else:
        logger.error("Repair failed")
        sys.exit(1)

if __name__ == "__main__":
    main()