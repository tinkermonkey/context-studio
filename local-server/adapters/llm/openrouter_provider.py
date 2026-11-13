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
import threading
import time
from collections import OrderedDict
from typing import Literal

import httpx

from domain.pipelines.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRequestRefusedError,
    LLMTransientError,
)
from domain.pipelines.ports import LLMResponse
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)


def _error_for_status(status: int, model: str) -> Exception:
    """
    The error for a status OpenRouter answered with, as an HTTP status or as
    the code of an error body: one that says whether asking again can help.
    """
    if status == 401:
        return LLMRequestRefusedError("OpenRouter API key is invalid or unauthorized")
    if status == 402:
        return LLMRequestRefusedError("OpenRouter account is out of credits")
    if status == 404:
        return LLMRequestRefusedError(f"Model not found on OpenRouter: {model}")
    if status == 429:
        return LLMRateLimitError("OpenRouter rate limit exceeded")
    if status == 408 or status >= 500:
        # The request timed out upstream, the model's provider is down, or none is available
        return LLMTransientError(f"OpenRouter API error: {status}")
    # Any other status (a bad request, flagged input) is about this request
    # and would be answered the same way again
    return RuntimeError(f"OpenRouter API error: {status}")


class OpenRouterProvider:
    """
    LLM provider adapter for OpenRouter API.

    Routes requests to any OpenRouter-available model. Supports response
    caching keyed by (prompt_hash, model, temperature, max_tokens, response_format)
    with a bounded LRU cache. A response the provider ended with an error is
    not cached; whether any other response is what its caller needed is the
    caller's call, which drops one it cannot use with forget().
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
        # Pipeline workers and the API thread pool call this provider concurrently
        self._cache_lock = threading.Lock()

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
            LLMRequestRefusedError: If the API key is rejected, the model is
                unknown or the account is out of credits
            LLMRateLimitError: If the rate limit turned the request away
            LLMTransientError: If OpenRouter answered with a server error, an
                error in place of a completion or a body that is not JSON, did
                not answer in time, or could not be reached
            RuntimeError: For other HTTP errors and malformed responses
        """
        # Check cache
        cache_key = self._make_cache_key(
            system_prompt, user_prompt, model, temperature, max_tokens, response_format
        )
        with self._cache_lock:
            cached = self._response_cache.get(cache_key)
            if cached is not None:
                # Move to end for LRU ordering
                self._response_cache.move_to_end(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for model {model}")
            return cached

        # Prepare request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        request_body = {
            "model": self._wire_model(model),
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
            try:
                data = response.json()
            except ValueError as e:
                # An empty body, or one cut off or replaced on the way: not an answer
                logger.error(
                    f"OpenRouter answered {response.status_code} with a body that is"
                    f" not JSON ({len(response.content)} bytes): {response.text[:500]}"
                )
                raise LLMTransientError("OpenRouter answered with a body that is not JSON") from e

            # Validate response structure
            if not isinstance(data, dict):
                raise RuntimeError("OpenRouter response is not a JSON object")

            if "choices" not in data:
                if data.get("error"):
                    raise self._error_for_body(data["error"], model)
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

            # A response the provider ended with an error is returned but never
            # cached, so asking again reaches the model
            if finish_reason == "error":
                logger.warning(
                    f"OpenRouter response for model {model} ended with an error;" " not caching it"
                )
                return llm_response

            # Cache result with LRU eviction
            with self._cache_lock:
                if len(self._response_cache) >= self.CACHE_MAX_SIZE:
                    # Remove oldest entry (first item in OrderedDict)
                    self._response_cache.popitem(last=False)
                self._response_cache[cache_key] = llm_response
            return llm_response

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API error: {e.response.status_code} {e.response.text}")
            raise _error_for_status(e.response.status_code, model) from e
        except httpx.TransportError as e:
            # No answer: a timeout, or a connection that failed or dropped
            raise LLMTransientError(
                f"OpenRouter did not answer: {type(e).__name__}: {str(e)}"
            ) from e
        except httpx.DecodingError as e:
            # The body could not be read under its declared content encoding
            raise LLMTransientError("OpenRouter answered with a body that is not JSON") from e
        except (RuntimeError, LLMProviderError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling OpenRouter: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {type(e).__name__}: {e}")

    @staticmethod
    def _error_for_body(error: object, model: str) -> Exception:
        """
        The error for an HTTP 200 whose body is an error in place of a
        completion, which OpenRouter sends when the model's provider failed
        after the request was accepted. Its code, when it has one, is read as
        an HTTP status would be; without one, asking again may help.
        """
        logger.error(f"OpenRouter returned an error in place of a completion: {error}")
        code = error.get("code") if isinstance(error, dict) else None
        if isinstance(code, int) and not isinstance(code, bool):
            return _error_for_status(code, model)
        return LLMTransientError("OpenRouter returned an error in place of a completion")

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
            LLMRequestRefusedError, LLMRateLimitError, LLMTransientError,
            RuntimeError: As complete() raises them
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

    # Bare (unprefixed) model-name patterns mapped to their OpenRouter vendor
    # prefix. In manual testing, OpenRouter rejected a bare "claude-opus-4-7"
    # outright with a 400 and an error to the effect of "not a valid model
    # ID" -- it wants "vendor/model" (e.g. "anthropic/claude-opus-4-7"). But
    # callers throughout this codebase (fixtures, ExtractionRun records,
    # other providers' model lists) commonly pass the bare form, especially
    # when OpenRouter is the only configured provider and there is no direct
    # provider key to route a bare name to instead. `is_model_available`'s
    # looser format check above predates this and doesn't reflect what
    # actually reaches OpenRouter's wire -- this translation is what does.
    _BARE_MODEL_VENDOR_PREFIXES: tuple[tuple[str, str], ...] = (
        ("claude-", "anthropic/"),
        ("gpt-", "openai/"),
        ("o1-", "openai/"),
        ("o3-", "openai/"),
        ("gemini-", "google/"),
    )

    @classmethod
    def _wire_model(cls, model: str) -> str:
        """
        Translate a bare model id to its OpenRouter vendor-prefixed form.

        Only the outgoing HTTP request uses this value. The `model` the caller
        passed keeps flowing everywhere else unchanged -- the cache key, the
        returned `LLMResponse.model`, and (for `RecordingLLMProvider`) the
        cassette key -- so switching between a direct provider key and
        OpenRouter-only never shifts a hash. Already-prefixed ids (containing
        "/") and unrecognized bare names pass through untouched, so OpenRouter
        itself still surfaces a clear error for a genuinely invalid model.
        """
        if "/" in model:
            return model
        for bare_prefix, vendor_prefix in cls._BARE_MODEL_VENDOR_PREFIXES:
            if model.startswith(bare_prefix):
                return f"{vendor_prefix}{model}"
        logger.warning(
            "OpenRouter: bare model id %r matched none of the known vendor "
            "prefixes (%s); forwarding unchanged -- OpenRouter will likely "
            "reject it. Add a mapping to _BARE_MODEL_VENDOR_PREFIXES if this "
            "is a known model family.",
            model,
            ", ".join(prefix for prefix, _ in cls._BARE_MODEL_VENDOR_PREFIXES),
        )
        return model

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

    def forget(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
    ) -> None:
        """Drop the cached response to this request, if there is one."""
        cache_key = self._make_cache_key(
            system_prompt, user_prompt, model, temperature, max_tokens, response_format
        )
        with self._cache_lock:
            self._response_cache.pop(cache_key, None)

    def clear_cache(self) -> None:
        """Clear the response cache."""
        with self._cache_lock:
            self._response_cache.clear()
        logger.info("OpenRouter response cache cleared")
