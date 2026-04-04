"""
Integration tests for JSONFileConfigStore adapter.

Tests the adapter's ability to load, convert, and save configuration
using actual file I/O with a temporary config file.
"""

import sys
import os
import tempfile
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
        config.sections["server"]["port"] = 9000
        store.save(config)

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
        config = AppConfiguration(sections=config_data)

        store = JSONFileConfigStore(config_mgr)
        store.save(config)

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

        # Load, modify all sections, save, and reload
        config = store.load()
        config.sections["logging"]["log_level"] = "WARNING"
        config.sections["server"]["port"] = 9999
        config.sections["llm"]["anthropic_api_key"] = "sk-ant-test"

        store.save(config)

        # Reload and verify all sections
        config_mgr2 = ConfigurationManager(config_file=config_file)
        store2 = JSONFileConfigStore(config_mgr2)
        config2 = store2.load()

        assert config2.sections["logging"]["log_level"] == "WARNING"
        assert config2.sections["server"]["port"] == 9999
        assert config2.sections["llm"]["anthropic_api_key"] == "sk-ant-test"
