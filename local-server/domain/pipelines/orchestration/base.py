"""
Base classes for pipeline orchestration.

Provides scaffolding that per-type implementations subclass to define their
execution flow. Concrete shapes are decided per-implementation;
this module provides the structure only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.ports import LLMProvider, LLMResponse, PipelineRunStatusWriter
from domain.pipelines.selection import RUN_PARAMETERS
from domain.pipelines.stage_prompts import StageDefinition

MODEL_REQUIRED = "model is required: the run's configuration names none, nor does its input"


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
        llm_metadata: Model, cost and latency of the run's model calls, recorded on the run
    """

    run_id: str
    pipeline_type: PipelineType
    input_data: dict[str, Any]
    current_status: PipelineRunStatus = PipelineRunStatus.PENDING
    llm_provider: LLMProvider | None = None
    result: dict[str, Any] | None = None
    parse_warnings: list[dict[str, Any]] = field(default_factory=list)
    llm_metadata: dict[str, Any] = field(default_factory=dict)


def run_model(*named: Any) -> str:
    """
    The model a run's LLM calls use: the first one named, in the order given
    (what the caller passed, the run's input, the run's configuration). A run
    started through PipelineResolver always has its configuration's.

    Raises:
        PipelineInputError: If none is named; orchestrators have no model of their own
    """
    for model in named:
        if model:
            return str(model)
    raise PipelineInputError(MODEL_REQUIRED)


def llm_parameters(
    input_data: Mapping[str, Any],
    config: Mapping[str, Any] | None,
    stage_max_tokens: int | None = None,
) -> dict[str, Any]:
    """
    The model, temperature and output-token limit of a run's LLM call, by the
    one rule every orchestrator follows: what the run's input names, then what
    the configuration the orchestrator was built with names. A run started
    through PipelineResolver carries its configuration's values in its input,
    so the second only matters to a caller that built the orchestrator itself.
    A call with no limit named gets its stage's own.

    Args:
        input_data: The run's input
        config: The configuration the orchestrator was built with, if any
        stage_max_tokens: The stage's own output-token limit

    Returns:
        ``model``, ``temperature`` and ``max_tokens`` (None when no limit is
        named and the stage has none of its own), as _call_llm takes them

    Raises:
        PipelineInputError: If no model is named
    """
    config = config or {}
    temperature = input_data.get("temperature")
    if temperature is None:
        temperature = config.get("temperature")
    return {
        "model": run_model(input_data.get("model"), config.get("model")),
        "temperature": 0.0 if temperature is None else temperature,
        "max_tokens": input_data.get("max_tokens") or config.get("max_tokens") or stage_max_tokens,
    }


def implementation_settings(config: Mapping[str, Any]) -> dict[str, Any]:
    """
    A configuration's settings other than the run parameters (model,
    temperature, output-token limit): what an orchestrator built with no
    configuration may take from its implementation's default one. Never a
    model: a run's model is its configuration's or its input's.
    """
    return {key: value for key, value in config.items() if key not in RUN_PARAMETERS}


class PipelineOrchestrator(ABC):
    """
    Abstract base for pipeline orchestration implementations.

    Subclasses define the execution flow for their pipeline type
    and implement the execute method.
    """

    # The LLM stages whose prompts a configuration can override (see
    # domain/pipelines/stage_prompts.py); empty for pipelines without them.
    STAGE_PROMPTS: tuple[StageDefinition, ...] = ()

    # Whether it can extract a source: read it chunk by chunk and end in one
    # change proposal (see domain/pipelines/source_extraction.py).
    EXTRACTS_SOURCES: bool = False

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
    ) -> None:
        """
        Initialize orchestrator with LLM provider and optional status writer.

        Args:
            llm_provider: Port implementation for LLM completions (optional for
                pipelines that don't use LLM)
            run_id: Pipeline run ID for writing RUNNING status
            status_writer: Optional port for writing run status to persistence
        """
        self._llm_provider = llm_provider
        self._run_id = run_id
        self._status_writer = status_writer

    def build_graph(self) -> None:
        """
        Return the compiled LangGraph for this orchestrator.

        Override in concrete implementations. Returns None in the base class
        and in orchestrators that do not use a pre-compiled graph.
        """
        return None

    def _write_running_status(self) -> None:
        """
        Write RUNNING status to persistence.

        This should be called at the start of execute() to ensure that the
        orchestrator—not the caller—is responsible for marking the run as RUNNING.
        This ensures that the status is written regardless of how the orchestrator
        is invoked (HTTP route, background worker, batch runner, etc.).

        Only writes if both run_id and status_writer are available.
        """
        if self._run_id and self._status_writer:
            self._status_writer.update_running_status(self._run_id, datetime.now(timezone.utc))

    def _report_progress(self, items_done: int, items_total: int | None) -> None:
        """
        Record progress on the run: items_done of items_total work items.

        Only writes if both run_id and status_writer are available.
        """
        if self._run_id and self._status_writer:
            self._status_writer.update_progress(self._run_id, items_done, items_total)

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
        response_format: Literal["json", "text"] | None = None,
    ) -> LLMResponse:
        """
        Helper to call the LLM provider asynchronously.

        Args:
            system_prompt: System context
            user_prompt: User message
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            response_format: Optional output format hint ("json" requests a JSON object)

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
            response_format=response_format,
        )
