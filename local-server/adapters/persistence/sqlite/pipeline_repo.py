"""
SQLite adapter implementation of PipelineRepository for the Pipeline Management bounded context.

Provides persistence for pipeline configurations and execution records in operations.db.
Handles domain-to-ORM mapping, session management, and query logic.
"""

from datetime import datetime
from typing import Literal, Optional, cast

from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.operations.models import (
    ExecutionModel,
    PipelineConfigurationModel,
    PipelineFlavorModel,
)
from domain.pipeline.entities import Execution, PipelineConfiguration, PipelineFlavor
from domain.pipeline.ports import ExecutionWithTitle


class SQLitePipelineRepository:
    """
    SQLite implementation of the PipelineRepository port for operations.db.

    Manages persistence of pipeline configurations and execution records.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """
        Initialize the repository with a SQLAlchemy session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker configured for operations.db
        """
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """
        Create and return a new isolated session.

        Returns:
            SQLAlchemy Session instance
        """
        return self.session_factory()

    def get_config(self, config_id: str) -> Optional[PipelineConfiguration]:
        """
        Retrieve a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration

        Returns:
            PipelineConfiguration if found, None otherwise
        """
        with self.session_factory() as session:
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
        with self.session_factory() as session:
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
        with self.session_factory() as session:
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
        with self.session_factory() as session:
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
        with self.session_factory() as session:
            model = self._to_model_execution(execution)
            session.add(model)
            session.commit()
            return execution

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
        with self.session_factory() as session:
            rows = (
                session.query(ExecutionModel)
                .filter_by(pipeline_config_id=str(pipeline_config_id))
                .order_by(ExecutionModel.timestamp.desc())  # type: ignore[attr-defined]
                .limit(limit)
                .all()
            )
            return [self._to_domain_execution(row) for row in rows]

    def get_all_executions(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ExecutionWithTitle], int]:
        """
        Retrieve execution history across all pipeline configurations with pagination.

        Results are returned in reverse chronological order (most recent first).
        Performs a JOIN with PipelineConfigurationModel to fetch pipeline titles.
        Only includes executions whose pipeline configurations exist (INNER JOIN).

        Args:
            status: Optional status filter ("success", "error", "timeout")
            limit: Maximum number of execution records to return
            offset: Number of execution records to skip for pagination

        Returns:
            Tuple of:
            - List of ExecutionWithTitle objects (combining executions with their pipeline titles)
            - Total count of all matching executions (for pagination)
        """
        with self.session_factory() as session:
            # Count query must use the same JOIN to exclude orphan executions
            count_query = session.query(ExecutionModel).join(
                PipelineConfigurationModel,
                ExecutionModel.pipeline_config_id == PipelineConfigurationModel.id,
            )
            if status:
                count_query = count_query.filter(ExecutionModel.status == status)
            total = count_query.count()

            query = session.query(  # type: ignore[call-overload]
                ExecutionModel,
                PipelineConfigurationModel.title,
            ).join(
                PipelineConfigurationModel,
                ExecutionModel.pipeline_config_id == PipelineConfigurationModel.id,
            )

            if status:
                query = query.filter(ExecutionModel.status == status)

            rows = (
                query.order_by(ExecutionModel.timestamp.desc())  # type: ignore[attr-defined]
                .offset(offset)
                .limit(limit)
                .all()
            )

            results = [
                ExecutionWithTitle(
                    execution=self._to_domain_execution(row[0]),
                    pipeline_title=row[1],
                )
                for row in rows
            ]

            return results, total

    def _to_domain_config(
        self,
        row: PipelineConfigurationModel,
    ) -> PipelineConfiguration:
        """
        Convert ORM model to domain entity for PipelineConfiguration.

        Args:
            row: SQLAlchemy ORM model instance

        Returns:
            Domain PipelineConfiguration entity
        """
        return PipelineConfiguration(
            id=cast(str, row.id),
            pipeline=cast(str, row.pipeline),
            title=cast(str, row.title),
            provider=cast(Literal["openai", "anthropic"], row.provider),
            model=cast(str, row.model),
            config=dict(row.config) if row.config else {},
            system_prompt=cast(str, row.system_prompt),
            user_prompt=cast(str, row.user_prompt),
            version=cast(int, row.version),
            enabled=cast(bool, row.enabled),
            created_at=cast(datetime, row.created_at),
            last_updated=cast(datetime, row.last_updated),
            seed=cast(int | None, row.seed),
        )

    def _to_model_config(
        self,
        config: PipelineConfiguration,
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
            seed=config.seed,
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
            id=cast(str, row.id),
            pipeline_config_id=cast(str, row.pipeline_config_id),
            input_text=cast(str, row.input_text) or "",
            output_text=cast(str, row.output_text) or "",
            provider=cast(str, row.provider) or "",
            model=cast(str, row.model) or "",
            tokens_in=cast(int, row.tokens_in),
            tokens_out=cast(int, row.tokens_out),
            duration_ms=cast(int, row.duration_ms),
            status=cast(Literal["success", "error", "timeout"], row.status),
            error_message=cast(str | None, row.error_message),
            timestamp=cast(datetime, row.timestamp),
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

    def get_flavor(self, flavor_id: str) -> Optional[PipelineFlavor]:
        """
        Retrieve a pipeline flavor by ID.

        Args:
            flavor_id: Unique identifier of the flavor

        Returns:
            PipelineFlavor if found, None otherwise
        """
        with self.session_factory() as session:
            row = session.get(PipelineFlavorModel, str(flavor_id))
            return self._to_domain_flavor(row) if row else None

    def list_flavors(self) -> list[PipelineFlavor]:
        """
        List all pipeline flavors.

        Returns:
            List of PipelineFlavor objects
        """
        with self.session_factory() as session:
            rows = session.query(PipelineFlavorModel).all()
            return [self._to_domain_flavor(row) for row in rows]

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
        with self.session_factory() as session:
            model = self._to_model_flavor(flavor)
            session.merge(model)
            session.commit()
            return flavor

    def delete_flavor(self, flavor_id: str) -> bool:
        """
        Delete a pipeline flavor by ID.

        Args:
            flavor_id: Unique identifier of the flavor to delete

        Returns:
            True if deletion was successful, False if flavor was not found
        """
        with self.session_factory() as session:
            row = session.get(PipelineFlavorModel, str(flavor_id))
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def _to_domain_flavor(self, row: PipelineFlavorModel) -> PipelineFlavor:
        """
        Convert ORM model to domain entity for PipelineFlavor.

        Args:
            row: SQLAlchemy ORM model instance

        Returns:
            Domain PipelineFlavor entity
        """
        return PipelineFlavor(
            id=cast(str, row.id),
            name=cast(str, row.name),
            description=cast(str, row.description),
            steps=list(row.steps) if row.steps else [],
            created_at=cast(datetime, row.created_at),
            last_updated=cast(datetime, row.last_updated),
        )

    def _to_model_flavor(self, flavor: PipelineFlavor) -> PipelineFlavorModel:
        """
        Convert domain entity to ORM model for PipelineFlavor.

        Args:
            flavor: Domain PipelineFlavor entity

        Returns:
            SQLAlchemy ORM model instance
        """
        return PipelineFlavorModel(
            id=str(flavor.id),
            name=flavor.name,
            description=flavor.description,
            steps=flavor.steps,
            created_at=flavor.created_at,
            last_updated=flavor.last_updated,
        )
