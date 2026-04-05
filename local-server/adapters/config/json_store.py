"""
JSONFileConfigStore adapter implementation.

Wraps the ConfigurationManager to implement the ConfigurationStore port,
enabling the domain layer to persist and retrieve application configuration
without direct dependency on the config.py module or Pydantic.
"""

from config import ConfigurationManager, Settings
from domain.admin.entities import AppConfiguration
from domain.admin.exceptions import ConfigurationError
from utils.logger import get_logger

logger = get_logger(__name__)


class JSONFileConfigStore:
    """
    Wraps ConfigurationManager to implement the ConfigurationStore port.

    This adapter converts Pydantic Settings objects to plain dicts for the domain
    entity, maintaining separation between infrastructure (Pydantic) and domain logic.
    """

    def __init__(self, config_manager: ConfigurationManager) -> None:
        """
        Initialize the JSON file configuration store.

        Args:
            config_manager: Existing ConfigurationManager instance to wrap
        """
        self._mgr = config_manager

    def load(self) -> AppConfiguration:
        """
        Load application configuration from file.

        Retrieves settings from the wrapped ConfigurationManager and converts
        Pydantic models to plain dicts for the domain entity.

        Returns:
            AppConfiguration with all configuration sections

        Raises:
            ConfigurationError: If loading fails
        """
        try:
            settings = self._mgr.get_settings()
            sections = {
                'server': settings.server.model_dump(),
                'database': settings.database.model_dump(),
                'logging': settings.logging.model_dump(),
                'llm': settings.llm.model_dump(),
                'reference': settings.reference.model_dump() if settings.reference else None,
                'sync': settings.sync.model_dump() if settings.sync else None,
            }
            logger.debug("Configuration loaded successfully")
            return AppConfiguration(sections=sections)
        except Exception as e:
            raise ConfigurationError(f'Failed to load configuration: {e}') from e

    def save(self, config: AppConfiguration) -> None:
        """
        Save application configuration to file.

        Takes an AppConfiguration with plain dicts, reconstructs Pydantic Settings,
        and persists it via the wrapped ConfigurationManager.

        Args:
            config: AppConfiguration to persist

        Raises:
            ConfigurationError: If saving fails
        """
        try:
            # Reconstruct Settings object from config sections
            settings_dict = {
                'server': config.sections.get('server', {}),
                'database': config.sections.get('database', {}),
                'logging': config.sections.get('logging', {}),
                'llm': config.sections.get('llm', {}),
            }
            if config.sections.get('reference') is not None:
                settings_dict['reference'] = config.sections['reference']
            if config.sections.get('sync') is not None:
                settings_dict['sync'] = config.sections['sync']

            new_settings = Settings(**settings_dict)
            self._mgr.settings = new_settings

            if not self._mgr.save():
                raise ConfigurationError("ConfigurationManager.save() returned False")
            logger.debug("Configuration saved successfully")
        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(f'Failed to save configuration: {e}') from e
