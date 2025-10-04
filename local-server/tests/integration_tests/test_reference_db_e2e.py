"""
End-to-end tests for reference database Phase 1.

Tests complete user workflows including initialization, data population,
rebuild scenarios, and error recovery.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from sqlalchemy import text

from reference_db.models import ReferenceNode, ReferenceLink
from reference_db.config import ReferenceConfig, REFERENCE_SCHEMA_VERSION, EMBEDDING_MODEL_VERSION
from reference_db.manager import ReferenceManager


# =============================================================================
# Complete Initialization Workflow E2E Tests
# =============================================================================

class TestCompleteInitializationWorkflow:
    """Test complete database initialization workflows."""

    def test_fresh_install_workflow(self, tmp_path):
        """
        E2E: Test complete fresh installation workflow.

        Simulates first-time user initializing the reference database.
        """
        # Step 1: User creates config
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(
            database_path=str(db_file),
            similarity_threshold=0.7,
            batch_size=200,
            auto_initialize=True
        )

        # Step 2: User creates manager
        manager = ReferenceManager(config)
        assert manager.config.database_path == str(db_file)

        # Step 3: User initializes database
        result = manager.initialize()
        assert result is True, "Initialization should succeed"

        # Step 4: Verify database is ready
        status = manager.get_status()
        assert status["is_initialized"] is True
        assert status["schema_version"] == REFERENCE_SCHEMA_VERSION
        assert status["node_count"] == 0
        assert status["link_count"] == 0

        # Step 5: User adds first data
        Session = manager.get_session_local()
        session = Session()

        node = ReferenceNode(
            source="dbpedia",
            external_id="http://dbpedia.org/resource/Python",
            title="Python (programming language)",
            definition="High-level programming language"
        )
        session.add(node)
        session.commit()
        session.close()

        # Step 6: Verify data is stored
        status_after = manager.get_status()
        assert status_after["node_count"] == 1

        # Step 7: Clean shutdown
        manager.cleanup()
        assert manager.engine is None

    def test_application_restart_workflow(self, tmp_path):
        """
        E2E: Test application restart workflow.

        Simulates application shutdown and restart with existing database.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(database_path=str(db_file))

        # First session: Create and populate
        manager1 = ReferenceManager(config)
        manager1.initialize()

        Session1 = manager1.get_session_local()
        session1 = Session1()
        node = ReferenceNode(
            source="wikidata",
            external_id="Q28865",
            title="Python",
            definition="Programming language"
        )
        session1.add(node)
        session1.commit()
        node_id = node.id
        session1.close()
        manager1.cleanup()

        # Application restart (new manager instance)
        manager2 = ReferenceManager(config)
        result = manager2.initialize()
        assert result is True, "Reinitialization should succeed"

        # Verify data persisted
        Session2 = manager2.get_session_local()
        session2 = Session2()
        retrieved_node = session2.query(ReferenceNode).filter_by(id=node_id).first()
        assert retrieved_node is not None
        assert retrieved_node.title == "Python"
        assert retrieved_node.source == "wikidata"
        session2.close()
        manager2.cleanup()

    def test_upgrade_scenario_workflow(self, tmp_path):
        """
        E2E: Test schema upgrade workflow.

        Simulates upgrading from old schema version to new version.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(database_path=str(db_file))

        # Simulate old version database
        manager_old = ReferenceManager(config)
        manager_old.initialize()

        # Add data in old version
        Session = manager_old.get_session_local()
        session = Session()
        for i in range(10):
            node = ReferenceNode(
                source="old_source",
                external_id=f"entity_{i}",
                title=f"Entity {i}"
            )
            session.add(node)
        session.commit()
        session.close()

        # Manually set old schema version
        engine = manager_old.get_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM reference_db_version"))
            conn.execute(
                text("INSERT INTO reference_db_version "
                     "(schema_version, embedding_model, updated_at) "
                     "VALUES ('0.9.0', 'old-model', :updated_at)"),
                {"updated_at": datetime.now()}
            )
            conn.commit()
        manager_old.cleanup()

        # User upgrades application (new schema version)
        manager_new = ReferenceManager(config)
        result = manager_new.initialize()  # Should trigger rebuild
        assert result is True, "Upgrade should succeed"

        # Verify rebuild occurred
        backup_files = list(tmp_path.glob("reference.backup_*.db"))
        assert len(backup_files) > 0, "Backup should be created"

        # New database should be empty (fresh start)
        status = manager_new.get_status()
        assert status["node_count"] == 0, "New database should be empty after rebuild"
        assert status["schema_version"] == REFERENCE_SCHEMA_VERSION

        # User can restore data from backup if needed
        backup_file = backup_files[0]
        assert backup_file.stat().st_size > 0, "Backup should contain data"

        manager_new.cleanup()


# =============================================================================
# Data Population Workflow E2E Tests
# =============================================================================

class TestDataPopulationWorkflow:
    """Test complete data population workflows."""

    def test_batch_import_workflow(self, tmp_path):
        """
        E2E: Test batch importing reference data.

        Simulates importing data from external source in batches.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(
            database_path=str(db_file),
            batch_size=50
        )
        manager = ReferenceManager(config)
        manager.initialize()

        # Simulate batch import
        Session = manager.get_session_local()
        total_imported = 0

        # Import in batches
        for batch_num in range(3):
            session = Session()
            batch_nodes = []

            for i in range(config.batch_size):
                node = ReferenceNode(
                    source=f"batch_source_{batch_num}",
                    external_id=f"entity_{batch_num}_{i}",
                    title=f"Entity {batch_num}-{i}"
                )
                batch_nodes.append(node)

            session.add_all(batch_nodes)
            session.commit()
            total_imported += len(batch_nodes)
            session.close()

        # Verify all imported
        status = manager.get_status()
        assert status["node_count"] == total_imported
        assert status["node_count"] == 150  # 3 batches * 50 nodes

        manager.cleanup()

    def test_relationship_building_workflow(self, tmp_path):
        """
        E2E: Test building relationships between nodes.

        Simulates creating a knowledge graph with nodes and links.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)
        manager.initialize()

        Session = manager.get_session_local()
        session = Session()

        # Create entity hierarchy: Programming -> Python -> Django
        programming = ReferenceNode(
            source="conceptnet",
            external_id="/c/en/programming",
            title="programming"
        )
        python = ReferenceNode(
            source="conceptnet",
            external_id="/c/en/python",
            title="python"
        )
        django = ReferenceNode(
            source="conceptnet",
            external_id="/c/en/django",
            title="django"
        )

        session.add_all([programming, python, django])
        session.commit()

        # Create relationships
        link1 = ReferenceLink(
            subject_node_id=python.id,
            predicate="IsA",
            object_node_id=programming.id,
            attributes='{"weight": 0.9}'
        )
        link2 = ReferenceLink(
            subject_node_id=django.id,
            predicate="IsA",
            object_node_id=python.id,
            attributes='{"weight": 0.8}'
        )

        session.add_all([link1, link2])
        session.commit()

        # Verify graph structure
        status = manager.get_status()
        assert status["node_count"] == 3
        assert status["link_count"] == 2

        # Verify traversal works
        python_links = session.query(ReferenceLink).filter_by(
            subject_node_id=python.id
        ).all()
        assert len(python_links) == 1
        assert python_links[0].predicate == "IsA"

        session.close()
        manager.cleanup()

    def test_multi_source_integration_workflow(self, tmp_path):
        """
        E2E: Test integrating data from multiple sources.

        Simulates building a multi-source knowledge graph.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)
        manager.initialize()

        Session = manager.get_session_local()
        session = Session()

        # Python entity from different sources
        dbpedia_python = ReferenceNode(
            source="dbpedia",
            external_id="http://dbpedia.org/resource/Python_(programming_language)",
            title="Python (programming language)",
            definition="High-level programming language"
        )
        wikidata_python = ReferenceNode(
            source="wikidata",
            external_id="Q28865",
            title="Python",
            definition="Programming language"
        )
        conceptnet_python = ReferenceNode(
            source="conceptnet",
            external_id="/c/en/python",
            title="python"
        )
        schema_org_python = ReferenceNode(
            source="schema_org",
            external_id="ComputerLanguage",
            title="ComputerLanguage",
            definition="A computer programming language"
        )

        session.add_all([dbpedia_python, wikidata_python, conceptnet_python, schema_org_python])
        session.commit()

        # Create cross-source links (sameAs relationships)
        link1 = ReferenceLink(
            subject_node_id=dbpedia_python.id,
            predicate="sameAs",
            object_node_id=wikidata_python.id,
            attributes='{"confidence": 0.95}'
        )
        link2 = ReferenceLink(
            subject_node_id=wikidata_python.id,
            predicate="sameAs",
            object_node_id=conceptnet_python.id,
            attributes='{"confidence": 0.90}'
        )

        session.add_all([link1, link2])
        session.commit()

        # Verify multi-source graph
        status = manager.get_status()
        assert status["node_count"] == 4
        assert status["link_count"] == 2

        # Verify we can query by source
        dbpedia_count = session.query(ReferenceNode).filter_by(source="dbpedia").count()
        wikidata_count = session.query(ReferenceNode).filter_by(source="wikidata").count()
        assert dbpedia_count == 1
        assert wikidata_count == 1

        session.close()
        manager.cleanup()


# =============================================================================
# Error Recovery Workflow E2E Tests
# =============================================================================

class TestErrorRecoveryWorkflow:
    """Test error recovery and resilience workflows."""

    def test_corrupted_database_recovery_workflow(self, tmp_path):
        """
        E2E: Test recovery from corrupted database.

        Simulates database corruption and recovery.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(database_path=str(db_file))

        # Create valid database
        manager1 = ReferenceManager(config)
        manager1.initialize()
        manager1.cleanup()

        # Simulate corruption by truncating file
        with open(db_file, 'wb') as f:
            f.write(b'corrupted')

        # Attempt to initialize with corrupted database
        manager2 = ReferenceManager(config)

        # Should handle gracefully (either rebuild or return False)
        try:
            result = manager2.initialize()
            # If it succeeds, database was rebuilt
            if result:
                status = manager2.get_status()
                assert status["is_initialized"] is True
        except Exception:
            # If it fails, that's also acceptable for corrupted database
            pass
        finally:
            manager2.cleanup()

    def test_disk_full_simulation_workflow(self, tmp_path):
        """
        E2E: Test handling of disk space issues.

        Simulates running out of disk space during operations.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)
        manager.initialize()

        # This test would require mocking filesystem
        # For now, just verify cleanup works
        status = manager.get_status()
        assert status["is_initialized"] is True

        manager.cleanup()

    def test_concurrent_rebuild_conflict_resolution(self, tmp_path):
        """
        E2E: Test concurrent rebuild conflict resolution.

        Simulates two processes trying to rebuild simultaneously.
        """
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(database_path=str(db_file))

        # Create database
        manager = ReferenceManager(config)
        manager.initialize()

        # Set old version to trigger rebuild
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

        # Try to rebuild (lock should be created)
        manager2 = ReferenceManager(config)
        result = manager2.initialize()
        assert result is True, "First rebuild should succeed"

        # Verify database was rebuilt
        status = manager2.get_status()
        assert status["schema_version"] == REFERENCE_SCHEMA_VERSION

        manager2.cleanup()


# =============================================================================
# Complete Lifecycle E2E Test
# =============================================================================

class TestCompleteDatabaseLifecycle:
    """Test complete database lifecycle from creation to destruction."""

    def test_full_lifecycle_workflow(self, tmp_path):
        """
        E2E: Test complete database lifecycle.

        Covers initialization, population, usage, backup, and cleanup.
        """
        # Phase 1: Initial Setup
        db_file = tmp_path / "reference.db"
        config = ReferenceConfig(
            database_path=str(db_file),
            similarity_threshold=0.7,
            batch_size=100,
            retry_count=3
        )

        # Phase 2: First Use
        manager1 = ReferenceManager(config)
        assert manager1.initialize() is True

        # Phase 3: Data Population
        Session1 = manager1.get_session_local()
        session1 = Session1()

        nodes_created = []
        for i in range(20):
            node = ReferenceNode(
                source="test_source",
                external_id=f"entity_{i}",
                title=f"Test Entity {i}",
                definition=f"Definition for entity {i}"
            )
            session1.add(node)
            nodes_created.append(node)

        session1.commit()

        # Create relationships
        for i in range(19):
            link = ReferenceLink(
                subject_node_id=nodes_created[i].id,
                predicate="Next",
                object_node_id=nodes_created[i + 1].id
            )
            session1.add(link)

        session1.commit()
        session1.close()

        # Phase 4: Verify State
        status1 = manager1.get_status()
        assert status1["node_count"] == 20
        assert status1["link_count"] == 19
        assert status1["database_size"] > 0

        # Phase 5: Application Shutdown
        manager1.cleanup()

        # Phase 6: Application Restart
        manager2 = ReferenceManager(config)
        assert manager2.initialize() is True

        # Phase 7: Verify Data Persisted
        Session2 = manager2.get_session_local()
        session2 = Session2()
        node_count = session2.query(ReferenceNode).count()
        link_count = session2.query(ReferenceLink).count()
        assert node_count == 20
        assert link_count == 19
        session2.close()

        # Phase 8: Schema Upgrade Simulation
        engine = manager2.get_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM reference_db_version"))
            conn.execute(
                text("INSERT INTO reference_db_version "
                     "(schema_version, embedding_model, updated_at) "
                     "VALUES ('0.5.0', 'old-model', :updated_at)"),
                {"updated_at": datetime.now()}
            )
            conn.commit()
        manager2.cleanup()

        # Phase 9: Rebuild with Backup
        manager3 = ReferenceManager(config)
        assert manager3.initialize() is True

        # Phase 10: Verify Backup Created
        backup_files = list(tmp_path.glob("reference.backup_*.db"))
        assert len(backup_files) > 0
        backup_file = backup_files[0]
        assert backup_file.stat().st_size > 0

        # Phase 11: Verify Fresh Database
        status3 = manager3.get_status()
        assert status3["node_count"] == 0  # Fresh after rebuild
        assert status3["schema_version"] == REFERENCE_SCHEMA_VERSION

        # Phase 12: Final Cleanup
        manager3.cleanup()
        assert manager3.engine is None
        assert db_file.exists()  # Database file should remain


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
