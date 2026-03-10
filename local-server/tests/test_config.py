"""
Test configuration management for isolated testing.

This module provides test configuration isolation to prevent test data pollution  # noqa: E501
in the global configuration files and ensure clean test environments.
"""

# mypy: ignore-errors

import json
from pathlib import Path
from typing import Dict, Any, Optional

from config import Settings


class TestConfigurationManager:
    """
    Test-isolated configuration manager that prevents pollution of global config files.  # noqa: E501

    Uses temporary directories and files to ensure complete isolation between tests  # noqa: E501
    and from the development environment.
    """

    def __init__(self, temp_dir: str):
        """
        Initialize test configuration manager.

        Args:
            temp_dir: Temporary directory path for test artifacts
        """
        self.temp_dir = Path(temp_dir)
        self.temp_config_file = self.temp_dir / "test_config.json"
        self.settings = None
        self._base_config = None

    def _load_base_config(self) -> Dict[str, Any]:
        """Load base configuration without modifying global state."""
        if self._base_config is None:
            # Create a default settings instance to get base configuration
            base_settings = Settings()
            self._base_config = base_settings.model_dump()
        return self._base_config.copy()

    def get_test_settings(
        self, overrides: Optional[Dict[str, Any]] = None
    ) -> Settings:  # noqa: E501
        """
        Get test settings with complete isolation.

        Args:
            overrides: Dictionary of configuration overrides to apply

        Returns:
            Settings instance with test-isolated configuration
        """
        # Start with base configuration
        config_data = self._load_base_config()

        # Apply test-specific defaults
        test_defaults = self._get_test_defaults()
        config_data = self._deep_update(config_data, test_defaults)

        # Apply any provided overrides
        if overrides:
            config_data = self._deep_update(config_data, overrides)

        # Create settings instance
        self.settings = Settings(**config_data)

        # Save configuration to temporary file (for any code that reads config file directly)  # noqa: E501
        self._save_temp_config(config_data)

        return self.settings

    def _get_test_defaults(self) -> Dict[str, Any]:
        """Get test-specific configuration defaults that isolate file paths only."""  # noqa: E501
        test_logs_dir = self.temp_dir / "logs"
        test_datasets_dir = self.temp_dir / "test_datasets"
        test_logs_dir.mkdir(exist_ok=True)
        test_datasets_dir.mkdir(exist_ok=True)

        return {
            # Only override file paths to prevent pollution - don't change database connections  # noqa: E501
            "logging": {
                "file_path": str(test_logs_dir / "test_context_studio.log"),
                "enable_console": False,  # Reduce test output noise
                "enable_file": True,
            },
            "proxy_server": {
                "database_path": str(self.temp_dir / "test_proxy_cache.db"),
                "enabled": False,  # Disable proxy for tests by default to avoid conflicts  # noqa: E501
            },
            "server": {
                "reload": False,  # Disable auto-reload in tests
                "access_log": False,  # Reduce noise in tests
            },
            "dataset": {
                "config_path": str(self.temp_dir / "test_datasets.json"),
                "datasets_directory": str(test_datasets_dir),
            },
            # Prevent NLP model downloads and use the smallest available model.
            # en_core_web_lg (750MB, auto-download) is the production default; in tests
            # we never want a 600s download attempt and we don't need linguistic quality.
            "nlp": {
                "model_name": "en_core_web_sm",  # 12MB vs 750MB
                "auto_download_models": False,    # Never download during tests
                "download_timeout": 30,           # Short safety timeout
            },
            # Note: Database URLs are NOT overridden to maintain shared database performance  # noqa: E501
            # Tests that need database isolation should use utilities from test_db_utils.py  # noqa: E501
        }

    def _deep_update(
        self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]
    ) -> Dict[str, Any]:  # noqa: E501
        """
        Deep update dictionary, merging nested dictionaries.

        Args:
            base_dict: Base dictionary to update
            update_dict: Updates to apply

        Returns:
            Updated dictionary
        """
        result = base_dict.copy()

        for key, value in update_dict.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):  # noqa: E501
                result[key] = self._deep_update(result[key], value)
            else:
                result[key] = value

        return result

    def _save_temp_config(self, config_data: Dict[str, Any]) -> None:
        """Save configuration to temporary file."""
        with open(self.temp_config_file, "w") as f:
            json.dump(config_data, f, indent=2)

    def cleanup(self) -> None:
        """Clean up temporary configuration files and directories."""
        if self.temp_config_file.exists():
            self.temp_config_file.unlink()

        # Clean up any temporary database files
        for db_file in self.temp_dir.glob("*.db*"):
            if db_file.is_file():
                try:
                    db_file.unlink()
                except (OSError, PermissionError):
                    # Handle cases where database might be locked
                    pass

    def get_config_file_path(self) -> str:
        """Get path to temporary configuration file."""
        return str(self.temp_config_file)


def create_test_settings(
    temp_dir: str, overrides: Optional[Dict[str, Any]] = None
) -> Settings:  # noqa: E501
    """
    Convenience function to create isolated test settings.

    Args:
        temp_dir: Temporary directory path
        overrides: Configuration overrides to apply

    Returns:
        Isolated Settings instance for testing
    """
    manager = TestConfigurationManager(temp_dir)
    return manager.get_test_settings(overrides)


def patch_config_manager_for_tests(
    temp_dir: str, overrides: Optional[Dict[str, Any]] = None
) -> TestConfigurationManager:  # noqa: E501
    """
    Create and configure a test configuration manager.

    This function can be used to patch the global configuration manager
    in tests that need complete isolation.

    Args:
        temp_dir: Temporary directory path
        overrides: Configuration overrides to apply

    Returns:
        TestConfigurationManager instance
    """
    manager = TestConfigurationManager(temp_dir)
    manager.get_test_settings(overrides)  # Initialize settings
    return manager
