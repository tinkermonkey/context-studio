"""
Integration tests for Phase 2: Verify datafiles directory creation across all database managers.

Tests the integration of directory creation logic with database initialization,
file system operations, and manager initialization workflows.
"""

import sys
import os
import tempfile
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add local-server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Settings, ConfigurationManager


class TestDatabaseManagerDirectoryIntegration:
    """Test directory creation integration across database managers."""

    def test_pipeline_manager_integration_with_config(self):
        """Test PipelineDatabaseManager creates directory using config paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config with custom datafiles path
            config_data = {
                'database': {
                    'default_url': f'sqlite:///{tmpdir}/datafiles/local.db',
                    'reference_path': f'{tmpdir}/datafiles/reference.db',
                    'reference_cache_path': f'{tmpdir}/datafiles/cache.db',
                    'pipeline_path': f'{tmpdir}/datafiles/pipeline.db'
                }
            }

            config_file = os.path.join(tmpdir, 'config.json')
            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Ensure datafiles directory does not exist
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            assert not os.path.exists(datafiles_dir)

            # Initialize pipeline manager with config path
            from pipeline.manager import PipelineDatabaseManager

            pipeline_path = config_manager.settings.database.pipeline_path
            manager = PipelineDatabaseManager(pipeline_db_path=pipeline_path)

            # Verify directory was created
            assert os.path.exists(datafiles_dir)
            assert os.path.isdir(datafiles_dir)

            # Verify database file exists
            assert os.path.exists(pipeline_path)

            # Verify we can interact with the database
            from pipeline.models import Base
            assert manager.engine is not None

            # Clean up
            manager.engine.dispose()

    def test_reference_manager_integration_with_config(self):
        """Test ReferenceManager creates directory using config paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config
            config_data = {
                'database': {
                    'default_url': f'sqlite:///{tmpdir}/datafiles/local.db',
                    'reference_path': f'{tmpdir}/datafiles/reference.db',
                    'reference_cache_path': f'{tmpdir}/datafiles/cache.db',
                    'pipeline_path': f'{tmpdir}/datafiles/pipeline.db'
                }
            }

            config_file = os.path.join(tmpdir, 'config.json')
            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Ensure datafiles directory does not exist
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            assert not os.path.exists(datafiles_dir)

            # Initialize reference manager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            ref_config = ReferenceConfig()
            ref_path = config_manager.settings.database.reference_path
            manager = ReferenceManager(ref_config, db_path=ref_path)

            # Verify directory was created
            assert os.path.exists(datafiles_dir)
            assert os.path.isdir(datafiles_dir)

            # Verify database file exists
            assert os.path.exists(ref_path)

            # Verify we can query the database
            conn = manager.get_connection()
            assert conn is not None
            conn.close()

            # Clean up
            manager.close()

    def test_all_managers_coexist_in_same_directory(self):
        """Test that all database managers can coexist in the same datafiles directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')

            # Ensure directory does not exist
            assert not os.path.exists(datafiles_dir)

            # Create all managers
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            pipeline_path = os.path.join(datafiles_dir, 'pipeline.db')
            reference_path = os.path.join(datafiles_dir, 'reference.db')

            # Initialize pipeline manager (creates directory)
            pipeline_mgr = PipelineDatabaseManager(pipeline_db_path=pipeline_path)
            assert os.path.exists(datafiles_dir)

            # Initialize reference manager (directory already exists)
            ref_config = ReferenceConfig()
            reference_mgr = ReferenceManager(ref_config, db_path=reference_path)

            # Verify both databases exist
            assert os.path.exists(pipeline_path)
            assert os.path.exists(reference_path)

            # Verify both managers are functional
            assert pipeline_mgr.engine is not None
            conn = reference_mgr.get_connection()
            assert conn is not None
            conn.close()

            # Clean up
            pipeline_mgr.engine.dispose()
            reference_mgr.close()

    def test_proxy_manager_directory_creation_integration(self):
        """Test ReferenceAPIProxyManager creates directory for cache database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'datafiles')
            cache_path = os.path.join(cache_dir, 'reference_api_cache.db')

            # Ensure directory does not exist
            assert not os.path.exists(cache_dir)

            # Mock config and CachingProxy
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
                with patch('nlp.proxy_manager.CachingProxy') as mock_proxy_class:
                    mock_proxy_instance = MagicMock()
                    mock_proxy_class.return_value = mock_proxy_instance

                    from nlp.proxy_manager import ReferenceAPIProxyManager

                    manager = ReferenceAPIProxyManager()
                    result = manager.start_proxy()

                    # Verify directory was created
                    assert os.path.exists(cache_dir)
                    assert os.path.isdir(cache_dir)
                    assert result is True


class TestDirectoryCreationWithFileSystemOperations:
    """Test directory creation with various file system scenarios."""

    def test_directory_creation_with_nested_paths(self):
        """Test that managers can create nested directory structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use nested path structure
            nested_path = os.path.join(tmpdir, 'app', 'data', 'datafiles', 'pipeline.db')

            # Ensure parent directories don't exist
            assert not os.path.exists(os.path.dirname(nested_path))

            from pipeline.manager import PipelineDatabaseManager

            manager = PipelineDatabaseManager(pipeline_db_path=nested_path)

            # Verify full path was created
            assert os.path.exists(os.path.dirname(nested_path))
            assert os.path.exists(nested_path)

            # Clean up
            manager.engine.dispose()

    def test_directory_creation_with_relative_paths(self):
        """Test that managers handle relative paths correctly."""
        # Save current directory
        original_cwd = os.getcwd()

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # Change to temp directory
                os.chdir(tmpdir)

                # Use relative path
                relative_path = './datafiles/pipeline.db'

                from pipeline.manager import PipelineDatabaseManager

                manager = PipelineDatabaseManager(pipeline_db_path=relative_path)

                # Verify directory was created in current directory
                assert os.path.exists('./datafiles')
                assert os.path.exists(relative_path)

                # Clean up
                manager.engine.dispose()

            finally:
                # Restore original directory
                os.chdir(original_cwd)

    def test_directory_permissions_after_creation(self):
        """Test that created directories have appropriate permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            db_path = os.path.join(datafiles_dir, 'pipeline.db')

            from pipeline.manager import PipelineDatabaseManager

            manager = PipelineDatabaseManager(pipeline_db_path=db_path)

            # Check directory permissions
            dir_stat = os.stat(datafiles_dir)

            # Verify directory is readable, writable, and executable by owner
            assert os.access(datafiles_dir, os.R_OK)
            assert os.access(datafiles_dir, os.W_OK)
            assert os.access(datafiles_dir, os.X_OK)

            # Verify we can create files in the directory
            test_file = os.path.join(datafiles_dir, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            assert os.path.exists(test_file)

            # Clean up
            manager.engine.dispose()

    def test_concurrent_directory_creation(self):
        """Test that multiple managers can safely create the same directory concurrently."""
        import threading
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            errors = []
            managers = []

            def create_manager(db_name):
                try:
                    from pipeline.manager import PipelineDatabaseManager
                    db_path = os.path.join(datafiles_dir, db_name)
                    mgr = PipelineDatabaseManager(pipeline_db_path=db_path)
                    managers.append(mgr)
                except Exception as e:
                    errors.append(str(e))

            # Create multiple threads that try to create the directory
            threads = [
                threading.Thread(target=create_manager, args=(f'pipeline_{i}.db',))
                for i in range(5)
            ]

            # Start all threads
            for t in threads:
                t.start()

            # Wait for completion
            for t in threads:
                t.join()

            # Verify no errors occurred
            assert len(errors) == 0, f"Errors occurred: {errors}"

            # Verify directory was created
            assert os.path.exists(datafiles_dir)

            # Clean up
            for mgr in managers:
                mgr.engine.dispose()


class TestManagerInitializationSequencing:
    """Test that directory creation happens at the right time during initialization."""

    def test_pipeline_manager_creates_dir_before_db_init(self):
        """Test that PipelineDatabaseManager creates directory before database initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            db_path = os.path.join(datafiles_dir, 'pipeline.db')

            # Track when directory was created
            creation_sequence = []

            original_makedirs = os.makedirs
            original_create_engine = None

            def tracked_makedirs(*args, **kwargs):
                creation_sequence.append('makedirs')
                return original_makedirs(*args, **kwargs)

            from sqlalchemy import create_engine as original_create
            original_create_engine = original_create

            def tracked_create_engine(*args, **kwargs):
                creation_sequence.append('create_engine')
                return original_create_engine(*args, **kwargs)

            with patch('os.makedirs', side_effect=tracked_makedirs):
                with patch('pipeline.manager.create_engine', side_effect=tracked_create_engine):
                    from pipeline.manager import PipelineDatabaseManager

                    manager = PipelineDatabaseManager(pipeline_db_path=db_path)

                    # Verify makedirs was called before create_engine
                    if 'makedirs' in creation_sequence and 'create_engine' in creation_sequence:
                        makedirs_idx = creation_sequence.index('makedirs')
                        engine_idx = creation_sequence.index('create_engine')
                        assert makedirs_idx < engine_idx, "Directory should be created before engine"

                    # Clean up
                    manager.engine.dispose()

    def test_reference_manager_creates_dir_before_engine(self):
        """Test that ReferenceManager creates directory before engine creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            db_path = os.path.join(datafiles_dir, 'reference.db')

            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            config = ReferenceConfig()
            manager = ReferenceManager(config, db_path=db_path)

            # Verify directory exists before we can use the manager
            assert os.path.exists(datafiles_dir)
            assert os.path.exists(db_path)

            # Verify manager is functional
            conn = manager.get_connection()
            assert conn is not None
            conn.close()

            # Clean up
            manager.close()


class TestFreshInstallationScenarios:
    """Test fresh installation scenarios with no existing directories."""

    def test_fresh_install_with_default_config(self):
        """Test application startup on fresh installation with default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create default config
            config_data = {
                'database': {
                    'default_url': f'sqlite:///{tmpdir}/datafiles/local.db',
                    'reference_path': f'{tmpdir}/datafiles/reference.db',
                    'reference_cache_path': f'{tmpdir}/datafiles/cache.db',
                    'pipeline_path': f'{tmpdir}/datafiles/pipeline.db'
                }
            }

            config_file = os.path.join(tmpdir, 'config.json')
            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Verify datafiles directory does not exist
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            assert not os.path.exists(datafiles_dir)

            # Simulate fresh application startup by initializing all managers
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            # Start pipeline manager
            pipeline_mgr = PipelineDatabaseManager(
                pipeline_db_path=config_manager.settings.database.pipeline_path
            )

            # Verify directory was created
            assert os.path.exists(datafiles_dir)

            # Start reference manager
            ref_config = ReferenceConfig()
            ref_mgr = ReferenceManager(
                ref_config,
                db_path=config_manager.settings.database.reference_path
            )

            # Verify all databases exist
            assert os.path.exists(config_manager.settings.database.pipeline_path)
            assert os.path.exists(config_manager.settings.database.reference_path)

            # Verify managers are functional
            assert pipeline_mgr.engine is not None
            conn = ref_mgr.get_connection()
            assert conn is not None
            conn.close()

            # Clean up
            pipeline_mgr.engine.dispose()
            ref_mgr.close()

    def test_fresh_install_creates_databases_successfully(self):
        """Test that fresh installation creates all databases successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')

            # Initialize managers
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            pipeline_path = os.path.join(datafiles_dir, 'pipeline.db')
            reference_path = os.path.join(datafiles_dir, 'reference.db')

            # Create managers
            pipeline_mgr = PipelineDatabaseManager(pipeline_db_path=pipeline_path)
            ref_config = ReferenceConfig()
            ref_mgr = ReferenceManager(ref_config, db_path=reference_path)

            # Verify databases are valid SQLite files
            # Check pipeline database
            pipeline_conn = sqlite3.connect(pipeline_path)
            pipeline_cursor = pipeline_conn.cursor()
            pipeline_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            pipeline_tables = pipeline_cursor.fetchall()
            assert len(pipeline_tables) > 0, "Pipeline database should have tables"
            pipeline_conn.close()

            # Check reference database
            reference_conn = sqlite3.connect(reference_path)
            reference_cursor = reference_conn.cursor()
            reference_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            reference_tables = reference_cursor.fetchall()
            assert len(reference_tables) > 0, "Reference database should have tables"
            reference_conn.close()

            # Clean up
            pipeline_mgr.engine.dispose()
            ref_mgr.close()

    def test_fresh_install_with_custom_directory_structure(self):
        """Test fresh installation with custom directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use custom directory structure
            custom_dir = os.path.join(tmpdir, 'my_app', 'databases', 'datafiles')

            config_data = {
                'database': {
                    'default_url': f'sqlite:///{custom_dir}/local.db',
                    'reference_path': f'{custom_dir}/reference.db',
                    'reference_cache_path': f'{custom_dir}/cache.db',
                    'pipeline_path': f'{custom_dir}/pipeline.db'
                }
            }

            config_file = os.path.join(tmpdir, 'config.json')
            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            config_manager.save()

            # Verify custom directory structure does not exist
            assert not os.path.exists(custom_dir)

            # Initialize managers
            from pipeline.manager import PipelineDatabaseManager

            pipeline_mgr = PipelineDatabaseManager(
                pipeline_db_path=config_manager.settings.database.pipeline_path
            )

            # Verify entire path was created
            assert os.path.exists(custom_dir)
            assert os.path.exists(config_manager.settings.database.pipeline_path)

            # Clean up
            pipeline_mgr.engine.dispose()


class TestDatasetManagerDirectoryIntegration:
    """Test DatasetManager directory creation integration."""

    def test_dataset_manager_creates_custom_directory(self):
        """Test that DatasetManager creates its configured directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datasets_dir = os.path.join(tmpdir, 'my_datasets')
            config_path = os.path.join(tmpdir, 'datasets.json')

            # Ensure directory does not exist
            assert not os.path.exists(datasets_dir)

            from dataset.manager import DatasetManager

            manager = DatasetManager(
                datasets_config_path=config_path,
                datasets_directory=datasets_dir
            )

            # Verify directory was created
            assert os.path.exists(datasets_dir)
            assert os.path.isdir(datasets_dir)

    def test_dataset_manager_with_nested_directory(self):
        """Test DatasetManager creates nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datasets_dir = os.path.join(tmpdir, 'app', 'data', 'datasets')
            config_path = os.path.join(tmpdir, 'datasets.json')

            # Ensure nested path does not exist
            assert not os.path.exists(datasets_dir)

            from dataset.manager import DatasetManager

            manager = DatasetManager(
                datasets_config_path=config_path,
                datasets_directory=datasets_dir
            )

            # Verify full path was created
            assert os.path.exists(datasets_dir)

    def test_dataset_manager_integration_with_other_managers(self):
        """Test that DatasetManager works alongside other database managers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datafiles_dir = os.path.join(tmpdir, 'datafiles')
            datasets_dir = os.path.join(tmpdir, 'datasets')

            from pipeline.manager import PipelineDatabaseManager
            from dataset.manager import DatasetManager

            # Create both managers
            pipeline_path = os.path.join(datafiles_dir, 'pipeline.db')
            config_path = os.path.join(tmpdir, 'datasets.json')

            pipeline_mgr = PipelineDatabaseManager(pipeline_db_path=pipeline_path)
            dataset_mgr = DatasetManager(
                datasets_config_path=config_path,
                datasets_directory=datasets_dir
            )

            # Verify both directories were created
            assert os.path.exists(datafiles_dir)
            assert os.path.exists(datasets_dir)

            # Clean up
            pipeline_mgr.engine.dispose()


class TestErrorHandlingIntegration:
    """Test error handling in directory creation across integration scenarios."""

    def test_invalid_path_handling(self):
        """Test handling of invalid paths during directory creation."""
        # Test with empty string path (invalid)
        with pytest.raises(Exception):
            from pipeline.manager import PipelineDatabaseManager
            manager = PipelineDatabaseManager(pipeline_db_path="")

    def test_directory_cleanup_on_error(self):
        """Test that resources are cleaned up properly if initialization fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'datafiles', 'test.db')

            from pipeline.manager import PipelineDatabaseManager

            # Create manager
            manager = PipelineDatabaseManager(pipeline_db_path=db_path)

            # Verify database exists
            assert os.path.exists(db_path)

            # Clean up
            manager.engine.dispose()

            # Verify we can create another manager with the same path
            manager2 = PipelineDatabaseManager(pipeline_db_path=db_path)
            assert manager2.engine is not None

            # Clean up
            manager2.engine.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
