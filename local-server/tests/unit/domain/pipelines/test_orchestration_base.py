"""
Unit tests for pipeline orchestration base class.

Tests verify:
- _call_llm() awaits complete_async on the LLM provider
- Error handling when LLM provider is not initialized
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


import pytest

from domain.pipeline.ports import LLMResponse
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from tests.fakes.fake_llm_provider import FakeLLMProvider


class ConcreteOrchestrator(PipelineOrchestrator):
    """Concrete implementation of PipelineOrchestrator for testing."""

    def build_graph(self):
        """Return a dummy graph for testing."""
        return None

    async def execute(self, state: PipelineState) -> PipelineState:
        """Dummy execute method for testing."""
        return state


class TestPipelineOrchestratorCallLLM:
    """Tests for PipelineOrchestrator._call_llm() method."""

    def test_call_llm_raises_when_provider_not_initialized(self):
        """_call_llm raises RuntimeError when LLM provider is None."""
        orchestrator = ConcreteOrchestrator(llm_provider=None)

        with pytest.raises(RuntimeError) as exc_info:
            import asyncio
            asyncio.run(
                orchestrator._call_llm(
                    system_prompt="sys",
                    user_prompt="user",
                    model="test-model",
                )
            )

        assert "LLM provider not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_llm_awaits_complete_async(self):
        """_call_llm awaits complete_async on the provider."""
        fake_provider = FakeLLMProvider(
            response_content="Test completion",
            tokens_in=10,
            tokens_out=20,
        )
        orchestrator = ConcreteOrchestrator(llm_provider=fake_provider)

        response = await orchestrator._call_llm(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="test-model",
            temperature=0.5,
            max_tokens=200,
        )

        assert isinstance(response, LLMResponse)
        assert response.content == "Test completion"
        assert response.tokens_in == 10
        assert response.tokens_out == 20
        assert response.model == "test-model"

    @pytest.mark.asyncio
    async def test_call_llm_passes_all_parameters(self):
        """_call_llm passes all parameters to complete_async."""
        fake_provider = FakeLLMProvider()
        orchestrator = ConcreteOrchestrator(llm_provider=fake_provider)

        await orchestrator._call_llm(
            system_prompt="system context",
            user_prompt="user message",
            model="specific-model",
            temperature=0.7,
            max_tokens=500,
        )

        # Verify the fake provider recorded the call
        assert fake_provider.call_count == 1
        assert fake_provider.last_call_args["system_prompt"] == "system context"
        assert fake_provider.last_call_args["user_prompt"] == "user message"
        assert fake_provider.last_call_args["model"] == "specific-model"
        assert fake_provider.last_call_args["temperature"] == 0.7
        assert fake_provider.last_call_args["max_tokens"] == 500
