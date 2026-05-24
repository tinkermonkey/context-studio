"""
Domain service for LLM pipeline configuration management and execution.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Literal, cast
from uuid import uuid4

from domain.ports import EventPublisher

from .entities import Execution, PipelineConfiguration
from .events import PipelineExecuted
from .exceptions import PipelineNotFoundError
from .ports import ExecutionWithTitle, LLMProvider, PipelineConfigRepository

_logger = logging.getLogger(__name__)

_UNSET = object()


class PipelineService:
    """
    Domain service for managing LLM pipeline configurations and executions.

    Orchestrates configuration lifecycle (CRUD), pipeline execution with
    complete instrumentation, event publishing, and timeout handling.
    """

    def __init__(
        self,
        pipeline_repo: PipelineConfigRepository,
        llm: LLMProvider,
        event_publisher: EventPublisher,
    ) -> None:
        self._pipeline_repo = pipeline_repo
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
        config = self._pipeline_repo.get_config(config_id)
        if config is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")
        return config

    def list_configs(self, enabled_only: bool = False) -> list[PipelineConfiguration]:
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
        existing = self._pipeline_repo.get_config(config_id)
        if existing is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")

        resolved_seed: int | None
        if seed is _UNSET:
            resolved_seed = existing.seed
        else:
            resolved_seed = seed

        updated = PipelineConfiguration(
            id=existing.id,
            pipeline=existing.pipeline,
            title=title if title is not None else existing.title,
            provider=cast(
                Literal["openai", "anthropic"],
                provider if provider is not None else existing.provider,
            ),
            model=model if model is not None else existing.model,
            config=config if config is not None else existing.config,
            system_prompt=(system_prompt if system_prompt is not None else existing.system_prompt),
            user_prompt=(user_prompt if user_prompt is not None else existing.user_prompt),
            version=existing.version + 1,
            enabled=enabled if enabled is not None else existing.enabled,
            created_at=existing.created_at,
            last_updated=datetime.now(timezone.utc),
            seed=resolved_seed,
        )
        return self._pipeline_repo.save_config(updated)

    def delete_config(self, config_id: str) -> None:
        config = self._pipeline_repo.get_config(config_id)
        if config is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")
        self._pipeline_repo.delete_config(config_id)

    def list_executions(self, config_id: str, limit: int = 50) -> list[Execution]:
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
        return self._pipeline_repo.get_all_executions(status=status, limit=limit, offset=offset)

    def execute_pipeline(self, config_id: str, input_text: str) -> Execution:
        config = self._pipeline_repo.get_config(config_id)
        if config is None:
            raise PipelineNotFoundError(f"Pipeline configuration {config_id} not found")

        execution_id = str(uuid4())
        start_time = time.time()
        user_message = config.user_prompt.replace("{text}", input_text)
        timeout = config.config.get("timeout", 30)

        try:
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

        recorded_execution = self._pipeline_repo.record_execution(execution)

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
