"""
Domain entities for the pipeline bounded context.

Entities represent LLM pipeline configurations and their executions.
They import only from Python stdlib.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field
from typing import Optional

from domain.pipeline.enums import PipelineType, ExecutionStatus


@dataclass
class PipelineConfiguration:
    """
    Represents a reusable LLM pipeline configuration.

    Attributes:
        id: Unique identifier for this pipeline configuration.
        name: Human-readable name of the pipeline.
        description: Optional description of what the pipeline does.
        pipeline_type: The type of pipeline (extraction, classification, etc.).
        model_name: Name of the LLM model to use.
        prompt_template: The prompt template for the LLM.
        parameters: Additional parameters for the pipeline (read-only).
        created_at: ISO 8601 timestamp of creation.
        updated_at: ISO 8601 timestamp of last update.
    """

    id: str
    name: str
    description: Optional[str]
    pipeline_type: PipelineType
    model_name: str
    prompt_template: str
    parameters: types.MappingProxyType = field(
        default_factory=lambda: types.MappingProxyType({})
    )
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        """Validate pipeline configuration invariants."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Pipeline configuration id must be a non-empty string")
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Pipeline configuration name must be a non-empty string")
        if not self.model_name or not isinstance(self.model_name, str):
            raise ValueError(
                "Pipeline configuration model_name must be a non-empty string"
            )
        if not self.prompt_template or not isinstance(self.prompt_template, str):
            raise ValueError(
                "Pipeline configuration prompt_template must be a non-empty string"
            )
        if not isinstance(self.pipeline_type, PipelineType):
            raise TypeError(
                f"pipeline_type must be a PipelineType enum, got {type(self.pipeline_type).__name__}"
            )
        if self.created_at and not isinstance(self.created_at, str):
            raise TypeError("created_at must be a string timestamp")
        if self.updated_at and not isinstance(self.updated_at, str):
            raise TypeError("updated_at must be a string timestamp")
        if not isinstance(self.parameters, types.MappingProxyType):
            raise TypeError("parameters must be a MappingProxyType (immutable mapping)")


@dataclass
class Execution:
    """
    Represents a single execution of a pipeline.

    Attributes:
        id: Unique identifier for this execution.
        pipeline_id: ID of the pipeline configuration that was executed.
        status: Current status of the execution (pending, running, completed, failed).
        input_data: Input data provided to the pipeline (read-only).
        output_data: Output data produced by the pipeline (read-only, only set when completed).
        error_message: Optional error message if the execution failed.
        created_at: ISO 8601 timestamp of execution start.
        completed_at: ISO 8601 timestamp of execution completion.
    """

    id: str
    pipeline_id: str
    status: ExecutionStatus
    input_data: types.MappingProxyType
    output_data: Optional[types.MappingProxyType] = None
    error_message: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate execution invariants."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Execution id must be a non-empty string")
        if not self.pipeline_id or not isinstance(self.pipeline_id, str):
            raise ValueError("Execution pipeline_id must be a non-empty string")
        if not isinstance(self.status, ExecutionStatus):
            raise TypeError(
                f"status must be an ExecutionStatus enum, got {type(self.status).__name__}"
            )
        if not isinstance(self.input_data, types.MappingProxyType):
            raise TypeError("input_data must be a MappingProxyType (immutable mapping)")
        if self.output_data is not None and not isinstance(
            self.output_data, types.MappingProxyType
        ):
            raise TypeError(
                "output_data must be None or MappingProxyType (immutable mapping)"
            )
        if not self.created_at or not isinstance(self.created_at, str):
            raise ValueError(
                "Execution created_at must be a non-empty timestamp string"
            )
        if self.completed_at is not None and not isinstance(self.completed_at, str):
            raise TypeError("Execution completed_at must be None or a timestamp string")
        if self.error_message is not None and not isinstance(self.error_message, str):
            raise TypeError("error_message must be None or a string")
