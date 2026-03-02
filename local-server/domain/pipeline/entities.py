"""
Domain entities for the pipeline bounded context.

Entities represent LLM pipeline configurations and their executions.
They import only from Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineConfiguration:
    """
    Represents a reusable LLM pipeline configuration.

    Attributes:
        id: Unique identifier for this pipeline configuration.
        name: Human-readable name of the pipeline.
        description: Optional description of what the pipeline does.
        pipeline_type: The type of pipeline (e.g., "extraction", "classification").
        model_name: Name of the LLM model to use.
        prompt_template: The prompt template for the LLM.
        parameters: Additional parameters for the pipeline (as a dict).
        created_at: ISO 8601 timestamp of creation.
        updated_at: ISO 8601 timestamp of last update.
    """

    id: str
    name: str
    description: Optional[str]
    pipeline_type: str
    model_name: str
    prompt_template: str
    parameters: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Execution:
    """
    Represents a single execution of a pipeline.

    Attributes:
        id: Unique identifier for this execution.
        pipeline_id: ID of the pipeline configuration that was executed.
        status: Current status of the execution (e.g., "pending", "running", "completed", "failed").
        input_data: Input data provided to the pipeline.
        output_data: Output data produced by the pipeline (only set when completed).
        error_message: Optional error message if the execution failed.
        created_at: ISO 8601 timestamp of execution start.
        completed_at: ISO 8601 timestamp of execution completion.
    """

    id: str
    pipeline_id: str
    status: str
    input_data: dict
    output_data: Optional[dict]
    error_message: Optional[str]
    created_at: str
    completed_at: Optional[str]
