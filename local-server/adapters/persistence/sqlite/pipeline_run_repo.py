"""
Repository for PipelineRun persistence and retrieval.

Implements CRUD operations and queries for pipeline execution records across
all pipeline types. Uses SQLAlchemy ORM for database access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy.orm import Session

from adapters.persistence.sqlite.models import (
    ChangeEvent,
    IndividualExtractionRun,
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
from utils.logger import get_logger

if TYPE_CHECKING:
    from domain.pipelines.ports import ChangeEventDictList, PipelineRunList

logger = get_logger(__name__)

# Map domain type to ORM class
_PIPELINE_TYPE_TO_ORM = {
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

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Initialize repository with session factory.

        Args:
            session_factory: Callable that returns a new SQLAlchemy session
        """
        self._session_factory = session_factory

    def create(
        self,
        batch_run_id: str,
        pipeline_type: PipelineType,
        implementation_id: str,
        configuration_ref: str,
        specific_data: dict[str, Any] | None = None,
    ) -> DomainPipelineRun:
        """
        Create a new pipeline run and persist it.

        In joined-table inheritance, the PipelineRun.id IS the FK to batch_runs.id.
        This method assumes the batch_run already exists.

        Args:
            batch_run_id: ID of the existing batch_run (becomes PipelineRun.id)
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            configuration_ref: Configuration reference
            specific_data: Type-specific fields (e.g., source_text_hash)

        Returns:
            Domain entity (specific subclass per pipeline_type)

        Raises:
            ValueError: If pipeline_type is invalid
        """
        orm_class = _PIPELINE_TYPE_TO_ORM.get(pipeline_type)
        if not orm_class:
            raise ValueError(f"Unknown pipeline type: {pipeline_type.value}")

        kwargs: dict[str, Any] = {
            "id": batch_run_id,  # In joined-table inheritance, id IS the FK
            "pipeline_type": pipeline_type.value,
            "implementation_id": implementation_id,
            "configuration_ref": configuration_ref,
            "input_summary": {},
            "output_summary": {},
            "llm_metadata": {},
        }

        # Add type-specific fields
        if specific_data:
            kwargs.update(specific_data)

        session = self._session_factory()
        try:
            orm_obj = orm_class(**kwargs)
            session.add(orm_obj)
            session.flush()
            session.commit()
            result = self._orm_to_domain(orm_obj)
            logger.info(f"Created pipeline run: {batch_run_id} ({pipeline_type.value})")
            return result
        finally:
            session.close()

    def get(self, run_id: str) -> DomainPipelineRun | None:
        """
        Retrieve a pipeline run by ID.

        Args:
            run_id: Pipeline run ID

        Returns:
            Domain entity if found, None otherwise
        """
        session = self._session_factory()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if orm_obj:
                return self._orm_to_domain(orm_obj)
            return None
        finally:
            session.close()

    def list(self) -> "PipelineRunList":
        """
        List all pipeline runs.

        Returns:
            List of all domain entities
        """
        session = self._session_factory()
        try:
            orm_objs = session.query(PipelineRun).all()
            return [self._orm_to_domain(obj) for obj in orm_objs]
        finally:
            session.close()

    def list_by_status(self, status: PipelineRunStatus) -> "PipelineRunList":
        """
        List all pipeline runs with a specific status.

        Args:
            status: PipelineRunStatus to filter by

        Returns:
            List of domain entities
        """
        session = self._session_factory()
        try:
            orm_objs = session.query(PipelineRun).filter(
                PipelineRun.status == status.value
            ).all()
            return [self._orm_to_domain(obj) for obj in orm_objs]
        finally:
            session.close()

    def list_by_type(self, pipeline_type: PipelineType) -> "PipelineRunList":
        """
        List all pipeline runs of a specific type.

        Args:
            pipeline_type: PipelineType to filter by

        Returns:
            List of domain entities
        """
        session = self._session_factory()
        try:
            orm_objs = session.query(PipelineRun).filter(
                PipelineRun.pipeline_type == pipeline_type.value
            ).all()
            return [self._orm_to_domain(obj) for obj in orm_objs]
        finally:
            session.close()

    def update_status(self, run_id: str, status: PipelineRunStatus) -> bool:
        """
        Update a pipeline run's status.

        Args:
            run_id: Pipeline run ID
            status: New status

        Returns:
            True if updated, False if not found
        """
        session = self._session_factory()
        try:
            orm_obj = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not orm_obj:
                return False
            orm_obj.status = status.value  # type: ignore[assignment]
            session.flush()
            session.commit()
            logger.info(f"Updated pipeline run status: {run_id} → {status.value}")
            return True
        finally:
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
        """
        session = self._session_factory()
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
        finally:
            session.close()

    def get_change_events_for_run(self, run_id: str) -> "ChangeEventDictList":
        """
        Get all change_events correlated with a pipeline run via batch_run_id.

        Args:
            run_id: Pipeline run ID (which is also the batch_run_id)

        Returns:
            List of change_event dicts with entity_type, entity_id, operation, etc.
        """
        session = self._session_factory()
        try:
            events = session.query(ChangeEvent).filter(
                ChangeEvent.batch_run_id == run_id
            ).all()

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
        finally:
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
            "batch_run_id": orm_obj.id,  # In joined-table inheritance, they're the same
            "implementation_id": orm_obj.implementation_id,
            "configuration_ref": orm_obj.configuration_ref,
            "input_summary": orm_obj.input_summary or {},
            "output_summary": orm_obj.output_summary or {},
            "llm_metadata": orm_obj.llm_metadata or {},
            "status": PipelineRunStatus(orm_obj.status),
            "created_at": orm_obj.created_at,
        }

        # Dispatch based on ORM type
        if isinstance(orm_obj, IndividualExtractionRun):
            return DomainIndividualExtractionRun(
                **common,  # type: ignore[arg-type]
                pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
                source_text_hash=orm_obj.source_text_hash,  # type: ignore[arg-type]
                source_document_uri=orm_obj.source_document_uri,  # type: ignore[arg-type]
            )
        elif isinstance(orm_obj, SchemaExtractionRun):
            return DomainSchemaExtractionRun(
                **common,  # type: ignore[arg-type]
                pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            )
        elif isinstance(orm_obj, SchemaGroundingRun):
            return DomainSchemaGroundingRun(
                **common,  # type: ignore[arg-type]
                pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            )
        elif isinstance(orm_obj, SchemaDefinitionRefinementRun):
            return DomainSchemaDefinitionRefinementRun(
                **common,  # type: ignore[arg-type]
                pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            )
        elif isinstance(orm_obj, SchemaConnectionRefinementRun):
            return DomainSchemaConnectionRefinementRun(
                **common,  # type: ignore[arg-type]
                pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            )
        else:
            # Fallback for unknown types (should not happen in practice)
            return DomainPipelineRun(
                **common,  # type: ignore[arg-type]
                pipeline_type=PipelineType(orm_obj.pipeline_type),
            )
