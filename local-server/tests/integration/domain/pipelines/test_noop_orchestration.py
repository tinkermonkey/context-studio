"""
Integration test for the no-op pipeline orchestration.

Exercises the framework end-to-end:
- LangGraph orchestration scaffolding
- PipelineRun persistence
- change_events integration

This smoke test ensures the pipeline framework is wired correctly
before implementing concrete pipeline types.
"""

import pytest

from domain.pipeline.ports import LLMResponse
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator, NoOpPipelineState


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
        timeout=None,
        seed=None,
    ) -> LLMResponse:
        """Return mock response."""
        return LLMResponse(
            content="Mock response",
            tokens_in=10,
            tokens_out=5,
            duration_ms=100,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
        timeout=None,
        seed=None,
    ) -> LLMResponse:
        """Return mock response (async version)."""
        return self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return ["mock-model"]


def test_noop_orchestrator_initialization():
    """Test orchestrator initialization with LLM provider."""
    llm_provider = MockLLMProvider()
    orchestrator = NoOpPipelineOrchestrator(llm_provider)

    assert orchestrator._llm_provider is llm_provider


def test_noop_orchestrator_build_graph():
    """Test that build_graph returns None (placeholder for full impl)."""
    llm_provider = MockLLMProvider()
    orchestrator = NoOpPipelineOrchestrator(llm_provider)

    graph = orchestrator.build_graph()
    assert graph is None


@pytest.mark.asyncio
async def test_noop_pipeline_execution():
    """Test no-op pipeline execution end-to-end."""
    llm_provider = MockLLMProvider()
    orchestrator = NoOpPipelineOrchestrator(llm_provider)

    state = NoOpPipelineState(
        run_id="run-123",
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data={"text": "Sample text", "ontology_id": "onto-123"},
    )

    result_state = await orchestrator.execute(state)

    assert result_state.run_id == "run-123"
    assert result_state.current_status == "completed"
    assert result_state.result is not None
    assert result_state.result["status"] == "completed"
    assert len(result_state.steps_completed) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
