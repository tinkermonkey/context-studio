"""
Integration tests for reference database Phase 1.

Tests cross-module interactions including database lifecycle management,
schema versioning, extension loading, and concurrent operations.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import pytest
import tempfile
import time
import threading
from pathlib import Path
from datetime import datetime
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

from reference_db.models import Base, ReferenceNode, ReferenceLink
from reference_db.config import ReferenceConfig, REFERENCE_SCHEMA_VERSION, EMBEDDING_MODEL_VERSION
from reference_db.manager import ReferenceManager


# =============================================================================
# Database Lifecycle Integration Tests
# =============================================================================

class TestDatabaseLifecycleIntegration:
    """Test database initialization and lifecycle management."""

    def test_fresh_database_initialization(self, tmp_path):
        """Test initializing a brand new database."""
        db_file = tmp_path / "fresh.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)

        # Initialize should succeed
        result = manager.initialize()
        assert result is True, "Fresh database initialization should succeed"

        # Database file should exist
        assert db_file.exists(), "Database file should be created"

        # Schema tables should exist
        engine = manager.get_engine()
        with engine.connect() as conn:
            tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
            table_names = [t[0] for t in tables]

            assert "reference_nodes" in table_names
            assert "reference_links" in table_names
            assert "reference_db_version" in table_names

        # Version should be stored correctly
        with engine.connect() as conn:
            version_row = conn.execute(
                text("SELECT schema_version, embedding_model FROM reference_db_version "
                     "ORDER BY updated_at DESC LIMIT 1")
            ).fetchone()

            assert version_row is not None
            assert version_row[0] == REFERENCE_SCHEMA_VERSION
            assert version_row[1] == EMBEDDING_MODEL_VERSION

        manager.cleanup()

    def test_existing_database_reinitialization(self, tmp_path):
        """Test reinitializing an existing database with same version."""
        db_file = tmp_path / "existing.db"
        config = ReferenceConfig(database_path=str(db_file))

        # First initialization
        manager1 = ReferenceManager(config)
        manager1.initialize()

        # Add some data
        Session = manager1.get_session_local()
        session = Session()
        node = ReferenceNode(
            source="test",
            external_id="node1",
            title="Test Node"
        )
        session.add(node)
        session.commit()
        node_id = node.id
        session.close()
        manager1.cleanup()

        # Second initialization (should not rebuild)
        manager2 = ReferenceManager(config)
        result = manager2.initialize()
        assert result is True, "Reinitialization should succeed"

        # Data should still exist (no rebuild occurred)
        Session2 = manager2.get_session_local()
        session2 = Session2()
        existing_node = session2.query(ReferenceNode).filter_by(id=node_id).first()
        assert existing_node is not None, "Existing data should be preserved"
        assert existing_node.title == "Test Node"
        session2.close()
        manager2.cleanup()

    def test_database_rebuild_on_schema_version_mismatch(self, tmp_path):
        """Test database is rebuilt when schema version changes."""
        db_file = tmp_path / "schema_change.db"
        config = ReferenceConfig(database_path=str(db_file))

        # First initialization
        manager1 = ReferenceManager(config)
        manager1.initialize()

        # Add data
        Session = manager1.get_session_local()
        session = Session()
        node = ReferenceNode(
            source="test",
            external_id="node1",
            title="Test Node"
        )
        session.add(node)
        session.commit()
        session.close()

        # Manually change version to trigger rebuild
        engine = manager1.get_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM reference_db_version"))
            conn.execute(
                text("INSERT INTO reference_db_version "
                     "(schema_version, embedding_model, updated_at) "
                     "VALUES ('0.0.1', 'old-model', :updated_at)"),
                {"updated_at": datetime.now()}
            )
            conn.commit()
        manager1.cleanup()

        # Reinitialize should trigger rebuild
        manager2 = ReferenceManager(config)
        result = manager2.initialize()
        assert result is True, "Rebuild should succeed"

        # Check for backup file
        backup_files = list(tmp_path.glob("schema_change.backup_*.db"))
        assert len(backup_files) > 0, "Backup file should be created"

        # Old data should be gone (fresh database)
        Session2 = manager2.get_session_local()
        session2 = Session2()
        count = session2.query(ReferenceNode).count()
        assert count == 0, "Old data should not exist after rebuild"
        session2.close()
        manager2.cleanup()

    def test_database_rebuild_on_embedding_model_mismatch(self, tmp_path):
        """Test database is rebuilt when embedding model version changes."""
        db_file = tmp_path / "embedding_change.db"
        config = ReferenceConfig(database_path=str(db_file))

        # First initialization
        manager1 = ReferenceManager(config)
        manager1.initialize()

        # Change embedding model version
        engine = manager1.get_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM reference_db_version"))
            conn.execute(
                text("INSERT INTO reference_db_version "
                     "(schema_version, embedding_model, updated_at) "
                     "VALUES (:schema_version, 'old-embedding-model', :updated_at)"),
                {"schema_version": REFERENCE_SCHEMA_VERSION, "updated_at": datetime.now()}
            )
            conn.commit()
        manager1.cleanup()

        # Reinitialize should trigger rebuild
        manager2 = ReferenceManager(config)
        result = manager2.initialize()
        assert result is True, "Rebuild should succeed"

        # Verify rebuild occurred
        backup_files = list(tmp_path.glob("embedding_change.backup_*.db"))
        assert len(backup_files) > 0, "Backup should be created on embedding model mismatch"

        manager2.cleanup()


# =============================================================================
# Concurrent Operations Integration Tests
# =============================================================================

class TestConcurrentOperationsIntegration:
    """Test concurrent database operations and locking."""

    def test_concurrent_initialization_atomic_lock(self, tmp_path):
        """Test that concurrent initializations use atomic locking."""
        db_file = tmp_path / "concurrent.db"
        config = ReferenceConfig(database_path=str(db_file))

        # Initialize once to create database
        manager = ReferenceManager(config)
        manager.initialize()

        # Manually set old version to force rebuild
        engine = manager.get_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM reference_db_version"))
            conn.execute(
                text("INSERT INTO reference_db_version "
                     "(schema_version, embedding_model, updated_at) "
                     "VALUES ('0.0.1', 'old', :updated_at)"),
                {"updated_at": datetime.now()}
            )
            conn.commit()
        manager.cleanup()

        # Now try concurrent initializations (which will trigger rebuilds)
        results = []
        errors = []

        def initialize_concurrent():
            try:
                mgr = ReferenceManager(config)
                result = mgr.initialize()
                results.append(result)
                mgr.cleanup()
            except Exception as e:
                errors.append(str(e))

        # Start multiple threads
        threads = [threading.Thread(target=initialize_concurrent) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At least one should succeed
        assert any(results), "At least one initialization should succeed"

        # No critical errors should occur
        assert len(errors) == 0, f"No errors expected, got: {errors}"

    def test_concurrent_read_operations(self, tmp_path):
        """Test concurrent read operations are safe."""
        db_file = tmp_path / "concurrent_reads.db"
        config = ReferenceConfig(database_path=str(db_file))

        # Initialize and populate
        manager = ReferenceManager(config)
        manager.initialize()

        Session = manager.get_session_local()
        session = Session()
        for i in range(10):
            node = ReferenceNode(
                source="test",
                external_id=f"node{i}",
                title=f"Node {i}"
            )
            session.add(node)
        session.commit()
        session.close()

        # Concurrent reads
        read_counts = []
        errors = []

        def read_concurrent():
            try:
                sess = Session()
                count = sess.query(ReferenceNode).count()
                read_counts.append(count)
                sess.close()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_concurrent) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed and return same count
        assert len(errors) == 0, f"No errors expected, got: {errors}"
        assert all(c == 10 for c in read_counts), "All reads should return same count"

        manager.cleanup()


# =============================================================================
# Data Integrity Integration Tests
# =============================================================================

class TestDataIntegrityIntegration:
    """Test data integrity constraints across operations."""

    def test_unique_constraint_enforcement(self, tmp_path):
        """Test UNIQUE constraint prevents duplicate nodes."""
        db_file = tmp_path / "unique_test.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)
        manager.initialize()

        Session = manager.get_session_local()
        session = Session()

        # Add first node
        node1 = ReferenceNode(
            source="dbpedia",
            external_id="http://dbpedia.org/resource/Python",
            title="Python"
        )
        session.add(node1)
        session.commit()

        # Try to add duplicate
        node2 = ReferenceNode(
            source="dbpedia",
            external_id="http://dbpedia.org/resource/Python",
            title="Python (different)"
        )
        session.add(node2)

        # Should raise integrity error
        with pytest.raises(Exception) as exc_info:
            session.commit()

        assert "UNIQUE constraint failed" in str(exc_info.value) or \
               "unique constraint" in str(exc_info.value).lower()

        session.rollback()
        session.close()
        manager.cleanup()

    def test_cascade_delete_referential_integrity(self, tmp_path):
        """Test CASCADE delete maintains referential integrity."""
        db_file = tmp_path / "cascade_test.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)
        manager.initialize()

        Session = manager.get_session_local()
        session = Session()

        # Create nodes and link
        node1 = ReferenceNode(source="test", external_id="n1", title="Node 1")
        node2 = ReferenceNode(source="test", external_id="n2", title="Node 2")
        session.add(node1)
        session.add(node2)
        session.commit()

        link = ReferenceLink(
            subject_node_id=node1.id,
            predicate="RelatedTo",
            object_node_id=node2.id
        )
        session.add(link)
        session.commit()

        # Verify link exists
        link_count = session.query(ReferenceLink).count()
        assert link_count == 1

        # Delete subject node
        session.delete(node1)
        session.commit()

        # Link should be automatically deleted
        link_count_after = session.query(ReferenceLink).count()
        assert link_count_after == 0, "Link should be deleted via CASCADE"

        session.close()
        manager.cleanup()

    def test_multi_source_data_separation(self, tmp_path):
        """Test that nodes from different sources can have same external_id."""
        db_file = tmp_path / "multi_source.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)
        manager.initialize()

        Session = manager.get_session_local()
        session = Session()

        # Add nodes with same external_id but different sources
        node1 = ReferenceNode(
            source="dbpedia",
            external_id="Q123",
            title="DBpedia Entity"
        )
        node2 = ReferenceNode(
            source="wikidata",
            external_id="Q123",
            title="Wikidata Entity"
        )
        node3 = ReferenceNode(
            source="conceptnet",
            external_id="Q123",
            title="ConceptNet Entity"
        )

        session.add_all([node1, node2, node3])
        session.commit()

        # All should be created successfully
        count = session.query(ReferenceNode).filter_by(external_id="Q123").count()
        assert count == 3, "Same external_id allowed for different sources"

        # Verify each source has exactly one
        dbpedia_count = session.query(ReferenceNode).filter_by(
            source="dbpedia", external_id="Q123"
        ).count()
        assert dbpedia_count == 1

        session.close()
        manager.cleanup()


# =============================================================================
# Status and Monitoring Integration Tests
# =============================================================================

class TestStatusMonitoringIntegration:
    """Test status reporting and monitoring functionality."""

    def test_status_reflects_initialization_state(self, tmp_path):
        """Test that status correctly reflects database state."""
        db_file = tmp_path / "status_test.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)

        # Before initialization
        status_before = manager.get_status()
        assert status_before["is_initialized"] is False
        assert status_before["node_count"] == 0
        assert status_before["link_count"] == 0

        # After initialization
        manager.initialize()
        status_after = manager.get_status()
        assert status_after["is_initialized"] is True
        assert status_after["schema_version"] == REFERENCE_SCHEMA_VERSION
        assert status_after["embedding_model"] == EMBEDDING_MODEL_VERSION
        assert status_after["database_size"] > 0

        manager.cleanup()

    def test_status_reflects_data_changes(self, tmp_path):
        """Test that status reflects data additions."""
        db_file = tmp_path / "status_data.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)
        manager.initialize()

        # Add nodes
        Session = manager.get_session_local()
        session = Session()

        for i in range(5):
            node = ReferenceNode(
                source="test",
                external_id=f"node{i}",
                title=f"Node {i}"
            )
            session.add(node)
        session.commit()

        # Add links
        nodes = session.query(ReferenceNode).all()
        for i in range(len(nodes) - 1):
            link = ReferenceLink(
                subject_node_id=nodes[i].id,
                predicate="Next",
                object_node_id=nodes[i + 1].id
            )
            session.add(link)
        session.commit()
        session.close()

        # Check status
        status = manager.get_status()
        assert status["node_count"] == 5
        assert status["link_count"] == 4

        manager.cleanup()


# =============================================================================
# Configuration Integration Tests
# =============================================================================

class TestConfigurationIntegration:
    """Test configuration integration with database operations."""

    def test_config_validation_prevents_invalid_operations(self):
        """Test that invalid config prevents operations."""
        # Invalid similarity threshold
        with pytest.raises(ValueError):
            ReferenceConfig(similarity_threshold=1.5)

        # Invalid batch size
        with pytest.raises(ValueError):
            ReferenceConfig(batch_size=0)

        # Invalid retry count
        with pytest.raises(ValueError):
            ReferenceConfig(retry_count=-1)

        # Invalid HTTP URL
        with pytest.raises(ValueError):
            ReferenceConfig(source_url="http://example.com")

    def test_config_https_enforcement(self):
        """Test HTTPS-only enforcement for source URLs."""
        # HTTPS should work
        config = ReferenceConfig(source_url="https://example.com/data.json")
        assert config.source_url == "https://example.com/data.json"

        # HTTP should fail
        with pytest.raises(ValueError) as exc_info:
            ReferenceConfig(source_url="http://example.com/data.json")

        assert "HTTPS" in str(exc_info.value)

    def test_config_parameter_ranges(self):
        """Test parameter range validation."""
        # Valid ranges
        config = ReferenceConfig(
            similarity_threshold=0.5,
            batch_size=500,
            retry_count=5
        )
        assert config.similarity_threshold == 0.5
        assert config.batch_size == 500
        assert config.retry_count == 5

        # Boundary values
        config_min = ReferenceConfig(
            similarity_threshold=0.0,
            batch_size=1,
            retry_count=0
        )
        assert config_min.similarity_threshold == 0.0

        config_max = ReferenceConfig(
            similarity_threshold=1.0,
            batch_size=1000,
            retry_count=10
        )
        assert config_max.retry_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
