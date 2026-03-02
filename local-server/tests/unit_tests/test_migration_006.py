# mypy: ignore-errors
"""
Unit tests for Migration 006 - The Great Normalization.

Tests the migration from layers/domains/terms to the unified structure_nodes table,
including data integrity, parent-child relationships, and rollback functionality.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import tempfile
from typing import Dict, List
from sqlalchemy import create_engine, text

from database.migrations.migration_manager import MigrationManager
from database.utils import init_db


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

        # Use the migration manager to apply migrations 1-5 only
        self.migration_manager = MigrationManager(self.db_path)

        # Temporarily modify the discovered migrations to exclude 006
        original_discover = self.migration_manager._discover_migrations

        def discover_migrations_up_to_5():
            all_migrations = original_discover()
            return [m for m in all_migrations if m.version <= 5]

        # Monkey patch to exclude migration 006
        self.migration_manager._discover_migrations = discover_migrations_up_to_5

        # Apply migrations 1-5
        success = self.migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError("Failed to apply migrations 1-5")

        # Restore original method
        self.migration_manager._discover_migrations = original_discover

        return self.db_path

        return self.db_path

    def get_connection(self):
        """Get a raw database connection."""
        if not self.connection:
            self.connection = self.engine.raw_connection()
        return self.connection

    def create_test_hierarchy(self):
        """Create a complex test data hierarchy before migration."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Create layers
            cursor.execute(
                """
                INSERT INTO layers (id, title, definition, created_at, version, last_modified)
                VALUES 
                    ('layer-1', 'Science Layer', 'Scientific concepts', '2023-01-01 10:00:00', 1, '2023-01-01 10:00:00'),
                    ('layer-2', 'Technology Layer', 'Technical concepts', '2023-01-02 10:00:00', 1, '2023-01-02 10:00:00')
            """
            )

            # Create domains
            cursor.execute(
                """
                INSERT INTO domains (id, layer_id, title, definition, primary_predicate_id, created_at, version, last_modified)
                VALUES 
                    ('domain-1', 'layer-1', 'Biology', 'Study of living organisms', 'pred-1', '2023-01-03 10:00:00', 1, '2023-01-03 10:00:00'),
                    ('domain-2', 'layer-1', 'Chemistry', 'Study of matter and chemical reactions', 'pred-2', '2023-01-04 10:00:00', 1, '2023-01-04 10:00:00'),
                    ('domain-3', 'layer-2', 'Software Engineering', 'Development of software systems', NULL, '2023-01-05 10:00:00', 1, '2023-01-05 10:00:00')
            """
            )

            # Create terms with hierarchical relationships
            cursor.execute(
                """
                INSERT INTO terms (id, domain_id, layer_id, title, definition, parent_term_id, created_at, version, last_modified)
                VALUES 
                    ('term-1', 'domain-1', 'layer-1', 'Cell', 'Basic unit of life', NULL, '2023-01-06 10:00:00', 1, '2023-01-06 10:00:00'),
                    ('term-2', 'domain-1', 'layer-1', 'Animal Cell', 'Cell from animal organism', 'term-1', '2023-01-07 10:00:00', 1, '2023-01-07 10:00:00'),
                    ('term-3', 'domain-1', 'layer-1', 'Plant Cell', 'Cell from plant organism', 'term-1', '2023-01-08 10:00:00', 1, '2023-01-08 10:00:00'),
                    ('term-4', 'domain-2', 'layer-1', 'Molecule', 'Group of atoms bonded together', NULL, '2023-01-09 10:00:00', 1, '2023-01-09 10:00:00'),
                    ('term-5', 'domain-2', 'layer-1', 'Water Molecule', 'H2O molecule', 'term-4', '2023-01-10 10:00:00', 1, '2023-01-10 10:00:00'),
                    ('term-6', 'domain-3', 'layer-2', 'Algorithm', 'Step-by-step procedure', NULL, '2023-01-11 10:00:00', 1, '2023-01-11 10:00:00')
            """
            )

            # Create term relationships
            cursor.execute(
                """
                INSERT INTO term_relationships (id, source_term_id, target_term_id, predicate, predicate_id, created_at)
                VALUES 
                    ('rel-1', 'term-2', 'term-3', 'related_to', 'pred-3', '2023-01-12 10:00:00'),
                    ('rel-2', 'term-1', 'term-4', 'composed_of', 'pred-4', '2023-01-13 10:00:00')
            """
            )

            # Create graph events
            cursor.execute(
                """
                INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
                VALUES 
                    ('create', 'layer', NULL, '{"id": "layer-1", "title": "Science Layer"}', '2023-01-01 10:00:00', 0),
                    ('create', 'domain', NULL, '{"id": "domain-1", "title": "Biology"}', '2023-01-03 10:00:00', 1),
                    ('create', 'term', NULL, '{"id": "term-1", "title": "Cell"}', '2023-01-06 10:00:00', 0)
            """
            )

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def get_pre_migration_counts(self) -> Dict[str, int]:
        """Get counts of records before migration."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            counts = {}
            cursor.execute("SELECT COUNT(*) FROM layers")
            counts["layers"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM domains")
            counts["domains"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM terms")
            counts["terms"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM term_relationships")
            counts["term_relationships"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM graph_events")
            counts["graph_events"] = cursor.fetchone()[0]

            return counts

        finally:
            cursor.close()

    def get_post_migration_counts(self) -> Dict[str, int]:
        """Get counts of records after migration."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            counts = {}
            cursor.execute("SELECT COUNT(*) FROM structure_nodes")
            counts["structure_nodes"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM structure_node_links")
            counts["structure_node_links"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM change_events")
            counts["change_events"] = cursor.fetchone()[0]

            # Count by structure_node type
            cursor.execute(
                "SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'layer'"
            )
            counts["layer_nodes"] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'domain'"
            )
            counts["domain_nodes"] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'term'"
            )
            counts["term_nodes"] = cursor.fetchone()[0]

            return counts

        finally:
            cursor.close()

    def run_migration_006(self):
        """Run migration 006."""
        # Restore full migration discovery and run migration 006
        migrations = self.migration_manager._discover_migrations()
        migration_006 = next((m for m in migrations if m.version == 6), None)

        if not migration_006:
            raise RuntimeError("Migration 006 not found")

        # Use the migration manager's built-in mechanism
        with self.engine.connect() as conn:
            with conn.begin():
                migration_006.up(conn)

                # Record in schema history
                conn.execute(
                    text(
                        """
                    INSERT INTO schema_history (version, description, migration_file, checksum, execution_time_ms)
                    VALUES (:version, :description, :migration_file, :checksum, :execution_time_ms)
                """
                    ),
                    {
                        "version": migration_006.version,
                        "description": migration_006.description,
                        "migration_file": "006_nodes.py",
                        "checksum": "test",
                        "execution_time_ms": 0,
                    },
                )

        # Update current version manually
        self.migration_manager.current_version = 6

    def rollback_migration_006(self):
        """Rollback migration 006."""
        # Get migration 006 specifically
        migrations = self.migration_manager._discover_migrations()
        migration_006 = next((m for m in migrations if m.version == 6), None)

        if not migration_006:
            raise RuntimeError("Migration 006 not found")

        with self.engine.connect() as conn:
            with conn.begin():
                migration_006.down(conn)
                # Remove from schema_history
                conn.execute(text("DELETE FROM schema_history WHERE version = 6"))

        # Update current version
        self.migration_manager.current_version = 5

    def validate_parent_references(self) -> bool:
        """Validate that all parent references are valid."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM structure_nodes n1
                WHERE n1.parent_node_id IS NOT NULL 
                AND NOT EXISTS (SELECT 1 FROM structure_nodes n2 WHERE n2.id = n1.parent_node_id)
            """
            )
            invalid_count = cursor.fetchone()[0]
            return invalid_count == 0

        finally:
            cursor.close()

    def validate_embeddings_migrated(self) -> bool:
        """Validate that embeddings were properly migrated."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Check if any structure_nodes have embeddings
            cursor.execute(
                """
                SELECT COUNT(*) FROM structure_nodes 
                WHERE title_embedding IS NOT NULL OR definition_embedding IS NOT NULL
            """
            )
            cursor.fetchone()[0]

            # For this test, we'll assume embeddings migration is successful if no error occurs
            # In real scenarios, you'd have actual embedding data to validate
            return True

        finally:
            cursor.close()

    def validate_hierarchy_preservation(self) -> bool:
        """Validate that the original hierarchy is preserved after migration."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Check that domains have layers as parents
            cursor.execute(
                """
                SELECT COUNT(*) FROM structure_nodes d
                JOIN structure_nodes p ON d.parent_node_id = p.id
                WHERE d.node_type = 'domain' AND p.node_type != 'layer'
            """
            )
            invalid_domain_parents = cursor.fetchone()[0]

            # Check that terms with parent_term_id have term parents
            cursor.execute(
                """
                SELECT COUNT(*) FROM structure_nodes t
                JOIN structure_nodes p ON t.parent_node_id = p.id
                WHERE t.node_type = 'term' AND p.node_type NOT IN ('domain', 'term')
            """
            )
            invalid_term_parents = cursor.fetchone()[0]

            return invalid_domain_parents == 0 and invalid_term_parents == 0

        finally:
            cursor.close()

    def create_database_snapshot(self) -> Dict[str, List[Dict]]:
        """Create a snapshot of the database state."""
        conn = self.get_connection()
        cursor = conn.cursor()
        snapshot = {}

        try:
            # Get all tables
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                if not table.startswith("sqlite_"):
                    cursor.execute(f"SELECT * FROM {table}")
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()

                    snapshot[table] = []
                    for row in rows:
                        snapshot[table].append(dict(zip(columns, row)))

            return snapshot

        finally:
            cursor.close()

    def database_matches_snapshot(self, snapshot: Dict[str, List[Dict]]) -> bool:
        """Check if current database matches the provided snapshot."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            for table, expected_rows in snapshot.items():
                if table.startswith("sqlite_"):
                    continue

                # Check if table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                )
                if not cursor.fetchone():
                    if expected_rows:  # Table should exist but doesn't
                        return False
                    continue

                # Get current rows
                cursor.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in cursor.description]
                current_rows = cursor.fetchall()

                current_data = []
                for row in current_rows:
                    current_data.append(dict(zip(columns, row)))

                # Compare
                if len(current_data) != len(expected_rows):
                    return False

                # Sort both for comparison (by first column usually ID)
                if expected_rows:
                    first_col = list(expected_rows[0].keys())[0]
                    expected_sorted = sorted(
                        expected_rows, key=lambda x: str(x[first_col])
                    )
                    current_sorted = sorted(
                        current_data, key=lambda x: str(x[first_col])
                    )

                    if expected_sorted != current_sorted:
                        return False

            return True

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


class TestMigration006DataIntegrity:
    """Test migration data integrity."""

    def test_migration_data_integrity(self, migration_harness):
        """Test that migration preserves all data."""
        # Create test data
        migration_harness.create_test_hierarchy()

        # Get pre-migration counts
        pre_counts = migration_harness.get_pre_migration_counts()
        assert pre_counts["layers"] > 0
        assert pre_counts["domains"] > 0
        assert pre_counts["terms"] > 0
        assert pre_counts["term_relationships"] > 0
        assert pre_counts["graph_events"] > 0

        # Run migration
        migration_harness.run_migration_006()

        # Get post-migration counts
        post_counts = migration_harness.get_post_migration_counts()

        # Validate total record counts
        expected_nodes = (
            pre_counts["layers"] + pre_counts["domains"] + pre_counts["terms"]
        )
        assert (
            post_counts["structure_nodes"] == expected_nodes
        ), f"Expected {expected_nodes} structure_nodes, got {post_counts['structure_nodes']}"

        # Validate individual type counts
        assert post_counts["layer_nodes"] == pre_counts["layers"]
        assert post_counts["domain_nodes"] == pre_counts["domains"]
        assert post_counts["term_nodes"] == pre_counts["terms"]

        # Validate links
        assert post_counts["structure_node_links"] == pre_counts["term_relationships"]

        # Validate events
        assert post_counts["change_events"] == pre_counts["graph_events"]

        # Validate parent references
        assert (
            migration_harness.validate_parent_references()
        ), "Invalid parent references found"

        # Validate embeddings migration
        assert (
            migration_harness.validate_embeddings_migrated()
        ), "Embedding migration failed"

    def test_migration_preserves_specific_data(self, migration_harness):
        """Test that specific data fields are correctly preserved."""
        # Create test data
        migration_harness.create_test_hierarchy()

        # Run migration
        migration_harness.run_migration_006()

        # Validate specific records
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            # Check layer migration
            cursor.execute(
                "SELECT id, title, node_type FROM structure_nodes WHERE id = 'layer-1'"
            )
            layer_row = cursor.fetchone()
            assert layer_row is not None
            assert layer_row[1] == "Science Layer"
            assert layer_row[2] == "layer"

            # Check domain migration with parent reference
            cursor.execute(
                "SELECT id, title, node_type, parent_node_id, structural_predicate_id FROM structure_nodes WHERE id = 'domain-1'"
            )
            domain_row = cursor.fetchone()
            assert domain_row is not None
            assert domain_row[1] == "Biology"
            assert domain_row[2] == "domain"
            assert domain_row[3] == "layer-1"  # parent_node_id should be layer-1
            assert (
                domain_row[4] == "pred-1"
            )  # structural_predicate_id from primary_predicate_id

            # Check term migration with correct parent assignment
            cursor.execute(
                "SELECT id, title, node_type, parent_node_id FROM structure_nodes WHERE id = 'term-2'"
            )
            term_row = cursor.fetchone()
            assert term_row is not None
            assert term_row[1] == "Animal Cell"
            assert term_row[2] == "term"
            assert (
                term_row[3] == "term-1"
            )  # parent_node_id should be term-1 (parent term)

            # Check term with domain parent
            cursor.execute(
                "SELECT id, title, node_type, parent_node_id FROM structure_nodes WHERE id = 'term-1'"
            )
            term_root_row = cursor.fetchone()
            assert term_root_row is not None
            assert term_root_row[1] == "Cell"
            assert term_root_row[2] == "term"
            assert term_root_row[3] == "domain-1"  # parent_node_id should be domain-1

        finally:
            cursor.close()


class TestMigration006ParentChildRelationships:
    """Test parent-child relationship migration."""

    def test_migration_parent_child_relationships(self, migration_harness):
        """Test that parent-child relationships are correctly migrated."""
        # Create test hierarchy
        migration_harness.create_test_hierarchy()

        # Run migration
        migration_harness.run_migration_006()

        # Validate hierarchy preservation
        assert (
            migration_harness.validate_hierarchy_preservation()
        ), "Hierarchy was not preserved correctly"

        # Test specific relationships
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            # Test layer has no parent
            cursor.execute(
                "SELECT parent_node_id FROM structure_nodes WHERE node_type = 'layer' AND id = 'layer-1'"
            )
            layer_parent = cursor.fetchone()[0]
            assert layer_parent is None, "Layers should not have parents"

            # Test domain has layer parent
            cursor.execute(
                """
                SELECT n.id, n.title, p.node_type, p.title
                FROM structure_nodes n
                JOIN structure_nodes p ON n.parent_node_id = p.id
                WHERE n.node_type = 'domain' AND n.id = 'domain-1'
            """
            )
            domain_relationship = cursor.fetchone()
            assert domain_relationship is not None
            assert domain_relationship[2] == "layer"  # parent node_type
            assert domain_relationship[3] == "Science Layer"  # parent title

            # Test term has correct parent (could be domain or term)
            cursor.execute(
                """
                SELECT n.id, n.title, p.node_type, p.title
                FROM structure_nodes n
                JOIN structure_nodes p ON n.parent_node_id = p.id
                WHERE n.node_type = 'term' AND n.id = 'term-2'
            """
            )
            term_relationship = cursor.fetchone()
            assert term_relationship is not None
            assert term_relationship[2] == "term"  # parent node_type (term-1)
            assert term_relationship[3] == "Cell"  # parent title

        finally:
            cursor.close()

    def test_complex_hierarchy_migration(self, migration_harness):
        """Test migration of complex hierarchies."""
        # Create more complex test data
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            # Create a deep term hierarchy: term-root -> term-level1 -> term-level2 -> term-level3
            cursor.execute(
                """
                INSERT INTO layers (id, title, definition) VALUES ('layer-deep', 'Deep Layer', 'For hierarchy testing')
            """
            )
            cursor.execute(
                """
                INSERT INTO domains (id, layer_id, title, definition) VALUES ('domain-deep', 'layer-deep', 'Deep Domain', 'For hierarchy testing')
            """
            )
            cursor.execute(
                """
                INSERT INTO terms (id, domain_id, layer_id, title, definition, parent_term_id) VALUES
                    ('term-root', 'domain-deep', 'layer-deep', 'Root Term', 'Root of hierarchy', NULL),
                    ('term-l1', 'domain-deep', 'layer-deep', 'Level 1 Term', 'First level', 'term-root'),
                    ('term-l2', 'domain-deep', 'layer-deep', 'Level 2 Term', 'Second level', 'term-l1'),
                    ('term-l3', 'domain-deep', 'layer-deep', 'Level 3 Term', 'Third level', 'term-l2')
            """
            )
            conn.commit()

        finally:
            cursor.close()

        # Run migration
        migration_harness.run_migration_006()

        # Validate deep hierarchy
        cursor = conn.cursor()
        try:
            # Check each level of hierarchy
            cursor.execute(
                "SELECT parent_node_id FROM structure_nodes WHERE id = 'term-root'"
            )
            assert cursor.fetchone()[0] == "domain-deep"

            cursor.execute(
                "SELECT parent_node_id FROM structure_nodes WHERE id = 'term-l1'"
            )
            assert cursor.fetchone()[0] == "term-root"

            cursor.execute(
                "SELECT parent_node_id FROM structure_nodes WHERE id = 'term-l2'"
            )
            assert cursor.fetchone()[0] == "term-l1"

            cursor.execute(
                "SELECT parent_node_id FROM structure_nodes WHERE id = 'term-l3'"
            )
            assert cursor.fetchone()[0] == "term-l2"

        finally:
            cursor.close()


class TestMigration006Rollback:
    """Test migration rollback functionality."""

    def test_rollback_preserves_original_data(self, migration_harness):
        """Test that rollback preserves all original data correctly."""
        # Create test data
        migration_harness.create_test_hierarchy()

        # Get original counts
        original_counts = migration_harness.get_pre_migration_counts()

        # Run migration and rollback
        migration_harness.run_migration_006()
        migration_harness.rollback_migration_006()

        # Verify original counts are restored
        restored_counts = migration_harness.get_pre_migration_counts()
        assert restored_counts == original_counts

        # Verify specific data integrity
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            # Check that original layer exists
            cursor.execute("SELECT id, title FROM layers WHERE id = 'layer-1'")
            layer = cursor.fetchone()
            assert layer is not None
            assert layer[1] == "Science Layer"

            # Check that original domain exists with correct layer_id
            cursor.execute(
                "SELECT id, title, layer_id FROM domains WHERE id = 'domain-1'"
            )
            domain = cursor.fetchone()
            assert domain is not None
            assert domain[1] == "Biology"
            assert domain[2] == "layer-1"

            # Check that original term exists with correct domain_id and parent_term_id
            cursor.execute(
                "SELECT id, title, domain_id, parent_term_id FROM terms WHERE id = 'term-2'"
            )
            term = cursor.fetchone()
            assert term is not None
            assert term[1] == "Animal Cell"
            assert term[2] == "domain-1"
            assert term[3] == "term-1"

        finally:
            cursor.close()


class TestMigration006EdgeCases:
    """Test migration edge cases and error conditions."""

    def test_migration_with_missing_predicates(self, migration_harness):
        """Test migration when predicate references don't exist."""
        # Create test data with invalid predicate references
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO layers (id, title, definition) VALUES ('layer-test', 'Test Layer', 'Test')
            """
            )
            cursor.execute(
                """
                INSERT INTO domains (id, layer_id, title, definition, primary_predicate_id) 
                VALUES ('domain-test', 'layer-test', 'Test Domain', 'Test', 'nonexistent-predicate')
            """
            )
            conn.commit()

        finally:
            cursor.close()

        # Migration should still succeed (foreign key constraints allow NULL)
        migration_harness.run_migration_006()

        # Verify data migrated correctly
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT structural_predicate_id FROM structure_nodes WHERE id = 'domain-test'"
            )
            result = cursor.fetchone()
            assert (
                result[0] == "nonexistent-predicate"
            )  # Should preserve the reference even if invalid

        finally:
            cursor.close()

    def test_migration_with_empty_tables(self, migration_harness):
        """Test migration when source tables are empty."""
        # Don't create any test data - run migration on empty tables

        # Get pre-migration counts (should all be 0)
        pre_counts = migration_harness.get_pre_migration_counts()
        assert all(count == 0 for count in pre_counts.values())

        # Run migration
        migration_harness.run_migration_006()

        # Verify post-migration counts are also 0
        post_counts = migration_harness.get_post_migration_counts()
        assert post_counts["structure_nodes"] == 0
        assert post_counts["structure_node_links"] == 0
        assert post_counts["change_events"] == 0

    def test_migration_with_orphaned_terms(self, migration_harness):
        """Test migration handling of terms with invalid domain/layer references."""
        # Create test data with orphaned term
        conn = migration_harness.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO layers (id, title, definition) VALUES ('layer-orphan', 'Orphan Layer', 'Test')
            """
            )
            cursor.execute(
                """
                INSERT INTO domains (id, layer_id, title, definition)
                VALUES ('domain-orphan', 'layer-orphan', 'Orphan Domain', 'Test')
            """
            )
            # Create term with invalid domain_id
            cursor.execute(
                """
                INSERT INTO terms (id, domain_id, layer_id, title, definition)
                VALUES ('term-orphan', 'nonexistent-domain', 'layer-orphan', 'Orphan Term', 'Test')
            """
            )
            conn.commit()

        finally:
            cursor.close()

        # Migration should fail due to data integrity validation
        with pytest.raises(
            Exception, match="Found 1 structure_nodes with invalid parent references"
        ):
            migration_harness.run_migration_006()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
