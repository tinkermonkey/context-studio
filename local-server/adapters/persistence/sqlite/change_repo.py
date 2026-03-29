"""
SQLite adapter implementing change event persistence.

Handles recording of domain events to the change_events audit trail table.
This adapter implements the change recording pattern described in the architecture,
where domain events are subscribed to and persisted as change records.
"""

import uuid
from datetime import datetime, timezone
from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.models import ChangeEvent


class SQLiteChangeRepository:
    """
    SQLAlchemy-based repository for persisting change events to the audit trail.

    Records domain events to the change_events table for versioning and
    audit trail purposes. Maintains referential integrity with ontology entities.

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

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: str,
        new_state: dict,
        previous_state: dict | None = None,
        user_id: str | None = None,
        change_reason: str | None = None,
        changeset_id: str | None = None,
    ) -> str:
        """
        Record a change event to the audit trail.

        Args:
            entity_id: ID of the entity that changed
            entity_type: Type of entity (e.g., 'extraction_result', 'pipeline_execution')
            operation: Type of operation ('create', 'update', 'delete')
            new_state: JSON snapshot of entity after change
            previous_state: JSON snapshot of entity before change (optional, for updates)
            user_id: Optional ID of user who made the change
            change_reason: Optional explanation of the change
            changeset_id: Optional ID of a changeset this event belongs to

        Returns:
            The ID of the recorded change event
        """
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
                changeset_id=changeset_id,
            )

            session.add(change_event)
            session.commit()

            return cast(str, change_event.id)
