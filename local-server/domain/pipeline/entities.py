"""
Domain entities for the LLM Pipeline Management bounded context.

PipelineConfiguration and Execution represent the core aggregates for managing
LLM pipeline configurations and tracking execution records with complete
instrumentation (tokens, duration, status).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PipelineConfiguration:
    """
    Configuration for an LLM pipeline.

    A pipeline configuration defines how to invoke an LLM, including the model,
    provider, prompts, and runtime settings.

    Attributes:
        id: Unique identifier (UUID string)
        pipeline: Pipeline identifier/slug for categorization
        title: Human-readable title for the pipeline
        provider: LLM provider name ("openai" | "anthropic")
        model: Model identifier (e.g., "gpt-4", "claude-opus")
        config: Provider-specific configuration (timeout, temperature, etc.)
        system_prompt: System prompt to guide the model behavior
        user_prompt: User message template with {text} placeholder
        version: Configuration version number for tracking changes
        enabled: Whether this configuration is active
        created_at: Timestamp when this configuration was created
        last_updated: Timestamp of the most recent update
    """

    id: str
    pipeline: str
    title: str
    provider: str
    model: str
    config: dict
    system_prompt: str
    user_prompt: str
    version: int
    enabled: bool
    created_at: datetime
    last_updated: datetime


@dataclass
class Execution:
    """
    Record of a single LLM pipeline execution.

    Each execution captures the input, output, resource consumption (tokens),
    execution time, and completion status of an LLM invocation.

    Attributes:
        id: Unique identifier (UUID string)
        pipeline_config_id: ID of the PipelineConfiguration that was executed
        input_text: The text provided to the LLM
        output_text: The generated response from the LLM
        provider: LLM provider that executed the request
        model: Model that generated the response
        tokens_in: Number of tokens in the input
        tokens_out: Number of tokens in the output
        duration_ms: Execution duration in milliseconds
        status: Completion status ("success" | "error" | "timeout")
        error_message: Error description if status is "error", None otherwise
        timestamp: When the execution occurred
    """

    id: str
    pipeline_config_id: str
    input_text: str
    output_text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: int
    status: str
    error_message: str | None
    timestamp: datetime
