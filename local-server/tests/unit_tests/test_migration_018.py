# mypy: ignore-errors
"""
Unit tests for Migration 018 - Add attributes column.

Tests the addition of attributes column to the structure_nodes table,
including schema validation, data preservation, and rollback functionality.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: E501
)

import pytest  # noqa: E402
import tempfile  # noqa: E402
import json  # noqa: E402
from typing import Dict, List  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from database.migrations.migration_manager import MigrationManager  # noqa: E402, E501
from database.utils import init_db  # noqa: E402


class MigrationTestHarness:
    """Test harness for migration testing with snapshot capabilities."""

    def __init__(self):
        self.db_path = None
        self.engine = None
        self.connection = None
        self.migration_manager = None

    def setup_test_database(self) -> str:
        """Create a fresh test database and return the path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            self.db_path = tf.name

        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(db_url)

        # Initialize with base schema
        init_db(engine=self.engine)

        # Use the migration manager to apply migrations up to 017
        self.migration_manager = MigrationManager(self.db_path)

        # Temporarily modify the discovered migrations to exclude 018
        original_discover = self.migration_manager._discover_migrations

        def discover_migrations_up_to_17():
            all_migrations = original_discover()
            return [m for m in all_migrations if m.version <= 17]

        # Monkey patch to exclude migration 018
        self.migration_manager._discover_migrations = discover_migrations_up_to_17  # noqa: E501

        # Apply migrations 1-17
        success = self.migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError("Failed to apply migrations 1-17")

        # Restore original method
        self.migration_manager._discover_migrations = original_discover

        return self.db_path

    def get_connection(self):
        """Get a raw database connection."""
        if not self.connection:
            self.connection = self.engine.raw_connection()
        return self.connection

    def create_test_structure_nodes(self):
        """Create test structure_nodes with various node types."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Create a layer
            cursor.execute(
                """
                INSERT INTO structure_nodes (id, node_type, title, definition, created_at, version, last_modified)  # noqa: E501
                VALUES
                    ('node-1', 'layer', 'Test Layer', 'Test layer definition', '2023-01-01 10:00:00', 1, '2023-01-01 10:00:00')  # noqa: E501
            """
            )

            # Create a domain
            cursor.execute(
                """
                INSERT INTO structure_nodes (id, node_type, parent_node_id, title, definition, created_at, version, last_modified)  # noqa: E501
                VALUES
                    ('node-2', 'domain', 'node-1', 'Test Domain', 'Test domain definition', '2023-01-02 10:00:00', 1, '2023-01-02 10:00:00')  # noqa: E501
            """
            )

            # Create terms
            cursor.execute(
                """
                INSERT INTO structure_nodes (id, node_type, parent_node_id, title, definition, created_at, version, last_modified)  # noqa: E501
                VALUES
                    ('node-3', 'term', 'node-2', 'Bank', 'Financial institution', '2023-01-03 10:00:00', 1, '2023-01-03 10:00:00'),  # noqa: E501
                    ('node-4', 'term', 'node-2', 'River Bank', 'Edge of a river', '2023-01-04 10:00:00', 1, '2023-01-04 10:00:00')  # noqa: E501
            """
            )

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def verify_column_exists(self, table_name: str, column_name: str) -> bool:
        """Verify that a column exists in a table."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            return column_name in columns
        finally:
            cursor.close()

    def get_column_type(self, table_name: str, column_name: str) -> str:
        """Get the type of a column."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            for row in cursor.fetchall():
                if row[1] == column_name:
                    return row[2]  # Type is the third column
            return None
        finally:
            cursor.close()

    def run_migration_018(self):
        """Run migration 018."""
        migrations = self.migration_manager._discover_migrations()
        migration_018 = next((m for m in migrations if m.version == 18), None)

        if not migration_018:
            raise RuntimeError("Migration 018 not found")

        # Use the migration manager's built-in mechanism
        with self.engine.connect() as conn:
            with conn.begin():
                migration_018.up(conn)

                # Record in schema history
                conn.execute(
                    text(
                        """
                    INSERT INTO schema_history (version, description, migration_file, checksum, execution_time_ms)  # noqa: E501
                    VALUES (:version, :description, :migration_file, :checksum, :execution_time_ms)  # noqa: E501
                """
                    ),
                    {
                        "version": migration_018.version,
                        "description": migration_018.description,
                        "migration_file": "018_add_attributes.py",
                        "checksum": "test",
                        "execution_time_ms": 0,
                    },
                )

        # Update current version manually
        self.migration_manager.current_version = 18

    def rollback_migration_018(self):
        """Rollback migration 018."""
        migrations = self.migration_manager._discover_migrations()
        migration_018 = next((m for m in migrations if m.version == 18), None)

        if not migration_018:
            raise RuntimeError("Migration 018 not found")

        with self.engine.connect() as conn:
            with conn.begin():
                migration_018.down(conn)
                # Remove from schema_history
                conn.execute(text("DELETE FROM schema_history WHERE version = 18"))  # noqa: E501

        # Update current version
        self.migration_manager.current_version = 17

    def insert_node_with_attributes(self, node_id: str, attributes: List[Dict]):  # noqa: E501
        """Insert a structure_node with attributes."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO structure_nodes
                (id, node_type, title, definition, attributes, created_at, version, last_modified)  # noqa: E501
                VALUES (?, ?, ?, ?, ?, datetime('now'), 1, datetime('now'))
            """,
                (
                    node_id,
                    'term',
                    'Test Node',
                    'Test definition',
                    json.dumps(attributes)
                )
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def update_node_attributes(self, node_id: str, attributes: List[Dict] = None):  # noqa: E501
        """Update attributes for a structure_node."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if attributes is not None:
                cursor.execute(
                    "UPDATE structure_nodes SET attributes = ? WHERE id = ?",
                    (json.dumps(attributes), node_id)
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def get_node_attributes(self, node_id: str) -> List[Dict]:
        """Get attributes for a structure_node."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT attributes FROM structure_nodes WHERE id = ?",
                (node_id,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
        finally:
            cursor.close()

    def get_structure_nodes_count(self) -> int:
        """Get count of structure_nodes."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM structure_nodes")
            return cursor.fetchone()[0]
        finally:
            cursor.close()

    def cleanup(self):
        """Clean up test resources."""
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()
        if self.db_path and os.path.exists(self.db_path):
            os.unlink(self.db_path)


@pytest.fixture
def migration_harness():
    """Provide a migration test harness."""
    harness = MigrationTestHarness()
    harness.setup_test_database()
    yield harness
    harness.cleanup()


class TestMigration018SchemaChanges:
    """Test migration schema changes."""

    def test_migration_adds_attributes_column(self, migration_harness):
        """Test that migration adds attributes column."""
        # Verify column doesn't exist before migration
        assert not migration_harness.verify_column_exists("structure_nodes", "attributes")  # noqa: E501

        # Run migration
        migration_harness.run_migration_018()

        # Verify column exists after migration
        assert migration_harness.verify_column_exists("structure_nodes", "attributes")  # noqa: E501

    def test_attributes_column_type(self, migration_harness):
        """Test that attributes column has correct type."""
        # Run migration
        migration_harness.run_migration_018()

        # Verify column type is TEXT
        column_type = migration_harness.get_column_type("structure_nodes", "attributes")  # noqa: E501
        assert column_type == "TEXT"


class TestMigration018DataPreservation:
    """Test that migration preserves existing data."""

    def test_migration_preserves_existing_nodes(self, migration_harness):
        """Test that migration doesn't affect existing structure_nodes."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Get count before migration
        count_before = migration_harness.get_structure_nodes_count()
        assert count_before == 4

        # Run migration
        migration_harness.run_migration_018()

        # Get count after migration
        count_after = migration_harness.get_structure_nodes_count()
        assert count_after == count_before

    def test_migration_preserves_node_data(self, migration_harness):
        """Test that migration preserves all existing node data."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_018()

        # Verify specific node data is preserved
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT id, node_type, title, definition FROM structure_nodes WHERE id = 'node-3'"  # noqa: E501
            )
            node = cursor.fetchone()
            assert node is not None
            assert node[0] == "node-3"
            assert node[1] == "term"
            assert node[2] == "Bank"
            assert node[3] == "Financial institution"
        finally:
            cursor.close()

    def test_existing_nodes_have_null_attributes(self, migration_harness):
        """Test that existing nodes have NULL values for attributes column."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_018()

        # Verify attributes column is NULL for existing nodes
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT attributes FROM structure_nodes WHERE id = 'node-3'"
            )
            row = cursor.fetchone()
            assert row[0] is None  # attributes should be NULL
        finally:
            cursor.close()


class TestMigration018NewColumnFunctionality:
    """Test that new column works correctly."""

    def test_insert_node_with_attributes(self, migration_harness):
        """Test inserting a node with attributes data."""
        # Run migration
        migration_harness.run_migration_018()

        # Insert node with attributes
        attributes = [
            {"key": "source_language", "title": "Source Language", "value_type": "string", "value": "English"},  # noqa: E501
            {"key": "confidence_score", "title": "Confidence Score", "value_type": "number", "value": 0.95}  # noqa: E501
        ]
        migration_harness.insert_node_with_attributes("test-node-1", attributes)  # noqa: E501

        # Verify data was stored correctly
        result = migration_harness.get_node_attributes("test-node-1")
        assert result is not None
        assert result == attributes

    def test_update_existing_node_with_attributes(self, migration_harness):
        """Test updating existing nodes with attributes data."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_018()

        # Update existing node with attributes data
        attributes = [
            {"key": "domain_category", "title": "Domain Category", "value_type": "string", "value": "Finance"}  # noqa: E501
        ]
        migration_harness.update_node_attributes("node-3", attributes)

        # Verify updates
        result = migration_harness.get_node_attributes("node-3")
        assert result is not None
        assert result == attributes

    def test_null_attributes_allowed(self, migration_harness):
        """Test that NULL values are allowed for attributes column."""
        # Run migration
        migration_harness.run_migration_018()

        # Insert node with NULL attributes
        migration_harness.insert_node_with_attributes("test-node-null", None)

        # Verify NULL values
        result = migration_harness.get_node_attributes("test-node-null")
        assert result is None

    def test_empty_json_array_attributes(self, migration_harness):
        """Test that empty JSON arrays are handled correctly."""
        # Run migration
        migration_harness.run_migration_018()

        # Insert node with empty array
        migration_harness.insert_node_with_attributes("test-empty", [])

        # Verify empty array is stored correctly
        result = migration_harness.get_node_attributes("test-empty")
        assert result is not None
        assert result == []


class TestMigration018Rollback:
    """Test migration rollback functionality."""

    def test_rollback_removes_attributes_column(self, migration_harness):
        """Test that rollback removes attributes column."""
        # Run migration
        migration_harness.run_migration_018()
        assert migration_harness.verify_column_exists("structure_nodes", "attributes")  # noqa: E501

        # Rollback migration
        migration_harness.rollback_migration_018()

        # Verify column is removed
        assert not migration_harness.verify_column_exists("structure_nodes", "attributes")  # noqa: E501

    def test_rollback_preserves_existing_data(self, migration_harness):
        """Test that rollback preserves all original data."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Get count before migration
        count_before = migration_harness.get_structure_nodes_count()

        # Run migration and rollback
        migration_harness.run_migration_018()
        migration_harness.rollback_migration_018()

        # Verify count is preserved
        count_after = migration_harness.get_structure_nodes_count()
        assert count_after == count_before

        # Verify specific data is preserved
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT id, node_type, title, definition, parent_node_id FROM structure_nodes WHERE id = 'node-3'"  # noqa: E501
            )
            node = cursor.fetchone()
            assert node is not None
            assert node[0] == "node-3"
            assert node[1] == "term"
            assert node[2] == "Bank"
            assert node[3] == "Financial institution"
            assert node[4] == "node-2"
        finally:
            cursor.close()

    def test_rollback_after_data_insertion(self, migration_harness):
        """Test rollback after inserting data into attributes column."""
        # Create test data
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_018()

        # Add data to attributes column
        attributes = [{"key": "test_key", "title": "Test", "value_type": "string", "value": "test"}]  # noqa: E501
        migration_harness.update_node_attributes("node-3", attributes)

        # Rollback migration
        migration_harness.rollback_migration_018()

        # Verify original data is preserved (without attributes column)
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT id, title FROM structure_nodes WHERE id = 'node-3'"
            )
            node = cursor.fetchone()
            assert node is not None
            assert node[0] == "node-3"
            assert node[1] == "Bank"

            # Verify attributes column doesn't exist
            assert not migration_harness.verify_column_exists("structure_nodes", "attributes")  # noqa: E501
        finally:
            cursor.close()


class TestMigration018EdgeCases:
    """Test edge cases and special scenarios."""

    def test_migration_with_empty_table(self, migration_harness):
        """Test migration on empty structure_nodes table."""
        # Don't create any test data
        count_before = migration_harness.get_structure_nodes_count()
        assert count_before == 0

        # Run migration
        migration_harness.run_migration_018()

        # Verify migration succeeded
        assert migration_harness.verify_column_exists("structure_nodes", "attributes")  # noqa: E501

        # Verify count is still 0
        count_after = migration_harness.get_structure_nodes_count()
        assert count_after == 0

    def test_json_array_storage(self, migration_harness):
        """Test that JSON arrays are stored and retrieved correctly."""
        # Run migration
        migration_harness.run_migration_018()

        # Insert node with complex JSON data
        attributes = [
            {"key": "language", "title": "Language", "value_type": "string", "value": "English"},  # noqa: E501
            {"key": "year", "title": "Year", "value_type": "number", "value": 2023},  # noqa: E501
            {"key": "is_verified", "title": "Is Verified", "value_type": "boolean", "value": True},  # noqa: E501
            {"key": "founding_date", "title": "Founding Date", "value_type": "date", "value": "2023-01-15"},  # noqa: E501
            {"key": "homepage", "title": "Homepage", "value_type": "url", "value": "https://example.com"}  # noqa: E501
        ]
        migration_harness.insert_node_with_attributes("test-json", attributes)

        # Verify JSON arrays are stored and retrieved correctly
        result = migration_harness.get_node_attributes("test-json")
        assert result is not None
        assert len(result) == 5
        assert result[0]['key'] == "language"
        assert result[1]['key'] == "year"
        assert result[2]['key'] == "is_verified"
        assert result[3]['key'] == "founding_date"
        assert result[4]['key'] == "homepage"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
