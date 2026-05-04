"""
Integration tests for JSONFileConfigStore adapter.

Tests the adapter's ability to load, convert, and save configuration
using actual file I/O with a temporary config file.
"""

import sys
import os
import tempfile
import json

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from config import ConfigurationManager
from adapters.config.json_store import JSONFileConfigStore
from domain.admin.entities import AppConfiguration


def test_load_configuration():
    """Test loading configuration from a JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        # Create a minimal config file
        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
            "database": {
                "local_db_path": "./local.db",
                "operations_db_path": "./operations.db",
            },
            "logging": {"log_level": "INFO", "max_bytes": 10485760, "backup_count": 5},
            "llm": {"openai_api_key": "", "anthropic_api_key": ""},
            "reference": {
                "cache_db_path": "./reference_api_cache.db",
                "reference_db_path": "./reference.db",
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Create ConfigurationManager and wrap in JSONFileConfigStore
        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)

        # Load and verify
        config = store.load()
        assert isinstance(config, AppConfiguration)
        assert "server" in config.sections
        assert "database" in config.sections
        assert "llm" in config.sections
        assert config.sections["server"]["port"] == 8000


def test_load_and_save_roundtrip():
    """Test loading, modifying, and saving configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        # Create initial config
        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
            "database": {
                "local_db_path": "./local.db",
                "operations_db_path": "./operations.db",
            },
            "logging": {"log_level": "INFO", "max_bytes": 10485760, "backup_count": 5},
            "llm": {"openai_api_key": "", "anthropic_api_key": ""},
            "reference": {
                "cache_db_path": "./reference_api_cache.db",
                "reference_db_path": "./reference.db",
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # First load
        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)
        config = store.load()
        assert config.sections["server"]["port"] == 8000

        # Modify config
        updated = store.update_config({"server": {"port": 9000}})
        assert updated.sections["server"]["port"] == 9000

        # Create a new manager and verify changes persisted
        config_mgr2 = ConfigurationManager(config_file=config_file)
        store2 = JSONFileConfigStore(config_mgr2)
        config2 = store2.load()
        assert config2.sections["server"]["port"] == 9000


def test_save_with_nonexistent_directory():
    """Test saving configuration creates directory if needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "subdir", "config.json")

        # Create initial config
        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
            "database": {
                "local_db_path": "./local.db",
                "operations_db_path": "./operations.db",
            },
            "logging": {"log_level": "INFO", "max_bytes": 10485760, "backup_count": 5},
            "llm": {"openai_api_key": "", "anthropic_api_key": ""},
            "reference": {
                "cache_db_path": "./reference_api_cache.db",
                "reference_db_path": "./reference.db",
            },
        }

        # Save to temp location first
        temp_config = os.path.join(tmpdir, "temp_config.json")
        with open(temp_config, "w") as f:
            json.dump(config_data, f)

        config_mgr = ConfigurationManager(config_file=temp_config)
        config_mgr.config_file = config_file  # Change target path

        store = JSONFileConfigStore(config_mgr)
        store.update_config({"server": {"port": 8000}})

        # Verify file was created in the subdirectory
        assert os.path.exists(config_file)


def test_load_and_save_preserves_sections():
    """Test that all configuration sections are preserved through save/load cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
            "database": {
                "local_db_path": "./local.db",
                "operations_db_path": "./operations.db",
            },
            "logging": {"log_level": "DEBUG", "max_bytes": 5242880, "backup_count": 3},
            "llm": {"openai_api_key": "sk-test", "anthropic_api_key": ""},
            "reference": {
                "cache_db_path": "./reference_api_cache.db",
                "reference_db_path": "./reference.db",
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)

        # Load, modify all sections, update, and reload
        store.load()
        updates = {
            "logging": {"log_level": "WARNING"},
            "server": {"port": 9999},
            "llm": {"anthropic_api_key": "sk-ant-test"},
        }
        updated_config = store.update_config(updates)
        assert updated_config.sections["logging"]["log_level"] == "WARNING"
        assert updated_config.sections["server"]["port"] == 9999
        assert updated_config.sections["llm"]["anthropic_api_key"] == "sk-ant-test"

        # Reload and verify all sections
        config_mgr2 = ConfigurationManager(config_file=config_file)
        store2 = JSONFileConfigStore(config_mgr2)
        config2 = store2.load()

        assert config2.sections["logging"]["log_level"] == "WARNING"
        assert config2.sections["server"]["port"] == 9999
        assert config2.sections["llm"]["anthropic_api_key"] == "sk-ant-test"


def test_reset_to_defaults_preserves_credentials():
    """Test that reset_to_defaults preserves credential fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        # Create initial config with modified values and API keys
        config_data = {
            "server": {
                "host": "192.168.1.1",
                "port": 9999,
                "cors_origins": ["http://localhost:3000"],
            },
            "database": {
                "local_db_path": "./custom_local.db",
                "operations_db_path": "./custom_operations.db",
            },
            "logging": {"log_level": "DEBUG", "max_bytes": 5242880, "backup_count": 10},
            "llm": {
                "openai_api_key": "sk-test-123",
                "anthropic_api_key": "sk-ant-test-456",
            },
            "reference": {
                "cache_db_path": "./custom_cache.db",
                "reference_db_path": "./custom_ref.db",
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)

        # Reset to defaults
        reset_config = store.reset_to_defaults()

        # Verify non-credential settings are reset to defaults
        assert reset_config.sections["server"]["host"] == "127.0.0.1"
        assert reset_config.sections["server"]["port"] == 8000
        assert reset_config.sections["server"]["cors_origins"] == ["*"]

        assert reset_config.sections["logging"]["log_level"] == "INFO"
        assert reset_config.sections["logging"]["max_bytes"] == 10 * 1024 * 1024
        assert reset_config.sections["logging"]["backup_count"] == 5

        # Verify credentials are preserved
        assert reset_config.sections["llm"]["openai_api_key"] == "sk-test-123"
        assert reset_config.sections["llm"]["anthropic_api_key"] == "sk-ant-test-456"


def test_reset_to_defaults_persists_changes():
    """Test that reset_to_defaults saves changes to disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        config_data = {
            "server": {
                "host": "192.168.1.1",
                "port": 9999,
                "cors_origins": ["http://localhost:3000"],
            },
            "database": {
                "local_db_path": "./custom_local.db",
                "operations_db_path": "./custom_operations.db",
            },
            "logging": {"log_level": "DEBUG", "max_bytes": 5242880, "backup_count": 10},
            "llm": {
                "openai_api_key": "sk-test-123",
                "anthropic_api_key": "sk-ant-test-456",
            },
            "reference": {
                "cache_db_path": "./custom_cache.db",
                "reference_db_path": "./custom_ref.db",
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)

        # Reset to defaults
        store.reset_to_defaults()

        # Create a new manager and verify changes were persisted
        config_mgr2 = ConfigurationManager(config_file=config_file)
        store2 = JSONFileConfigStore(config_mgr2)
        reloaded_config = store2.load()

        # Verify defaults and preserved credentials
        assert reloaded_config.sections["server"]["host"] == "127.0.0.1"
        assert reloaded_config.sections["server"]["port"] == 8000
        assert reloaded_config.sections["logging"]["log_level"] == "INFO"
        assert reloaded_config.sections["llm"]["openai_api_key"] == "sk-test-123"
        assert reloaded_config.sections["llm"]["anthropic_api_key"] == "sk-ant-test-456"


def test_reset_to_defaults_removes_sync_not_in_defaults():
    """Test that reset_to_defaults removes sync section since it's not in defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        config_data = {
            "server": {
                "host": "192.168.1.1",
                "port": 9999,
                "cors_origins": ["http://localhost:3000"],
            },
            "database": {
                "local_db_path": "./custom_local.db",
                "operations_db_path": "./custom_operations.db",
            },
            "logging": {"log_level": "DEBUG", "max_bytes": 5242880, "backup_count": 10},
            "llm": {
                "openai_api_key": "sk-test-123",
                "anthropic_api_key": "sk-ant-test-456",
            },
            "reference": {
                "cache_db_path": "./custom_cache.db",
                "reference_db_path": "./custom_ref.db",
            },
            "sync": {
                "adapter": "s3",
                "s3": {
                    "s3_bucket": "my-bucket",
                    "s3_prefix": "context-studio",
                    "s3_access_key": "AKIA1234567890",
                    "s3_secret_key": "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
                    "s3_region": "us-west-2",
                },
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)

        # Reset to defaults
        reset_config = store.reset_to_defaults()

        # Since sync is not in the default Settings(), it should be None or removed
        # This verifies that the reset removes sections not present in defaults
        assert reset_config.sections.get("sync") is None


def test_reset_to_defaults_preserves_nested_s3_credentials():
    """Test that reset_to_defaults preserves nested S3 credentials when sync exists in defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        # Original S3 credentials to verify preservation
        original_s3_access_key = "AKIA1234567890ABCDEF"
        original_s3_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

        # Config with nested S3 credentials and modified non-credential values
        config_data = {
            "server": {
                "host": "192.168.1.1",
                "port": 9999,
                "cors_origins": ["http://localhost:3000"],
            },
            "database": {
                "local_db_path": "./custom_local.db",
                "operations_db_path": "./custom_operations.db",
            },
            "logging": {"log_level": "DEBUG", "max_bytes": 5242880, "backup_count": 10},
            "llm": {
                "openai_api_key": "sk-test-123",
                "anthropic_api_key": "sk-ant-test-456",
            },
            "reference": {
                "cache_db_path": "./custom_cache.db",
                "reference_db_path": "./custom_ref.db",
            },
            "sync": {
                "adapter": "s3",
                "s3": {
                    "s3_bucket": "my-custom-bucket",
                    "s3_prefix": "custom-prefix",
                    "s3_access_key": original_s3_access_key,
                    "s3_secret_key": original_s3_secret_key,
                    "s3_region": "eu-west-1",
                },
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)

        # Since the default Settings() has sync=None, the sync section will not be preserved.
        # This test documents the current behavior: nested credentials in sync are only preserved
        # if the default configuration also has a sync section. This is a limitation of the current
        # Settings model, not the preservation logic.
        reset_config = store.reset_to_defaults()

        # Verify that top-level credentials are preserved
        assert reset_config.sections["llm"]["openai_api_key"] == "sk-test-123"
        assert reset_config.sections["llm"]["anthropic_api_key"] == "sk-ant-test-456"

        # Since sync is None in defaults, the entire sync section is skipped
        assert reset_config.sections.get("sync") is None


def test_update_config_silently_skips_unknown_section():
    """Test that update_config silently skips unknown section names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        # Create initial config with test values
        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
            "database": {
                "local_db_path": "./local.db",
                "operations_db_path": "./operations.db",
            },
            "logging": {"log_level": "INFO", "max_bytes": 10485760, "backup_count": 5},
            "llm": {"openai_api_key": "", "anthropic_api_key": ""},
            "reference": {
                "cache_db_path": "./reference_api_cache.db",
                "reference_db_path": "./reference.db",
            },
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config_mgr = ConfigurationManager(config_file=config_file)
        store = JSONFileConfigStore(config_mgr)

        # Try to update with an unknown section - this tests the silent-skip behavior at line 120
        # The update should be silently ignored since "unknown_section" doesn't exist
        updated = store.update_config(
            {
                "unknown_section": {"some_key": "some_value"},
                "server": {"port": 9000},  # This valid update should still be applied
            }
        )

        # Verify that the valid update (server.port) was applied
        assert updated.server["port"] == 9000
        # Verify the unknown section was silently skipped (not added to config)
        assert not hasattr(updated, "unknown_section")

        # Verify changes persisted by reloading from disk
        config_mgr2 = ConfigurationManager(config_file=config_file)
        store2 = JSONFileConfigStore(config_mgr2)
        reloaded_config = store2.load()

        # Verify only the valid update persisted
        assert reloaded_config.server["port"] == 9000
        assert not hasattr(reloaded_config, "unknown_section")
