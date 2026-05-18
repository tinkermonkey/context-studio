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

from typing import Sequence, cast

from sqlalchemy import desc
from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.models import ExtractionRun as ExtractionRunORM
from domain.extraction.entities import ExtractionRun, ExtractionRunStatus


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
            orm_run = session.query(ExtractionRunORM).filter(ExtractionRunORM.id == run_id).first()

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
            orm_run = session.query(ExtractionRunORM).filter(ExtractionRunORM.id == run.id).first()

            if not orm_run:
                raise ValueError(f"ExtractionRun with id {run.id} not found")

            orm_run.status = run.status.value  # type: ignore[assignment]
            orm_run.tokens_used = run.tokens_used  # type: ignore[assignment]
            orm_run.duration_ms = run.duration_ms  # type: ignore[assignment]
            orm_run.triples_extracted = run.triples_extracted  # type: ignore[assignment]
            orm_run.triples_committed = run.triples_committed  # type: ignore[assignment]

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
        status_str = cast(str, orm_run.status)
        status = status_map.get(status_str, ExtractionRunStatus.PENDING)

        return ExtractionRun(
            id=str(orm_run.id) if orm_run.id else "",
            source_document_uri=cast(str | None, orm_run.source_document_uri),
            source_text_hash=(str(orm_run.source_text_hash) if orm_run.source_text_hash else ""),
            pipeline_config_ref=(
                str(orm_run.pipeline_config_ref) if orm_run.pipeline_config_ref else ""
            ),
            model=str(orm_run.model) if orm_run.model else "",
            temperature=(float(orm_run.temperature) if orm_run.temperature is not None else 0.0),
            tokens_used=(int(orm_run.tokens_used) if orm_run.tokens_used is not None else 0),
            duration_ms=(int(orm_run.duration_ms) if orm_run.duration_ms is not None else 0),
            triples_extracted=(
                int(orm_run.triples_extracted) if orm_run.triples_extracted is not None else 0
            ),
            triples_committed=(
                int(orm_run.triples_committed) if orm_run.triples_committed is not None else 0
            ),
            status=status,
        )
