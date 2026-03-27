"""
LLM provider router implementation.

Routes requests to the appropriate LLM provider based on the model identifier.
Currently provides a stub implementation for testing and future provider expansion.

This adapter implements the LLMProvider port and is used by the Knowledge Extraction
and LLM Pipeline services.
"""

from dataclasses import dataclass
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str  # "stop", "length", "error", etc.


class LLMProviderRouter:
    """
    Routes LLM requests to appropriate providers based on model.

    This adapter currently provides a stub implementation. In a full implementation,
    it would route to specific providers (OpenAI, Anthropic, etc.) based on the
    model identifier.

    For desktop deployments, we may use local models via Ollama or similar,
    or route to cloud providers based on configuration.
    """

    def __init__(self) -> None:
        """Initialize the LLM provider router."""
        logger.info("LLM Provider Router initialized (stub implementation)")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM provider.

        Args:
            system_prompt: System prompt to set context
            user_prompt: The user's prompt
            model: Model identifier (e.g., 'gpt-4', 'claude-opus')
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            response_format: Optional response format ("json", "text")

        Returns:
            LLMResponse with the completion

        Raises:
            NotImplementedError: Currently a stub implementation
        """
        raise NotImplementedError(
            "LLM provider router is not yet implemented. "
            "Configure an LLM provider (OpenAI, Anthropic, etc.) in the adapters."
        )

    def is_model_available(self, model: str) -> bool:
        """
        Check if a model is available.

        Args:
            model: Model identifier to check

        Returns:
            True if the model is available, False otherwise
        """
        return False  # Stub: no models available yet

    def list_available_models(self) -> list[str]:
        """
        List all available models from configured providers.

        Returns:
            List of available model identifiers
        """
        return []  # Stub: no models available yet
