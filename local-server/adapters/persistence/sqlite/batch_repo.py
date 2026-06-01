"""
Repository for Batch persistence and retrieval.

Implements CRUD operations and queries for batch entities.
Uses SQLAlchemy ORM for database access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from adapters.persistence.sqlite.models import Batch as BatchORM
from adapters.persistence.sqlite.models import BatchRun as BatchRunORM
from domain.pipelines.entities import Batch, BatchStatus, PipelineRunStatus
from domain.pipelines.exceptions import PipelineStorageError
from utils.logger import get_logger

logger = get_logger(__name__)


class BatchRepository:
    """
    Repository for Batch persistence and retrieval.

    Handles all data access for batches, including creation, status updates,
    lifecycle management, and retrieval of batch information.
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

    def _orm_to_domain(self, orm_obj: BatchORM) -> Batch:
        """
        Convert ORM object to domain entity.

        Args:
            orm_obj: SQLAlchemy ORM object

        Returns:
            Domain entity
        """
        return Batch(
            id=orm_obj.id,  # type: ignore[arg-type]
            status=BatchStatus(orm_obj.status),  # type: ignore[arg-type]
            created_at=orm_obj.created_at,  # type: ignore[arg-type]
            started_at=orm_obj.started_at,  # type: ignore[arg-type]
            completed_at=orm_obj.completed_at,  # type: ignore[arg-type]
            last_updated=orm_obj.last_updated,  # type: ignore[arg-type]
        )

    def create(self) -> Batch:
        """
        Create a new batch and persist it.

        Returns:
            Domain entity with status=PENDING

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            batch_id = str(uuid4())
            now = datetime.now(timezone.utc)
            orm_obj = BatchORM(
                id=batch_id,
                status=BatchStatus.PENDING.value,
                created_at=now,
                last_updated=now,
            )
            session.add(orm_obj)
            session.commit()

            return self._orm_to_domain(orm_obj)
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to create batch: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to create batch: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def get(self, batch_id: str) -> Batch | None:
        """
        Retrieve a batch by ID.

        Args:
            batch_id: Batch ID

        Returns:
            Domain entity if found, None otherwise

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(BatchORM).filter(BatchORM.id == batch_id).first()
            if not orm_obj:
                return None

            return self._orm_to_domain(orm_obj)
        except SQLAlchemyError as e:
            logger.error(f"Failed to get batch {batch_id}: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to get batch: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def list(self) -> "list[Batch]":  # type: ignore[valid-type]
        """
        List all batches.

        Returns:
            List of all domain entities

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_objs = session.query(BatchORM).all()
            return [self._orm_to_domain(orm_obj) for orm_obj in orm_objs]
        except SQLAlchemyError as e:
            logger.error(f"Failed to list batches: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to list batches: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def list_by_status(self, status: BatchStatus) -> "list[Batch]":  # type: ignore[valid-type]
        """
        List all batches with a specific status.

        Args:
            status: BatchStatus to filter by

        Returns:
            List of domain entities

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_objs = session.query(BatchORM).filter(BatchORM.status == status.value).all()
            return [self._orm_to_domain(orm_obj) for orm_obj in orm_objs]
        except SQLAlchemyError as e:
            logger.error(f"Failed to list batches by status {status}: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to list batches by status: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_status(self, batch_id: str, status: BatchStatus) -> bool:
        """
        Update a batch's status.

        Args:
            batch_id: Batch ID
            status: New status

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(BatchORM).filter(BatchORM.id == batch_id).first()
            if not orm_obj:
                return False

            orm_obj.status = status.value  # type: ignore[assignment]
            orm_obj.last_updated = datetime.now(timezone.utc)  # type: ignore[assignment]
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to update batch {batch_id} status: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to update batch status: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_started_at(self, batch_id: str) -> bool:
        """
        Update a batch's started_at timestamp (PENDING -> RUNNING transition).

        Args:
            batch_id: Batch ID

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(BatchORM).filter(BatchORM.id == batch_id).first()
            if not orm_obj:
                return False

            if orm_obj.started_at is None:
                now = datetime.now(timezone.utc)
                orm_obj.started_at = now  # type: ignore[assignment,unreachable]
                orm_obj.last_updated = now  # type: ignore[assignment,unreachable]
                session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to update batch {batch_id} started_at: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to update batch started_at: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def update_completed_at(self, batch_id: str) -> bool:
        """
        Update a batch's completed_at timestamp (terminal state transition).

        Args:
            batch_id: Batch ID

        Returns:
            True if updated, False if not found

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            orm_obj = session.query(BatchORM).filter(BatchORM.id == batch_id).first()
            if not orm_obj:
                return False

            if orm_obj.completed_at is None:
                now = datetime.now(timezone.utc)
                orm_obj.completed_at = now  # type: ignore[assignment,unreachable]
                orm_obj.last_updated = now  # type: ignore[assignment,unreachable]
                session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to update batch {batch_id} completed_at: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to update batch completed_at: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def compute_aggregate_status(self, batch_id: str) -> BatchStatus:
        """
        Compute batch status from child pipeline runs.

        Batch status transitions:
        - PENDING: No child runs started yet, or all runs still PENDING
        - RUNNING: At least one run is RUNNING
        - COMPLETED: All runs are terminal (COMPLETED or FAILED) and at least one COMPLETED
        - FAILED: All runs are terminal and all FAILED
        - CANCELLED: User issued cancel command explicitly (stored status)

        Args:
            batch_id: Batch ID

        Returns:
            Computed BatchStatus (does not update database)

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            runs = session.query(BatchRunORM).filter(BatchRunORM.batch_id == batch_id).all()
            if not runs:
                return BatchStatus.PENDING

            statuses = [r.status for r in runs]

            if PipelineRunStatus.RUNNING.value in statuses:
                return BatchStatus.RUNNING

            terminal_statuses = (
                PipelineRunStatus.COMPLETED.value,
                PipelineRunStatus.FAILED.value,
                PipelineRunStatus.CANCELLED.value,
            )
            all_terminal = all(s in terminal_statuses for s in statuses)

            if all_terminal:
                if PipelineRunStatus.COMPLETED.value in statuses:
                    return BatchStatus.COMPLETED
                elif PipelineRunStatus.CANCELLED.value in statuses:
                    return BatchStatus.CANCELLED
                else:
                    return BatchStatus.FAILED

            return BatchStatus.PENDING
        except SQLAlchemyError as e:
            msg = f"Failed to compute aggregate status for batch {batch_id}: {e}"
            logger.error(msg, exc_info=e)
            raise PipelineStorageError("Failed to compute aggregate status") from e
        finally:
            if self._should_close_session():
                session.close()

    def get_run_counts(self, batch_id: str) -> dict[str, int]:
        """
        Get count of runs in each status for a batch.

        Args:
            batch_id: Batch ID

        Returns:
            Dict with keys: pending, running, completed, failed

        Raises:
            PipelineStorageError: If database operation fails
        """
        session = self._get_session()
        try:
            runs = session.query(BatchRunORM).filter(BatchRunORM.batch_id == batch_id).all()

            counts = {
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            }

            for run in runs:
                if run.status == PipelineRunStatus.PENDING.value:
                    counts["pending"] += 1
                elif run.status == PipelineRunStatus.RUNNING.value:
                    counts["running"] += 1
                elif run.status == PipelineRunStatus.COMPLETED.value:
                    counts["completed"] += 1
                elif run.status == PipelineRunStatus.FAILED.value:
                    counts["failed"] += 1
                elif run.status == PipelineRunStatus.CANCELLED.value:
                    counts["cancelled"] += 1

            return counts
        except SQLAlchemyError as e:
            logger.error(f"Failed to get run counts for batch {batch_id}: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to get run counts: {e}") from e
        finally:
            if self._should_close_session():
                session.close()
