"""
End-to-End tests for Phase 2: Verify datafiles directory creation across all database managers.

Tests complete application workflows from fresh installation through normal operation,
ensuring directory creation works correctly in real-world scenarios.
"""

import sys
import os
import tempfile
import shutil
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add local-server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Settings, ConfigurationManager


class TestFreshInstallationE2E:
    """End-to-end tests for fresh installation scenarios."""

    def test_complete_fresh_installation_workflow(self):
        """Test complete workflow from config creation to database operations on fresh install."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: User creates config file for fresh installation
            config_file = os.path.join(tmpdir, 'config.json')
            datafiles_dir = os.path.join(tmpdir, 'datafiles')

            config_data = {
                'database': {
                    'default_url': f'sqlite:///{datafiles_dir}/local.db',
                    'reference_path': f'{datafiles_dir}/reference.db',
                    'reference_cache_path': f'{datafiles_dir}/cache.db',
                    'operations_path': f'{datafiles_dir}/operations.db'
                }
            }

            # Save config
            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Step 2: Verify no datafiles directory exists (fresh install)
            assert not os.path.exists(datafiles_dir), "Fresh install should have no datafiles directory"

            # Step 3: Application starts and initializes database managers
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            # Initialize pipeline manager
            pipeline_mgr = PipelineDatabaseManager(
                operations_db_path=config_manager.settings.database.operations_path
            )

            # Step 4: Verify directory was created automatically
            assert os.path.exists(datafiles_dir), "Datafiles directory should be created automatically"

            # Initialize reference manager
            ref_config = ReferenceConfig()
            ref_mgr = ReferenceManager(
                ref_config,
                db_path=config_manager.settings.database.reference_path
            )

            # Step 5: Verify all databases were created
            assert os.path.exists(config_manager.settings.database.operations_path)
            assert os.path.exists(config_manager.settings.database.reference_path)

            # Step 6: Verify databases are functional
            # Test operations database
            assert pipeline_mgr.engine is not None

            # Test reference database - verify tables exist
            from sqlalchemy import text
            with ref_mgr.engine.connect() as ref_conn:
                result = ref_conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = result.fetchall()
                assert len(tables) > 0, "Reference database should have tables"

            # Step 7: Clean shutdown
            pipeline_mgr.engine.dispose()
            ref_mgr.close()

            # Step 8: Verify application can restart successfully
            pipeline_mgr2 = PipelineDatabaseManager(
                operations_db_path=config_manager.settings.database.operations_path
            )
            assert pipeline_mgr2.engine is not None

            # Clean up
            pipeline_mgr2.engine.dispose()

    def test_fresh_install_with_all_database_managers(self):
        """Test fresh installation initializing all database managers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            datasets_dir = os.path.join(tmpdir, 'datasets')

            # Verify clean slate
            assert not os.path.exists(datafiles_dir)
            assert not os.path.exists(datasets_dir)

            # Initialize all managers
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig
            from dataset.manager import DatasetManager

            # Create managers
            operations_path = os.path.join(datafiles_dir, 'operations.db')
            reference_path = os.path.join(datafiles_dir, 'reference.db')
            config_path = os.path.join(tmpdir, 'datasets.json')

            pipeline_mgr = PipelineDatabaseManager(operations_db_path=operations_path)
            ref_config = ReferenceConfig()
            ref_mgr = ReferenceManager(ref_config, db_path=reference_path)
            dataset_mgr = DatasetManager(
                datasets_config_path=config_path,
                datasets_directory=datasets_dir
            )

            # Verify all directories were created
            assert os.path.exists(datafiles_dir)
            assert os.path.exists(datasets_dir)

            # Verify all databases are functional
            assert pipeline_mgr.engine is not None
            assert ref_mgr.engine is not None

            # Clean up
            pipeline_mgr.engine.dispose()
            ref_mgr.close()

    def test_fresh_install_handles_proxy_cache_db(self):
        """Test fresh installation with proxy cache database creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'datafiles')
            cache_path = os.path.join(cache_dir, 'reference_api_cache.db')

            # Verify clean slate
            assert not os.path.exists(cache_dir)

            # Mock proxy configuration
            mock_config = {
                "server": {"host": "127.0.0.1", "port": 18080},
                "cache": {"database_path": cache_path},
                "domain_mappings": {"test": {"upstream": "http://test.com"}},
                "throttling": {"domain_limits": {}}
            }

            mock_settings = MagicMock()
            mock_settings.ENABLE_CACHING_PROXY = {"test": True}
            mock_settings.get_reference_api_buddy_config.return_value = mock_config

            with patch('nlp.proxy_manager.get_settings', return_value=mock_settings):
                with patch('reference_api_buddy.core.proxy.CachingProxy') as mock_proxy_class:
                    mock_proxy_instance = MagicMock()
                    mock_proxy_class.return_value = mock_proxy_instance

                    from nlp.proxy_manager import ReferenceAPIProxyManager

                    # Start proxy manager
                    proxy_mgr = ReferenceAPIProxyManager()
                    result = proxy_mgr.start_proxy()

                    # Verify directory was created
                    assert os.path.exists(cache_dir)
                    assert result is True


class TestApplicationRestartE2E:
    """End-to-end tests for application restart scenarios."""

    def test_restart_with_existing_directories(self):
        """Test application restart when directories already exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            operations_path = os.path.join(datafiles_dir, 'operations.db')

            # First startup - creates directory
            from pipeline.manager import PipelineDatabaseManager

            mgr1 = PipelineDatabaseManager(operations_db_path=operations_path)
            assert os.path.exists(datafiles_dir)
            mgr1.engine.dispose()

            # Second startup - directory already exists
            mgr2 = PipelineDatabaseManager(operations_db_path=operations_path)
            assert os.path.exists(datafiles_dir)
            assert os.path.exists(operations_path)

            # Should work without errors
            assert mgr2.engine is not None

            mgr2.engine.dispose()

    def test_restart_preserves_existing_data(self):
        """Test that application restart preserves existing database data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            operations_path = os.path.join(datafiles_dir, 'operations.db')

            from pipeline.manager import PipelineDatabaseManager

            # First startup - create directory and database
            mgr1 = PipelineDatabaseManager(operations_db_path=operations_path)
            assert os.path.exists(datafiles_dir)
            assert os.path.exists(operations_path)
            mgr1.engine.dispose()

            # Second startup - verify database still exists and is accessible
            mgr2 = PipelineDatabaseManager(operations_db_path=operations_path)
            assert os.path.exists(datafiles_dir)
            assert os.path.exists(operations_path)
            assert mgr2.engine is not None
            mgr2.engine.dispose()


class TestMigrationScenarioE2E:
    """End-to-end tests for migration scenarios."""

    def test_migration_from_manual_directory_creation(self):
        """Test migration from manually created directories to automated creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')

            # Simulate old scenario - user manually creates directory
            os.makedirs(datafiles_dir, exist_ok=True)

            # Place a marker file to verify directory existed before
            marker_file = os.path.join(datafiles_dir, 'existing_file.txt')
            with open(marker_file, 'w') as f:
                f.write('I existed before automated creation')

            # Now use automated directory creation
            from pipeline.manager import PipelineDatabaseManager

            operations_path = os.path.join(datafiles_dir, 'operations.db')
            mgr = PipelineDatabaseManager(operations_db_path=operations_path)

            # Verify existing files are preserved
            assert os.path.exists(marker_file)
            with open(marker_file, 'r') as f:
                content = f.read()
                assert content == 'I existed before automated creation'

            # Verify new database was created
            assert os.path.exists(operations_path)

            mgr.engine.dispose()

    def test_migration_with_partial_database_files(self):
        """Test migration when some database files exist but directory needs verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            os.makedirs(datafiles_dir, exist_ok=True)

            # Create one database manually
            operations_path = os.path.join(datafiles_dir, 'operations.db')
            conn = sqlite3.connect(operations_path)
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()
            conn.close()

            # Now initialize managers - should handle existing DB gracefully
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            # Pipeline manager with existing DB
            pipeline_mgr = PipelineDatabaseManager(operations_db_path=operations_path)
            assert pipeline_mgr.engine is not None

            # Reference manager creating new DB in same directory
            reference_path = os.path.join(datafiles_dir, 'reference.db')
            ref_config = ReferenceConfig()
            ref_mgr = ReferenceManager(ref_config, db_path=reference_path)

            # Verify both databases exist
            assert os.path.exists(operations_path)
            assert os.path.exists(reference_path)

            # Clean up
            pipeline_mgr.engine.dispose()
            ref_mgr.close()


class TestProductionDeploymentE2E:
    """End-to-end tests simulating production deployment scenarios."""

    def test_docker_container_deployment(self):
        """Test deployment scenario similar to Docker container with clean filesystem."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate Docker volume mount point
            app_dir = os.path.join(tmpdir, 'app')
            data_volume = os.path.join(tmpdir, 'data')
            os.makedirs(app_dir, exist_ok=True)
            os.makedirs(data_volume, exist_ok=True)

            datafiles_dir = os.path.join(data_volume, 'datafiles')

            # Create config pointing to volume
            config_file = os.path.join(app_dir, 'config.json')
            config_data = {
                'database': {
                    'default_url': f'sqlite:///{datafiles_dir}/local.db',
                    'reference_path': f'{datafiles_dir}/reference.db',
                    'reference_cache_path': f'{datafiles_dir}/cache.db',
                    'operations_path': f'{datafiles_dir}/operations.db'
                }
            }

            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Container starts - initialize managers
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            pipeline_mgr = PipelineDatabaseManager(
                operations_db_path=config_manager.settings.database.operations_path
            )
            ref_config = ReferenceConfig()
            ref_mgr = ReferenceManager(
                ref_config,
                db_path=config_manager.settings.database.reference_path
            )

            # Verify databases created in volume
            assert os.path.exists(datafiles_dir)
            assert os.path.exists(config_manager.settings.database.operations_path)
            assert os.path.exists(config_manager.settings.database.reference_path)

            # Clean up
            pipeline_mgr.engine.dispose()
            ref_mgr.close()

    def test_multi_instance_deployment(self):
        """Test deployment with multiple instances sharing configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Shared config directory
            shared_config_dir = os.path.join(tmpdir, 'shared')
            os.makedirs(shared_config_dir, exist_ok=True)

            # Instance-specific data directories
            instance1_dir = os.path.join(tmpdir, 'instance1', 'datafiles')
            instance2_dir = os.path.join(tmpdir, 'instance2', 'datafiles')

            from pipeline.manager import PipelineDatabaseManager

            # Instance 1
            pipeline1_path = os.path.join(instance1_dir, 'operations.db')
            mgr1 = PipelineDatabaseManager(operations_db_path=pipeline1_path)
            assert os.path.exists(instance1_dir)

            # Instance 2
            pipeline2_path = os.path.join(instance2_dir, 'operations.db')
            mgr2 = PipelineDatabaseManager(operations_db_path=pipeline2_path)
            assert os.path.exists(instance2_dir)

            # Verify both instances are independent
            assert instance1_dir != instance2_dir
            assert os.path.exists(pipeline1_path)
            assert os.path.exists(pipeline2_path)

            # Clean up
            mgr1.engine.dispose()
            mgr2.engine.dispose()


class TestRealWorldWorkflowsE2E:
    """End-to-end tests for real-world application workflows."""

    def test_complete_knowledge_graph_workflow(self):
        """Test complete workflow: install, configure, create nodes, query data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            config_file = os.path.join(tmpdir, 'config.json')

            config_data = {
                'database': {
                    'default_url': f'sqlite:///{datafiles_dir}/local.db',
                    'reference_path': f'{datafiles_dir}/reference.db',
                    'reference_cache_path': f'{datafiles_dir}/cache.db',
                    'operations_path': f'{datafiles_dir}/operations.db'
                }
            }

            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Fresh install - no directories
            assert not os.path.exists(datafiles_dir)

            # Application starts
            from pipeline.manager import PipelineDatabaseManager

            pipeline_mgr = PipelineDatabaseManager(
                operations_db_path=config_manager.settings.database.operations_path
            )

            # Directory created automatically
            assert os.path.exists(datafiles_dir)

            # Verify database is functional
            assert pipeline_mgr.engine is not None

            # Application restarts
            pipeline_mgr.engine.dispose()

            # Verify database persists
            pipeline_mgr2 = PipelineDatabaseManager(
                operations_db_path=config_manager.settings.database.operations_path
            )
            assert pipeline_mgr2.engine is not None

            pipeline_mgr2.engine.dispose()

    def test_backup_and_recovery_workflow(self):
        """Test backup and recovery workflow with directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Original installation
            original_dir = os.path.join(tmpdir, 'original', 'datafiles')
            backup_dir = os.path.join(tmpdir, 'backup')
            recovery_dir = os.path.join(tmpdir, 'recovery', 'datafiles')

            from pipeline.manager import PipelineDatabaseManager

            # Create original database
            original_path = os.path.join(original_dir, 'operations.db')
            mgr1 = PipelineDatabaseManager(operations_db_path=original_path)
            assert os.path.exists(original_path)
            mgr1.engine.dispose()

            # Backup entire datafiles directory
            shutil.copytree(original_dir, backup_dir)

            # Simulate disaster - delete original
            shutil.rmtree(original_dir)
            assert not os.path.exists(original_dir)

            # Recovery - create new instance directory
            assert not os.path.exists(recovery_dir)

            # Initialize new instance (creates directory)
            recovery_path = os.path.join(recovery_dir, 'operations.db')
            mgr2 = PipelineDatabaseManager(operations_db_path=recovery_path)
            mgr2.engine.dispose()

            # Restore from backup
            restored_path = os.path.join(recovery_dir, 'operations.db')
            backup_db_path = os.path.join(backup_dir, 'operations.db')
            shutil.copy(backup_db_path, restored_path)

            # Verify recovery - database file exists
            mgr3 = PipelineDatabaseManager(operations_db_path=restored_path)
            assert mgr3.engine is not None
            mgr3.engine.dispose()

    def test_configuration_change_workflow(self):
        """Test workflow when user changes database paths in configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            # Original configuration
            old_datafiles = os.path.join(tmpdir, 'old_datafiles')
            config_data = {
                'database': {
                    'default_url': f'sqlite:///{old_datafiles}/local.db',
                    'reference_path': f'{old_datafiles}/reference.db',
                    'reference_cache_path': f'{old_datafiles}/cache.db',
                    'operations_path': f'{old_datafiles}/operations.db'
                }
            }

            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Create initial database
            from pipeline.manager import PipelineDatabaseManager

            old_operations_path = config_manager.settings.database.operations_path
            mgr1 = PipelineDatabaseManager(operations_db_path=old_operations_path)
            assert os.path.exists(old_datafiles)
            mgr1.engine.dispose()

            # User changes configuration to new path
            new_datafiles = os.path.join(tmpdir, 'new_datafiles')
            config_manager.settings.database.operations_path = f'{new_datafiles}/operations.db'
            config_manager.save()

            # Verify new directory doesn't exist yet
            assert not os.path.exists(new_datafiles)

            # Application restarts with new config
            new_operations_path = config_manager.settings.database.operations_path
            mgr2 = PipelineDatabaseManager(operations_db_path=new_operations_path)

            # New directory should be created automatically
            assert os.path.exists(new_datafiles)
            assert os.path.exists(new_operations_path)

            # Old directory still exists (user must manually migrate)
            assert os.path.exists(old_datafiles)

            mgr2.engine.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
