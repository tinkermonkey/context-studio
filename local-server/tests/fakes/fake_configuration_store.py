"""Fake in-memory implementation of ConfigurationStore for testing."""

import sys
import os
from typing import Optional

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
                          default sections (llm and database).
        """
        self._config = initial_config or AppConfiguration(
            sections={"llm": {}, "database": {}}
        )
        # Store default sections for reset operation
        self._default_sections = {"llm": {}, "database": {}}

    def load(self) -> AppConfiguration:
        """
        Load the current configuration.

        Returns:
            AppConfiguration object
        """
        return self._config

    def save(self, config: AppConfiguration) -> None:
        """
        Save configuration.

        Args:
            config: AppConfiguration to persist
        """
        self._config = config

    def reset_to_defaults(self) -> AppConfiguration:
        """
        Reset configuration to defaults while preserving credentials.

        Creates a fresh configuration from defaults, then copies any credential
        fields from the current configuration to preserve API keys and secrets.

        Returns:
            AppConfiguration reset to defaults with credentials preserved
        """
        # Start with fresh defaults
        reset_config = AppConfiguration(
            sections={section: dict(defaults) for section, defaults in self._default_sections.items()}
        )

        # Preserve credentials from current config
        for section in self._config.sections:
            if section not in reset_config.sections:
                reset_config.sections[section] = {}
            current_section = self._config.sections[section]
            reset_section = reset_config.sections[section]
            for key, value in current_section.items():
                if key in CREDENTIAL_FIELD_NAMES:
                    reset_section[key] = value

        self._config = reset_config
        return reset_config
