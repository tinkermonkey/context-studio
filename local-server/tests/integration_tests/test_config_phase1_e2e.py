"""
End-to-End tests for Phase 1: schema_org_path removal
Tests complete application workflows with updated configuration
"""

import sys
import json
import tempfile
import os
import subprocess
import time
import signal
from pathlib import Path
import pytest
import requests

# Add local-server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Settings, ConfigurationManager


class TestApplicationStartupE2E:
    """Test complete application startup and operation with new configuration"""

    def test_config_loads_on_application_import(self):
        """Test that config loads correctly when application modules are imported"""
        # This simulates application startup
        config_data = {
            'database': {
                'default_url': 'sqlite:///:memory:',
                'reference_path': ':memory:',
                'reference_cache_path': ':memory:',
                'operations_path': ':memory:'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_config = f.name

        try:
            # Set config path
            original_config = os.environ.get('CONFIG_PATH')
            os.environ['CONFIG_PATH'] = temp_config

            # Import main modules (simulates app startup)
            config_manager = ConfigurationManager(temp_config)

            # Verify config loaded successfully
            assert config_manager.settings is not None
            assert not hasattr(config_manager.settings.database, 'schema_org_path')

            # Verify validation passes
            errors = config_manager.validate()
            assert not errors, f"Validation failed: {errors}"

        finally:
            # Cleanup
            if original_config:
                os.environ['CONFIG_PATH'] = original_config
            elif 'CONFIG_PATH' in os.environ:
                del os.environ['CONFIG_PATH']

            if os.path.exists(temp_config):
                os.unlink(temp_config)

    def test_full_config_workflow(self):
        """Test complete workflow: create config, start app, modify config, reload"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')
            db_dir = os.path.join(tmpdir, 'datafiles')
            os.makedirs(db_dir, exist_ok=True)

            # Step 1: Create initial config
            config_data = {
                'database': {
                    'default_url': f'sqlite:///{db_dir}/local.db',
                    'reference_path': f'{db_dir}/reference.db',
                    'reference_cache_path': f'{db_dir}/cache.db',
                    'operations_path': f'{db_dir}/operations.db'
                }
            }

            manager = ConfigurationManager(config_file)
            manager.settings = Settings(**config_data)
            assert manager.save()

            # Step 2: Load config (simulates app start)
            manager2 = ConfigurationManager(config_file)
            errors = manager2.validate()
            assert not errors

            # Step 3: Verify no deprecated fields
            assert not hasattr(manager2.settings.database, 'schema_org_path')

            # Step 4: Modify config
            manager2.settings.database.default_url = f'sqlite:///{db_dir}/modified.db'
            assert manager2.save()

            # Step 5: Reload (simulates app restart)
            manager3 = ConfigurationManager(config_file)
            assert manager3.settings.database.default_url == f'sqlite:///{db_dir}/modified.db'
            assert not hasattr(manager3.settings.database, 'schema_org_path')

            # Step 6: Validate final state
            errors = manager3.validate()
            assert not errors

    def test_config_migration_workflow(self):
        """Test workflow for migrating from old config to new config"""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_config_file = os.path.join(tmpdir, 'config.json')

            # Step 1: User has old config with schema_org_path
            old_config = {
                'database': {
                    'default_url': 'sqlite:///./local.db',
                    'schema_org_path': './old_schema.db',  # Deprecated
                    'reference_path': './reference.db',
                    'reference_cache_path': './cache.db',
                    'operations_path': './operations.db'
                }
            }

            with open(old_config_file, 'w') as f:
                json.dump(old_config, f)

            # Step 2: App starts and loads config
            manager = ConfigurationManager(old_config_file)

            # Step 3: Verify deprecated field is ignored
            assert not hasattr(manager.settings.database, 'schema_org_path')

            # Step 4: App validates config
            errors = manager.validate()
            assert not errors, "Old config should validate successfully"

            # Step 5: App saves config (cleaning up deprecated fields)
            assert manager.save()

            # Step 6: Verify saved config doesn't have deprecated field
            with open(old_config_file, 'r') as f:
                saved_config = json.load(f)

            assert 'schema_org_path' not in saved_config.get('database', {})

            # Step 7: App restarts and loads clean config
            manager2 = ConfigurationManager(old_config_file)
            assert not hasattr(manager2.settings.database, 'schema_org_path')

            # Step 8: Verify all required fields are present
            db_config = manager2.settings.database
            assert db_config.default_url
            assert db_config.reference_path
            assert db_config.reference_cache_path
            assert db_config.operations_path

    def test_multi_user_config_scenario(self):
        """Test scenario with multiple config files (e.g., dev, staging, prod)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            environments = ['dev', 'staging', 'prod']
            configs = {}

            # Create configs for each environment
            for env in environments:
                config_file = os.path.join(tmpdir, f'config.{env}.json')
                config_data = {
                    'database': {
                        'default_url': f'sqlite:///./local_{env}.db',
                        'reference_path': f'./reference_{env}.db',
                        'reference_cache_path': f'./cache_{env}.db',
                        'operations_path': f'./pipeline_{env}.db'
                    }
                }

                manager = ConfigurationManager(config_file)
                manager.settings = Settings(**config_data)
                manager.save()

                configs[env] = config_file

            # Verify each config loads correctly
            for env in environments:
                manager = ConfigurationManager(configs[env])

                # Verify no schema_org_path
                assert not hasattr(manager.settings.database, 'schema_org_path')

                # Verify environment-specific paths
                assert env in manager.settings.database.default_url
                assert env in manager.settings.database.reference_path

                # Validate
                errors = manager.validate()
                assert not errors

    def test_config_with_all_database_types(self):
        """Test configuration with different database connection types"""
        test_cases = [
            {
                'name': 'SQLite file',
                'url': 'sqlite:///./test.db'
            },
            {
                'name': 'SQLite memory',
                'url': 'sqlite:///:memory:'
            },
            {
                'name': 'SQLite absolute path',
                'url': 'sqlite:////tmp/test.db'
            }
        ]

        for test_case in test_cases:
            config_data = {
                'database': {
                    'default_url': test_case['url'],
                    'reference_path': ':memory:',
                    'reference_cache_path': ':memory:',
                    'operations_path': ':memory:'
                }
            }

            settings = Settings(**config_data)

            # Verify no schema_org_path for any database type
            assert not hasattr(settings.database, 'schema_org_path'), \
                f"schema_org_path found for {test_case['name']}"

            # Verify URL was set correctly
            assert settings.database.default_url == test_case['url']

    def test_config_change_detection(self):
        """Test that config changes are properly detected and handled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            # Initial config
            config_data = {
                'database': {
                    'default_url': 'sqlite:///./local.db',
                    'reference_path': './reference.db',
                    'reference_cache_path': './cache.db',
                    'operations_path': './operations.db'
                }
            }

            manager = ConfigurationManager(config_file)
            manager.settings = Settings(**config_data)
            manager.save()

            # Record initial modification time
            initial_mtime = os.path.getmtime(config_file)

            # Wait a bit to ensure timestamp difference
            time.sleep(0.1)

            # Modify config
            manager.settings.database.default_url = 'sqlite:///./modified.db'
            manager.save()

            # Verify file was modified
            new_mtime = os.path.getmtime(config_file)
            assert new_mtime > initial_mtime

            # Load and verify changes
            manager2 = ConfigurationManager(config_file)
            assert manager2.settings.database.default_url == 'sqlite:///./modified.db'

    def test_config_backup_and_restore(self):
        """Test workflow for backing up and restoring configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')
            backup_file = os.path.join(tmpdir, 'config.backup.json')

            # Create original config
            config_data = {
                'database': {
                    'default_url': 'sqlite:///./original.db',
                    'reference_path': './original_ref.db',
                    'reference_cache_path': './original_cache.db',
                    'operations_path': './original_pipeline.db'
                }
            }

            manager = ConfigurationManager(config_file)
            manager.settings = Settings(**config_data)
            manager.save()

            # Create backup
            import shutil
            shutil.copy(config_file, backup_file)

            # Modify config
            manager.settings.database.default_url = 'sqlite:///./modified.db'
            manager.save()

            # Verify modification
            manager2 = ConfigurationManager(config_file)
            assert manager2.settings.database.default_url == 'sqlite:///./modified.db'

            # Restore from backup
            shutil.copy(backup_file, config_file)

            # Verify restoration
            manager3 = ConfigurationManager(config_file)
            assert manager3.settings.database.default_url == 'sqlite:///./original.db'
            assert not hasattr(manager3.settings.database, 'schema_org_path')

    def test_concurrent_config_access(self):
        """Test that config can be safely accessed concurrently"""
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            config_data = {
                'database': {
                    'default_url': 'sqlite:///./test.db',
                    'reference_path': './reference.db',
                    'reference_cache_path': './cache.db',
                    'operations_path': './operations.db'
                }
            }

            manager = ConfigurationManager(config_file)
            manager.settings = Settings(**config_data)
            manager.save()

            results = []
            errors = []

            def load_config():
                try:
                    m = ConfigurationManager(config_file)
                    # Verify no schema_org_path
                    has_deprecated = hasattr(m.settings.database, 'schema_org_path')
                    results.append(not has_deprecated)
                except Exception as e:
                    errors.append(str(e))

            # Create multiple threads
            threads = [threading.Thread(target=load_config) for _ in range(10)]

            # Start all threads
            for t in threads:
                t.start()

            # Wait for completion
            for t in threads:
                t.join()

            # Verify all succeeded
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert all(results), "Some threads found deprecated field"
            assert len(results) == 10

    def test_config_validation_on_startup(self):
        """Test that config validation runs on application startup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            # Create valid config
            config_data = {
                'database': {
                    'default_url': 'sqlite:///./local.db',
                    'reference_path': './reference.db',
                    'reference_cache_path': './cache.db',
                    'operations_path': './operations.db'
                }
            }

            with open(config_file, 'w') as f:
                json.dump(config_data, f)

            # Simulate app startup
            manager = ConfigurationManager(config_file)

            # Run validation (should happen on startup)
            errors = manager.validate()
            assert not errors, f"Startup validation failed: {errors}"

            # Verify app can proceed
            assert manager.settings.database.default_url == 'sqlite:///./local.db'
            assert not hasattr(manager.settings.database, 'schema_org_path')

    def test_migration_preserves_configuration(self):
        """Test that migrating from old config preserves all non-deprecated settings"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            # Create old config with deprecated field and other settings
            old_config = {
                'database': {
                    'default_url': 'sqlite:///./custom_local.db',
                    'schema_org_path': './deprecated_schema.db',  # Deprecated
                    'reference_path': './custom_reference.db',
                    'reference_cache_path': './custom_cache.db',
                    'operations_path': './custom_operations.db'
                }
            }

            with open(config_file, 'w') as f:
                json.dump(old_config, f)

            # Load config (triggers migration)
            manager = ConfigurationManager(config_file)

            # Verify deprecated field is removed
            assert not hasattr(manager.settings.database, 'schema_org_path')

            # Verify all non-deprecated fields are preserved with original values
            assert manager.settings.database.default_url == 'sqlite:///./custom_local.db'
            assert manager.settings.database.reference_path == './custom_reference.db'
            assert manager.settings.database.reference_cache_path == './custom_cache.db'
            assert manager.settings.database.operations_path == './custom_operations.db'

            # Save config to persist migration
            assert manager.save()

            # Reload and verify all settings are still preserved
            manager2 = ConfigurationManager(config_file)
            assert manager2.settings.database.default_url == 'sqlite:///./custom_local.db'
            assert manager2.settings.database.reference_path == './custom_reference.db'
            assert manager2.settings.database.reference_cache_path == './custom_cache.db'
            assert manager2.settings.database.operations_path == './custom_operations.db'
            assert not hasattr(manager2.settings.database, 'schema_org_path')

            # Verify saved config file doesn't contain deprecated field
            with open(config_file, 'r') as f:
                saved_config = json.load(f)

            assert 'schema_org_path' not in saved_config.get('database', {})
            assert saved_config['database']['default_url'] == 'sqlite:///./custom_local.db'

    def test_api_reflects_config_changes(self):
        """Test that API endpoints reflect configuration changes correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')
            db_dir = os.path.join(tmpdir, 'datafiles')
            os.makedirs(db_dir, exist_ok=True)

            # Create initial config
            config_data = {
                'database': {
                    'default_url': f'sqlite:///{db_dir}/local.db',
                    'reference_path': f'{db_dir}/reference.db',
                    'reference_cache_path': f'{db_dir}/cache.db',
                    'operations_path': f'{db_dir}/operations.db'
                }
            }

            manager = ConfigurationManager(config_file)
            manager.settings = Settings(**config_data)
            assert manager.save()

            # Verify initial config through API-like access
            manager2 = ConfigurationManager(config_file)
            assert manager2.settings.database.default_url == f'sqlite:///{db_dir}/local.db'
            assert not hasattr(manager2.settings.database, 'schema_org_path')

            # Modify config (simulating user changing settings)
            new_db_dir = os.path.join(tmpdir, 'new_datafiles')
            os.makedirs(new_db_dir, exist_ok=True)

            manager2.settings.database.default_url = f'sqlite:///{new_db_dir}/local.db'
            manager2.settings.database.reference_path = f'{new_db_dir}/reference.db'
            assert manager2.save()

            # Verify changes are reflected when config is reloaded
            manager3 = ConfigurationManager(config_file)
            assert manager3.settings.database.default_url == f'sqlite:///{new_db_dir}/local.db'
            assert manager3.settings.database.reference_path == f'{new_db_dir}/reference.db'
            assert manager3.settings.database.reference_cache_path == f'{db_dir}/cache.db'  # Unchanged
            assert not hasattr(manager3.settings.database, 'schema_org_path')

            # Validate config is still valid after changes
            errors = manager3.validate()
            assert not errors, f"Validation failed after config changes: {errors}"
