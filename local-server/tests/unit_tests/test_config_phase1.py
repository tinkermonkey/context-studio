"""
Unit tests for Phase 1: schema_org_path removal
Tests configuration changes without requiring full app dependencies
"""

import sys
import json
import tempfile
import os
from pathlib import Path
import pytest

# Add local-server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Settings, DatabaseConfig, ConfigurationManager


class TestSchemaOrgPathRemoval:
    """Test suite for schema_org_path field removal"""

    def test_schema_org_path_removed_from_database_config(self):
        """Test that schema_org_path field is removed from DatabaseConfig"""
        db_config = DatabaseConfig()

        # Verify field does not exist
        assert not hasattr(db_config, 'schema_org_path'), \
            "schema_org_path field still exists in DatabaseConfig"

        # Verify required fields exist
        required_fields = ['default_url', 'reference_path', 'reference_cache_path', 'operations_path']
        for field in required_fields:
            assert hasattr(db_config, field), f"Required field '{field}' is missing"

    def test_backward_compatibility_with_deprecated_field(self):
        """Test that old configs with schema_org_path are handled gracefully"""
        # Create old config with deprecated field
        old_config = {
            'database': {
                'default_url': 'sqlite:///./local.db',
                'schema_org_path': './old_schemaorg.db',  # Deprecated field
                'reference_path': './reference.db',
                'reference_cache_path': './reference_api_cache.db',
                'operations_path': './operations.db'
            }
        }

        # Should load successfully, ignoring the deprecated field
        settings = Settings(**old_config)

        # Verify the deprecated field was ignored
        assert not hasattr(settings.database, 'schema_org_path'), \
            "schema_org_path was not ignored during loading"

        # Verify required fields were loaded
        assert settings.database.default_url == 'sqlite:///./local.db'
        assert settings.database.reference_path == './reference.db'

    def test_config_validation_passes(self):
        """Test that configuration validation works correctly"""
        # Create valid config
        valid_config = {
            'database': {
                'default_url': 'sqlite:///./local.db',
                'reference_path': './reference.db',
                'reference_cache_path': './reference_api_cache.db',
                'operations_path': './operations.db'
            }
        }

        Settings(**valid_config)

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_config, f)
            temp_config = f.name

        try:
            # Test ConfigurationManager
            config_manager = ConfigurationManager(temp_config)

            # Validate
            errors = config_manager.validate()
            assert not errors, f"Validation errors: {errors}"

        finally:
            # Cleanup
            if os.path.exists(temp_config):
                os.unlink(temp_config)

    def test_config_file_loading_from_project_root(self):
        """Test loading from actual config.json file"""
        config_file = Path(__file__).parent.parent.parent / 'config.json'

        if not config_file.exists():
            pytest.skip(f"config.json not found at {config_file}")

        # Create a temporary copy to avoid modifying the actual config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_config = f.name
            # Copy the config content
            with open(config_file, 'r') as original:
                config_data = json.load(original)
                json.dump(config_data, f)

        try:
            config_manager = ConfigurationManager(temp_config)

            # Validate
            errors = config_manager.validate()
            assert not errors, f"Config file validation errors: {errors}"

            # Verify schema_org_path is not in the loaded config
            assert not hasattr(config_manager.settings.database, 'schema_org_path'), \
                "schema_org_path found in loaded config"

            # Verify required fields
            db_config = config_manager.settings.database
            assert db_config.default_url
            assert db_config.reference_path
            assert db_config.reference_cache_path
            assert db_config.operations_path
        
        finally:
            # Cleanup temporary file
            if os.path.exists(temp_config):
                os.unlink(temp_config)

    def test_config_save_and_reload_cycle(self):
        """Test that config can be saved and reloaded"""
        # Create config
        config_data = {
            'database': {
                'default_url': 'sqlite:///./test.db',
                'reference_path': './test_reference.db',
                'reference_cache_path': './test_cache.db',
                'operations_path': './test_pipeline.db'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_config = f.name

        try:
            # Create and save
            config_manager = ConfigurationManager(temp_config)
            config_manager.settings = Settings(**config_data)

            assert config_manager.save(), "Failed to save configuration"

            # Reload
            config_manager2 = ConfigurationManager(temp_config)

            # Verify
            assert config_manager2.settings.database.default_url == 'sqlite:///./test.db'
            assert config_manager2.settings.database.reference_path == './test_reference.db'

            # Validate
            errors = config_manager2.validate()
            assert not errors, f"Reloaded config validation errors: {errors}"

        finally:
            if os.path.exists(temp_config):
                os.unlink(temp_config)

    def test_default_database_config_values(self):
        """Test that default DatabaseConfig values are set correctly"""
        db_config = DatabaseConfig()

        # Check defaults
        assert db_config.default_url == "sqlite:///./datafiles/local.db"
        assert db_config.default_dataset_filename == "default.db"
        assert db_config.reference_path == "./datafiles/reference.db"
        assert db_config.reference_cache_path == "./datafiles/reference_api_cache.db"
        assert db_config.operations_path == "./datafiles/operations.db"
        assert not db_config.check_same_thread
        assert db_config.pool_timeout == 30

    def test_config_with_multiple_deprecated_fields(self):
        """Test handling config with multiple deprecated fields"""
        config_with_multiple_deprecated = {
            'database': {
                'default_url': 'sqlite:///./local.db',
                'schema_org_path': './old_schemaorg.db',  # Deprecated
                'unknown_field': 'some_value',  # Another unknown field
                'reference_path': './reference.db',
                'reference_cache_path': './reference_api_cache.db',
                'operations_path': './operations.db'
            }
        }

        # Should load successfully, ignoring all deprecated/unknown fields
        settings = Settings(**config_with_multiple_deprecated)

        # Verify deprecated fields were ignored
        assert not hasattr(settings.database, 'schema_org_path')
        assert not hasattr(settings.database, 'unknown_field')

        # Verify valid fields were loaded
        assert settings.database.default_url == 'sqlite:///./local.db'

    def test_empty_config_uses_defaults(self):
        """Test that empty config uses default values"""
        empty_config = {}

        settings = Settings(**empty_config)

        # Should have default database config
        assert settings.database.default_url == "sqlite:///./datafiles/local.db"
        assert settings.database.reference_path == "./datafiles/reference.db"
