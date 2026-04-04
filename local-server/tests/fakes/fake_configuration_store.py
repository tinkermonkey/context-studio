"""Fake in-memory implementation of ConfigurationStore for testing."""

import sys
import os
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.admin.entities import AppConfiguration


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
