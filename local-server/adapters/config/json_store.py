"""
JSONFileConfigStore adapter implementation.

Wraps the ConfigurationManager to implement the ConfigurationStore port,
enabling the domain layer to persist and retrieve application configuration
without direct dependency on the config.py module or Pydantic.
"""

from config import ConfigurationManager, Settings
from domain.admin.entities import AppConfiguration
from domain.admin.exceptions import ConfigurationError
from domain.admin.value_objects import CREDENTIAL_FIELD_NAMES
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

    def reset_to_defaults(self) -> AppConfiguration:
        """
        Reset configuration to defaults while preserving credentials.

        Creates a fresh Settings object with default values, preserves any
        credential fields from the current configuration, and saves the result.

        Returns:
            AppConfiguration reset to defaults with credentials preserved

        Raises:
            ConfigurationError: If reset fails
        """
        try:
            # Get current configuration to preserve credentials
            current_config = self.load()

            # Create fresh defaults
            default_settings = Settings()
            default_sections = {
                'server': default_settings.server.model_dump(),
                'database': default_settings.database.model_dump(),
                'logging': default_settings.logging.model_dump(),
                'llm': default_settings.llm.model_dump(),
                'reference': default_settings.reference.model_dump() if default_settings.reference else None,
                'sync': default_settings.sync.model_dump() if default_settings.sync else None,
            }

            # Preserve credentials from current config
            for section_name, section_data in current_config.sections.items():
                if section_name not in default_sections or section_data is None:
                    continue
                default_section = default_sections[section_name]
                if default_section is None:
                    continue
                for key, value in section_data.items():
                    if key in CREDENTIAL_FIELD_NAMES:
                        default_section[key] = value

            reset_config = AppConfiguration(sections=default_sections)
            self.save(reset_config)
            logger.debug("Configuration reset to defaults with credentials preserved")
            return reset_config
        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(f'Failed to reset configuration: {e}') from e
