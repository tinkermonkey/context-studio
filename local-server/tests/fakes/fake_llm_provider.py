"""Fake implementation of LLMProvider for testing."""

import sys
import os
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Literal
from domain.extraction.ports import LLMResponse


class FakeLLMProvider:
    """Fake LLM provider that returns canned responses for testing."""

    def __init__(self, response_content: str = "Test response", tokens_in: int = 10, tokens_out: int = 20, should_fail: bool = False) -> None:
        """
        Initialize the fake LLM provider.

        Args:
            response_content: Content to return in responses
            tokens_in: Number of input tokens to report
            tokens_out: Number of output tokens to report
            should_fail: If True, raise RuntimeError on complete() calls
        """
        self.response_content = response_content
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.call_count = 0
        self.last_call_args: dict[str, Literal["json", "text"] | None] | None = None
        self.should_raise_error = should_fail
        self.error_to_raise = RuntimeError("LLM provider error") if should_fail else None
        self.available_models = ["test-model", "gpt-4", "claude-opus"]

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
        Request a completion from the fake LLM.

        Args:
            system_prompt: System prompt
            user_prompt: User message
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            response_format: Optional response format
            timeout: Request timeout in seconds

        Returns:
            LLMResponse with canned content and token counts
        """
        self.call_count += 1
        self.last_call_args = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
            "timeout": timeout,
        }

        if self.should_raise_error and self.error_to_raise:
            raise self.error_to_raise

        return LLMResponse(
            content=self.response_content,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            duration_ms=0.0,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model: str) -> bool:
        """
        Check if a model is available.

        Args:
            model: Model identifier

        Returns:
            True if the model is in available_models
        """
        return model in self.available_models

    def list_available_models(self) -> list[str]:
        """
        Get list of available models.

        Returns:
            List of available model names
        """
        return list(self.available_models)
