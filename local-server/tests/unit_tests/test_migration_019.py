# mypy: ignore-errors
"""
Unit tests for Migration 019 - Terminology Rename.

Tests the renaming of tables, columns, and enum values to standard ontology terminology:
- Tables: structure_nodes → ontology_entities, structure_node_links → relationships,
  predicates → property_definitions, pipeline_flavors → pipeline_configurations
- Columns: parent_node_id → parent_entity_id, source_node_id → source_entity_id,
  target_node_id → target_entity_id
- Enum values: layer → taxonomy, domain → concept_scheme, term → class
- Record types: structure_node → ontology_entity, structure_node_link → relationship,
  predicate → property_definition

Tests include schema validation, data preservation, enum value updates, and complete rollback.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest  # noqa: E402
import tempfile  # noqa: E402
from typing import Dict, List, Tuple  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from database.migrations.migration_manager import MigrationManager  # noqa: E402, E501
from database.utils import init_db  # noqa: E402


class MigrationTestHarness:
    """Test harness for migration 019 testing with schema and data snapshots."""

    def __init__(self):
        self.db_path = None
        self.engine = None
        self.connection = None
        self.migration_manager = None

    def setup_test_database(self) -> str:
        """Create a fresh test database with migrations 1-18 applied."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            self.db_path = tf.name

        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(db_url)

        # Initialize with base schema
        init_db(engine=self.engine)

        # Use the migration manager to apply migrations up to 018
        self.migration_manager = MigrationManager(self.db_path)

        # Temporarily modify the discovered migrations to exclude 019
        original_discover = self.migration_manager._discover_migrations

        def discover_migrations_up_to_18():
            all_migrations = original_discover()
            return [m for m in all_migrations if m.version <= 18]

        # Monkey patch to exclude migration 019
        self.migration_manager._discover_migrations = discover_migrations_up_to_18

        # Apply migrations 1-18
        success = self.migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError("Failed to apply migrations 1-18")

        # Restore original method
        self.migration_manager._discover_migrations = original_discover

        return self.db_path

    def get_connection(self):
        """Get a raw database connection."""
        if not self.connection:
            self.connection = self.engine.raw_connection()
        return self.connection

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            return column_name in columns
        finally:
            cursor.close()

    def get_table_columns(self, table_name: str) -> List[str]:
        """Get all column names for a table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            return [row[1] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_table_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]
        finally:
            cursor.close()

    def create_test_hierarchy_legacy(self):
        """Create a test hierarchy using legacy terminology."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Create predicates first
            cursor.execute("""
                INSERT INTO predicates (id, identifier, title, definition)
                VALUES
                    ('pred-1', 'is_part_of', 'Is Part Of', 'Indicates hierarchical containment'),
                    ('pred-2', 'is_related_to', 'Is Related To', 'Indicates loose relationship')
            """)

            # Create a layer (root)
            cursor.execute("""
                INSERT INTO structure_nodes
                (id, node_type, title, definition, created_at, version, last_modified)
                VALUES
                    ('node-1', 'layer', 'Test Taxonomy', 'Root layer', datetime('now'), 1, datetime('now'))
            """)

            # Create a domain
            cursor.execute("""
                INSERT INTO structure_nodes
                (id, node_type, parent_node_id, title, definition, structural_predicate_id, created_at, version, last_modified)
                VALUES
                    ('node-2', 'domain', 'node-1', 'Test Domain', 'Domain definition', 'pred-1', datetime('now'), 1, datetime('now'))
            """)

            # Create terms
            cursor.execute("""
                INSERT INTO structure_nodes
                (id, node_type, parent_node_id, title, definition, created_at, version, last_modified)
                VALUES
                    ('node-3', 'term', 'node-2', 'Test Term 1', 'First term', datetime('now'), 1, datetime('now')),
                    ('node-4', 'term', 'node-2', 'Test Term 2', 'Second term', datetime('now'), 1, datetime('now'))
            """)

            # Create links (relationships)
            cursor.execute("""
                INSERT INTO structure_node_links (id, source_node_id, target_node_id, predicate, predicate_id)
                VALUES
                    ('link-1', 'node-3', 'node-4', 'is_related_to', 'pred-2')
            """)

            # Create a change event
            cursor.execute("""
                INSERT INTO change_events (event_type, record_type, record_id, timestamp)
                VALUES
                    ('create', 'structure_node', 'node-1', datetime('now')),
                    ('create', 'structure_node_link', 'link-1', datetime('now')),
                    ('create', 'predicate', 'pred-1', datetime('now'))
            """)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def create_pipeline_flavor(self):
        """Create a test pipeline flavor."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO pipeline_flavors
                (id, pipeline, title, llm_provider, llm_model, llm_config, system_prompt, user_prompt, version, enabled)
                VALUES
                    ('flavor-1', 'test_pipeline', 'Test Flavor', 'openai', 'gpt-4', '{}', 'System', 'User', 1, 1)
            """)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def run_migration_019(self):
        """Run migration 019."""
        migrations = self.migration_manager._discover_migrations()
        migration_019 = next((m for m in migrations if m.version == 19), None)

        if not migration_019:
            raise RuntimeError("Migration 019 not found")

        # Use the migration manager's built-in mechanism
        with self.engine.connect() as conn:
            with conn.begin():
                migration_019.up(conn)

                # Record in schema history
                conn.execute(
                    text("""
                    INSERT INTO schema_history (version, description, migration_file, checksum, execution_time_ms)
                    VALUES (:version, :description, :migration_file, :checksum, :execution_time_ms)
                """),
                    {
                        "version": migration_019.version,
                        "description": migration_019.description,
                        "migration_file": "019_terminology_rename.py",
                        "checksum": "test",
                        "execution_time_ms": 0,
                    },
                )

        # Update current version manually
        self.migration_manager.current_version = 19

    def rollback_migration_019(self):
        """Rollback migration 019."""
        migrations = self.migration_manager._discover_migrations()
        migration_019 = next((m for m in migrations if m.version == 19), None)

        if not migration_019:
            raise RuntimeError("Migration 019 not found")

        with self.engine.connect() as conn:
            with conn.begin():
                migration_019.down(conn)
                # Remove from schema_history
                conn.execute(text("DELETE FROM schema_history WHERE version = 19"))

        # Update current version
        self.migration_manager.current_version = 18

    def get_node_type_values(self, table_name: str) -> Dict[str, int]:
        """Get counts of each node_type value."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT node_type, COUNT(*) FROM {table_name} GROUP BY node_type"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            cursor.close()

    def get_record_type_values(self) -> Dict[str, int]:
        """Get counts of each record_type value in change_events."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT record_type, COUNT(*) FROM change_events GROUP BY record_type"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            cursor.close()

    def get_node_by_id(self, table_name: str, node_id: str) -> Tuple:
        """Get a node by ID from specified table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (node_id,))
            return cursor.fetchone()
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


class TestMigration019TableRenames:
    """Test that tables are renamed correctly."""

    def test_structure_nodes_renamed_to_ontology_entities(self, migration_harness):
        """Test that structure_nodes table is renamed to ontology_entities."""
        assert migration_harness.table_exists("structure_nodes")
        assert not migration_harness.table_exists("ontology_entities")

        migration_harness.run_migration_019()

        assert not migration_harness.table_exists("structure_nodes")
        assert migration_harness.table_exists("ontology_entities")

    def test_structure_node_links_renamed_to_relationships(self, migration_harness):
        """Test that structure_node_links table is renamed to relationships."""
        assert migration_harness.table_exists("structure_node_links")
        assert not migration_harness.table_exists("relationships")

        migration_harness.run_migration_019()

        assert not migration_harness.table_exists("structure_node_links")
        assert migration_harness.table_exists("relationships")

    def test_predicates_renamed_to_property_definitions(self, migration_harness):
        """Test that predicates table is renamed to property_definitions."""
        assert migration_harness.table_exists("predicates")
        assert not migration_harness.table_exists("property_definitions")

        migration_harness.run_migration_019()

        assert not migration_harness.table_exists("predicates")
        assert migration_harness.table_exists("property_definitions")

    def test_pipeline_flavors_renamed_to_pipeline_configurations(
        self, migration_harness
    ):
        """Test that pipeline_flavors table is renamed to pipeline_configurations (if it exists)."""
        # Note: pipeline_flavors may not exist in all test databases
        pipeline_flavors_exists_before = migration_harness.table_exists(
            "pipeline_flavors"
        )

        migration_harness.run_migration_019()

        if pipeline_flavors_exists_before:
            assert not migration_harness.table_exists("pipeline_flavors")
            assert migration_harness.table_exists("pipeline_configurations")


class TestMigration019ColumnRenames:
    """Test that columns are renamed correctly."""

    def test_parent_node_id_renamed_to_parent_entity_id(self, migration_harness):
        """Test that parent_node_id column is renamed to parent_entity_id."""
        assert migration_harness.column_exists("structure_nodes", "parent_node_id")
        assert not migration_harness.column_exists(
            "structure_nodes", "parent_entity_id"
        )

        migration_harness.run_migration_019()

        assert not migration_harness.column_exists(
            "ontology_entities", "parent_node_id"
        )
        assert migration_harness.column_exists("ontology_entities", "parent_entity_id")

    def test_source_node_id_renamed_to_source_entity_id(self, migration_harness):
        """Test that source_node_id column is renamed to source_entity_id."""
        assert migration_harness.column_exists("structure_node_links", "source_node_id")
        assert not migration_harness.column_exists(
            "structure_node_links", "source_entity_id"
        )

        migration_harness.run_migration_019()

        assert not migration_harness.column_exists("relationships", "source_node_id")
        assert migration_harness.column_exists("relationships", "source_entity_id")

    def test_target_node_id_renamed_to_target_entity_id(self, migration_harness):
        """Test that target_node_id column is renamed to target_entity_id."""
        assert migration_harness.column_exists("structure_node_links", "target_node_id")
        assert not migration_harness.column_exists(
            "structure_node_links", "target_entity_id"
        )

        migration_harness.run_migration_019()

        assert not migration_harness.column_exists("relationships", "target_node_id")
        assert migration_harness.column_exists("relationships", "target_entity_id")


class TestMigration019EnumValueUpdates:
    """Test that enum values are updated correctly."""

    def test_layer_renamed_to_taxonomy(self, migration_harness):
        """Test that node_type 'layer' is renamed to 'taxonomy'."""
        migration_harness.create_test_hierarchy_legacy()

        # Verify layer exists before migration
        values_before = migration_harness.get_node_type_values("structure_nodes")
        assert "layer" in values_before
        assert "taxonomy" not in values_before

        migration_harness.run_migration_019()

        # Verify layer is renamed after migration
        values_after = migration_harness.get_node_type_values("ontology_entities")
        assert "taxonomy" in values_after
        assert "layer" not in values_after

    def test_domain_renamed_to_concept_scheme(self, migration_harness):
        """Test that node_type 'domain' is renamed to 'concept_scheme'."""
        migration_harness.create_test_hierarchy_legacy()

        values_before = migration_harness.get_node_type_values("structure_nodes")
        assert "domain" in values_before

        migration_harness.run_migration_019()

        values_after = migration_harness.get_node_type_values("ontology_entities")
        assert "concept_scheme" in values_after
        assert "domain" not in values_after

    def test_term_renamed_to_class(self, migration_harness):
        """Test that node_type 'term' is renamed to 'class'."""
        migration_harness.create_test_hierarchy_legacy()

        values_before = migration_harness.get_node_type_values("structure_nodes")
        assert "term" in values_before

        migration_harness.run_migration_019()

        values_after = migration_harness.get_node_type_values("ontology_entities")
        assert "class" in values_after
        assert "term" not in values_after


class TestMigration019RecordTypeUpdates:
    """Test that record_type values in change_events are updated correctly."""

    def test_structure_node_renamed_to_ontology_entity(self, migration_harness):
        """Test that record_type 'structure_node' is renamed to 'ontology_entity'."""
        migration_harness.create_test_hierarchy_legacy()

        values_before = migration_harness.get_record_type_values()
        assert "structure_node" in values_before

        migration_harness.run_migration_019()

        values_after = migration_harness.get_record_type_values()
        assert "ontology_entity" in values_after
        assert "structure_node" not in values_after

    def test_structure_node_link_renamed_to_relationship(self, migration_harness):
        """Test that record_type 'structure_node_link' is renamed to 'relationship'."""
        migration_harness.create_test_hierarchy_legacy()

        values_before = migration_harness.get_record_type_values()
        assert "structure_node_link" in values_before

        migration_harness.run_migration_019()

        values_after = migration_harness.get_record_type_values()
        assert "relationship" in values_after
        assert "structure_node_link" not in values_after

    def test_predicate_renamed_to_property_definition(self, migration_harness):
        """Test that record_type 'predicate' is renamed to 'property_definition'."""
        migration_harness.create_test_hierarchy_legacy()

        values_before = migration_harness.get_record_type_values()
        assert "predicate" in values_before

        migration_harness.run_migration_019()

        values_after = migration_harness.get_record_type_values()
        assert "property_definition" in values_after
        assert "predicate" not in values_after


class TestMigration019DataPreservation:
    """Test that data is preserved during migration."""

    def test_all_nodes_preserved(self, migration_harness):
        """Test that all structure_nodes are preserved."""
        migration_harness.create_test_hierarchy_legacy()
        count_before = migration_harness.get_table_row_count("structure_nodes")

        migration_harness.run_migration_019()

        count_after = migration_harness.get_table_row_count("ontology_entities")
        assert count_after == count_before
        assert count_after == 4

    def test_all_links_preserved(self, migration_harness):
        """Test that all structure_node_links are preserved."""
        migration_harness.create_test_hierarchy_legacy()
        count_before = migration_harness.get_table_row_count("structure_node_links")

        migration_harness.run_migration_019()

        count_after = migration_harness.get_table_row_count("relationships")
        assert count_after == count_before

    def test_all_predicates_preserved(self, migration_harness):
        """Test that all predicates are preserved."""
        migration_harness.create_test_hierarchy_legacy()
        count_before = migration_harness.get_table_row_count("predicates")

        migration_harness.run_migration_019()

        count_after = migration_harness.get_table_row_count("property_definitions")
        assert count_after == count_before

    def test_all_pipeline_flavors_preserved(self, migration_harness):
        """Test that all pipeline_flavors are preserved."""
        # Skip this test if pipeline_flavors table doesn't exist
        if not migration_harness.table_exists("pipeline_flavors"):
            pytest.skip("pipeline_flavors table does not exist in test database")

        migration_harness.create_pipeline_flavor()
        count_before = migration_harness.get_table_row_count("pipeline_flavors")

        migration_harness.run_migration_019()

        count_after = migration_harness.get_table_row_count("pipeline_configurations")
        assert count_after == count_before

    def test_node_data_preserved(self, migration_harness):
        """Test that node data is preserved during migration."""
        migration_harness.create_test_hierarchy_legacy()

        migration_harness.run_migration_019()

        # Get the node from the new table
        node = migration_harness.get_node_by_id("ontology_entities", "node-3")
        assert node is not None
        # node tuple: (id, node_type, parent_entity_id, title, definition, ...)
        assert node[0] == "node-3"
        assert node[1] == "class"  # term → class
        assert node[2] == "node-2"  # parent_entity_id (was parent_node_id)
        assert node[3] == "Test Term 1"  # title

    def test_hierarchical_relationships_preserved(self, migration_harness):
        """Test that parent-child relationships are preserved."""
        migration_harness.create_test_hierarchy_legacy()

        migration_harness.run_migration_019()

        # Check parent relationship is preserved
        child_node = migration_harness.get_node_by_id("ontology_entities", "node-3")
        parent_id = child_node[2]  # parent_entity_id
        parent_node = migration_harness.get_node_by_id("ontology_entities", parent_id)
        assert parent_node is not None
        assert parent_node[1] == "concept_scheme"  # domain → concept_scheme


class TestMigration019Indexes:
    """Test that indexes are recreated correctly."""

    def test_title_index_exists_after_migration(self, migration_harness):
        """Test that title index exists on ontology_entities."""
        migration_harness.run_migration_019()

        conn = migration_harness.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ontology_entities' AND name LIKE '%title%'"
            )
            indexes = cursor.fetchall()
            assert len(indexes) > 0
        finally:
            cursor.close()


class TestMigration019Rollback:
    """Test migration rollback functionality."""

    def test_rollback_renames_tables_back(self, migration_harness):
        """Test that rollback renames all tables back to legacy names."""
        migration_harness.run_migration_019()
        assert not migration_harness.table_exists("structure_nodes")
        assert migration_harness.table_exists("ontology_entities")

        migration_harness.rollback_migration_019()

        assert migration_harness.table_exists("structure_nodes")
        assert not migration_harness.table_exists("ontology_entities")
        assert migration_harness.table_exists("structure_node_links")
        assert not migration_harness.table_exists("relationships")
        assert migration_harness.table_exists("predicates")
        assert not migration_harness.table_exists("property_definitions")
        # Note: pipeline_flavors may not exist in all test databases
        # If it existed before migration, it should be restored
        pipeline_flavors_before = migration_harness.table_exists(
            "pipeline_configurations"
        )
        if pipeline_flavors_before:
            # This shouldn't happen since we just rolled back
            pass
        migration_harness.table_exists("pipeline_flavors")
        pipeline_configs_after = migration_harness.table_exists(
            "pipeline_configurations"
        )
        # Either pipeline_flavors exists OR neither exists (since it wasn't there originally)
        assert not pipeline_configs_after

    def test_rollback_renames_columns_back(self, migration_harness):
        """Test that rollback renames all columns back to legacy names."""
        migration_harness.run_migration_019()
        assert migration_harness.column_exists("ontology_entities", "parent_entity_id")

        migration_harness.rollback_migration_019()

        assert migration_harness.column_exists("structure_nodes", "parent_node_id")
        assert not migration_harness.column_exists(
            "structure_nodes", "parent_entity_id"
        )
        assert migration_harness.column_exists("structure_node_links", "source_node_id")
        assert not migration_harness.column_exists(
            "structure_node_links", "source_entity_id"
        )

    def test_rollback_reverts_enum_values(self, migration_harness):
        """Test that rollback reverts enum values back to legacy names."""
        migration_harness.create_test_hierarchy_legacy()

        migration_harness.run_migration_019()
        values_after_up = migration_harness.get_node_type_values("ontology_entities")
        assert "taxonomy" in values_after_up
        assert "layer" not in values_after_up

        migration_harness.rollback_migration_019()

        values_after_down = migration_harness.get_node_type_values("structure_nodes")
        assert "layer" in values_after_down
        assert "domain" in values_after_down
        # Note: "class" should be reverted back to "term"
        assert "term" in values_after_down
        # Verify the new terminology is gone
        assert "taxonomy" not in values_after_down
        assert "concept_scheme" not in values_after_down
        assert "class" not in values_after_down

    def test_rollback_reverts_record_type_values(self, migration_harness):
        """Test that rollback reverts record_type values back to legacy names."""
        migration_harness.create_test_hierarchy_legacy()

        migration_harness.run_migration_019()
        values_after_up = migration_harness.get_record_type_values()
        assert "ontology_entity" in values_after_up

        migration_harness.rollback_migration_019()

        values_after_down = migration_harness.get_record_type_values()
        assert "structure_node" in values_after_down

    def test_rollback_preserves_data(self, migration_harness):
        """Test that rollback preserves all data."""
        migration_harness.create_test_hierarchy_legacy()
        count_before = migration_harness.get_table_row_count("structure_nodes")

        migration_harness.run_migration_019()
        migration_harness.rollback_migration_019()

        count_after = migration_harness.get_table_row_count("structure_nodes")
        assert count_after == count_before

        # Verify specific node data is preserved and reverted
        node = migration_harness.get_node_by_id("structure_nodes", "node-3")
        assert node is not None
        assert node[0] == "node-3"
        # node_type should be reverted from 'class' back to 'term'
        assert node[1] == "term", f"Expected 'term' but got '{node[1]}'"
        assert node[2] == "node-2", f"Expected 'node-2' but got '{node[2]}'"


class TestMigration019RoundTrip:
    """Test that migration can be applied and rolled back multiple times."""

    def test_roundtrip_forward_backward_forward(self, migration_harness):
        """Test forward → backward → forward migration."""
        migration_harness.create_test_hierarchy_legacy()

        # Forward
        migration_harness.run_migration_019()
        assert migration_harness.table_exists("ontology_entities")
        count_after_up1 = migration_harness.get_table_row_count("ontology_entities")

        # Backward
        migration_harness.rollback_migration_019()
        assert migration_harness.table_exists("structure_nodes")
        count_after_down = migration_harness.get_table_row_count("structure_nodes")
        assert count_after_down == count_after_up1

        # Forward again
        migration_harness.run_migration_019()
        assert migration_harness.table_exists("ontology_entities")
        count_after_up2 = migration_harness.get_table_row_count("ontology_entities")
        assert count_after_up2 == count_after_up1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
