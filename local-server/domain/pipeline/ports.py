"""
Port interfaces (protocols) for the LLM Pipeline Management bounded context.

PipelineRepository defines the contract for persisting and retrieving pipeline
configurations and execution records. Using typing.Protocol enables structural
subtyping — implementations do not explicitly inherit from these protocols.

LLMProvider is a driven port for language model completion and introspection,
shared across pipeline and extraction bounded contexts as a cross-context dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .entities import Execution, PipelineConfiguration, PipelineFlavor

# ============================================================================
# Value types used in port contracts
# ============================================================================


@dataclass(frozen=True)
class ExecutionWithTitle:
    """Pairs an execution with its pipeline title."""

    execution: Execution
    pipeline_title: str


@dataclass(frozen=True)
class LLMResponse:
    """
    Response from an LLM completion request.

    Attributes:
        content: The generated text response
        tokens_in: Count of input tokens consumed
        tokens_out: Count of output tokens generated
        duration_ms: Time spent processing the request in milliseconds
        finish_reason: Reason the model stopped (e.g., 'stop', 'length')
        model: Name of the model that generated the response
    """

    content: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str
    model: str


# ============================================================================
# Port interfaces (Protocols)
# ============================================================================


class LLMProvider(Protocol):
    """
    Port for LLM completion and model introspection.

    Implementations provide access to language models for text generation
    and information about available models. This port is used by both
    the extraction and pipeline bounded contexts.
    """

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier
            temperature: Sampling temperature (0.0–2.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional response format ("json" for JSON output, "text" for plain
            text)
            timeout: Request timeout in seconds (provider-specific behavior)
            seed: Optional random seed for reproducible generation (passed to model if supported)

        Returns:
            LLMResponse with generated content and metadata
        """
        ...

    def is_model_available(self, model: str) -> bool:
        """
        Check if a specific model is available.

        Args:
            model: Model identifier

        Returns:
            True if the model can be used, False otherwise
        """
        ...

    def list_available_models(self) -> list[str]:
        """
        Get list of available model identifiers.

        Returns:
            List of model names that can be used with complete()
        """
        ...


class PipelineRepository(Protocol):
    """
    Port for persisting and retrieving pipeline configurations and executions.

    The PipelineRepository handles all data access for pipeline management,
    including configuration lifecycle (CRUD) and execution history tracking.
    """

    def get_config(self, config_id: str) -> PipelineConfiguration | None:
        """
        Retrieve a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration

        Returns:
            PipelineConfiguration if found, None otherwise
        """
        ...

    def list_configs(self, enabled_only: bool = False) -> list[PipelineConfiguration]:
        """
        List all pipeline configurations.

        Args:
            enabled_only: If True, return only enabled configurations (default False)

        Returns:
            List of PipelineConfiguration objects
        """
        ...

    def save_config(self, config: PipelineConfiguration) -> PipelineConfiguration:
        """
        Create or update a pipeline configuration.

        If the configuration's ID already exists, it is updated.
        Otherwise, a new configuration is created.

        Args:
            config: PipelineConfiguration to save

        Returns:
            The saved PipelineConfiguration
        """
        ...

    def delete_config(self, config_id: str) -> bool:
        """
        Delete a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration to delete

        Returns:
            True if deletion was successful, False if configuration was not found
        """
        ...

    def record_execution(self, execution: Execution) -> Execution:
        """
        Record a pipeline execution.

        Args:
            execution: Execution record to store

        Returns:
            The recorded Execution
        """
        ...

    def get_executions(self, pipeline_config_id: str, limit: int = 50) -> list[Execution]:
        """
        Retrieve execution history for a pipeline configuration.

        Results are returned in reverse chronological order (most recent first).

        Args:
            pipeline_config_id: ID of the pipeline configuration
            limit: Maximum number of execution records to return (default 50)

        Returns:
            List of Execution objects, up to limit
        """
        ...

    def get_all_executions(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ExecutionWithTitle], int]:
        """
        Retrieve execution history across all pipeline configurations.

        Results are returned in reverse chronological order (most recent first).

        Args:
            status: Optional status filter ("success", "error", "timeout")
            limit: Maximum number of execution records to return (1-500, default 100)
            offset: Number of execution records to skip for pagination (default 0)

        Returns:
            Tuple of (list of ExecutionWithTitle objects, total count of executions matching filter)
        """
        ...


class FlavorRepository(Protocol):
    """
    Port for persisting and retrieving pipeline flavor templates.

    Flavors are reusable templates for creating pipeline configurations.
    """

    def get_flavor(self, flavor_id: str) -> PipelineFlavor | None:
        """
        Retrieve a pipeline flavor by ID.

        Args:
            flavor_id: Unique identifier of the flavor

        Returns:
            PipelineFlavor if found, None otherwise
        """
        ...

    def list_flavors(self) -> list[PipelineFlavor]:
        """
        List all pipeline flavors.

        Returns:
            List of PipelineFlavor objects
        """
        ...

    def save_flavor(self, flavor: PipelineFlavor) -> PipelineFlavor:
        """
        Create or update a pipeline flavor.

        If the flavor's ID already exists, it is updated.
        Otherwise, a new flavor is created.

        Args:
            flavor: PipelineFlavor to save

        Returns:
            The saved PipelineFlavor
        """
        ...

    def delete_flavor(self, flavor_id: str) -> bool:
        """
        Delete a pipeline flavor by ID.

        Args:
            flavor_id: Unique identifier of the flavor to delete

        Returns:
            True if deletion was successful, False if flavor was not found
        """
        ...
