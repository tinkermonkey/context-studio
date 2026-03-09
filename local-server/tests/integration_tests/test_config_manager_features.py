"""
Test ConfigurationManager advanced features in isolation.

This file tests configuration validation, runtime reload, nested access,
and key existence checks without dependencies on the full application stack.
"""

import sys
import os
import tempfile
import json
from pathlib import Path

# Add local-server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import only what we need for configuration testing
from config import ConfigurationManager  # noqa: E402


def test_config_validation_enforcement():
    """Test that invalid configuration is rejected during validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")
        config_manager = ConfigurationManager(config_file)

        # Set an invalid value (port out of range)
        config_manager.settings.server.port = (
            99999  # Exceeds max value of 65535  # noqa: E501
        )

        # Validate should return errors
        errors = config_manager.validate()
        assert len(errors) > 0, "Invalid configuration should be rejected"
        assert any(
            "port" in error.lower() for error in errors
        ), f"Expected port validation error, got: {errors}"  # noqa: E501


def test_reload_configuration_at_runtime():
    """Test that configuration can be reloaded at runtime."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")

        # Create initial config
        config_manager = ConfigurationManager(config_file)

        # Modify the config file directly
        config_data = config_manager.settings.model_dump()
        config_data["server"]["port"] = 9999
        with open(config_file, "w") as f:
            json.dump(config_data, f, indent=2)

        # Reload configuration
        reloaded_settings = config_manager.load()

        # Verify configuration was reloaded
        assert (
            reloaded_settings.server.port == 9999
        ), "Configuration reload failed"  # noqa: E501
        assert (
            config_manager.settings.server.port == 9999
        ), "Configuration manager state not updated"  # noqa: E501


def test_nested_config_value_access():
    """Test that nested configuration values can be accessed using dot notation."""  # noqa: E501
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")
        config_manager = ConfigurationManager(config_file)

        # Test nested get
        port = config_manager.get("server.port")
        assert (
            port == config_manager.settings.server.port
        ), "Nested configuration access failed"  # noqa: E501

        # Test deeper nesting
        cache_ttl = config_manager.get(
            "reference_sources.conceptnet.rate_limit.requests_per_hour"
        )  # noqa: E501
        assert (
            cache_ttl
            == config_manager.settings.reference_sources.conceptnet.rate_limit.requests_per_hour
        )  # noqa: E501


def test_config_key_existence_checks():
    """Test that configuration key existence can be checked properly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")
        config_manager = ConfigurationManager(config_file)

        # Test that valid keys can be accessed
        try:
            config_manager.get("server.port")
            config_manager.get("database.default_url")
            config_manager.get("llm.model_name")
        except KeyError:
            raise AssertionError(
                "Configuration key existence check failed - valid keys should exist"
            )  # noqa: E501

        # Test that invalid keys raise KeyError
        try:
            config_manager.get("invalid.key.path")
            raise AssertionError("Expected KeyError for invalid path")
        except KeyError:
            pass  # Expected

        try:
            config_manager.get("server.nonexistent_field")
            raise AssertionError("Expected KeyError for nonexistent field")
        except KeyError:
            pass  # Expected


if __name__ == "__main__":
    print("Running test_config_validation_enforcement...")
    try:
        test_config_validation_enforcement()
        print("✓ PASSED: test_config_validation_enforcement")
    except AssertionError as e:
        print(f"✗ FAILED: test_config_validation_enforcement - {e}")

    print("\nRunning test_reload_configuration_at_runtime...")
    try:
        test_reload_configuration_at_runtime()
        print("✓ PASSED: test_reload_configuration_at_runtime")
    except AssertionError as e:
        print(f"✗ FAILED: test_reload_configuration_at_runtime - {e}")

    print("\nRunning test_nested_config_value_access...")
    try:
        test_nested_config_value_access()
        print("✓ PASSED: test_nested_config_value_access")
    except AssertionError as e:
        print(f"✗ FAILED: test_nested_config_value_access - {e}")

    print("\nRunning test_config_key_existence_checks...")
    try:
        test_config_key_existence_checks()
        print("✓ PASSED: test_config_key_existence_checks")
    except AssertionError as e:
        print(f"✗ FAILED: test_config_key_existence_checks - {e}")

    print("\n" + "=" * 60)
    print("All tests completed!")
