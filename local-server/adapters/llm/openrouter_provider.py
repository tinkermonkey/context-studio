"""
OpenRouter LLM provider adapter.

Implements the LLMProvider port for OpenRouter, which provides unified access
to multiple LLM providers through a single API. Supports hundreds of models
including OpenAI GPT, Anthropic Claude, Meta Llama, and others.

Configuration:
    API key: config.json (llm.openrouter_api_key)
    Base URL: https://openrouter.ai/api/v1
    Default model: google/gemini-3-flash-preview
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import OrderedDict
from typing import Literal

import httpx

from domain.pipeline.exceptions import PipelineExternalServiceError
from domain.pipeline.ports import LLMResponse
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)


class OpenRouterProvider:
    """
    LLM provider adapter for OpenRouter API.

    Routes requests to any OpenRouter-available model. Supports response
    caching keyed by (prompt_hash, model, temperature, max_tokens, response_format)
    with a bounded LRU cache.
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "google/gemini-3-flash-preview"
    CACHE_MAX_SIZE = 1000  # Maximum number of cached responses

    def __init__(self, api_key: str) -> None:
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key from configuration.

        Raises:
            ValueError: If API key is empty
        """
        if not api_key:
            raise ValueError(
                "OpenRouter API key not configured. Provide openrouter_api_key in"
                " config.json under the llm section."
            )
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": "https://contextstudio.local",
                "X-Title": "Context Studio",
            },
            timeout=60.0,
        )
        # Bounded LRU cache: OrderedDict with max size to prevent unbounded growth
        self._response_cache: OrderedDict[str, LLMResponse] = OrderedDict()

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
        Request a completion from OpenRouter.

        Uses (prompt_hash, model, temperature, max_tokens, response_format) caching.
        Cache invalidates on configuration version change (handled by caller).

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier (e.g., 'gpt-4', 'claude-opus-4-7',
                   'google/gemini-3-flash-preview')
            temperature: Sampling temperature (0.0–2.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional response format ("json" for JSON output)
            timeout: Request timeout in seconds
            seed: Optional random seed for reproducible generation

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            ValueError: If model is invalid or API key is unauthorized
            RuntimeError: For other HTTP errors
            PipelineExternalServiceError: If request times out or connection fails
        """
        # Check cache
        cache_key = self._make_cache_key(
            system_prompt, user_prompt, model, temperature, max_tokens, response_format
        )
        if cache_key in self._response_cache:
            logger.debug(f"Cache hit for model {model}")
            # Move to end for LRU ordering
            self._response_cache.move_to_end(cache_key)
            return self._response_cache[cache_key]

        # Prepare request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        request_body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format == "json":
            request_body["response_format"] = {"type": "json_object"}

        if seed is not None:
            request_body["seed"] = seed

        # Execute request
        start_ms = time.time() * 1000
        try:
            response = self._client.post(
                "/chat/completions",
                json=request_body,
                timeout=timeout or 60.0,
            )
            duration_ms = time.time() * 1000 - start_ms

            response.raise_for_status()
            data = response.json()

            # Validate response structure
            if not isinstance(data, dict):
                raise RuntimeError("OpenRouter response is not a JSON object")

            if "choices" not in data:
                raise RuntimeError("OpenRouter response missing 'choices' field")

            choices = data["choices"]
            if not isinstance(choices, list) or len(choices) == 0:
                raise RuntimeError("OpenRouter response 'choices' is empty or not a list")

            choice = choices[0]
            if not isinstance(choice, dict) or "message" not in choice:
                raise RuntimeError("OpenRouter response choice missing 'message' field")

            message = choice["message"]
            if not isinstance(message, dict) or "content" not in message:
                raise RuntimeError("OpenRouter response message missing 'content' field")

            content = message["content"]

            if "usage" not in data:
                raise RuntimeError("OpenRouter response missing 'usage' field")

            usage = data["usage"]
            if not isinstance(usage, dict):
                raise RuntimeError("OpenRouter response 'usage' is not a JSON object")

            if "prompt_tokens" not in usage or "completion_tokens" not in usage:
                raise RuntimeError("OpenRouter response usage missing token counts")

            tokens_in = usage["prompt_tokens"]
            tokens_out = usage["completion_tokens"]
            finish_reason = choice.get("finish_reason", "stop")

            llm_response = LLMResponse(
                content=content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=duration_ms,
                finish_reason=finish_reason,
                model=model,
            )

            # Cache result with LRU eviction
            if len(self._response_cache) >= self.CACHE_MAX_SIZE:
                # Remove oldest entry (first item in OrderedDict)
                self._response_cache.popitem(last=False)
            self._response_cache[cache_key] = llm_response
            return llm_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("OpenRouter API key is invalid or unauthorized")
            elif e.response.status_code == 404:
                raise ValueError(f"Model not found on OpenRouter: {model}")
            elif e.response.status_code == 429:
                raise RuntimeError("OpenRouter rate limit exceeded")
            else:
                logger.error(f"OpenRouter API error: {e.response.status_code} {e.response.text}")
                raise RuntimeError(f"OpenRouter API error: {e.response.status_code}")
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            raise PipelineExternalServiceError(
                f"External service error: {type(e).__name__}: {str(e)}"
            ) from e
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling OpenRouter: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {type(e).__name__}: {e}")

    def is_model_available(self, model: str) -> bool:
        """
        Check if a model is available on OpenRouter.

        Validates that the model string has a reasonable format (provider/model-name
        or just model-name). OpenRouter supports hundreds of models in these formats.
        Returns False for obviously invalid identifiers.

        Args:
            model: Model identifier

        Returns:
            True if model appears valid for OpenRouter, False otherwise
        """
        if not model or not isinstance(model, str):
            return False

        # Remove whitespace and check if still valid
        model_clean = model.strip()
        if not model_clean:
            return False

        # OpenRouter models are typically in format:
        # - "provider/model-name" (e.g., "openai/gpt-4", "google/gemini-3-flash-preview")
        # - "model-name" (sometimes without provider prefix)
        # Allow alphanumeric, hyphens, underscores, forward slashes, colons, and dots
        if not re.match(r"^[a-zA-Z0-9._:/-]+$", model_clean):
            return False

        return True

    def list_available_models(self) -> list[str]:
        """
        Get list of available models.

        For now, returns an empty list (in production, would fetch from
        OpenRouter /models endpoint). Callers can assume OpenRouter supports
        any model string they pass to complete().

        Returns:
            Empty list (OpenRouter catalog is dynamic)
        """
        return []

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
        Request a completion from OpenRouter (async version).

        Runs the API call in a thread pool to avoid blocking the event loop.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier (e.g., 'gpt-4', 'claude-opus-4-7')
            temperature: Sampling temperature (0.0–2.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional response format ("json" for JSON output)
            timeout: Request timeout in seconds
            seed: Optional random seed for reproducible generation

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            ValueError: If model is invalid or API key is unauthorized
            RuntimeError: For other HTTP errors
            PipelineExternalServiceError: If request times out or connection fails
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

    def _make_cache_key(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: Literal["json", "text"] | None,
    ) -> str:
        """
        Generate cache key from prompt and model parameters.

        Combines (prompt_hash, model, temperature, max_tokens, response_format)
        to avoid cache collisions. Including max_tokens and response_format is
        critical: identical prompts with different max_tokens produce different
        results (e.g., definitions vs connections in schema extraction).

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format specification

        Returns:
            Cache key string
        """
        combined = f"{system_prompt}||{user_prompt}"
        prompt_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        format_str = response_format or "text"
        return f"{prompt_hash}:{model}:{temperature}:{max_tokens}:{format_str}"

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._response_cache.clear()
        logger.info("OpenRouter response cache cleared")
