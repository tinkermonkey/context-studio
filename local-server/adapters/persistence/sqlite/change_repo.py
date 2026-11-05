"""
SQLite adapter implementing versioning domain persistence.

Handles recording and querying change events in the audit trail table for the
Version Control & Collaboration bounded context.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy import func, literal_column, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import ChangeEvent
from domain.versioning.entities import ChangeEvent as DomainChangeEvent
from domain.versioning.exceptions import VersionNotFoundError
from domain.versioning.value_objects import ChangeHistoryResult, ChangeOperation


class SQLiteChangeRepository:
    """
    SQLAlchemy-based repository for change events.

    Implements the ChangeRepository protocol, handling persistence of change events
    to SQLite.

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

    # ChangeEvent operations

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: ChangeOperation,
        new_state: dict,
        previous_state: Optional[dict] = None,
        user_id: Optional[str] = None,
        change_reason: Optional[str] = None,
        batch_run_id: Optional[str] = None,
    ) -> str:
        """
        Record a change event to the audit trail.

        Args:
            entity_id: ID of the entity that changed
            entity_type: Type of entity
            operation: Type of operation ('create', 'update', 'delete')
            new_state: JSON snapshot of entity after change
            previous_state: JSON snapshot of entity before change (optional)
            user_id: Optional ID of user who made the change
            change_reason: Optional explanation of the change
            batch_run_id: Optional ID of the batch run (import or extraction) that produced this
            change

        Returns:
            The ID of the recorded change event

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                change_event = ChangeEvent(
                    id=str(uuid.uuid4()),
                    entity_id=entity_id,
                    entity_type=entity_type,
                    operation=operation,
                    new_state=new_state,
                    previous_state=previous_state,
                    timestamp=datetime.now(timezone.utc),
                    user_id=user_id,
                    change_reason=change_reason,
                    batch_run_id=batch_run_id,
                    processed=False,
                )

                session.add(change_event)
                session.commit()

                return cast(str, change_event.id)
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to record change event: {str(e)}") from e

    def get_changes(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        batch_run_id: Optional[str] = None,
        limit: Optional[int] = 100,
    ) -> ChangeHistoryResult:
        """
        Retrieve change events with optional filters.

        Args:
            entity_id: Optional filter to changes for a specific entity
            since: Optional filter to changes after a specific timestamp
            batch_run_id: Optional filter to changes for a specific batch run
            limit: Maximum number of results to return

        Returns:
            ChangeHistoryResult with paginated events and total count without limit
        """
        with self.session_factory() as session:
            # Build filter conditions once
            conditions = []
            if entity_id:
                conditions.append(ChangeEvent.entity_id == entity_id)
            if since:
                conditions.append(ChangeEvent.timestamp >= since)
            if batch_run_id:
                conditions.append(ChangeEvent.batch_run_id == batch_run_id)

            # Apply filters to base query
            base_query = select(ChangeEvent)
            for condition in conditions:
                base_query = base_query.where(condition)

            # Get total count before applying limit
            count_query = select(func.count(ChangeEvent.id)).select_from(ChangeEvent)
            for condition in conditions:
                count_query = count_query.where(condition)
            total_count = session.execute(count_query).scalar() or 0

            # Apply ordering and limit to get paginated results
            # rowid breaks timestamp ties in insertion order, so revert (which walks
            # this newest first) undoes same-timestamp events in the right order.
            paginated_query = base_query.order_by(
                ChangeEvent.timestamp.desc(), literal_column("change_events.rowid").desc()
            ).limit(limit)
            orm_events = session.execute(paginated_query).scalars().all()

            events = [self._to_domain_change_event(e) for e in orm_events]
            return ChangeHistoryResult(events=tuple(events), total=total_count)

    def mark_processed(self, event_ids: list[str]) -> None:
        """
        Mark change events as processed (synchronized to remote).

        Args:
            event_ids: List of change event IDs to mark as processed

        Raises:
            VersionNotFoundError: If any event IDs don't exist
            RuntimeError: If database operation fails
        """
        if not event_ids:
            return

        try:
            with self.session_factory() as session:
                query = select(ChangeEvent).where(ChangeEvent.id.in_(event_ids))
                events = session.execute(query).scalars().all()
                found_ids = {cast(str, e.id) for e in events}

                missing_ids = set(event_ids) - found_ids
                if missing_ids:
                    raise VersionNotFoundError(
                        f"Change events not found: {', '.join(sorted(missing_ids))}"
                    )

                for event in events:
                    event.processed = True

                session.commit()
        except VersionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to mark change events as processed: {str(e)}") from e

    def delete_changes(self, event_ids: list[str]) -> None:
        """
        Delete change events by their IDs (used for rollback on pull failure).

        Args:
            event_ids: List of change event IDs to delete

        Raises:
            VersionNotFoundError: If any event IDs don't exist
            RuntimeError: If database operation fails
        """
        if not event_ids:
            return

        try:
            with self.session_factory() as session:
                query = select(ChangeEvent).where(ChangeEvent.id.in_(event_ids))
                events = session.execute(query).scalars().all()
                found_ids = {cast(str, e.id) for e in events}

                missing_ids = set(event_ids) - found_ids
                if missing_ids:
                    raise VersionNotFoundError(
                        f"Change events not found: {', '.join(sorted(missing_ids))}"
                    )

                for event in events:
                    session.delete(event)

                session.commit()
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to delete change events: {str(e)}") from e

    def get_unprocessed(self, limit: int = 500) -> list[DomainChangeEvent]:
        """
        Retrieve change events not yet synchronized to remote.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of unprocessed ChangeEvent domain entities
        """
        with self.session_factory() as session:
            query = (
                select(ChangeEvent)
                .where(~ChangeEvent.processed)
                .order_by(
                    ChangeEvent.timestamp.asc(), literal_column("change_events.rowid").asc()
                )
                .limit(limit)
            )

            orm_events = session.execute(query).scalars().all()

            return [self._to_domain_change_event(e) for e in orm_events]

    def count_unprocessed(self) -> int:
        """
        Count total unprocessed change events without loading them.

        Returns:
            Count of unprocessed ChangeEvent records

        Raises:
            RuntimeError: If database query fails
        """
        try:
            with self.session_factory() as session:
                query = select(func.count()).select_from(ChangeEvent).where(~ChangeEvent.processed)
                count = session.scalar(query)
                return count or 0
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to count unprocessed changes: {str(e)}") from e

    # Helper methods for domain conversion

    def _to_domain_change_event(self, orm_event: ChangeEvent) -> DomainChangeEvent:
        """Convert ORM ChangeEvent to domain entity."""
        return DomainChangeEvent(
            id=cast(str, orm_event.id),
            entity_id=cast(str, orm_event.entity_id),
            entity_type=cast(str, orm_event.entity_type),
            operation=ChangeOperation(orm_event.operation),
            new_state=cast(dict, orm_event.new_state),
            timestamp=cast(datetime, orm_event.timestamp),
            previous_state=cast(Optional[dict], orm_event.previous_state),
            user_id=cast(Optional[str], orm_event.user_id),
            change_reason=cast(Optional[str], orm_event.change_reason),
            batch_run_id=cast(Optional[str], orm_event.batch_run_id),
            processed=cast(bool, orm_event.processed),
        )
