"""
JSONFileConfigStore adapter implementation.

Wraps the ConfigurationManager to implement the ConfigurationStore port,
enabling the domain layer to persist and retrieve application configuration
without direct dependency on the config.py module or Pydantic.
"""

from pydantic import ValidationError

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
            logger.debug("Configuration loaded successfully")
            return AppConfiguration(
                server=settings.server.model_dump(),
                database=settings.database.model_dump(),
                logging=settings.logging.model_dump(),
                llm=settings.llm.model_dump(),
                nlp=settings.nlp.model_dump() if hasattr(settings, 'nlp') and settings.nlp else {},
                embedding=settings.embedding.model_dump() if hasattr(settings, 'embedding') and settings.embedding else {},
                reference_sources=settings.reference.model_dump() if hasattr(settings, 'reference') and settings.reference else {},
                sync=settings.sync.model_dump() if hasattr(settings, 'sync') and settings.sync else None,
            )
        except RuntimeError as e:
            raise ConfigurationError(f'Failed to load configuration: {e}') from e

    def save(self, config: AppConfiguration) -> AppConfiguration:
        """
        Save application configuration.

        Takes an AppConfiguration object and persists it to storage.

        Args:
            config: AppConfiguration object to save

        Returns:
            AppConfiguration object that was saved

        Raises:
            ConfigurationError: If save fails
        """
        self._persist_config(config)
        logger.debug("Configuration saved successfully")
        return config

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
            default_config = AppConfiguration(
                server=default_settings.server.model_dump(),
                database=default_settings.database.model_dump(),
                logging=default_settings.logging.model_dump(),
                llm=default_settings.llm.model_dump(),
                nlp=default_settings.nlp.model_dump() if hasattr(default_settings, 'nlp') and default_settings.nlp else {},
                embedding=default_settings.embedding.model_dump() if hasattr(default_settings, 'embedding') and default_settings.embedding else {},
                reference_sources=default_settings.reference.model_dump() if hasattr(default_settings, 'reference') and default_settings.reference else {},
                sync=default_settings.sync.model_dump() if hasattr(default_settings, 'sync') and default_settings.sync else None,
            )

            # Map of section names to their config attributes for preserving credentials
            section_mapping = {
                'server': 'server',
                'database': 'database',
                'logging': 'logging',
                'llm': 'llm',
                'nlp': 'nlp',
                'embedding': 'embedding',
                'reference_sources': 'reference_sources',
                'sync': 'sync',
            }

            # Preserve credentials from current config
            for section_name, attr_name in section_mapping.items():
                current_section = getattr(current_config, attr_name, None)
                default_section = getattr(default_config, attr_name, None)

                if current_section is None or default_section is None:
                    continue
                if not isinstance(default_section, dict) or not isinstance(current_section, dict):
                    continue

                for key, value in current_section.items():
                    if key in CREDENTIAL_FIELD_NAMES:
                        default_section[key] = value

            self._persist_config(default_config)
            logger.debug("Configuration reset to defaults with credentials preserved")
            return default_config
        except ConfigurationError:
            raise
        except ValidationError as e:
            raise ConfigurationError(f'Failed to reset configuration: {e}') from e

    def _persist_config(self, config: AppConfiguration) -> None:
        """
        Internal helper to persist configuration to storage.

        Args:
            config: AppConfiguration to persist

        Raises:
            ConfigurationError: If persistence fails
        """
        try:
            # Reconstruct Settings object from config sections
            # Map AppConfiguration fields to Settings constructor arguments
            settings_dict = {
                'server': config.server or {},
                'database': config.database or {},
                'logging': config.logging or {},
                'llm': config.llm or {},
            }
            # Add optional sections only if they exist
            if config.reference_sources is not None:
                settings_dict['reference'] = config.reference_sources

            if config.sync is not None:
                settings_dict['sync'] = config.sync

            # Add nlp and embedding if they exist and have handlers in Settings
            if hasattr(config, 'nlp') and config.nlp is not None:
                settings_dict['nlp'] = config.nlp
            if hasattr(config, 'embedding') and config.embedding is not None:
                settings_dict['embedding'] = config.embedding

            # Pydantic will convert dicts to config classes
            new_settings = Settings(**settings_dict)  # type: ignore[arg-type]
            self._mgr.settings = new_settings

            if not self._mgr.save():
                raise ConfigurationError("ConfigurationManager.save() returned False")
        except ConfigurationError:
            raise
        except ValidationError as e:
            raise ConfigurationError(f'Failed to persist configuration: {e}') from e
