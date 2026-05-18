"""
OpenAI LLM provider implementation.

Provides integration with OpenAI's API for language model completions.
"""

import time
from typing import Any, Literal

try:
    import openai

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    openai = None  # type: ignore[assignment]

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from domain.pipeline.ports import LLMResponse
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class OpenAIProvider:
    """
    LLM provider for OpenAI models.

    Implements the LLMProvider protocol to provide access to OpenAI models
    including GPT-4, GPT-4o, and GPT-3.5-turbo.
    """

    AVAILABLE_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

    def __init__(self, api_key: str) -> None:
        """
        Initialize OpenAI provider with API key.

        Args:
            api_key: OpenAI API key for authentication
        """
        self._api_key = api_key
        self._client: Any = None
        if HAS_OPENAI:
            self._client = openai.OpenAI(api_key=api_key)  # type: ignore[attr-defined]
        else:
            logger.warning("openai package not installed — completions will fail")

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
        Request a completion from OpenAI.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier (e.g., 'gpt-4o')
            temperature: Sampling temperature (0.0–2.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output
            timeout: Request timeout in seconds (passed to OpenAI client)
            seed: Optional random seed for reproducible generation (passed to OpenAI API if supported)

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            RuntimeError: If OpenAI client is not initialized or API call fails
        """
        if self._client is None:
            raise RuntimeError("OpenAI client not initialized — package not installed")

        if not self.is_model_available(model):
            raise ValueError(f"Model {model} is not available from OpenAI provider")

        with tracer.start_as_current_span("llm.complete.openai") as span:
            span.set_attribute("llm.provider", "openai")
            span.set_attribute("llm.model", model)

            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

                kwargs = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                if response_format == "json":
                    kwargs["response_format"] = {"type": "json_object"}
                elif response_format == "text":
                    # OpenAI doesn't require special handling for text mode
                    pass

                if seed is not None:
                    kwargs["seed"] = seed

                if timeout is not None:
                    kwargs["timeout"] = timeout

                start_time = time.perf_counter()
                response = self._client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
                elapsed_time = time.perf_counter() - start_time
                duration_ms = elapsed_time * 1000

                span.set_attribute("llm.tokens.input", response.usage.prompt_tokens)
                span.set_attribute("llm.tokens.output", response.usage.completion_tokens)

                return LLMResponse(
                    content=response.choices[0].message.content or "",
                    tokens_in=response.usage.prompt_tokens,
                    tokens_out=response.usage.completion_tokens,
                    duration_ms=duration_ms,
                    finish_reason=response.choices[0].finish_reason or "unknown",
                    model=model,
                )
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                logger.error(
                    f"OpenAI API error for model {model}: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                raise

    def is_model_available(self, model: str) -> bool:
        """
        Check if a model is available from OpenAI.

        Args:
            model: Model identifier to check

        Returns:
            True if the model is in the available models list, False otherwise
        """
        return model in self.AVAILABLE_MODELS

    def list_available_models(self) -> list[str]:
        """
        Get list of available OpenAI models.

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
        seed: int | None = None,
    ) -> LLMResponse:
        """
        Request a completion from OpenAI (async version).

        Runs the API call in a thread pool to avoid blocking the event loop.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier (e.g., 'gpt-4o')
            temperature: Sampling temperature (0.0–2.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output
            timeout: Request timeout in seconds (passed to OpenAI client)
            seed: Optional random seed for reproducible generation (passed to OpenAI API if supported)

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            RuntimeError: If OpenAI client is not initialized or API call fails
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
            seed,
        )
