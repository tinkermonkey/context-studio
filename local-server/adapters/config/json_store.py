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
                nlp=settings.nlp if settings.nlp else {},
                embedding=settings.embedding if settings.embedding else {},
                reference_sources=settings.reference.model_dump() if settings.reference else {},
                sync=settings.sync.model_dump() if settings.sync else None,
            )
        except RuntimeError as e:
            raise ConfigurationError(f'Failed to load configuration: {e}') from e

    def get_config(self) -> AppConfiguration:
        """
        Get current application configuration.

        Returns:
            AppConfiguration with all configuration sections

        Raises:
            ConfigurationError: If loading fails
        """
        return self.load()

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

    def update_config(self, updates: dict[str, dict]) -> AppConfiguration:
        """
        Update application configuration with partial updates.

        Loads current configuration, merges updates into specified sections,
        and saves the result.

        Args:
            updates: Dictionary with section names as keys and dicts of updates as values.
                    Merges updates into existing sections.

        Returns:
            AppConfiguration with updates applied

        Raises:
            ConfigurationError: If update fails
        """
        try:
            # Load current config
            current_config = self.load()

            # Merge updates into each section
            for section_name, section_updates in updates.items():
                if hasattr(current_config, section_name):
                    current_section = getattr(current_config, section_name)
                    if isinstance(current_section, dict) and isinstance(section_updates, dict):
                        current_section.update(section_updates)
                    else:
                        setattr(current_config, section_name, section_updates)

            # Save the updated config
            self._persist_config(current_config)
            logger.debug("Configuration updated successfully")
            return current_config
        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(f'Failed to update configuration: {e}') from e

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
                nlp=default_settings.nlp if default_settings.nlp else {},
                embedding=default_settings.embedding if default_settings.embedding else {},
                reference_sources=default_settings.reference.model_dump() if default_settings.reference else {},
                sync=default_settings.sync.model_dump() if default_settings.sync else None,
            )

            # Preserve credentials from current config for each section
            # Only preserve credentials in sections that exist in the defaults
            section_names = ('server', 'database', 'logging', 'llm', 'nlp', 'embedding', 'reference_sources', 'sync')
            for attr_name in section_names:
                current_section = getattr(current_config, attr_name, None)
                default_section = getattr(default_config, attr_name, None)

                # Skip if current section has no credentials
                if current_section is None or not isinstance(current_section, dict):
                    continue

                # Skip if default section doesn't exist (don't recreate sections not in defaults)
                if default_section is None:
                    continue

                # Only preserve if default section is a dict
                if not isinstance(default_section, dict):
                    continue

                # Preserve credential fields from current to default, including nested dicts
                self._preserve_credentials_recursive(current_section, default_section)

            self._persist_config(default_config)
            logger.debug("Configuration reset to defaults with credentials preserved")
            return default_config
        except ConfigurationError:
            raise
        except ValidationError as e:
            raise ConfigurationError(f'Failed to reset configuration: {e}') from e

    def _preserve_credentials_recursive(self, current: dict, default: dict) -> None:
        """
        Recursively preserve credential fields from current to default configuration.

        Preserves credential values in both top-level and nested dictionaries.

        Args:
            current: Current configuration dict
            default: Default configuration dict to update with preserved credentials
        """
        for key, value in current.items():
            if key in CREDENTIAL_FIELD_NAMES and value:
                # Preserve credential
                default[key] = value
            elif isinstance(value, dict) and isinstance(default.get(key), dict):
                # Recursively preserve credentials in nested dicts
                self._preserve_credentials_recursive(value, default[key])

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
                'nlp': config.nlp or {},
                'embedding': config.embedding or {},
            }
            # Add optional sections only if they exist
            if config.reference_sources is not None:
                settings_dict['reference'] = config.reference_sources

            if config.sync is not None:
                settings_dict['sync'] = config.sync

            # Pydantic will convert dicts to config classes
            new_settings = Settings(**settings_dict)  # type: ignore[arg-type]
            self._mgr.settings = new_settings

            if not self._mgr.save():
                raise ConfigurationError("ConfigurationManager.save() returned False")
        except ConfigurationError:
            raise
        except ValidationError as e:
            raise ConfigurationError(f'Failed to persist configuration: {e}') from e
