"""
LLM provider router implementation.

Routes requests to the appropriate LLM provider based on the model identifier.
Manages multiple LLM providers (OpenAI, Anthropic, etc.) and routes completion
requests to the appropriate provider based on model availability.

This adapter implements the LLMProvider port and is used by the Knowledge Extraction
and LLM Pipeline services.
"""

from typing import Any

from adapters.llm.openai_provider import OpenAIProvider
from adapters.llm.anthropic_provider import AnthropicProvider
from domain.ports import LLMProvider, LLMResponse
from utils.logger import get_logger

logger = get_logger(__name__)


class LLMProviderRouter:
    """
    Routes LLM requests to appropriate providers based on model.

    Manages multiple LLM providers and routes completion requests to the correct
    provider based on which models are available. Validates API keys at initialization
    and logs warnings for invalid configurations without raising exceptions.
    """

    def __init__(self, openai_api_key: str = "", anthropic_api_key: str = "") -> None:
        """
        Initialize the LLM provider router with API keys.

        Args:
            openai_api_key: OpenAI API key (optional)
            anthropic_api_key: Anthropic API key (optional)
        """
        self._providers: dict[str, LLMProvider] = {}

        if openai_api_key:
            if not openai_api_key.startswith("sk-"):
                logger.warning(
                    "OpenAI API key format invalid — provider marked unavailable"
                )
            else:
                try:
                    self._providers["openai"] = OpenAIProvider(openai_api_key)
                    logger.info("OpenAI provider initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI provider: {str(e)}")

        if anthropic_api_key:
            if not anthropic_api_key.startswith("sk-ant-"):
                logger.warning(
                    "Anthropic API key format invalid — provider marked unavailable"
                )
            else:
                try:
                    self._providers["anthropic"] = AnthropicProvider(anthropic_api_key)
                    logger.info("Anthropic provider initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize Anthropic provider: {str(e)}")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM provider.

        Routes to the appropriate provider based on the model identifier.

        Args:
            system_prompt: System context for the model
            user_prompt: The user's prompt
            model: Model identifier (e.g., 'gpt-4o', 'claude-opus-4-6')
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            response_format: Optional response format specification
            timeout: Request timeout in seconds (provider-specific behavior)

        Returns:
            LLMResponse with the completion

        Raises:
            ValueError: If no provider is available for the requested model
        """
        provider = self._route_to_provider(model)
        return provider.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
        )

    def _route_to_provider(self, model: str) -> LLMProvider:
        """
        Find the appropriate provider for a model.

        Args:
            model: Model identifier to route

        Returns:
            LLMProvider instance that supports the model

        Raises:
            ValueError: If no provider supports the model
        """
        for provider in self._providers.values():
            if provider.is_model_available(model):
                return provider
        raise ValueError(f"No provider available for model: {model}")

    def is_model_available(self, model: str) -> bool:
        """
        Check if a model is available from any provider.

        Args:
            model: Model identifier to check

        Returns:
            True if any configured provider supports the model, False otherwise
        """
        return any(p.is_model_available(model) for p in self._providers.values())

    def list_available_models(self) -> list[str]:
        """
        List all available models from configured providers.

        Returns the union of models from all configured providers.

        Returns:
            List of available model identifiers
        """
        models = []
        for provider in self._providers.values():
            models.extend(provider.list_available_models())
        return models

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM provider (async version).

        Routes to the appropriate provider based on the model identifier.

        Args:
            system_prompt: System context for the model
            user_prompt: The user's prompt
            model: Model identifier (e.g., 'gpt-4o', 'claude-opus-4-6')
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            response_format: Optional response format specification
            timeout: Request timeout in seconds (provider-specific behavior)

        Returns:
            LLMResponse with the completion

        Raises:
            ValueError: If no provider is available for the requested model
        """
        provider = self._route_to_provider(model)
        # Check if provider has async method and use it, otherwise fallback to sync
        if hasattr(provider, 'complete_async'):
            return await provider.complete_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                timeout=timeout,
            )
        else:
            # Fallback for providers without async support
            return provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                timeout=timeout,
            )
