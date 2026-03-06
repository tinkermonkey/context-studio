# mypy: ignore-errors
"""
Unit tests for Migration 017 - Add reference_links and word_senses columns.

Tests the addition of reference_links and word_senses columns to the structure_nodes table,  # noqa: E501
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

        # Use the migration manager to apply migrations up to 016
        self.migration_manager = MigrationManager(self.db_path)

        # Temporarily modify the discovered migrations to exclude 017
        original_discover = self.migration_manager._discover_migrations

        def discover_migrations_up_to_16():
            all_migrations = original_discover()
            return [m for m in all_migrations if m.version <= 16]

        # Monkey patch to exclude migration 017
        self.migration_manager._discover_migrations = discover_migrations_up_to_16  # noqa: E501

        # Apply migrations 1-16
        success = self.migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError("Failed to apply migrations 1-16")

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

    def run_migration_017(self):
        """Run migration 017."""
        migrations = self.migration_manager._discover_migrations()
        migration_017 = next((m for m in migrations if m.version == 17), None)

        if not migration_017:
            raise RuntimeError("Migration 017 not found")

        # Use the migration manager's built-in mechanism
        with self.engine.connect() as conn:
            with conn.begin():
                migration_017.up(conn)

                # Record in schema history
                conn.execute(
                    text(
                        """
                    INSERT INTO schema_history (version, description, migration_file, checksum, execution_time_ms)  # noqa: E501
                    VALUES (:version, :description, :migration_file, :checksum, :execution_time_ms)  # noqa: E501
                """
                    ),
                    {
                        "version": migration_017.version,
                        "description": migration_017.description,
                        "migration_file": "017_add_reference_links.py",
                        "checksum": "test",
                        "execution_time_ms": 0,
                    },
                )

        # Update current version manually
        self.migration_manager.current_version = 17

    def rollback_migration_017(self):
        """Rollback migration 017."""
        migrations = self.migration_manager._discover_migrations()
        migration_017 = next((m for m in migrations if m.version == 17), None)

        if not migration_017:
            raise RuntimeError("Migration 017 not found")

        with self.engine.connect() as conn:
            with conn.begin():
                migration_017.down(conn)
                # Remove from schema_history
                conn.execute(text("DELETE FROM schema_history WHERE version = 17"))  # noqa: E501

        # Update current version
        self.migration_manager.current_version = 16

    def insert_node_with_new_columns(self, node_id: str, reference_links: List[Dict], word_senses: List[Dict]):  # noqa: E501
        """Insert a structure_node with reference_links and word_senses."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO structure_nodes
                (id, node_type, title, definition, reference_links, word_senses, created_at, version, last_modified)  # noqa: E501
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), 1, datetime('now'))
            """,
                (
                    node_id,
                    'term',
                    'Test Node',
                    'Test definition',
                    json.dumps(reference_links),
                    json.dumps(word_senses)
                )
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def update_node_columns(self, node_id: str, reference_links: List[Dict] = None, word_senses: List[Dict] = None):  # noqa: E501
        """Update reference_links and/or word_senses for a structure_node."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            updates = []
            params = []

            if reference_links is not None:
                updates.append("reference_links = ?")
                params.append(json.dumps(reference_links))

            if word_senses is not None:
                updates.append("word_senses = ?")
                params.append(json.dumps(word_senses))

            if updates:
                params.append(node_id)
                cursor.execute(
                    f"UPDATE structure_nodes SET {', '.join(updates)} WHERE id = ?",  # noqa: E501
                    params
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def get_node_columns(self, node_id: str) -> Dict:
        """Get reference_links and word_senses for a structure_node."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT reference_links, word_senses FROM structure_nodes WHERE id = ?",  # noqa: E501
                (node_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'reference_links': json.loads(row[0]) if row[0] else None,
                    'word_senses': json.loads(row[1]) if row[1] else None
                }
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


class TestMigration017SchemaChanges:
    """Test migration schema changes."""

    def test_migration_adds_reference_links_column(self, migration_harness):
        """Test that migration adds reference_links column."""
        # Verify column doesn't exist before migration
        assert not migration_harness.verify_column_exists("structure_nodes", "reference_links")  # noqa: E501

        # Run migration
        migration_harness.run_migration_017()

        # Verify column exists after migration
        assert migration_harness.verify_column_exists("structure_nodes", "reference_links")  # noqa: E501

    def test_migration_adds_word_senses_column(self, migration_harness):
        """Test that migration adds word_senses column."""
        # Verify column doesn't exist before migration
        assert not migration_harness.verify_column_exists("structure_nodes", "word_senses")  # noqa: E501

        # Run migration
        migration_harness.run_migration_017()

        # Verify column exists after migration
        assert migration_harness.verify_column_exists("structure_nodes", "word_senses")  # noqa: E501

    def test_reference_links_column_type(self, migration_harness):
        """Test that reference_links column has correct type."""
        # Run migration
        migration_harness.run_migration_017()

        # Verify column type is TEXT
        column_type = migration_harness.get_column_type("structure_nodes", "reference_links")  # noqa: E501
        assert column_type == "TEXT"

    def test_word_senses_column_type(self, migration_harness):
        """Test that word_senses column has correct type."""
        # Run migration
        migration_harness.run_migration_017()

        # Verify column type is TEXT
        column_type = migration_harness.get_column_type("structure_nodes", "word_senses")  # noqa: E501
        assert column_type == "TEXT"


class TestMigration017DataPreservation:
    """Test that migration preserves existing data."""

    def test_migration_preserves_existing_nodes(self, migration_harness):
        """Test that migration doesn't affect existing structure_nodes."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Get count before migration
        count_before = migration_harness.get_structure_nodes_count()
        assert count_before == 4

        # Run migration
        migration_harness.run_migration_017()

        # Get count after migration
        count_after = migration_harness.get_structure_nodes_count()
        assert count_after == count_before

    def test_migration_preserves_node_data(self, migration_harness):
        """Test that migration preserves all existing node data."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_017()

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

    def test_existing_nodes_have_null_new_columns(self, migration_harness):
        """Test that existing nodes have NULL values for new columns."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_017()

        # Verify new columns are NULL for existing nodes
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT reference_links, word_senses FROM structure_nodes WHERE id = 'node-3'"  # noqa: E501
            )
            row = cursor.fetchone()
            assert row[0] is None  # reference_links should be NULL
            assert row[1] is None  # word_senses should be NULL
        finally:
            cursor.close()


class TestMigration017NewColumnFunctionality:
    """Test that new columns work correctly."""

    def test_insert_node_with_reference_links(self, migration_harness):
        """Test inserting a node with reference_links data."""
        # Run migration
        migration_harness.run_migration_017()

        # Insert node with reference_links
        reference_links = [
            {"source": "schema.org", "external_id": "Person"},
            {"source": "wikidata", "external_id": "Q5"}
        ]
        migration_harness.insert_node_with_new_columns("test-node-1", reference_links, [])  # noqa: E501

        # Verify data was stored correctly
        result = migration_harness.get_node_columns("test-node-1")
        assert result is not None
        assert result['reference_links'] == reference_links

    def test_insert_node_with_word_senses(self, migration_harness):
        """Test inserting a node with word_senses data."""
        # Run migration
        migration_harness.run_migration_017()

        # Insert node with word_senses
        word_senses = [
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.01",
                "definition": "financial institution",
                "domain": "noun.group"
            },
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.02",
                "definition": "sloping land beside water",
                "domain": "noun.object"
            }
        ]
        migration_harness.insert_node_with_new_columns("test-node-2", [], word_senses)  # noqa: E501

        # Verify data was stored correctly
        result = migration_harness.get_node_columns("test-node-2")
        assert result is not None
        assert result['word_senses'] == word_senses

    def test_update_existing_node_with_new_columns(self, migration_harness):
        """Test updating existing nodes with new column data."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_017()

        # Update existing node with new column data
        reference_links = [{"source": "conceptnet", "external_id": "/c/en/bank"}]  # noqa: E501
        word_senses = [
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.01",
                "definition": "financial institution",
                "domain": "noun.group"
            }
        ]
        migration_harness.update_node_columns("node-3", reference_links, word_senses)  # noqa: E501

        # Verify updates
        result = migration_harness.get_node_columns("node-3")
        assert result is not None
        assert result['reference_links'] == reference_links
        assert result['word_senses'] == word_senses

    def test_null_values_allowed(self, migration_harness):
        """Test that NULL values are allowed for new columns."""
        # Run migration
        migration_harness.run_migration_017()

        # Insert node with NULL values
        migration_harness.insert_node_with_new_columns("test-node-null", None, None)  # noqa: E501

        # Verify NULL values
        result = migration_harness.get_node_columns("test-node-null")
        assert result is not None
        assert result['reference_links'] is None
        assert result['word_senses'] is None


class TestMigration017Rollback:
    """Test migration rollback functionality."""

    def test_rollback_removes_reference_links_column(self, migration_harness):
        """Test that rollback removes reference_links column."""
        # Run migration
        migration_harness.run_migration_017()
        assert migration_harness.verify_column_exists("structure_nodes", "reference_links")  # noqa: E501

        # Rollback migration
        migration_harness.rollback_migration_017()

        # Verify column is removed
        assert not migration_harness.verify_column_exists("structure_nodes", "reference_links")  # noqa: E501

    def test_rollback_removes_word_senses_column(self, migration_harness):
        """Test that rollback removes word_senses column."""
        # Run migration
        migration_harness.run_migration_017()
        assert migration_harness.verify_column_exists("structure_nodes", "word_senses")  # noqa: E501

        # Rollback migration
        migration_harness.rollback_migration_017()

        # Verify column is removed
        assert not migration_harness.verify_column_exists("structure_nodes", "word_senses")  # noqa: E501

    def test_rollback_preserves_existing_data(self, migration_harness):
        """Test that rollback preserves all original data."""
        # Create test data before migration
        migration_harness.create_test_structure_nodes()

        # Get count before migration
        count_before = migration_harness.get_structure_nodes_count()

        # Run migration and rollback
        migration_harness.run_migration_017()
        migration_harness.rollback_migration_017()

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
        """Test rollback after inserting data into new columns."""
        # Create test data
        migration_harness.create_test_structure_nodes()

        # Run migration
        migration_harness.run_migration_017()

        # Add data to new columns
        reference_links = [{"source": "wikidata", "external_id": "Q5"}]
        migration_harness.update_node_columns("node-3", reference_links=reference_links)  # noqa: E501

        # Rollback migration
        migration_harness.rollback_migration_017()

        # Verify original data is preserved (without new columns)
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

            # Verify new columns don't exist
            assert not migration_harness.verify_column_exists("structure_nodes", "reference_links")  # noqa: E501
            assert not migration_harness.verify_column_exists("structure_nodes", "word_senses")  # noqa: E501
        finally:
            cursor.close()


class TestMigration017EdgeCases:
    """Test edge cases and special scenarios."""

    def test_migration_with_empty_table(self, migration_harness):
        """Test migration on empty structure_nodes table."""
        # Don't create any test data
        count_before = migration_harness.get_structure_nodes_count()
        assert count_before == 0

        # Run migration
        migration_harness.run_migration_017()

        # Verify migration succeeded
        assert migration_harness.verify_column_exists("structure_nodes", "reference_links")  # noqa: E501
        assert migration_harness.verify_column_exists("structure_nodes", "word_senses")  # noqa: E501

        # Verify count is still 0
        count_after = migration_harness.get_structure_nodes_count()
        assert count_after == 0

    def test_json_array_storage(self, migration_harness):
        """Test that JSON arrays are stored and retrieved correctly."""
        # Run migration
        migration_harness.run_migration_017()

        # Insert node with complex JSON data
        reference_links = [
            {"source": "schema.org", "external_id": "Person"},
            {"source": "wikidata", "external_id": "Q5"},
            {"source": "conceptnet", "external_id": "/c/en/person"}
        ]
        word_senses = [
            {
                "term": "person",
                "sense_type": "wordnet",
                "sense_id": "person.n.01",
                "definition": "a human being",
                "domain": "noun.Tops"
            }
        ]
        migration_harness.insert_node_with_new_columns("test-json", reference_links, word_senses)  # noqa: E501

        # Verify JSON arrays are stored and retrieved correctly
        result = migration_harness.get_node_columns("test-json")
        assert result is not None
        assert len(result['reference_links']) == 3
        assert len(result['word_senses']) == 1
        assert result['reference_links'][0]['source'] == "schema.org"
        assert result['word_senses'][0]['term'] == "person"

    def test_empty_json_arrays(self, migration_harness):
        """Test that empty JSON arrays are handled correctly."""
        # Run migration
        migration_harness.run_migration_017()

        # Insert node with empty arrays
        migration_harness.insert_node_with_new_columns("test-empty", [], [])

        # Verify empty arrays are stored correctly
        result = migration_harness.get_node_columns("test-empty")
        assert result is not None
        assert result['reference_links'] == []
        assert result['word_senses'] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
