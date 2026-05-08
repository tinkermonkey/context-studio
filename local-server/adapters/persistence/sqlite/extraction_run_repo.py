"""
SQLite adapter implementing the ExtractionRunRepository port.

Provides persistence for extraction run records, including pipeline configuration,
LLM settings, and resource metrics.

Key responsibilities:
- Store extraction run records with all metadata
- Retrieve extraction runs by ID
- List extraction runs with pagination
- Update extraction run status and metrics
"""

from typing import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import desc

from domain.extraction.entities import ExtractionRun, ExtractionRunStatus
from adapters.persistence.sqlite.models import ExtractionRun as ExtractionRunORM


class SQLiteExtractionRunRepository:
    """
    SQLAlchemy-based implementation of the ExtractionRunRepository port.

    Manages persistence of extraction run records using SQLAlchemy ORM.
    ExtractionRun records track extraction operations from inception through
    completion, recording pipeline configuration, LLM settings, and outcome metrics.

    Attributes:
        session_factory: SQLAlchemy sessionmaker for creating isolated sessions
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """
        Initialize the repository with a database session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker for creating isolated sessions
        """
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """
        Create and return a new isolated session.

        Returns:
            SQLAlchemy Session instance
        """
        return self.session_factory()

    def save_extraction_run(self, run: ExtractionRun) -> ExtractionRun:
        """
        Save an extraction run to persistent storage.

        Creates a new ExtractionRun record in the database. If the run already
        exists, use update_extraction_run instead.

        Args:
            run: The ExtractionRun to save

        Returns:
            The saved ExtractionRun

        Raises:
            Exception: If persistence fails
        """
        session = self._get_session()
        try:
            orm_run = ExtractionRunORM(
                id=run.id,
                source_document_uri=run.source_document_uri,
                source_text_hash=run.source_text_hash,
                pipeline_config_ref=run.pipeline_config_ref,
                model=run.model,
                temperature=run.temperature,
                tokens_used=run.tokens_used,
                duration_ms=run.duration_ms,
                triples_extracted=run.triples_extracted,
                triples_committed=run.triples_committed,
                status=run.status.value,
                run_type="extraction",
                affected_entity_ids=[],
            )

            session.add(orm_run)
            session.commit()

            return run

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_extraction_run(self, run_id: str) -> ExtractionRun | None:
        """
        Retrieve an extraction run by ID.

        Converts ORM model back to domain entity.

        Args:
            run_id: The ID of the extraction run

        Returns:
            The ExtractionRun or None if not found
        """
        session = self._get_session()
        try:
            orm_run = (
                session.query(ExtractionRunORM)
                .filter(ExtractionRunORM.id == run_id)
                .first()
            )

            if not orm_run:
                return None

            return self._orm_to_domain(orm_run)

        finally:
            session.close()

    def list_extraction_runs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionRun]:
        """
        List extraction runs with pagination.

        Results are ordered by created_at descending (most recent first).

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of ExtractionRun objects
        """
        session = self._get_session()
        try:
            orm_runs = (
                session.query(ExtractionRunORM)
                .order_by(desc(ExtractionRunORM.created_at))
                .offset(offset)
                .limit(limit)
                .all()
            )

            return [self._orm_to_domain(orm) for orm in orm_runs]

        finally:
            session.close()

    def update_extraction_run(self, run: ExtractionRun) -> ExtractionRun:
        """
        Update an existing extraction run.

        Updates the run's status and metrics (tokens_used, duration_ms,
        triples_extracted, triples_committed).

        Args:
            run: The ExtractionRun with updated fields

        Returns:
            The updated ExtractionRun

        Raises:
            Exception: If persistence fails or run not found
        """
        session = self._get_session()
        try:
            orm_run = (
                session.query(ExtractionRunORM)
                .filter(ExtractionRunORM.id == run.id)
                .first()
            )

            if not orm_run:
                raise ValueError(f"ExtractionRun with id {run.id} not found")

            orm_run.status = run.status.value
            orm_run.tokens_used = run.tokens_used
            orm_run.duration_ms = run.duration_ms
            orm_run.triples_extracted = run.triples_extracted
            orm_run.triples_committed = run.triples_committed

            session.commit()

            return run

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _orm_to_domain(self, orm_run: ExtractionRunORM) -> ExtractionRun:
        """
        Convert ORM model to domain entity.

        Args:
            orm_run: ORM model instance

        Returns:
            Domain ExtractionRun entity
        """
        status_map = {
            "pending": ExtractionRunStatus.PENDING,
            "completed": ExtractionRunStatus.COMPLETED,
            "failed": ExtractionRunStatus.FAILED,
        }
        status = status_map.get(orm_run.status, ExtractionRunStatus.PENDING)

        return ExtractionRun(
            id=orm_run.id or "",  # type: ignore[arg-type]
            source_document_uri=orm_run.source_document_uri,  # type: ignore[arg-type]
            source_text_hash=orm_run.source_text_hash or "",  # type: ignore[arg-type]
            pipeline_config_ref=orm_run.pipeline_config_ref or "",  # type: ignore[arg-type]
            model=orm_run.model or "",  # type: ignore[arg-type]
            temperature=orm_run.temperature or 0.0,  # type: ignore[arg-type]
            tokens_used=orm_run.tokens_used or 0,  # type: ignore[arg-type]
            duration_ms=orm_run.duration_ms or 0,  # type: ignore[arg-type]
            triples_extracted=orm_run.triples_extracted or 0,  # type: ignore[arg-type]
            triples_committed=orm_run.triples_committed or 0,  # type: ignore[arg-type]
            status=status,
        )
