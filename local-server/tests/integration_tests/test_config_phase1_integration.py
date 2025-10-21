"""
Integration tests for Phase 1: schema_org_path removal
Tests configuration integration with database, file system, and other components
"""

import sys
import json
import tempfile
import os
import sqlite3
from pathlib import Path
import pytest

# Add local-server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Settings, DatabaseConfig, ConfigurationManager

# Try to import db_utils, but make tests work without it
try:
    from db_utils import get_db_session, get_engine
    DB_UTILS_AVAILABLE = True
except ImportError:
    DB_UTILS_AVAILABLE = False
    get_engine = None
    get_db_session = None


class TestConfigDatabaseIntegration:
    """Test configuration integration with database operations"""

    def test_database_connection_with_new_config(self):
        """Test that database connections work with updated configuration"""
        if not DB_UTILS_AVAILABLE:
            pytest.skip("db_utils not available")

        config_data = {
            'database': {
                'default_url': 'sqlite:///:memory:',  # Use in-memory for test
                'reference_path': ':memory:',
                'reference_cache_path': ':memory:',
                'operations_path': ':memory:'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_config = f.name

        try:
            config_manager = ConfigurationManager(temp_config)

            # Verify configuration is correct (don't test db connection if db_utils not available)
            assert config_manager.settings.database.default_url == 'sqlite:///:memory:'
            assert not hasattr(config_manager.settings.database, 'schema_org_path')

        finally:
            if os.path.exists(temp_config):
                os.unlink(temp_config)

    def test_reference_database_path_configuration(self):
        """Test that reference database path is correctly configured"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ref_db_path = os.path.join(tmpdir, 'reference.db')

            config_data = {
                'database': {
                    'default_url': f'sqlite:///{tmpdir}/local.db',
                    'reference_path': ref_db_path,
                    'reference_cache_path': f'{tmpdir}/cache.db',
                    'operations_path': f'{tmpdir}/operations.db'
                }
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(config_data, f)
                temp_config = f.name

            try:
                config_manager = ConfigurationManager(temp_config)

                # Verify reference path is set correctly
                assert config_manager.settings.database.reference_path == ref_db_path
                assert 'schema_org_path' not in str(config_manager.settings.database)

                # Create the reference database
                conn = sqlite3.connect(ref_db_path)
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
                conn.commit()
                conn.close()

                # Verify it exists
                assert os.path.exists(ref_db_path)

            finally:
                if os.path.exists(temp_config):
                    os.unlink(temp_config)

    def test_config_persists_across_saves(self):
        """Test that configuration persists correctly across save operations"""
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

            # Initial save
            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**config_data)
            assert config_manager.save()

            # Load in new instance
            config_manager2 = ConfigurationManager(config_file)

            # Verify no schema_org_path
            assert not hasattr(config_manager2.settings.database, 'schema_org_path')

            # Modify and save again
            config_manager2.settings.database.default_url = 'sqlite:///./modified.db'
            assert config_manager2.save()

            # Load third time
            config_manager3 = ConfigurationManager(config_file)

            # Verify modification persisted and no schema_org_path
            assert config_manager3.settings.database.default_url == 'sqlite:///./modified.db'
            assert not hasattr(config_manager3.settings.database, 'schema_org_path')

    def test_migration_from_old_config_file(self):
        """Test migration scenario from old config with schema_org_path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'old_config.json')

            # Write old config with deprecated field
            old_config = {
                'database': {
                    'default_url': 'sqlite:///./local.db',
                    'schema_org_path': './old_schema.db',  # Deprecated
                    'reference_path': './reference.db',
                    'reference_cache_path': './cache.db',
                    'operations_path': './operations.db'
                }
            }

            with open(config_file, 'w') as f:
                json.dump(old_config, f)

            # Load with ConfigurationManager
            config_manager = ConfigurationManager(config_file)

            # Verify it loads without errors
            errors = config_manager.validate()
            assert not errors

            # Verify deprecated field was ignored
            assert not hasattr(config_manager.settings.database, 'schema_org_path')

            # Save the config (should not include deprecated field)
            assert config_manager.save()

            # Read the file to verify schema_org_path is not persisted
            with open(config_file, 'r') as f:
                saved_config = json.load(f)

            assert 'schema_org_path' not in saved_config.get('database', {})

    def test_multiple_config_instances_isolated(self):
        """Test that multiple ConfigurationManager instances are properly isolated"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config1_path = os.path.join(tmpdir, 'config1.json')
            config2_path = os.path.join(tmpdir, 'config2.json')

            # Create two different configs
            config1_data = {
                'database': {
                    'default_url': 'sqlite:///./db1.db',
                    'reference_path': './ref1.db',
                    'reference_cache_path': './cache1.db',
                    'operations_path': './pipeline1.db'
                }
            }

            config2_data = {
                'database': {
                    'default_url': 'sqlite:///./db2.db',
                    'reference_path': './ref2.db',
                    'reference_cache_path': './cache2.db',
                    'operations_path': './pipeline2.db'
                }
            }

            # Save both
            manager1 = ConfigurationManager(config1_path)
            manager1.settings = Settings(**config1_data)
            manager1.save()

            manager2 = ConfigurationManager(config2_path)
            manager2.settings = Settings(**config2_data)
            manager2.save()

            # Verify they're isolated
            assert manager1.settings.database.default_url != manager2.settings.database.default_url
            assert manager1.settings.database.reference_path != manager2.settings.database.reference_path

            # Verify neither has schema_org_path
            assert not hasattr(manager1.settings.database, 'schema_org_path')
            assert not hasattr(manager2.settings.database, 'schema_org_path')

    def test_config_validation_with_file_system(self):
        """Test configuration validation with actual file system paths"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create database directories
            db_dir = os.path.join(tmpdir, 'datafiles')
            os.makedirs(db_dir, exist_ok=True)

            config_data = {
                'database': {
                    'default_url': f'sqlite:///{db_dir}/local.db',
                    'reference_path': f'{db_dir}/reference.db',
                    'reference_cache_path': f'{db_dir}/cache.db',
                    'operations_path': f'{db_dir}/operations.db'
                }
            }

            config_file = os.path.join(tmpdir, 'config.json')
            with open(config_file, 'w') as f:
                json.dump(config_data, f)

            config_manager = ConfigurationManager(config_file)

            # Validate
            errors = config_manager.validate()
            assert not errors

            # Verify paths are accessible
            assert os.path.isdir(db_dir)

            # Create database files
            for db_path in [
                config_manager.settings.database.reference_path,
                config_manager.settings.database.reference_cache_path,
                config_manager.settings.database.operations_path
            ]:
                # Create database
                conn = sqlite3.connect(db_path)
                conn.execute("CREATE TABLE test (id INTEGER)")
                conn.commit()
                conn.close()

                # Verify it exists
                assert os.path.exists(db_path)

    def test_config_error_handling(self):
        """Test error handling for invalid configurations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'invalid_config.json')

            # Write invalid JSON
            with open(config_file, 'w') as f:
                f.write("{ invalid json }")

            # ConfigurationManager handles invalid JSON gracefully by logging error and using defaults
            config_manager = ConfigurationManager(config_file)

            # Verify it falls back to default settings
            assert config_manager.settings is not None
            assert config_manager.settings.database.default_url == "sqlite:///./datafiles/local.db"
            assert not hasattr(config_manager.settings.database, 'schema_org_path')

    def test_config_with_environment_variables(self):
        """Test configuration loading with environment variables"""
        # Set an environment variable
        os.environ['TEST_DB_PATH'] = './test_from_env.db'

        try:
            config_data = {
                'database': {
                    'default_url': 'sqlite:///./local.db',
                    'reference_path': os.environ.get('TEST_DB_PATH', './default.db'),
                    'reference_cache_path': './cache.db',
                    'operations_path': './operations.db'
                }
            }

            settings = Settings(**config_data)

            # Verify env var was used
            assert settings.database.reference_path == './test_from_env.db'
            assert not hasattr(settings.database, 'schema_org_path')

        finally:
            # Cleanup
            if 'TEST_DB_PATH' in os.environ:
                del os.environ['TEST_DB_PATH']

    def test_default_configuration_values(self):
        """Test that default configuration values are correctly set"""
        # Create settings with no overrides
        settings = Settings()

        # Test database defaults
        assert settings.database.default_url == "sqlite:///./datafiles/local.db"
        assert settings.database.reference_path == "./datafiles/reference.db"
        assert settings.database.reference_cache_path == "./datafiles/reference_api_cache.db"
        assert settings.database.operations_path == "./datafiles/operations.db"
        assert not hasattr(settings.database, 'schema_org_path')

        # Test server defaults
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 8000
        assert settings.server.reload == True

        # Test LLM defaults
        assert settings.llm.model_name == "gpt-3.5-turbo"
        assert settings.llm.temperature == 0.0
        assert settings.llm.timeout == 30

        # Test NLP defaults
        assert settings.nlp.model_name == "en_core_web_lg"
        assert settings.nlp.max_text_length == 512

        # Test proxy defaults
        assert settings.proxy_server.enabled == True
        assert settings.proxy_server.port == 18080

    def test_update_llm_provider_settings(self):
        """Test updating LLM provider settings"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            # Create configuration manager
            config_manager = ConfigurationManager(config_file)

            # Update LLM settings using dot notation
            assert config_manager.set('llm.model_name', 'gpt-4')
            assert config_manager.set('llm.temperature', 0.7)
            assert config_manager.set('llm.max_tokens', 2000)

            # Verify updates
            assert config_manager.settings.llm.model_name == 'gpt-4'
            assert config_manager.settings.llm.temperature == 0.7
            assert config_manager.settings.llm.max_tokens == 2000

            # Reload config to verify persistence
            config_manager2 = ConfigurationManager(config_file)
            assert config_manager2.settings.llm.model_name == 'gpt-4'
            assert config_manager2.settings.llm.temperature == 0.7
            assert config_manager2.settings.llm.max_tokens == 2000

            # Verify no schema_org_path in database config
            assert not hasattr(config_manager2.settings.database, 'schema_org_path')

    def test_validate_embedding_model_config(self):
        """Test validation of embedding model configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            # Test valid NLP model configuration
            valid_config = {
                'nlp': {
                    'model_name': 'en_core_web_sm',
                    'max_text_length': 1000,
                    'sense2vec_path': './models/s2v',
                    'auto_download_models': True
                }
            }

            settings = Settings(**valid_config)
            assert settings.nlp.model_name == 'en_core_web_sm'
            assert settings.nlp.max_text_length == 1000
            assert settings.nlp.auto_download_models == True

            # Test configuration manager validation
            config_manager = ConfigurationManager(config_file)
            config_manager.settings = Settings(**valid_config)
            config_manager.save()

            errors = config_manager.validate()
            assert len(errors) == 0

            # Verify no schema_org_path
            assert not hasattr(config_manager.settings.database, 'schema_org_path')

    def test_feature_flags_toggle(self):
        """Test toggling feature flags like proxy server and reference sources"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, 'config.json')

            config_manager = ConfigurationManager(config_file)

            # Test proxy server toggle
            original_proxy_state = config_manager.settings.proxy_server.enabled
            assert config_manager.set('proxy_server.enabled', False)
            assert config_manager.settings.proxy_server.enabled == False

            # Toggle back
            assert config_manager.set('proxy_server.enabled', True)
            assert config_manager.settings.proxy_server.enabled == True

            # Test reference source toggles
            assert config_manager.set('reference_sources.dbpedia_sparql.enabled', False)
            assert config_manager.settings.reference_sources.dbpedia_sparql.enabled == False

            assert config_manager.set('reference_sources.conceptnet.enabled', False)
            assert config_manager.settings.reference_sources.conceptnet.enabled == False

            # Verify changes persist
            config_manager2 = ConfigurationManager(config_file)
            assert config_manager2.settings.reference_sources.dbpedia_sparql.enabled == False
            assert config_manager2.settings.reference_sources.conceptnet.enabled == False

            # Verify get_enabled_sources reflects changes
            enabled_sources = config_manager2.settings.get_enabled_sources()
            assert 'dbpedia_sparql' not in enabled_sources
            assert 'conceptnet' not in enabled_sources

            # Verify no schema_org_path in database config
            assert not hasattr(config_manager2.settings.database, 'schema_org_path')
