"""
SQLite adapter implementing versioning domain persistence.

Handles recording of change events to the audit trail table and implements
all persistence operations for the Version Control & Collaboration bounded context,
including entity versions, changesets, and proposals.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.models import (
    ChangeEvent,
    EntityVersion,
    Changeset,
    ChangesetEvent,
    Proposal,
)
from domain.versioning.entities import (
    ChangeEvent as DomainChangeEvent,
    EntityVersion as DomainEntityVersion,
    Changeset as DomainChangeset,
    Proposal as DomainProposal,
)
from domain.versioning.value_objects import ChangeState


class SQLiteChangeRepository:
    """
    SQLAlchemy-based repository for persisting versioning domain entities.

    Implements the ChangeRepository protocol, handling persistence of change events,
    entity versions, changesets, and proposals to SQLite.

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
        operation: str,
        new_state: dict,
        previous_state: Optional[dict] = None,
        user_id: Optional[str] = None,
        change_reason: Optional[str] = None,
        changeset_id: Optional[str] = None,
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
                processed=False,
            )

            session.add(change_event)
            session.commit()

            return cast(str, change_event.id)

    def get_changes(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[DomainChangeEvent]:
        """
        Retrieve change events with optional filters.

        Args:
            entity_id: Optional filter to changes for a specific entity
            since: Optional filter to changes after a specific timestamp
            limit: Maximum number of results to return

        Returns:
            List of matching ChangeEvent domain entities
        """
        with self.session_factory() as session:
            query = select(ChangeEvent)

            if entity_id:
                query = query.where(ChangeEvent.entity_id == entity_id)
            if since:
                query = query.where(ChangeEvent.timestamp >= since)

            query = query.order_by(ChangeEvent.timestamp.desc()).limit(limit)

            orm_events = session.execute(query).scalars().all()

            return [self._to_domain_change_event(e) for e in orm_events]

    def mark_processed(self, event_ids: list[str]) -> None:
        """
        Mark change events as processed (synchronized to remote).

        Args:
            event_ids: List of change event IDs to mark as processed
        """
        with self.session_factory() as session:
            query = select(ChangeEvent).where(ChangeEvent.id.in_(event_ids))
            events = session.execute(query).scalars().all()

            for event in events:
                event.processed = True

            session.commit()

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
                .where(not ChangeEvent.processed)
                .order_by(ChangeEvent.timestamp.asc())
                .limit(limit)
            )

            orm_events = session.execute(query).scalars().all()

            return [self._to_domain_change_event(e) for e in orm_events]

    # EntityVersion operations

    def save_version(self, version: DomainEntityVersion) -> None:
        """
        Persist an entity version snapshot.

        Args:
            version: The EntityVersion domain entity to save
        """
        with self.session_factory() as session:
            orm_version = EntityVersion(
                entity_id=version.entity_id,
                version=version.version,
                state=version.state,
                snapshot=version.snapshot,
                created_at=version.created_at,
                parent_version=version.parent_version,
            )

            session.add(orm_version)
            session.commit()

    def get_version(
        self, entity_id: str, version: int
    ) -> Optional[DomainEntityVersion]:
        """
        Retrieve a specific version of an entity.

        Args:
            entity_id: ID of the entity
            version: Version number

        Returns:
            The EntityVersion domain entity if found, None otherwise
        """
        with self.session_factory() as session:
            orm_version = session.get(EntityVersion, (entity_id, version))

            if orm_version:
                return self._to_domain_entity_version(orm_version)

            return None

    def get_latest_version(self, entity_id: str) -> Optional[DomainEntityVersion]:
        """
        Retrieve the most recent version of an entity.

        Args:
            entity_id: ID of the entity

        Returns:
            The latest EntityVersion domain entity if found, None otherwise
        """
        with self.session_factory() as session:
            query = (
                select(EntityVersion)
                .where(EntityVersion.entity_id == entity_id)
                .order_by(EntityVersion.version.desc())
                .limit(1)
            )

            orm_version = session.execute(query).scalar_one_or_none()

            if orm_version:
                return self._to_domain_entity_version(orm_version)

            return None

    def list_versions(self, entity_id: str) -> list[DomainEntityVersion]:
        """
        Retrieve all versions of an entity in order.

        Args:
            entity_id: ID of the entity

        Returns:
            List of EntityVersion domain entities in version order
        """
        with self.session_factory() as session:
            query = (
                select(EntityVersion)
                .where(EntityVersion.entity_id == entity_id)
                .order_by(EntityVersion.version.asc())
            )

            orm_versions = session.execute(query).scalars().all()

            return [self._to_domain_entity_version(v) for v in orm_versions]

    # Changeset operations

    def create_changeset(self, changeset: DomainChangeset) -> DomainChangeset:
        """
        Create a new changeset.

        Args:
            changeset: The Changeset domain entity to create

        Returns:
            The persisted Changeset domain entity
        """
        with self.session_factory() as session:
            orm_changeset = Changeset(
                id=changeset.id,
                name=changeset.name,
                description=changeset.description,
                state=changeset.state.value,
                created_at=changeset.created_at,
                updated_at=changeset.updated_at,
            )

            session.add(orm_changeset)
            session.commit()

            return changeset

    def get_changeset(self, changeset_id: str) -> Optional[DomainChangeset]:
        """
        Retrieve a changeset by ID.

        Args:
            changeset_id: ID of the changeset

        Returns:
            The Changeset domain entity if found, None otherwise
        """
        with self.session_factory() as session:
            orm_changeset = session.get(Changeset, changeset_id)

            if orm_changeset:
                return self._to_domain_changeset(orm_changeset, session)

            return None

    def update_changeset(self, changeset: DomainChangeset) -> DomainChangeset:
        """
        Update an existing changeset.

        Args:
            changeset: The Changeset domain entity to update

        Returns:
            The updated Changeset domain entity
        """
        with self.session_factory() as session:
            orm_changeset = session.get(Changeset, changeset.id)

            if orm_changeset:
                orm_changeset.name = changeset.name
                orm_changeset.description = changeset.description
                orm_changeset.state = changeset.state.value
                orm_changeset.updated_at = datetime.now(timezone.utc)

                session.commit()

            return changeset

    # Proposal operations

    def create_proposal(self, proposal: DomainProposal) -> DomainProposal:
        """
        Create a new proposal.

        Args:
            proposal: The Proposal domain entity to create

        Returns:
            The persisted Proposal domain entity
        """
        with self.session_factory() as session:
            orm_proposal = Proposal(
                id=proposal.id,
                changeset_id=proposal.changeset_id,
                state=proposal.state,
                submitted_at=proposal.submitted_at,
                reviewed_at=proposal.reviewed_at,
                reviewer_notes=proposal.reviewer_notes,
            )

            session.add(orm_proposal)
            session.commit()

            return proposal

    def get_proposal(self, proposal_id: str) -> Optional[DomainProposal]:
        """
        Retrieve a proposal by ID.

        Args:
            proposal_id: ID of the proposal

        Returns:
            The Proposal domain entity if found, None otherwise
        """
        with self.session_factory() as session:
            orm_proposal = session.get(Proposal, proposal_id)

            if orm_proposal:
                return self._to_domain_proposal(orm_proposal)

            return None

    def update_proposal(self, proposal: DomainProposal) -> DomainProposal:
        """
        Update an existing proposal.

        Args:
            proposal: The Proposal domain entity to update

        Returns:
            The updated Proposal domain entity
        """
        with self.session_factory() as session:
            orm_proposal = session.get(Proposal, proposal.id)

            if orm_proposal:
                orm_proposal.state = proposal.state
                orm_proposal.reviewed_at = proposal.reviewed_at
                orm_proposal.reviewer_notes = proposal.reviewer_notes

                session.commit()

            return proposal

    # Helper methods for domain conversion

    def _to_domain_change_event(self, orm_event: ChangeEvent) -> DomainChangeEvent:
        """Convert ORM ChangeEvent to domain entity."""
        return DomainChangeEvent(
            id=orm_event.id,
            entity_id=orm_event.entity_id,
            entity_type=orm_event.entity_type,
            operation=orm_event.operation,
            new_state=orm_event.new_state,
            timestamp=orm_event.timestamp,
            previous_state=orm_event.previous_state,
            user_id=orm_event.user_id,
            change_reason=orm_event.change_reason,
            changeset_id=orm_event.changeset_id,
            processed=orm_event.processed,
        )

    def _to_domain_entity_version(
        self, orm_version: EntityVersion
    ) -> DomainEntityVersion:
        """Convert ORM EntityVersion to domain entity."""
        return DomainEntityVersion(
            entity_id=orm_version.entity_id,
            version=orm_version.version,
            state=orm_version.state,
            snapshot=orm_version.snapshot,
            created_at=orm_version.created_at,
            parent_version=orm_version.parent_version,
        )

    def _to_domain_changeset(
        self, orm_changeset: Changeset, session: Session
    ) -> DomainChangeset:
        """Convert ORM Changeset to domain entity."""
        # Get event IDs for this changeset
        query = select(ChangesetEvent.change_event_id).where(
            ChangesetEvent.changeset_id == orm_changeset.id
        )
        event_ids = [r[0] for r in session.execute(query).all()]

        return DomainChangeset(
            id=orm_changeset.id,
            name=orm_changeset.name,
            description=orm_changeset.description,
            state=ChangeState(orm_changeset.state),
            created_at=orm_changeset.created_at,
            updated_at=orm_changeset.updated_at,
            event_ids=event_ids,
        )

    def _to_domain_proposal(self, orm_proposal: Proposal) -> DomainProposal:
        """Convert ORM Proposal to domain entity."""
        return DomainProposal(
            id=orm_proposal.id,
            changeset_id=orm_proposal.changeset_id,
            state=orm_proposal.state,
            submitted_at=orm_proposal.submitted_at,
            reviewed_at=orm_proposal.reviewed_at,
            reviewer_notes=orm_proposal.reviewer_notes,
        )
