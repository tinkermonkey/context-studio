"""
Repository for PipelineRun persistence and retrieval.

Implements CRUD operations and queries for pipeline execution records across
all pipeline types. Uses SQLAlchemy ORM for database access.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import exists
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from adapters.persistence.sqlite.models import (
    ChangeEvent,
    IndividualExtractionRun,
    NoOpPipelineRun,
    PipelineRun,
    SchemaConnectionRefinementRun,
    SchemaDefinitionRefinementRun,
    SchemaExtractionRun,
    SchemaGroundingRun,
)
from domain.pipelines.entities import (
    IndividualExtractionRun as DomainIndividualExtractionRun,
)
from domain.pipelines.entities import (
    NoOpPipelineRun as DomainNoOpPipelineRun,
)
from domain.pipelines.entities import (
    PipelineRun as DomainPipelineRun,
)
from domain.pipelines.entities import (
    PipelineRunStatus,
    PipelineType,
)
from domain.pipelines.entities import (
    SchemaConnectionRefinementRun as DomainSchemaConnectionRefinementRun,
)
from domain.pipelines.entities import (
    SchemaDefinitionRefinementRun as DomainSchemaDefinitionRefinementRun,
)
from domain.pipelines.entities import (
    SchemaExtractionRun as DomainSchemaExtractionRun,
)
from domain.pipelines.entities import (
    SchemaGroundingRun as DomainSchemaGroundingRun,
)
from domain.pipelines.exceptions import PipelineStorageError
from utils.logger import get_logger

if TYPE_CHECKING:
    from domain.pipelines.ports import ChangeEventDictList, PipelineRunList

logger = get_logger(__name__)

# Map domain type to ORM class
_PIPELINE_TYPE_TO_ORM = {
    PipelineType.NO_OP: NoOpPipelineRun,
    PipelineType.INDIVIDUAL_EXTRACTION: IndividualExtractionRun,
    PipelineType.SCHEMA_EXTRACTION: SchemaExtractionRun,
    PipelineType.SCHEMA_NODE_GROUNDING: SchemaGroundingRun,
    PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT: SchemaDefinitionRefinementRun,
    PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT: SchemaConnectionRefinementRun,
}


class PipelineRepository:
    """
    Repository for PipelineRun persistence and retrieval.

    Handles all data access for pipeline runs, including creation, updates,
    status queries, and change_events correlation.
    """

    def __init__(self, session_factory: Callable[[], Session] | Session) -> None:
        """
        Initialize repository with session factory or session instance.

        Args:
            session_factory: Callable that returns a new SQLAlchemy session, or a Session instance
        """
        self._session_factory = session_factory
        self._owns_session = callable(session_factory)

    def _get_session(self) -> Session:
        """
        Get a session, handling both factory and direct session instances.

        Returns:
            SQLAlchemy Session instance
        """
        if callable(self._session_factory):
            return self._session_factory()
        return self._session_factory

    def _should_close_session(self) -> bool:
        """
        Determine if this repository should close sessions it creates.

        Returns True only if the session was created from a factory (we own it).
        Returns False if a session was passed directly (caller owns it).
        """
        return self._owns_session

    def create(
        self,
        batch_run_id: str,
        pipeline_type: PipelineType,
        implementation_id: str,
        configuration_ref: str,
        configuration_slug: str,
        configuration_version: int,
        specific_data: dict[str, Any] | None = None,
    ) -> DomainPipelineRun:
        """
        Create a new pipeline run and persist it.

        In joined-table inheritance, the PipelineRun.id IS the FK to batch_runs.id.
        SQLAlchemy creates the parent batch_runs row automatically when the subclass
        ORM object is added to the session — no separate batch_run insert is required.

        The batch_run_id parameter now represents the batch's ID (not the run's ID).
        The run gets its own UUID, and batch_id in the ORM points to the batch.

        Args:
            batch_run_id: ID of the batch this run belongs to
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            configuration_ref: Configuration reference
            configuration_slug: Configuration slug part
            configuration_version: Configuration version part
            specific_data: Type-specific fields (e.g., source_text_hash)

        Returns:
            Domain entity (specific subclass per pipeline_type)

        Raises:
            ValueError: If pipeline_type is invalid
            PipelineStorageError: If database operation fails
        """
        from uuid import uuid4

        orm_class = _PIPELINE_TYPE_TO_ORM.get(pipeline_type)
        if not orm_class:
            raise ValueError(f"Unknown pipeline type: {pipeline_type.value}")

        run_id = str(uuid4())
        kwargs: dict[str, Any] = {
            # Each run has its own UUID
            "id": run_id,
            "batch_id": batch_run_id,
            "pipeline_type": pipeline_type.value,
            "implementation_id": implementation_id,
            "configuration_ref": configuration_ref,
            "configuration_slug": configuration_slug,
            "configuration_version": configuration_version,
            "input_summary": {},
            "output_summary": {},
            "llm_metadata": {},
        }

        # Add type-specific fields
        if specific_data:
            kwargs.update(specific_data)

        session = self._get_session()
        try:
            orm_obj = orm_class(**kwargs)
            session.add(orm_obj)
            session.flush()
            session.commit()
            result = self._orm_to_domain(orm_obj)
            logger.info(
                f"Created pipeline run {run_id} in batch {batch_run_id} " f"({pipeline_type.value})"
            )
            return result
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error when creating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to create pipeline run") from e
        except OperationalError as e:
            session.rollback()
            msg = f"Database operational error when creating pipeline run {run_id}: {e}"
            logger.error(msg)
            raise PipelineStorageError("Failed to create pipeline run") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when creating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to create pipeline run") from e
        finally:
            if self._should_close_session():
                session.close()

    def get(self, run_id: str) -> DomainPipelineRun | None:
        """
        Retrieve a pipeline run by ID.

        Args:
            run_id: Pipeline run ID

        Returns:
            Domain entity if found, None otherwise

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if orm_obj:
                return self._orm_to_domain(orm_obj)
            return None
        except OperationalError as e:
            logger.error(f"Database operational error when retrieving pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to retrieve pipeline run") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error when retrieving pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to retrieve pipeline run") from e
        finally:
            if self._should_close_session():
                session.close()

    def list(self) -> "PipelineRunList":
        """
        List all pipeline runs.

        Returns:
            List of all domain entities

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_objs = session.query(PipelineRun).all()
            return [self._orm_to_domain(obj) for obj in orm_objs]
        except OperationalError as e:
            logger.error(f"Database operational error when listing pipeline runs: {e}")
            raise PipelineStorageError("Failed to list pipeline runs") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error when listing pipeline runs: {e}")
            raise PipelineStorageError("Failed to list pipeline runs") from e
        finally:
            if self._should_close_session():
                session.close()

    def list_by_status(self, status: PipelineRunStatus) -> "PipelineRunList":
        """
        List all pipeline runs with a specific status.

        Args:
            status: PipelineRunStatus to filter by

        Returns:
            List of domain entities

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_objs = session.query(PipelineRun).filter(PipelineRun.status == status.value).all()
            return [self._orm_to_domain(obj) for obj in orm_objs]
        except OperationalError as e:
            msg = (
                "Database operational error when listing pipeline runs "
                f"by status {status.value}: {e}"
            )
            logger.error(msg)
            raise PipelineStorageError("Failed to list pipeline runs by status") from e
        except SQLAlchemyError as e:
            msg = "Database error when listing pipeline runs " f"by status {status.value}: {e}"
            logger.error(msg)
            raise PipelineStorageError("Failed to list pipeline runs by status") from e
        finally:
            if self._should_close_session():
                session.close()

    def list_by_type(self, pipeline_type: PipelineType) -> "PipelineRunList":
        """
        List all pipeline runs of a specific type.

        Args:
            pipeline_type: PipelineType to filter by

        Returns:
            List of domain entities

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_objs = (
                session.query(PipelineRun)
                .filter(PipelineRun.pipeline_type == pipeline_type.value)
                .all()
            )
            return [self._orm_to_domain(obj) for obj in orm_objs]
        except OperationalError as e:
            msg = (
                "Database operational error when listing pipeline runs "
                f"by type {pipeline_type.value}: {e}"
            )
            logger.error(msg)
            raise PipelineStorageError("Failed to list pipeline runs by type") from e
        except SQLAlchemyError as e:
            msg = "Database error when listing pipeline runs " f"by type {pipeline_type.value}: {e}"
            logger.error(msg)
            raise PipelineStorageError("Failed to list pipeline runs by type") from e
        finally:
            if self._should_close_session():
                session.close()

    def list_by_batch_id(self, batch_id: str) -> "PipelineRunList":
        """
        List all pipeline runs in a specific batch.

        Args:
            batch_id: Batch ID

        Returns:
            List of domain entities

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_objs = session.query(PipelineRun).filter(PipelineRun.batch_id == batch_id).all()
            return [self._orm_to_domain(obj) for obj in orm_objs]
        except OperationalError as e:
            msg = f"Database operational error when listing runs for batch {batch_id}"
            logger.error(msg, exc_info=e)
            raise PipelineStorageError("Failed to list pipeline runs by batch") from e
        except SQLAlchemyError as e:
            msg = f"Database error when listing runs for batch {batch_id}"
            logger.error(msg, exc_info=e)
            raise PipelineStorageError("Failed to list pipeline runs by batch") from e
        finally:
            if self._should_close_session():
                session.close()

    def list_filtered(
        self,
        pipeline_type: PipelineType | None = None,
        status: PipelineRunStatus | None = None,
        implementation_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        applied: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple["PipelineRunList", int]:
        """
        List pipeline runs with DB-level filtering and pagination.

        All filters are applied in the database query; no in-memory post-processing
        is performed, so this is safe to call on large run tables.

        Args:
            pipeline_type: Filter by pipeline type
            status: Filter by status
            implementation_id: Filter by implementation ID
            start_date: Include only runs created on or after this UTC datetime
            end_date: Include only runs created on or before this UTC datetime
            applied: True for applied runs (have change_events), False for not-applied
            limit: Maximum number of rows to return
            offset: Number of rows to skip (for pagination)

        Returns:
            Tuple of (page of domain entities, total matching count)

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            q = session.query(PipelineRun)
            if pipeline_type is not None:
                q = q.filter(PipelineRun.pipeline_type == pipeline_type.value)
            if status is not None:
                q = q.filter(PipelineRun.status == status.value)
            if implementation_id is not None:
                q = q.filter(PipelineRun.implementation_id == implementation_id)
            if start_date is not None:
                q = q.filter(PipelineRun.created_at >= start_date)
            if end_date is not None:
                q = q.filter(PipelineRun.created_at <= end_date)

            if applied is not None:
                subquery = session.query(ChangeEvent).filter(
                    ChangeEvent.batch_run_id == PipelineRun.batch_id
                ).exists()
                if applied:
                    q = q.filter(subquery)
                else:
                    q = q.filter(~subquery)

            q = q.order_by(PipelineRun.created_at.desc())
            total = q.count()
            orm_objs = q.offset(offset).limit(limit).all()
            return [self._orm_to_domain(obj) for obj in orm_objs], total
        except OperationalError as e:
            logger.error(f"Database operational error when listing filtered pipeline runs: {e}")
            raise PipelineStorageError("Failed to list pipeline runs") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error when listing filtered pipeline runs: {e}")
            raise PipelineStorageError("Failed to list pipeline runs") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_status(self, run_id: str, status: PipelineRunStatus) -> bool:
        """
        Update a pipeline run's status.

        When status is set to PENDING, failure_reason is cleared to maintain
        the invariant that PENDING status requires failure_reason to be None.

        Args:
            run_id: Pipeline run ID
            status: New status

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not orm_obj:
                return False
            orm_obj.status = status.value  # type: ignore[assignment]
            if status == PipelineRunStatus.PENDING:
                orm_obj.failure_reason = None  # type: ignore[assignment]
            session.flush()
            session.commit()
            logger.info(f"Updated pipeline run status: {run_id} → {status.value}")
            return True
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run status") from e
        except OperationalError as e:
            session.rollback()
            logger.error(f"Database operational error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run status") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run status") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_summaries(
        self,
        run_id: str,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        llm_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update pipeline run summaries and metadata.

        Args:
            run_id: Pipeline run ID
            input_summary: Input metadata dict
            output_summary: Output counts/metrics dict
            llm_metadata: LLM metadata dict

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not orm_obj:
                return False

            if input_summary is not None:
                orm_obj.input_summary = input_summary  # type: ignore[assignment]
            if output_summary is not None:
                orm_obj.output_summary = output_summary  # type: ignore[assignment]
            if llm_metadata is not None:
                orm_obj.llm_metadata = llm_metadata  # type: ignore[assignment]

            session.flush()
            session.commit()
            logger.info(f"Updated pipeline run summaries: {run_id}")
            return True
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run summaries") from e
        except OperationalError as e:
            session.rollback()
            logger.error(f"Database operational error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run summaries") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run summaries") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_running_status(self, run_id: str, started_at: datetime) -> bool:
        """
        Atomically update status to RUNNING and set started_at timestamp.

        Updates both fields in a single transaction to prevent partial updates.

        Args:
            run_id: Pipeline run ID
            started_at: Started timestamp

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not orm_obj:
                return False
            orm_obj.status = PipelineRunStatus.RUNNING.value  # type: ignore[assignment]
            orm_obj.started_at = started_at  # type: ignore[assignment]
            session.flush()
            session.commit()
            logger.info(f"Updated pipeline run to RUNNING: {run_id}")
            return True
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run running status") from e
        except OperationalError as e:
            session.rollback()
            logger.error(f"Database operational error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run running status") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run running status") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_failure_info(
        self,
        run_id: str,
        failure_reason: str,
        output_summary: dict[str, Any] | None = None,
    ) -> bool:
        """
        Atomically update status to FAILED, set failure_reason, and optionally
        update output_summary.

        Updates all fields in a single transaction to prevent partial updates.

        Args:
            run_id: Pipeline run ID
            failure_reason: Failure reason string
            output_summary: Output metadata dict (optional)

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not orm_obj:
                return False
            orm_obj.status = PipelineRunStatus.FAILED.value  # type: ignore[assignment]
            orm_obj.failure_reason = failure_reason  # type: ignore[assignment]
            if output_summary is not None:
                orm_obj.output_summary = output_summary  # type: ignore[assignment]
            session.flush()
            session.commit()
            logger.info(f"Updated pipeline run to FAILED: {run_id}")
            return True
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run failure info") from e
        except OperationalError as e:
            session.rollback()
            logger.error(f"Database operational error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run failure info") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run failure info") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_started_at(self, run_id: str, started_at: datetime) -> bool:
        """
        Update a pipeline run's started_at timestamp.

        Args:
            run_id: Pipeline run ID
            started_at: Started timestamp

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not orm_obj:
                return False
            orm_obj.started_at = started_at  # type: ignore[assignment]
            session.flush()
            session.commit()
            logger.info(f"Updated pipeline run started_at: {run_id}")
            return True
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run started_at") from e
        except OperationalError as e:
            session.rollback()
            logger.error(f"Database operational error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run started_at") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run started_at") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_failure_reason(self, run_id: str, failure_reason: str) -> bool:
        """
        Update a pipeline run's failure_reason.

        Args:
            run_id: Pipeline run ID
            failure_reason: Failure reason string

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not orm_obj:
                return False
            orm_obj.failure_reason = failure_reason  # type: ignore[assignment]
            session.flush()
            session.commit()
            logger.info(f"Updated pipeline run failure_reason: {run_id}")
            return True
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run failure_reason") from e
        except OperationalError as e:
            session.rollback()
            logger.error(f"Database operational error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run failure_reason") from e
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when updating pipeline run {run_id}: {e}")
            raise PipelineStorageError("Failed to update pipeline run failure_reason") from e
        finally:
            if self._should_close_session():
                session.close()

    def get_change_events_for_run(self, run_id: str) -> "ChangeEventDictList":
        """
        Get all change_events correlated with a pipeline run via batch_run_id.

        Args:
            run_id: Pipeline run ID

        Returns:
            List of change_event dicts with entity_type, entity_id, operation, etc.

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            # Query change_events by the run's ID
            events = session.query(ChangeEvent).filter(ChangeEvent.batch_run_id == run_id).all()

            return [
                {
                    "id": e.id,
                    "entity_type": e.entity_type,
                    "entity_id": e.entity_id,
                    "operation": e.operation,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "batch_run_id": e.batch_run_id,
                }
                for e in events
            ]
        except OperationalError as e:
            msg = (
                "Database operational error when retrieving change events " f"for run {run_id}: {e}"
            )
            logger.error(msg)
            raise PipelineStorageError("Failed to retrieve change events") from e
        except SQLAlchemyError as e:
            msg = "Database error when retrieving change events " f"for run {run_id}: {e}"
            logger.error(msg)
            raise PipelineStorageError("Failed to retrieve change events") from e
        finally:
            if self._should_close_session():
                session.close()

    def _orm_to_domain(self, orm_obj: PipelineRun) -> DomainPipelineRun:
        """
        Convert ORM object to domain entity.

        Args:
            orm_obj: SQLAlchemy ORM object

        Returns:
            Domain entity (specific subclass per type)
        """
        # Common attributes for all pipeline runs
        common: dict[str, Any] = {
            "id": orm_obj.id,
            "batch_run_id": orm_obj.batch_id,  # FK to the batch this run belongs to
            "implementation_id": orm_obj.implementation_id,
            "configuration_ref": orm_obj.configuration_ref,
            "configuration_slug": orm_obj.configuration_slug,
            "configuration_version": orm_obj.configuration_version,
            "input_summary": orm_obj.input_summary or {},
            "output_summary": orm_obj.output_summary or {},
            "llm_metadata": orm_obj.llm_metadata or {},
            "status": PipelineRunStatus(orm_obj.status),
            "created_at": orm_obj.created_at,
            "started_at": orm_obj.started_at,
            "failure_reason": orm_obj.failure_reason,
        }

        # Dispatch based on ORM type
        if isinstance(orm_obj, NoOpPipelineRun):
            return DomainNoOpPipelineRun(
                **common,  # type: ignore[arg-type]
            )
        elif isinstance(orm_obj, IndividualExtractionRun):
            return DomainIndividualExtractionRun(
                **common,  # type: ignore[arg-type]
                source_text_hash=orm_obj.source_text_hash,  # type: ignore[arg-type]
                source_document_uri=orm_obj.source_document_uri,  # type: ignore[arg-type]
            )
        elif isinstance(orm_obj, SchemaExtractionRun):
            return DomainSchemaExtractionRun(
                **common,  # type: ignore[arg-type]
            )
        elif isinstance(orm_obj, SchemaGroundingRun):
            return DomainSchemaGroundingRun(
                **common,  # type: ignore[arg-type]
            )
        elif isinstance(orm_obj, SchemaDefinitionRefinementRun):
            return DomainSchemaDefinitionRefinementRun(
                **common,  # type: ignore[arg-type]
            )
        elif isinstance(orm_obj, SchemaConnectionRefinementRun):
            return DomainSchemaConnectionRefinementRun(
                **common,  # type: ignore[arg-type]
            )
        else:
            # Fallback for unknown types (should not happen in practice)
            return DomainPipelineRun(
                **common,  # type: ignore[arg-type]
                pipeline_type=PipelineType(orm_obj.pipeline_type),
            )
