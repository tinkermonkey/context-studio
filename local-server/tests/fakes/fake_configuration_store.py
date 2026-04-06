"""Fake in-memory implementation of ConfigurationStore for testing."""

import sys
import os
from typing import Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.admin.entities import AppConfiguration
from domain.admin.value_objects import CREDENTIAL_FIELD_NAMES


class FakeConfigurationStore:
    """
    Fake implementation of ConfigurationStore for unit testing.

    Stores configuration in memory with optional initialization.
    """

    def __init__(self, initial_config: Optional[AppConfiguration] = None):
        """
        Initialize with optional pre-configured state.

        Args:
            initial_config: Optional AppConfiguration to use. If None, initializes with
                          default sections matching the real ConfigurationStore.
        """
        self._config = initial_config or AppConfiguration(
            sections={
                "server": {},
                "database": {},
                "logging": {},
                "llm": {},
                "reference": None,
                "sync": None,
            }
        )
        # Store default sections for reset operation, matching real implementation
        self._default_sections: dict[str, Any] = {
            "server": {},
            "database": {},
            "logging": {},
            "llm": {},
            "reference": None,
            "sync": None,
        }

    def get_config(self) -> AppConfiguration:
        """
        Load the current configuration.

        Returns:
            AppConfiguration object
        """
        return self._config

    def update_config(self, updates: dict) -> AppConfiguration:
        """
        Update configuration with partial updates.

        Args:
            updates: Dictionary with section names as keys and section updates as values

        Returns:
            AppConfiguration object with updated configuration
        """
        for section_name, section_updates in updates.items():
            if section_name in self._config.sections and self._config.sections[section_name] is not None:
                self._config.sections[section_name].update(section_updates)
            else:
                self._config.sections[section_name] = section_updates
        return self._config

    def reset_to_defaults(self) -> AppConfiguration:
        """
        Reset configuration to defaults while preserving credentials.

        Creates a fresh configuration from defaults, then copies any credential
        fields from the current configuration to preserve API keys and secrets.
        Only preserves credentials for sections that exist in the defaults.

        Returns:
            AppConfiguration reset to defaults with credentials preserved
        """
        # Start with fresh defaults, handling None values
        reset_config = AppConfiguration(
            sections={
                section: dict(defaults) if defaults is not None else None
                for section, defaults in self._default_sections.items()
            }
        )

        # Preserve credentials from current config, only for sections in defaults
        for section_name, current_section in self._config.sections.items():
            if section_name not in reset_config.sections or current_section is None:
                continue
            reset_section = reset_config.sections[section_name]
            if reset_section is None:
                continue
            for key, value in current_section.items():
                if key in CREDENTIAL_FIELD_NAMES:
                    reset_section[key] = value

        self._config = reset_config
        return reset_config
