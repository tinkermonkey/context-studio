"""Test migration system functionality."""

import os
import tempfile
import shutil

# Add the project root to the path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.migrations.migration_manager import MigrationManager


def test_migration_system():
    """Test the migration system."""
    # Create temporary database file
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    try:
        print(f"Testing migrations with database: {db_path}")

        # Initialize migration manager
        manager = MigrationManager(db_path)

        # Check initial status
        print("\nInitial migration status:")
        status = manager.get_migration_status()
        print(f"Current version: {status.current_version}")
        print(f"Target version: {status.target_version}")
        print(f"Needs migration: {status.needs_migration}")
        print(f"Pending migrations: {status.pending_migrations}")

        # Apply migrations
        if status.needs_migration:
            print("\nApplying migrations...")
            success = manager.migrate_to_latest()
            print(f"Migration successful: {success}")

            # Check status after migration
            print("\nPost-migration status:")
            status = manager.get_migration_status()
            print(f"Current version: {status.current_version}")
            print(f"Needs migration: {status.needs_migration}")

        print("\nMigration system test completed successfully!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_migration_system()
