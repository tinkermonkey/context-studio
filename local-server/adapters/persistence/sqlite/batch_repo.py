"""
Repository for Batch persistence and retrieval.

Implements CRUD operations and queries for batch entities.
Uses SQLAlchemy ORM for database access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from adapters.persistence.sqlite.models import Batch as BatchORM
from domain.pipelines.entities import Batch, BatchStatus
from domain.pipelines.exceptions import PipelineStorageError
from utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class BatchRepository:
    """
    Repository for Batch persistence and retrieval.

    Handles all data access for batches, including creation, status updates,
    and retrieval of batch information.
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
            )
            session.add(orm_obj)
            session.commit()

            return Batch(
                id=orm_obj.id,
                status=BatchStatus(orm_obj.status),
                created_at=orm_obj.created_at,
            )
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

            return Batch(
                id=orm_obj.id,
                status=BatchStatus(orm_obj.status),
                created_at=orm_obj.created_at,
            )
        except SQLAlchemyError as e:
            logger.error(f"Failed to get batch {batch_id}: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to get batch: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def list(self) -> list[Batch]:
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
            return [
                Batch(
                    id=orm_obj.id,
                    status=BatchStatus(orm_obj.status),
                    created_at=orm_obj.created_at,
                )
                for orm_obj in orm_objs
            ]
        except SQLAlchemyError as e:
            logger.error(f"Failed to list batches: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to list batches: {e}") from e
        finally:
            if self._should_close_session():
                session.close()

    def list_by_status(self, status: BatchStatus) -> list[Batch]:
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
            return [
                Batch(
                    id=orm_obj.id,
                    status=BatchStatus(orm_obj.status),
                    created_at=orm_obj.created_at,
                )
                for orm_obj in orm_objs
            ]
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

            orm_obj.status = status.value
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to update batch {batch_id} status: {e}", exc_info=e)
            raise PipelineStorageError(f"Failed to update batch status: {e}") from e
        finally:
            if self._should_close_session():
                session.close()
