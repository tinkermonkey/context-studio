"""
Provider routing service for LLM models.

This module handles routing LLM requests to the appropriate provider
(native LangChain vs OpenRouter) based on enabled model configuration.
"""

import os
import warnings
from typing import Optional, Dict, Any, Union
from langchain.chat_models import init_chat_model
from langchain.schema import BaseMessage

from .enabled_models import (
    EnabledModelsManager,
    ProviderType,
    EnabledModelConfig,
    get_enabled_models_manager
)
from .model_capabilities import get_model_capabilities, validate_model_config
from .exceptions import LLMConfigurationError
from utils.logger import get_logger

logger = get_logger(__name__)


class ProviderRouter:
    """Routes LLM requests to appropriate providers based on configuration"""

    def __init__(self):
        self.logger = logger
        self.models_manager = get_enabled_models_manager()
        self._llm_cache: Dict[str, Any] = {}  # Cache initialized LLMs

    def get_llm_for_model(self, model_name: str, **kwargs) -> Any:
        """
        Get the appropriate LLM instance for a model.

        Args:
            model_name: The model to get LLM for
            **kwargs: Additional parameters for LLM initialization

        Returns:
            Initialized LLM instance

        Raises:
            LLMConfigurationError: If model is not enabled or configuration is invalid
        """
        # Check if model is enabled
        config = self.models_manager.get_model_config(model_name)
        if not config or not config.enabled:
            raise LLMConfigurationError(f"Model '{model_name}' is not enabled")

        # Use cache key that includes config-specific parameters
        cache_key = self._get_cache_key(model_name, config, kwargs)

        if cache_key in self._llm_cache:
            self.logger.debug(f"Using cached LLM for model: {model_name}")
            return self._llm_cache[cache_key]

        # Route to appropriate provider
        llm = self._create_llm_for_provider(config, **kwargs)

        # Cache the LLM instance
        self._llm_cache[cache_key] = llm

        self.logger.info(f"Created LLM for model: {model_name} via {config.provider_type.value}")
        return llm

    def _get_cache_key(self, model_name: str, config: EnabledModelConfig, kwargs: Dict) -> str:
        """Generate cache key for LLM instance"""
        # Include key parameters that affect LLM initialization
        key_params = {
            'model': model_name,
            'provider': config.provider_type.value,
            'temperature': kwargs.get('temperature', 0),
            'api_key_var': config.api_key_env_var,
            'endpoint': config.custom_endpoint,
            'model_override': config.model_override
        }
        return str(sorted(key_params.items()))

    def _create_llm_for_provider(self, config: EnabledModelConfig, **kwargs) -> Any:
        """Create LLM instance based on provider type"""

        if config.provider_type == ProviderType.NATIVE_OPENAI:
            return self._create_openai_llm(config, **kwargs)
        elif config.provider_type == ProviderType.NATIVE_ANTHROPIC:
            return self._create_anthropic_llm(config, **kwargs)
        elif config.provider_type == ProviderType.NATIVE_GOOGLE:
            return self._create_google_llm(config, **kwargs)
        elif config.provider_type == ProviderType.OPENROUTER:
            return self._create_openrouter_llm(config, **kwargs)
        else:
            raise LLMConfigurationError(f"Unsupported provider type: {config.provider_type}")

    def _create_openai_llm(self, config: EnabledModelConfig, **kwargs) -> Any:
        """Create OpenAI LLM via LangChain"""
        try:
            # Get API key
            api_key_var = config.api_key_env_var or "OPENAI_API_KEY"
            api_key = os.getenv(api_key_var)
            if not api_key:
                raise LLMConfigurationError(f"Environment variable '{api_key_var}' not set")

            # Validate API key format
            if not api_key.startswith("sk-"):
                raise LLMConfigurationError(f"Invalid OpenAI API key format in '{api_key_var}'")

            # Determine model name (allow override)
            model_name = config.model_override or config.model_name

            # Apply model capabilities validation
            capabilities = get_model_capabilities(model_name)
            validated_config, warnings_list = validate_model_config(model_name, kwargs)

            # Log warnings
            for warning in warnings_list:
                self.logger.warning(warning)

            # Create LLM
            llm_params = {
                'model': model_name,
                'model_provider': 'openai',
                'openai_api_key': api_key,
                **validated_config
            }

            # Add custom endpoint if specified
            if config.custom_endpoint:
                llm_params['openai_api_base'] = config.custom_endpoint
            else:
                # Check if caching proxy is enabled for OpenAI
                from config import get_settings
                settings = get_settings()
                if (settings.reference_sources.openai.enabled and
                    settings.reference_sources.openai.use_proxy and
                    settings.proxy_server.enabled):
                    # Route through caching proxy
                    proxy_url = f"http://{settings.proxy_server.host}:{settings.proxy_server.port}"
                    llm_params['openai_proxy'] = proxy_url
                    self.logger.info(f"OpenAI LLM configured to use caching proxy: {proxy_url}")

            # Suppress LangChain warnings about JSON schema
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*json_schema.*")
                llm = init_chat_model(**llm_params)

            self.logger.debug(f"OpenAI LLM created: {model_name}")
            return llm

        except Exception as e:
            self.logger.error(f"Failed to create OpenAI LLM for {config.model_name}: {e}")
            raise LLMConfigurationError(f"OpenAI LLM creation failed: {str(e)}")

    def _create_anthropic_llm(self, config: EnabledModelConfig, **kwargs) -> Any:
        """Create Anthropic LLM via LangChain"""
        try:
            # Get API key
            api_key_var = config.api_key_env_var or "ANTHROPIC_API_KEY"
            api_key = os.getenv(api_key_var)
            if not api_key:
                raise LLMConfigurationError(f"Environment variable '{api_key_var}' not set")

            # Determine model name (allow override)
            model_name = config.model_override or config.model_name

            # Apply model capabilities validation
            capabilities = get_model_capabilities(model_name)
            validated_config, warnings_list = validate_model_config(model_name, kwargs)

            # Log warnings
            for warning in warnings_list:
                self.logger.warning(warning)

            # Create LLM
            llm_params = {
                'model': model_name,
                'model_provider': 'anthropic',
                'anthropic_api_key': api_key,
                **validated_config
            }

            # Add custom endpoint if specified
            if config.custom_endpoint:
                llm_params['anthropic_api_url'] = config.custom_endpoint
            else:
                # Check if caching proxy is enabled for Anthropic
                from config import get_settings
                settings = get_settings()
                if (settings.reference_sources.anthropic.enabled and
                    settings.reference_sources.anthropic.use_proxy and
                    settings.proxy_server.enabled):
                    # Route through caching proxy
                    proxy_url = f"http://{settings.proxy_server.host}:{settings.proxy_server.port}"
                    llm_params['anthropic_proxy'] = proxy_url
                    self.logger.info(f"Anthropic LLM configured to use caching proxy: {proxy_url}")

            llm = init_chat_model(**llm_params)

            self.logger.debug(f"Anthropic LLM created: {model_name}")
            return llm

        except Exception as e:
            self.logger.error(f"Failed to create Anthropic LLM for {config.model_name}: {e}")
            raise LLMConfigurationError(f"Anthropic LLM creation failed: {str(e)}")

    def _create_google_llm(self, config: EnabledModelConfig, **kwargs) -> Any:
        """Create Google LLM via LangChain"""
        try:
            # Get API key
            api_key_var = config.api_key_env_var or "GOOGLE_API_KEY"
            api_key = os.getenv(api_key_var)
            if not api_key:
                raise LLMConfigurationError(f"Environment variable '{api_key_var}' not set")

            # Determine model name (allow override)
            model_name = config.model_override or config.model_name

            # Apply model capabilities validation
            capabilities = get_model_capabilities(model_name)
            validated_config, warnings_list = validate_model_config(model_name, kwargs)

            # Log warnings
            for warning in warnings_list:
                self.logger.warning(warning)

            # Create LLM
            llm_params = {
                'model': model_name,
                'model_provider': 'google-genai',  # or 'google-vertexai' depending on setup
                'google_api_key': api_key,
                **validated_config
            }

            # Add custom endpoint if specified
            if config.custom_endpoint:
                llm_params['google_api_base'] = config.custom_endpoint

            llm = init_chat_model(**llm_params)

            self.logger.debug(f"Google LLM created: {model_name}")
            return llm

        except Exception as e:
            self.logger.error(f"Failed to create Google LLM for {config.model_name}: {e}")
            raise LLMConfigurationError(f"Google LLM creation failed: {str(e)}")

    def _create_openrouter_llm(self, config: EnabledModelConfig, **kwargs) -> Any:
        """Create OpenRouter LLM via LangChain OpenAI-compatible interface"""
        try:
            # Get API key
            api_key_var = config.api_key_env_var or "OPENROUTER_API_KEY"
            api_key = os.getenv(api_key_var)
            if not api_key:
                raise LLMConfigurationError(f"Environment variable '{api_key_var}' not set")

            # Determine model name (allow override)
            model_name = config.model_override or config.model_name

            # OpenRouter uses OpenAI-compatible API
            # Apply model capabilities validation
            capabilities = get_model_capabilities(model_name)
            validated_config, warnings_list = validate_model_config(model_name, kwargs)

            # Log warnings
            for warning in warnings_list:
                self.logger.warning(warning)

            # Create LLM using OpenAI provider but with OpenRouter endpoint
            openrouter_endpoint = config.custom_endpoint or "https://openrouter.ai/api/v1"

            llm_params = {
                'model': model_name,
                'model_provider': 'openai',  # OpenRouter is OpenAI-compatible
                'openai_api_key': api_key,
                'openai_api_base': openrouter_endpoint,
                **validated_config
            }

            # Suppress LangChain warnings about JSON schema
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*json_schema.*")
                llm = init_chat_model(**llm_params)

            self.logger.debug(f"OpenRouter LLM created: {model_name}")
            return llm

        except Exception as e:
            self.logger.error(f"Failed to create OpenRouter LLM for {config.model_name}: {e}")
            raise LLMConfigurationError(f"OpenRouter LLM creation failed: {str(e)}")

    def clear_cache(self) -> None:
        """Clear the LLM cache"""
        self._llm_cache.clear()
        self.logger.info("LLM cache cleared")

    def get_enabled_models(self) -> list[str]:
        """Get list of currently enabled model names"""
        return [config.model_name for config in self.models_manager.get_enabled_models()]

    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available (enabled and configured)"""
        return self.models_manager.is_model_enabled(model_name)

    def get_provider_for_model(self, model_name: str) -> Optional[ProviderType]:
        """Get the provider type for a model"""
        return self.models_manager.get_provider_for_model(model_name)


# Global instance
_provider_router: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    """Get the global provider router instance"""
    global _provider_router
    if _provider_router is None:
        _provider_router = ProviderRouter()
    return _provider_router