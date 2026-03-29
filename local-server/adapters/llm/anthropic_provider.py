"""
Anthropic LLM provider implementation.

Provides integration with Anthropic's Claude API for language model completions.
"""

import time
from typing import Literal

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    anthropic = None  # type: ignore[assignment]

from domain.extraction.ports import LLMResponse
from utils.logger import get_logger
from utils.async_executor import run_sync_in_executor

logger = get_logger(__name__)


class AnthropicProvider:
    """
    LLM provider for Anthropic Claude models.

    Implements the LLMProvider protocol to provide access to Anthropic's
    Claude models including Claude Opus, Sonnet, and Haiku.
    """

    AVAILABLE_MODELS = [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    ]

    def __init__(self, api_key: str) -> None:
        """
        Initialize Anthropic provider with API key.

        Args:
            api_key: Anthropic API key for authentication
        """
        self._api_key = api_key
        self._client: Any = None
        if HAS_ANTHROPIC:
            self._client = anthropic.Anthropic(api_key=api_key)  # type: ignore[attr-defined]
        else:
            logger.warning("anthropic package not installed — completions will fail")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        Request a completion from Anthropic Claude.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier (e.g., 'claude-opus-4-6')
            temperature: Sampling temperature (0.0–1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output (not used by Anthropic)
            timeout: Request timeout in seconds (passed to Anthropic client)

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            RuntimeError: If Anthropic client is not initialized or API call fails
        """
        if self._client is None:
            raise RuntimeError("Anthropic client not initialized — package not installed")

        if not self.is_model_available(model):
            raise ValueError(f"Model {model} is not available from Anthropic provider")

        try:
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }

            if timeout is not None:
                kwargs["timeout"] = timeout

            start_time = time.perf_counter()
            response = self._client.messages.create(**kwargs)  # type: ignore[union-attr]
            elapsed_time = time.perf_counter() - start_time
            duration_ms = elapsed_time * 1000

            return LLMResponse(
                content=response.content[0].text if response.content else "",
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
                duration_ms=duration_ms,
                finish_reason=response.stop_reason or "unknown",
                model=model,
            )
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise

    def is_model_available(self, model: str) -> bool:
        """
        Check if a model is available from Anthropic.

        Args:
            model: Model identifier to check

        Returns:
            True if the model is in the available models list, False otherwise
        """
        return model in self.AVAILABLE_MODELS

    def list_available_models(self) -> list[str]:
        """
        Get list of available Anthropic models.

        Returns:
            List of available model identifiers
        """
        return list(self.AVAILABLE_MODELS)

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        Request a completion from Anthropic Claude (async version).

        Runs the API call in a thread pool to avoid blocking the event loop.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier (e.g., 'claude-opus-4-6')
            temperature: Sampling temperature (0.0–1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output (not used by Anthropic)
            timeout: Request timeout in seconds (passed to Anthropic client)

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            RuntimeError: If Anthropic client is not initialized or API call fails
        """
        return await run_sync_in_executor(
            self.complete,
            system_prompt,
            user_prompt,
            model,
            temperature,
            max_tokens,
            response_format,
            timeout,
        )
