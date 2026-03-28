"""
SQLite adapter implementation of PipelineRepository for the Pipeline Management bounded context.

Provides persistence for pipeline configurations and execution records in operations.db.
Handles domain-to-ORM mapping, session management, and query logic.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import sessionmaker, Session

from domain.pipeline.entities import PipelineConfiguration, Execution
from adapters.persistence.sqlite.operations.models import (
    PipelineConfigurationModel,
    ExecutionModel,
)


class SQLitePipelineRepository:
    """
    SQLite implementation of the PipelineRepository port for operations.db.

    Manages persistence of pipeline configurations and execution records with
    complete instrumentation for observability.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """
        Initialize the repository with a SQLAlchemy session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker configured for operations.db
        """
        self._session_factory = session_factory

    def get_config(self, config_id: str) -> Optional[PipelineConfiguration]:
        """
        Retrieve a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration

        Returns:
            PipelineConfiguration if found, None otherwise
        """
        with self._session_factory() as session:
            row = session.get(PipelineConfigurationModel, str(config_id))
            return self._to_domain_config(row) if row else None

    def list_configs(self, enabled_only: bool = False) -> list[PipelineConfiguration]:
        """
        List all pipeline configurations.

        Args:
            enabled_only: If True, return only enabled configurations (default False)

        Returns:
            List of PipelineConfiguration objects
        """
        with self._session_factory() as session:
            query = session.query(PipelineConfigurationModel)
            if enabled_only:
                query = query.filter_by(enabled=True)
            rows = query.all()
            return [self._to_domain_config(row) for row in rows]

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
        with self._session_factory() as session:
            model = self._to_model_config(config)
            session.merge(model)
            session.commit()
        return config

    def delete_config(self, config_id: str) -> bool:
        """
        Delete a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration to delete

        Returns:
            True if deletion was successful, False if configuration was not found
        """
        with self._session_factory() as session:
            row = session.get(PipelineConfigurationModel, str(config_id))
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def record_execution(self, execution: Execution) -> Execution:
        """
        Record a pipeline execution.

        Args:
            execution: Execution record to store

        Returns:
            The recorded Execution
        """
        with self._session_factory() as session:
            model = self._to_model_execution(execution)
            session.add(model)
            session.commit()
        return execution

    def get_executions(
        self, pipeline_config_id: str, limit: int = 50
    ) -> list[Execution]:
        """
        Retrieve execution history for a pipeline configuration.

        Results are returned in reverse chronological order (most recent first).

        Args:
            pipeline_config_id: ID of the pipeline configuration
            limit: Maximum number of execution records to return (default 50)

        Returns:
            List of Execution objects, up to limit
        """
        with self._session_factory() as session:
            rows = (
                session.query(ExecutionModel)
                .filter_by(pipeline_config_id=str(pipeline_config_id))
                .order_by(ExecutionModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [self._to_domain_execution(row) for row in rows]

    def _to_domain_config(
        self, row: PipelineConfigurationModel,
    ) -> PipelineConfiguration:
        """
        Convert ORM model to domain entity for PipelineConfiguration.

        Args:
            row: SQLAlchemy ORM model instance

        Returns:
            Domain PipelineConfiguration entity
        """
        return PipelineConfiguration(
            id=row.id,
            pipeline=row.pipeline,
            title=row.title,
            provider=row.provider,
            model=row.model,
            config=dict(row.config) if row.config else {},
            system_prompt=row.system_prompt,
            user_prompt=row.user_prompt,
            version=row.version,
            enabled=row.enabled,
            created_at=row.created_at,
            last_updated=row.last_updated,
        )

    def _to_model_config(
        self, config: PipelineConfiguration,
    ) -> PipelineConfigurationModel:
        """
        Convert domain entity to ORM model for PipelineConfiguration.

        Args:
            config: Domain PipelineConfiguration entity

        Returns:
            SQLAlchemy ORM model instance
        """
        return PipelineConfigurationModel(
            id=str(config.id),
            pipeline=config.pipeline,
            title=config.title,
            provider=config.provider,
            model=config.model,
            config=config.config,
            system_prompt=config.system_prompt,
            user_prompt=config.user_prompt,
            version=config.version,
            enabled=config.enabled,
            created_at=config.created_at,
            last_updated=config.last_updated,
        )

    def _to_domain_execution(self, row: ExecutionModel) -> Execution:
        """
        Convert ORM model to domain entity for Execution.

        Args:
            row: SQLAlchemy ORM model instance

        Returns:
            Domain Execution entity
        """
        return Execution(
            id=row.id,
            pipeline_config_id=row.pipeline_config_id,
            input_text=row.input_text or "",
            output_text=row.output_text or "",
            provider=row.provider or "",
            model=row.model or "",
            tokens_in=row.tokens_in,
            tokens_out=row.tokens_out,
            duration_ms=row.duration_ms,
            status=row.status,
            error_message=row.error_message,
            timestamp=row.timestamp,
        )

    def _to_model_execution(self, execution: Execution) -> ExecutionModel:
        """
        Convert domain entity to ORM model for Execution.

        Args:
            execution: Domain Execution entity

        Returns:
            SQLAlchemy ORM model instance
        """
        return ExecutionModel(
            id=str(execution.id),
            pipeline_config_id=str(execution.pipeline_config_id),
            input_text=execution.input_text,
            output_text=execution.output_text,
            provider=execution.provider,
            model=execution.model,
            tokens_in=execution.tokens_in,
            tokens_out=execution.tokens_out,
            duration_ms=execution.duration_ms,
            status=execution.status,
            error_message=execution.error_message,
            timestamp=execution.timestamp,
        )
