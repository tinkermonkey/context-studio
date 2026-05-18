"""
Domain entities for the LLM Pipeline Management bounded context.

PipelineConfiguration and Execution represent the core aggregates for managing
LLM pipeline configurations and tracking execution records with complete
instrumentation (tokens, duration, status).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
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
        seed: Optional random seed for reproducible generation (passed to model if supported)

    Raises:
        ValueError: If provider is not "openai" or "anthropic", or if version < 1
    """

    id: str
    pipeline: str
    title: str
    provider: Literal["openai", "anthropic"]
    model: str
    config: dict
    system_prompt: str
    user_prompt: str
    version: int
    enabled: bool
    created_at: datetime
    last_updated: datetime
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate pipeline configuration invariants."""
        if self.provider not in ("openai", "anthropic"):
            raise ValueError(f"provider must be 'openai' or 'anthropic', got '{self.provider}'")
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")
        if self.seed is not None and self.seed < 0:
            raise ValueError(f"seed must be non-negative if provided, got {self.seed}")


@dataclass(frozen=True)
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
        error_message: Error description if status is "error" or "timeout", None otherwise
        timestamp: When the execution occurred

    Raises:
        ValueError: If status is invalid, tokens/duration are negative, or error_message validation fails
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
    status: Literal["success", "error", "timeout"]
    error_message: str | None
    timestamp: datetime

    def __post_init__(self) -> None:
        """Validate execution invariants."""
        if self.status not in ("success", "error", "timeout"):
            raise ValueError(
                f"status must be 'success', 'error', or 'timeout', got '{self.status}'"
            )
        if self.tokens_in < 0:
            raise ValueError(f"tokens_in must be non-negative, got {self.tokens_in}")
        if self.tokens_out < 0:
            raise ValueError(f"tokens_out must be non-negative, got {self.tokens_out}")
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms must be non-negative, got {self.duration_ms}")
        if self.status == "error" and not self.error_message:
            raise ValueError("error_message must be set when status is 'error'")


@dataclass(frozen=True)
class PipelineFlavor:
    """
    Reusable template for creating pipeline configurations.

    A flavor is a parameterized blueprint that can be instantiated into
    multiple pipeline configurations, allowing users to create common
    configurations from predefined templates.

    Attributes:
        id: Unique identifier (UUID string)
        name: Human-readable name for the flavor
        description: Description of what this flavor is for
        steps: List of configuration step dicts defining the template
        created_at: Timestamp when this flavor was created
        last_updated: Timestamp of the most recent update

    Raises:
        ValueError: If name is empty or steps is not a list
    """

    id: str
    name: str
    description: str
    steps: list[dict]
    created_at: datetime
    last_updated: datetime

    def __post_init__(self) -> None:
        """Validate flavor invariants."""
        if not self.name or not self.name.strip():
            raise ValueError("name cannot be empty")
        if not isinstance(self.steps, list):
            raise ValueError("steps must be a list of dicts")

    @property
    def step_count(self) -> int:
        """Return the number of steps in this flavor."""
        return len(self.steps)
