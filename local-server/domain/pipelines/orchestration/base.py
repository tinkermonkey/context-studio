"""
Base classes for pipeline orchestration.

Provides scaffolding that per-type implementations subclass to define their
execution flow. Concrete shapes are decided per-implementation;
this module provides the structure only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from domain.pipeline.ports import LLMProvider, LLMResponse
from domain.pipelines.entities import PipelineRunStatus, PipelineType


@dataclass
class PipelineState:
    """
    State for a pipeline execution.

    Represents the state object passed through pipeline execution stages.
    Subclasses extend with type-specific state fields.

    Attributes:
        run_id: The PipelineRun ID
        pipeline_type: Type of pipeline
        input_data: Input to the pipeline
        current_status: Current execution status
        llm_provider: Injected LLM provider for completions
        result: Accumulated result (populated as execution progresses)
        parse_warnings: List of parse/validation warnings encountered during execution
    """

    run_id: str
    pipeline_type: PipelineType
    input_data: dict[str, Any]
    current_status: PipelineRunStatus = PipelineRunStatus.PENDING
    llm_provider: LLMProvider | None = None
    result: dict[str, Any] | None = None
    parse_warnings: list[dict[str, Any]] = field(default_factory=list)


class PipelineOrchestrator(ABC):
    """
    Abstract base for pipeline orchestration implementations.

    Subclasses define the execution flow for their pipeline type
    and implement the execute method.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        """
        Initialize orchestrator with LLM provider.

        Args:
            llm_provider: Port implementation for LLM completions
        """
        self._llm_provider = llm_provider

    @abstractmethod
    def build_graph(self) -> Any:
        """
        Build and return the pipeline execution graph.

        Returns:
            Pipeline execution graph (implementation-specific)
        """
        ...

    @abstractmethod
    async def execute(self, state: PipelineState) -> PipelineState:
        """
        Execute the pipeline with the given state.

        Args:
            state: Initial PipelineState

        Returns:
            Updated PipelineState with result populated
        """
        ...

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Helper to call the LLM provider asynchronously.

        Args:
            system_prompt: System context
            user_prompt: User message
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum output tokens

        Returns:
            LLMResponse with generated content and metadata
        """
        if not self._llm_provider:
            raise RuntimeError("LLM provider not initialized")
        return await self._llm_provider.complete_async(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
