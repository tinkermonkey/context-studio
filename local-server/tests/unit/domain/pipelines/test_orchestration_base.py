"""
Unit tests for pipeline orchestration base class.

Tests verify:
- _call_llm() awaits complete_async on the LLM provider
- Error handling when LLM provider is not initialized
- _write_running_status() calls status writer with correct parameters
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import LLMResponse, PipelineRunStatusWriter
from tests.fakes.fake_llm_provider import FakeLLMProvider


class ConcreteOrchestrator(PipelineOrchestrator):
    """Concrete implementation of PipelineOrchestrator for testing."""

    def build_graph(self):
        """Return a dummy graph for testing."""
        return None

    async def execute(self, state: PipelineState) -> PipelineState:
        """Dummy execute method for testing."""
        self._write_running_status()
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


class TestWriteRunningStatus:
    """Tests for PipelineOrchestrator._write_running_status() method."""

    @pytest.mark.asyncio
    async def test_write_running_status_calls_writer_with_correct_params(self):
        """_write_running_status calls status writer with run_id and UTC timestamp."""
        mock_writer = Mock(spec=PipelineRunStatusWriter)
        mock_writer.update_running_status.return_value = True
        fake_provider = FakeLLMProvider()

        orchestrator = ConcreteOrchestrator(
            llm_provider=fake_provider,
            run_id="test-run-123",
            status_writer=mock_writer,
        )

        state = PipelineState(
            run_id="test-run-123",
            pipeline_type="individual_extraction",
            input_data={"text": "test"},
        )

        await orchestrator.execute(state)

        # Verify update_running_status was called once
        assert mock_writer.update_running_status.call_count == 1

        # Verify the run_id parameter
        call_args = mock_writer.update_running_status.call_args
        assert call_args[0][0] == "test-run-123"

        # Verify the timestamp is a UTC datetime
        timestamp = call_args[0][1]
        assert isinstance(timestamp, datetime)
        assert timestamp.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_write_running_status_not_called_without_writer(self):
        """_write_running_status is no-op when status_writer is None."""
        fake_provider = FakeLLMProvider()
        orchestrator = ConcreteOrchestrator(
            llm_provider=fake_provider,
            run_id="test-run-123",
            status_writer=None,
        )

        state = PipelineState(
            run_id="test-run-123",
            pipeline_type="individual_extraction",
            input_data={"text": "test"},
        )

        # Should not raise an error even without a status writer
        result = await orchestrator.execute(state)
        assert result is not None

    @pytest.mark.asyncio
    async def test_write_running_status_not_called_without_run_id(self):
        """_write_running_status is no-op when run_id is None."""
        mock_writer = Mock(spec=PipelineRunStatusWriter)
        fake_provider = FakeLLMProvider()

        orchestrator = ConcreteOrchestrator(
            llm_provider=fake_provider,
            run_id=None,
            status_writer=mock_writer,
        )

        state = PipelineState(
            run_id="state-run-id",
            pipeline_type="individual_extraction",
            input_data={"text": "test"},
        )

        await orchestrator.execute(state)

        # update_running_status should not be called
        assert mock_writer.update_running_status.call_count == 0
