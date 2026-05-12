"""
Domain service for LLM pipeline management.

PipelineService orchestrates pipeline configuration lifecycle and execution
tracking. It depends on PipelineRepository (for persistence), LLMProvider
(for model invocation), and EventPublisher (for event-driven workflows).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import cast, Literal
from uuid import uuid4

from domain.ports import EventPublisher
from .entities import Execution, PipelineConfiguration, PipelineFlavor
from .ports import PipelineRepository, LLMProvider, ExecutionWithTitle, FlavorRepository
from .events import PipelineExecuted
from .exceptions import PipelineNotFoundError

_logger = logging.getLogger(__name__)

_UNSET = object()


class PipelineService:
    """
    Domain service for managing LLM pipeline configurations and executions.

    The service orchestrates:
    - Configuration lifecycle (create, read, update, delete)
    - Pipeline execution with complete instrumentation (tokens, duration, status)
    - Event publishing for all execution completions
    - Timeout handling for long-running LLM calls
    """

    def __init__(
        self,
        pipeline_repo: PipelineRepository,
        flavor_repo: FlavorRepository,
        llm: LLMProvider,
        event_publisher: EventPublisher,
    ) -> None:
        """
        Initialize the pipeline service.

        Args:
            pipeline_repo: Port for persisting pipeline configurations and executions
            flavor_repo: Port for persisting pipeline flavor templates
            llm: Port for invoking LLM models
            event_publisher: Port for publishing domain events
        """
        self._pipeline_repo = pipeline_repo
        self._flavor_repo = flavor_repo
        self._llm = llm
        self._event_publisher = event_publisher

    def create_config(
        self,
        pipeline: str,
        title: str,
        provider: str,
        model: str,
        config: dict,
        system_prompt: str,
        user_prompt: str,
        enabled: bool = True,
    ) -> PipelineConfiguration:
        """
        Create a new pipeline configuration.

        Args:
            pipeline: Pipeline identifier/slug
            title: Human-readable title
            provider: LLM provider name
            model: Model identifier
            config: Provider-specific configuration
            system_prompt: System prompt for the model
            user_prompt: User message template with {text} placeholder
            enabled: Whether this configuration is active (default True)

        Returns:
            The created PipelineConfiguration
        """
        now = datetime.now(timezone.utc)
        config_obj = PipelineConfiguration(
            id=str(uuid4()),
            pipeline=pipeline,
            title=title,
            provider=cast(Literal["openai", "anthropic"], provider),
            model=model,
            config=config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            version=1,
            enabled=enabled,
            created_at=now,
            last_updated=now,
        )
        return self._pipeline_repo.save_config(config_obj)

    def get_config(self, config_id: str) -> PipelineConfiguration:
        """
        Retrieve a pipeline configuration by ID.

        Args:
            config_id: Configuration ID

        Returns:
            PipelineConfiguration

        Raises:
            PipelineNotFoundError: If configuration not found
        """
        config = self._pipeline_repo.get_config(config_id)
        if config is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")
        return config

    def list_configs(self, enabled_only: bool = False) -> list[PipelineConfiguration]:
        """
        List pipeline configurations.

        Args:
            enabled_only: If True, return only enabled configurations

        Returns:
            List of PipelineConfiguration objects
        """
        return self._pipeline_repo.list_configs(enabled_only=enabled_only)

    def update_config(
        self,
        config_id: str,
        title: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        config: dict | None = None,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        enabled: bool | None = None,
        seed: int | None = _UNSET,  # type: ignore
    ) -> PipelineConfiguration:
        """
        Update a pipeline configuration.

        Args:
            config_id: Configuration ID
            title: Updated title (optional)
            provider: Updated provider (optional)
            model: Updated model (optional)
            config: Updated config dict (optional)
            system_prompt: Updated system prompt (optional)
            user_prompt: Updated user prompt (optional)
            enabled: Updated enabled status (optional)
            seed: Updated random seed (optional); pass None to clear, omit to preserve existing

        Returns:
            The updated PipelineConfiguration

        Raises:
            PipelineNotFoundError: If configuration not found
        """
        existing = self._pipeline_repo.get_config(config_id)
        if existing is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")

        # Resolve seed: use existing value if not explicitly provided
        resolved_seed: int | None
        if seed is _UNSET:
            resolved_seed = existing.seed
        else:
            resolved_seed = seed

        # Create updated config by copying and applying changes
        updated = PipelineConfiguration(
            id=existing.id,
            pipeline=existing.pipeline,
            title=title if title is not None else existing.title,
            provider=cast(Literal["openai", "anthropic"], provider if provider is not None else existing.provider),
            model=model if model is not None else existing.model,
            config=config if config is not None else existing.config,
            system_prompt=(
                system_prompt if system_prompt is not None else existing.system_prompt
            ),
            user_prompt=(
                user_prompt if user_prompt is not None else existing.user_prompt
            ),
            version=existing.version + 1,
            enabled=enabled if enabled is not None else existing.enabled,
            created_at=existing.created_at,
            last_updated=datetime.now(timezone.utc),
            seed=resolved_seed,
        )
        return self._pipeline_repo.save_config(updated)

    def delete_config(self, config_id: str) -> None:
        """
        Delete a pipeline configuration.

        Args:
            config_id: Configuration ID

        Raises:
            PipelineNotFoundError: If configuration not found
        """
        config = self._pipeline_repo.get_config(config_id)
        if config is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")
        self._pipeline_repo.delete_config(config_id)

    def list_executions(self, config_id: str, limit: int = 50) -> list[Execution]:
        """
        Retrieve execution history for a pipeline configuration.

        Results are returned in reverse chronological order (most recent first).

        Args:
            config_id: Configuration ID
            limit: Maximum number of executions to return (default 50)

        Returns:
            List of Execution objects, up to the specified limit

        Raises:
            PipelineNotFoundError: If configuration not found
        """
        config = self._pipeline_repo.get_config(config_id)
        if config is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")
        return self._pipeline_repo.get_executions(config_id, limit=limit)

    def list_all_executions(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ExecutionWithTitle], int]:
        """
        Retrieve all pipeline executions across all configurations.

        Results are returned in reverse chronological order (most recent first).

        Args:
            status: Optional status filter ("success", "error", "timeout").
                    If None, returns all executions regardless of status.
            limit: Maximum number of executions to return (default 100)
            offset: Number of executions to skip for pagination (default 0)

        Returns:
            Tuple of (list of ExecutionWithTitle objects, total count)
        """
        return self._pipeline_repo.get_all_executions(
            status=status, limit=limit, offset=offset
        )

    def execute_pipeline(self, config_id: str, input_text: str) -> Execution:
        """
        Execute a pipeline configuration with the given input.

        Records a complete execution record including tokens, duration, and status.
        Handles timeouts by recording an execution with status="timeout".
        Publishes a PipelineExecuted event on completion.

        Args:
            config_id: Configuration ID to execute
            input_text: Input text to process

        Returns:
            The recorded Execution

        Raises:
            PipelineNotFoundError: If configuration not found
        """
        config = self._pipeline_repo.get_config(config_id)
        if config is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")

        execution_id = str(uuid4())
        start_time = time.time()

        # Prepare the user prompt by replacing the placeholder
        user_message = config.user_prompt.replace("{text}", input_text)

        # Get timeout from config, default to 30 seconds
        timeout = config.config.get("timeout", 30)

        try:
            # Call the LLM with timeout handling
            response = self._llm.complete(
                system_prompt=config.system_prompt,
                user_prompt=user_message,
                model=config.model,
                temperature=config.config.get("temperature", 0.0),
                max_tokens=config.config.get("max_tokens", 2000),
                response_format=config.config.get("response_format"),
                timeout=timeout,
                seed=config.seed,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Record successful execution
            execution = Execution(
                id=execution_id,
                pipeline_config_id=config_id,
                input_text=input_text,
                output_text=response.content,
                provider=config.provider,
                model=response.model,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                duration_ms=duration_ms,
                status="success",
                error_message=None,
                timestamp=datetime.now(timezone.utc),
            )

        except TimeoutError as e:
            # Record timeout execution
            duration_ms = int((time.time() - start_time) * 1000)
            execution = Execution(
                id=execution_id,
                pipeline_config_id=config_id,
                input_text=input_text,
                output_text="",
                provider=config.provider,
                model=config.model,
                tokens_in=0,
                tokens_out=0,
                duration_ms=duration_ms,
                status="timeout",
                error_message=str(e),
                timestamp=datetime.now(timezone.utc),
            )
        except (ValueError, RuntimeError, TypeError, KeyError) as e:
            # Record error execution for expected application-level errors
            # Excludes system errors (MemoryError, SystemError, etc.) and KeyboardInterrupt
            duration_ms = int((time.time() - start_time) * 1000)
            execution = Execution(
                id=execution_id,
                pipeline_config_id=config_id,
                input_text=input_text,
                output_text="",
                provider=config.provider,
                model=config.model,
                tokens_in=0,
                tokens_out=0,
                duration_ms=duration_ms,
                status="error",
                error_message=str(e),
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            # Record error execution for all remaining application errors
            # (e.g. ConnectionError, httpx.HTTPError, network timeouts, provider API errors)
            # System errors (KeyboardInterrupt, SystemExit) propagate for observability
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            duration_ms = int((time.time() - start_time) * 1000)
            execution = Execution(
                id=execution_id,
                pipeline_config_id=config_id,
                input_text=input_text,
                output_text="",
                provider=config.provider,
                model=config.model,
                tokens_in=0,
                tokens_out=0,
                duration_ms=duration_ms,
                status="error",
                error_message=str(e),
                timestamp=datetime.now(timezone.utc),
            )

        # Record the execution
        recorded_execution = self._pipeline_repo.record_execution(execution)

        # Publish completion event
        event = PipelineExecuted(
            execution_id=recorded_execution.id,
            pipeline_id=config_id,
            status=recorded_execution.status,
        )
        failures = self._event_publisher.publish(event)
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for PipelineExecuted (execution_id=%s): %s. "
                "Pipeline execution is recorded but audit trail may have gaps.",
                recorded_execution.id,
                handler_names,
            )

        return recorded_execution

    def create_flavor(
        self,
        name: str,
        description: str,
        steps: list[dict],
    ) -> PipelineFlavor:
        """
        Create a new pipeline flavor.

        Args:
            name: Human-readable name for the flavor
            description: Description of the flavor
            steps: List of step definitions

        Returns:
            The created PipelineFlavor
        """
        now = datetime.now(timezone.utc)
        flavor = PipelineFlavor(
            id=str(uuid4()),
            name=name,
            description=description,
            steps=steps,
            created_at=now,
            last_updated=now,
        )
        return self._flavor_repo.save_flavor(flavor)

    def get_flavor(self, flavor_id: str) -> PipelineFlavor:
        """
        Retrieve a pipeline flavor by ID.

        Args:
            flavor_id: Flavor ID

        Returns:
            PipelineFlavor

        Raises:
            PipelineNotFoundError: If flavor not found
        """
        flavor = self._flavor_repo.get_flavor(flavor_id)
        if flavor is None:
            raise PipelineNotFoundError(f"Pipeline flavor {flavor_id} not found")
        return flavor

    def list_flavors(self) -> list[PipelineFlavor]:
        """
        List all pipeline flavors.

        Returns:
            List of PipelineFlavor objects
        """
        return self._flavor_repo.list_flavors()

    def update_flavor(
        self,
        flavor_id: str,
        name: str | None = None,
        description: str | None = None,
        steps: list[dict] | None = None,
    ) -> PipelineFlavor:
        """
        Update a pipeline flavor.

        Args:
            flavor_id: Flavor ID
            name: Updated name (optional)
            description: Updated description (optional)
            steps: Updated steps (optional)

        Returns:
            The updated PipelineFlavor

        Raises:
            PipelineNotFoundError: If flavor not found
        """
        existing = self._flavor_repo.get_flavor(flavor_id)
        if existing is None:
            raise PipelineNotFoundError(f"Pipeline flavor {flavor_id} not found")

        updated = PipelineFlavor(
            id=existing.id,
            name=name if name is not None else existing.name,
            description=description if description is not None else existing.description,
            steps=steps if steps is not None else existing.steps,
            created_at=existing.created_at,
            last_updated=datetime.now(timezone.utc),
        )
        return self._flavor_repo.save_flavor(updated)

    def delete_flavor(self, flavor_id: str) -> None:
        """
        Delete a pipeline flavor.

        Args:
            flavor_id: Flavor ID

        Raises:
            PipelineNotFoundError: If flavor not found
        """
        flavor = self._flavor_repo.get_flavor(flavor_id)
        if flavor is None:
            raise PipelineNotFoundError(f"Pipeline flavor {flavor_id} not found")
        self._flavor_repo.delete_flavor(flavor_id)
