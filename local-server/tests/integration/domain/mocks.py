"""
Shared mock classes for domain integration tests.
"""

from domain.pipeline.ports import LLMResponse
from domain.ports import EventPublisher


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response: str = ""):
        self.response = response
        self.calls = []

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return LLMResponse(
            content=self.response,
            tokens_in=50,
            tokens_out=50,
            duration_ms=100.0,
            finish_reason="stop",
            model=model,
        )


class DummyEventPublisher(EventPublisher):
    """Dummy event publisher for testing."""

    def publish(self, event):
        pass


class DummyEmbeddingService:
    """Dummy embedding service for testing."""

    def embed(self, text: str) -> list[float]:
        return [0.0] * 384
