"""
LLM provider router implementation.

Routes requests to the appropriate LLM provider based on the model identifier.
Manages multiple LLM providers (OpenAI, Anthropic, etc.) and routes completion
requests to the appropriate provider based on model availability. When a provider
rejects its API key (HTTP 401/403), the request falls through to the next provider
that supports the model, and the rejecting provider is skipped from then on. Chat
turns also fall through, for that call only, when a provider can't be reached.

This adapter implements the LLMProvider port and is used by the Knowledge Extraction
and LLM Pipeline services.
"""

from typing import AsyncIterator, Literal, Sequence

import anthropic
import httpx
import openai

from adapters.llm.anthropic_chat import AnthropicChatModel
from adapters.llm.anthropic_provider import AnthropicProvider
from adapters.llm.openai_provider import OpenAIProvider
from adapters.llm.openrouter_chat import OpenRouterChatModel
from adapters.llm.openrouter_provider import OpenRouterProvider
from domain.chat.entities import ChatMessage
from domain.chat.ports import ChatModel
from domain.chat.value_objects import ModelEvent, ToolSpec
from domain.pipelines.ports import LLMProvider, LLMResponse
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)

# HTTP statuses meaning "this provider will not accept our API key". The OpenAI and
# Anthropic SDK errors (AuthenticationError / PermissionDeniedError) carry them as
# `status_code`.
_AUTH_FAILURE_STATUSES = (401, 403)


def _is_auth_failure(error: Exception) -> bool:
    """Return True if the error is a provider rejecting its API key."""
    return getattr(error, "status_code", None) in _AUTH_FAILURE_STATUSES


# Errors meaning "the provider could not be reached or did not answer in time":
# the SDKs' connection errors (their timeout errors subclass them) and httpx's
# transport errors (connect errors and timeouts), which the OpenRouter chat
# adapter wraps in a ChatModelError raised from the original.
_CONNECTION_ERRORS = (anthropic.APIConnectionError, openai.APIConnectionError, httpx.TransportError)


def _is_connection_failure(error: BaseException | None) -> bool:
    """Return True if the error, or an error it was raised from, is a connection failure."""
    while error is not None:
        if isinstance(error, _CONNECTION_ERRORS):
            return True
        error = error.__cause__
    return False


class LLMProviderRouter:
    """
    Routes LLM requests to appropriate providers based on model.

    Manages multiple LLM providers and routes completion requests to the correct
    provider based on which models are available. Initialization errors are logged
    and tolerated as long as at least one configured provider succeeds. A ValueError
    is raised if all configured providers fail to initialize.

    Providers are tried in registration order (openai, anthropic, openrouter). If a
    provider rejects its API key, the router logs a warning, stops using that
    provider, and tries the next provider that supports the model. Other errors are
    raised unchanged.

    `stream_chat` implements the ChatModel port for tool-calling chat with the same
    provider order and auth fallback, over the providers that have a streaming chat
    adapter (Anthropic and OpenRouter). Chat also falls through when a provider
    can't be reached (connection error or timeout), without rejecting it, since
    that may be transient.
    """

    def __init__(
        self,
        openai_api_key: str = "",
        anthropic_api_key: str = "",
        openrouter_api_key: str = "",
    ) -> None:
        """
        Initialize the LLM provider router with API keys.

        Args:
            openai_api_key: OpenAI API key (optional)
            anthropic_api_key: Anthropic API key (optional)
            openrouter_api_key: OpenRouter API key (optional)

        Raises:
            ValueError: If no API keys are provided or all configured providers fail to initialize
        """
        self._providers: dict[str, LLMProvider] = {}
        # Streaming tool-calling chat models, keyed by the same provider names.
        # OpenAI has none, so chat routes to Anthropic or OpenRouter only.
        self._chat_models: dict[str, ChatModel] = {}
        self._rejected_providers: set[str] = set()
        init_errors: dict[str, Exception] = {}

        if not openai_api_key and not anthropic_api_key and not openrouter_api_key:
            raise ValueError(
                "At least one LLM provider API key must be configured (openai_api_key,"
                " anthropic_api_key, or openrouter_api_key)"
            )

        if openai_api_key:
            try:
                self._providers["openai"] = OpenAIProvider(openai_api_key)
                logger.info("OpenAI provider initialized")
            except Exception as e:
                init_errors["openai"] = e
                logger.error(
                    f"Failed to initialize OpenAI provider: {type(e).__name__}: {e}",
                    exc_info=True,
                )

        if anthropic_api_key:
            try:
                self._providers["anthropic"] = AnthropicProvider(anthropic_api_key)
                self._chat_models["anthropic"] = AnthropicChatModel(anthropic_api_key)
                logger.info("Anthropic provider initialized")
            except Exception as e:
                init_errors["anthropic"] = e
                logger.error(
                    f"Failed to initialize Anthropic provider: {type(e).__name__}: {e}",
                    exc_info=True,
                )

        if openrouter_api_key:
            try:
                self._providers["openrouter"] = OpenRouterProvider(openrouter_api_key)
                self._chat_models["openrouter"] = OpenRouterChatModel(openrouter_api_key)
                logger.info("OpenRouter provider initialized")
            except Exception as e:
                init_errors["openrouter"] = e
                logger.error(
                    f"Failed to initialize OpenRouter provider: {type(e).__name__}: {e}",
                    exc_info=True,
                )

        if init_errors and not self._providers:
            error_details = "; ".join(
                f"{name}: {type(e).__name__}: {e}" for name, e in init_errors.items()
            )
            raise ValueError(f"No LLM providers could be initialized. Errors: {error_details}")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM provider.

        Routes to the appropriate provider based on the model identifier.

        Args:
            system_prompt: System context for the model
            user_prompt: The user's prompt
            model: Model identifier (e.g., 'gpt-4o', 'claude-opus-4-6')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            response_format: Optional response format specification
            timeout: Request timeout in seconds (provider-specific behavior)
            seed: Optional random seed for reproducible generation

        Returns:
            LLMResponse with the completion

        Raises:
            ValueError: If no provider is available for the requested model
            Exception: The provider's own error for non-auth failures, or the last
                provider's auth error if every supporting provider rejected its key
        """
        auth_error: Exception | None = None
        for name, provider in self._providers_for(model):
            try:
                return provider.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout=timeout,
                    seed=seed,
                )
            except Exception as e:
                if not _is_auth_failure(e):
                    raise
                self._reject_provider(name, e)
                auth_error = e
        # Every supporting provider rejected its API key
        assert auth_error is not None
        raise auth_error

    def supports_model(self, model: str) -> bool:
        """Whether a chat-capable provider that hasn't rejected its key serves the model."""
        return any(
            name in self._chat_models
            and name not in self._rejected_providers
            and provider.is_model_available(model)
            for name, provider in self._providers.items()
        )

    def list_models(self) -> list[str]:
        """Known model ids of the chat providers that haven't rejected their key, deduplicated."""
        models: list[str] = []
        for name, chat_model in self._chat_models.items():
            if name not in self._rejected_providers:
                models.extend(m for m in chat_model.list_models() if m not in models)
        return models

    async def stream_chat(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        model: str,
        max_tokens: int = 16000,
    ) -> AsyncIterator[ModelEvent]:
        """
        Stream one tool-calling chat turn from the first provider that supports the model.

        Implements the ChatModel port. Providers are tried in the same order as
        `complete`. A provider that rejects its API key, or can't be reached
        (connection error or timeout), falls through to the next one, but only
        before the first event is yielded: once output has streamed, a retry
        elsewhere would duplicate it, so later errors propagate. Only a rejected
        key stops the provider being used again.

        Raises:
            ValueError: If no chat-capable provider supports the model
            Exception: The provider's own error for other failures or failures
                after streaming started, or the last fall-through error if every
                supporting provider failed
        """
        last_error: Exception | None = None
        candidates = [
            (name, self._chat_models[name])
            for name, _ in self._providers_for(model)
            if name in self._chat_models
        ]
        if not candidates:
            raise ValueError(
                f"No chat-capable provider available for model: {model}"
                " (chat runs through Anthropic or OpenRouter)"
            )
        for name, chat_model in candidates:
            started = False
            try:
                async for event in chat_model.stream_chat(
                    system=system,
                    messages=messages,
                    tools=tools,
                    model=model,
                    max_tokens=max_tokens,
                ):
                    started = True
                    yield event
                return
            except Exception as e:
                if started:
                    raise
                if _is_auth_failure(e):
                    self._reject_provider(name, e)
                elif _is_connection_failure(e):
                    logger.warning(
                        f"LLM provider '{name}' could not be reached for chat"
                        f" ({type(e).__name__}: {e}); trying the next provider that"
                        " supports the model, if any."
                    )
                else:
                    raise
                last_error = e
        # Every supporting provider rejected its key or could not be reached
        assert last_error is not None
        raise last_error

    def _providers_for(self, model: str) -> list[tuple[str, LLMProvider]]:
        """
        List the usable providers that support a model, in registration order.

        Providers that have rejected their API key are excluded.

        Args:
            model: Model identifier to route

        Returns:
            Non-empty list of (provider name, provider) pairs

        Raises:
            ValueError: If no usable provider supports the model
        """
        candidates = [
            (name, provider)
            for name, provider in self._providers.items()
            if name not in self._rejected_providers and provider.is_model_available(model)
        ]
        if not candidates:
            message = f"No provider available for model: {model}"
            if self._rejected_providers:
                rejected = ", ".join(sorted(self._rejected_providers))
                message += f" (providers that rejected their API key: {rejected})"
            raise ValueError(message)
        return candidates

    def _reject_provider(self, name: str, error: Exception) -> None:
        """Stop routing to a provider that rejected its API key, with a warning."""
        self._rejected_providers.add(name)
        logger.warning(
            f"LLM provider '{name}' rejected its API key"
            f" (HTTP {getattr(error, 'status_code', '?')}: {type(error).__name__});"
            " skipping it for the rest of this session and trying the next provider"
            " that supports the model, if any."
        )

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

    def list_available_providers(self) -> list[str]:
        """
        List all configured LLM provider names.

        Returns:
            List of provider names (e.g., ['openai', 'anthropic'])
        """
        return list(self._providers.keys())

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM provider (async version).

        Routes to the appropriate provider based on the model identifier.

        Args:
            system_prompt: System context for the model
            user_prompt: The user's prompt
            model: Model identifier (e.g., 'gpt-4o', 'claude-opus-4-6')
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            response_format: Optional response format specification
            timeout: Request timeout in seconds (provider-specific behavior)
            seed: Optional random seed for reproducible generation

        Returns:
            LLMResponse with the completion

        Raises:
            ValueError: If no provider is available for the requested model
            Exception: The provider's own error for non-auth failures, or the last
                provider's auth error if every supporting provider rejected its key
        """
        auth_error: Exception | None = None
        for name, provider in self._providers_for(model):
            try:
                # Use the provider's async method if it has one, otherwise run the
                # sync method in an executor
                if hasattr(provider, "complete_async"):
                    return await provider.complete_async(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                        timeout=timeout,
                        seed=seed,
                    )
                return await run_sync_in_executor(
                    provider.complete,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout=timeout,
                    seed=seed,
                )
            except Exception as e:
                if not _is_auth_failure(e):
                    raise
                self._reject_provider(name, e)
                auth_error = e
        # Every supporting provider rejected its API key
        assert auth_error is not None
        raise auth_error
