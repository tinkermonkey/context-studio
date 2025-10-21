"""
Enabled models configuration and management.

This module handles dynamic LLM model configuration separate from static capabilities.
Users can enable/disable models and configure how they should be routed (native vs OpenRouter).
"""

import json
import os
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)


class ProviderType(str, Enum):
    """LLM provider routing types"""
    NATIVE_OPENAI = "native_openai"        # Use LangChain OpenAI directly
    NATIVE_ANTHROPIC = "native_anthropic"  # Use LangChain Anthropic directly
    NATIVE_GOOGLE = "native_google"        # Use LangChain Google directly
    OPENROUTER = "openrouter"              # Route through OpenRouter


@dataclass
class EnabledModelConfig:
    """Configuration for an enabled LLM model"""
    model_name: str                        # The model identifier (e.g., "gpt-4", "claude-3-sonnet")
    provider_type: ProviderType            # How to route this model
    display_name: str                      # User-friendly name for UI
    enabled: bool = True                   # Whether model is currently enabled

    # Provider-specific configuration
    api_key_env_var: Optional[str] = None  # Environment variable for API key
    custom_endpoint: Optional[str] = None  # Custom endpoint URL if needed
    model_override: Optional[str] = None   # Override model name for provider

    # Additional metadata
    description: Optional[str] = None      # Model description for UI
    cost_tier: Optional[str] = None        # Cost indicator (low/medium/high)
    tags: List[str] = None                 # Tags for filtering/grouping

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnabledModelConfig':
        """Create from dictionary"""
        # Handle enum conversion
        if isinstance(data.get('provider_type'), str):
            data['provider_type'] = ProviderType(data['provider_type'])
        return cls(**data)


class EnabledModelsManager:
    """Manages the user's enabled models configuration"""

    def __init__(self, config_file: str = "./enabled_models.json"):
        self.config_file = Path(config_file)
        self.logger = logger
        self._models: Dict[str, EnabledModelConfig] = {}
        self.load()

    def load(self) -> None:
        """Load enabled models from config file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)

                self._models = {}
                for model_name, model_data in data.get('models', {}).items():
                    try:
                        config = EnabledModelConfig.from_dict(model_data)
                        self._models[model_name] = config
                    except Exception as e:
                        self.logger.warning(f"Failed to load model config for {model_name}: {e}")

                self.logger.info(f"Loaded {len(self._models)} enabled models from {self.config_file}")
            else:
                # Create default configuration
                self._create_default_config()
                self.save()

        except Exception as e:
            self.logger.error(f"Failed to load enabled models config: {e}")
            self._create_default_config()

    def save(self) -> bool:
        """Save enabled models to config file"""
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare data for serialization
            data = {
                "models": {
                    name: config.to_dict()
                    for name, config in self._models.items()
                },
                "metadata": {
                    "version": "1.0",
                    "last_updated": None  # Could add timestamp if needed
                }
            }

            # Write to file
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)  # default=str for enum serialization

            self.logger.info(f"Saved {len(self._models)} enabled models to {self.config_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save enabled models config: {e}")
            return False

    def _create_default_config(self) -> None:
        """Create default enabled models configuration"""
        self.logger.info("Creating default enabled models configuration")

        # Default native models - conservative set for initial setup
        default_models = [
            EnabledModelConfig(
                model_name="gpt-3.5-turbo",
                provider_type=ProviderType.NATIVE_OPENAI,
                display_name="GPT-3.5 Turbo",
                api_key_env_var="OPENAI_API_KEY",
                description="Fast, cost-effective OpenAI model",
                cost_tier="low",
                tags=["openai", "fast", "cost-effective"]
            ),
            EnabledModelConfig(
                model_name="gpt-4o-mini",
                provider_type=ProviderType.NATIVE_OPENAI,
                display_name="GPT-4o Mini",
                api_key_env_var="OPENAI_API_KEY",
                description="Efficient GPT-4 class model with strong performance",
                cost_tier="low",
                tags=["openai", "fast", "cost-effective", "gpt4-class"]
            ),
            EnabledModelConfig(
                model_name="gpt-4",
                provider_type=ProviderType.NATIVE_OPENAI,
                display_name="GPT-4",
                api_key_env_var="OPENAI_API_KEY",
                description="Advanced OpenAI model with high reasoning capability",
                cost_tier="high",
                tags=["openai", "advanced", "reasoning"],
                enabled=False  # Disabled by default due to cost
            ),
            EnabledModelConfig(
                model_name="claude-3-haiku-20240307",
                provider_type=ProviderType.NATIVE_ANTHROPIC,
                display_name="Claude 3 Haiku",
                api_key_env_var="ANTHROPIC_API_KEY",
                description="Fast, efficient Claude model",
                cost_tier="low",
                tags=["anthropic", "fast", "efficient"]
            ),
            EnabledModelConfig(
                model_name="claude-3-sonnet-20240229",
                provider_type=ProviderType.NATIVE_ANTHROPIC,
                display_name="Claude 3 Sonnet",
                api_key_env_var="ANTHROPIC_API_KEY",
                description="Balanced Claude model with good performance",
                cost_tier="medium",
                tags=["anthropic", "balanced", "capable"],
                enabled=False  # Disabled by default, user can enable
            )
        ]

        self._models = {model.model_name: model for model in default_models}

    def get_enabled_models(self) -> List[EnabledModelConfig]:
        """Get list of currently enabled models"""
        return [config for config in self._models.values() if config.enabled]

    def get_all_models(self) -> List[EnabledModelConfig]:
        """Get list of all configured models (enabled and disabled)"""
        return list(self._models.values())

    def get_model_config(self, model_name: str) -> Optional[EnabledModelConfig]:
        """Get configuration for a specific model"""
        return self._models.get(model_name)

    def add_model(self, config: EnabledModelConfig) -> bool:
        """Add or update a model configuration"""
        try:
            self._models[config.model_name] = config
            return self.save()
        except Exception as e:
            self.logger.error(f"Failed to add model {config.model_name}: {e}")
            return False

    def remove_model(self, model_name: str) -> bool:
        """Remove a model configuration"""
        try:
            if model_name in self._models:
                del self._models[model_name]
                return self.save()
            return True  # Already removed
        except Exception as e:
            self.logger.error(f"Failed to remove model {model_name}: {e}")
            return False

    def enable_model(self, model_name: str) -> bool:
        """Enable a model"""
        if model_name in self._models:
            self._models[model_name].enabled = True
            return self.save()
        return False

    def disable_model(self, model_name: str) -> bool:
        """Disable a model"""
        if model_name in self._models:
            self._models[model_name].enabled = False
            return self.save()
        return False

    def get_models_by_provider(self, provider_type: ProviderType, enabled_only: bool = True) -> List[EnabledModelConfig]:
        """Get models filtered by provider type"""
        models = self.get_enabled_models() if enabled_only else self.get_all_models()
        return [model for model in models if model.provider_type == provider_type]

    def get_models_by_tag(self, tag: str, enabled_only: bool = True) -> List[EnabledModelConfig]:
        """Get models filtered by tag"""
        models = self.get_enabled_models() if enabled_only else self.get_all_models()
        return [model for model in models if tag in model.tags]

    def is_model_enabled(self, model_name: str) -> bool:
        """Check if a model is enabled"""
        config = self.get_model_config(model_name)
        return config is not None and config.enabled

    def get_provider_for_model(self, model_name: str) -> Optional[ProviderType]:
        """Get the provider type for a model"""
        config = self.get_model_config(model_name)
        return config.provider_type if config else None


# Global instance
_enabled_models_manager: Optional[EnabledModelsManager] = None


def get_enabled_models_manager() -> EnabledModelsManager:
    """Get the global enabled models manager instance"""
    global _enabled_models_manager
    if _enabled_models_manager is None:
        _enabled_models_manager = EnabledModelsManager()
    return _enabled_models_manager