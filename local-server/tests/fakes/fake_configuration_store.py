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
            server={},
            database={},
            logging={},
            llm={},
            nlp={},
            embedding={},
            reference_sources={},
            sync=None,
        )
        # Store default sections for reset operation, matching real implementation
        self._defaults = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={},
            nlp={},
            embedding={},
            reference_sources={},
            sync=None,
        )

    def load(self) -> AppConfiguration:
        """
        Load the current configuration.

        Returns:
            AppConfiguration object
        """
        return self._config

    def save(self, config: AppConfiguration) -> AppConfiguration:
        """
        Save configuration.

        Args:
            config: AppConfiguration object to save

        Returns:
            AppConfiguration object that was saved
        """
        self._config = config
        return config

    def reset_to_defaults(self) -> AppConfiguration:
        """
        Reset configuration to defaults while preserving credentials.

        Creates a fresh configuration from defaults, then copies any credential
        fields from the current configuration to preserve API keys and secrets.

        Returns:
            AppConfiguration reset to defaults with credentials preserved
        """
        # Create a deep copy of the defaults
        import copy
        reset_config = copy.deepcopy(self._defaults)

        # Preserve credentials from current config
        for attr_name in ["server", "database", "logging", "llm", "nlp", "embedding", "reference_sources", "sync"]:
            current_section = getattr(self._config, attr_name, None)
            reset_section = getattr(reset_config, attr_name, None)

            if current_section is None or reset_section is None:
                continue
            if not isinstance(current_section, dict) or not isinstance(reset_section, dict):
                continue

            for key, value in current_section.items():
                if key in CREDENTIAL_FIELD_NAMES:
                    reset_section[key] = value

        self._config = reset_config
        return reset_config
