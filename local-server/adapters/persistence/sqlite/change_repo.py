"""
SQLite adapter implementing versioning domain persistence.

Handles recording of change events to the audit trail table and implements
all persistence operations for the Version Control & Collaboration bounded context,
including entity versions, changesets, and proposals.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.models import (
    ChangeEvent,
    EntityVersion,
    Changeset,
    ChangesetEvent,
    Proposal,
    ConflictResolution,
)
from domain.versioning.entities import (
    ChangeEvent as DomainChangeEvent,
    EntityVersion as DomainEntityVersion,
    Changeset as DomainChangeset,
    Proposal as DomainProposal,
)
from domain.versioning.value_objects import (
    ChangeState,
    ProposalState,
    ChangeOperation,
    EntityVersionState,
    ChangeHistoryResult,
)
from domain.versioning.exceptions import VersionNotFoundError


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
        operation: ChangeOperation,
        new_state: dict,
        previous_state: Optional[dict] = None,
        user_id: Optional[str] = None,
        change_reason: Optional[str] = None,
        changeset_id: Optional[str] = None,
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
            changeset_id: Optional ID of a changeset this event belongs to
            batch_run_id: Optional ID of the batch run (import or extraction) that produced this change

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
                    changeset_id=changeset_id,
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
        limit: int = 100,
    ) -> ChangeHistoryResult:
        """
        Retrieve change events with optional filters.

        Args:
            entity_id: Optional filter to changes for a specific entity
            since: Optional filter to changes after a specific timestamp
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
            paginated_query = base_query.order_by(ChangeEvent.timestamp.desc()).limit(
                limit
            )
            orm_events = session.execute(paginated_query).scalars().all()

            events = [self._to_domain_change_event(e) for e in orm_events]
            return ChangeHistoryResult(events=tuple(events), total=total_count)

    def get_changes_by_ids(self, event_ids: list[str]) -> list[DomainChangeEvent]:
        """
        Retrieve change events by their IDs.

        Args:
            event_ids: List of change event IDs to retrieve

        Returns:
            List of matching ChangeEvent domain entities

        Raises:
            RuntimeError: If database operation fails
        """
        if not event_ids:
            return []

        try:
            with self.session_factory() as session:
                query = select(ChangeEvent).where(ChangeEvent.id.in_(event_ids))
                orm_events = session.execute(query).scalars().all()
                return [self._to_domain_change_event(e) for e in orm_events]
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to retrieve change events: {str(e)}") from e

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
            raise RuntimeError(
                f"Failed to mark change events as processed: {str(e)}"
            ) from e

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
                .order_by(ChangeEvent.timestamp.asc())
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
                query = (
                    select(func.count())
                    .select_from(ChangeEvent)
                    .where(~ChangeEvent.processed)
                )
                count = session.scalar(query)
                return count or 0
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to count unprocessed changes: {str(e)}") from e

    # EntityVersion operations

    def save_version(self, version: DomainEntityVersion) -> None:
        """
        Persist an entity version snapshot.

        Args:
            version: The EntityVersion domain entity to save

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_version = EntityVersion(
                    entity_id=version.entity_id,
                    version=version.version,
                    state=version.state.value,
                    snapshot=version.snapshot,
                    created_at=version.created_at,
                    parent_version=version.parent_version,
                )

                session.add(orm_version)
                session.commit()
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to save entity version: {str(e)}") from e

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
        Create a new changeset and persist associated event IDs to junction table.

        Args:
            changeset: The Changeset domain entity to create

        Returns:
            The persisted Changeset domain entity

        Raises:
            RuntimeError: If database operation fails
        """
        try:
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
                session.flush()

                # Persist event IDs to junction table
                for event_id in changeset.event_ids:
                    changeset_event = ChangesetEvent(
                        changeset_id=changeset.id,
                        change_event_id=event_id,
                    )
                    session.add(changeset_event)

                session.commit()

                return changeset
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to create changeset: {str(e)}") from e

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
        Update an existing changeset and persist associated event IDs to junction table.

        Args:
            changeset: The Changeset domain entity to update

        Returns:
            The updated Changeset domain entity

        Raises:
            VersionNotFoundError: If the changeset does not exist
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_changeset = session.get(Changeset, changeset.id)

                if not orm_changeset:
                    raise VersionNotFoundError(f"Changeset not found: {changeset.id}")

                orm_changeset.name = changeset.name
                orm_changeset.description = changeset.description
                orm_changeset.state = changeset.state.value
                orm_changeset.updated_at = changeset.updated_at

                # Delete existing event associations and re-insert with updated list
                session.query(ChangesetEvent).filter(
                    ChangesetEvent.changeset_id == changeset.id
                ).delete()

                for event_id in changeset.event_ids:
                    changeset_event = ChangesetEvent(
                        changeset_id=changeset.id,
                        change_event_id=event_id,
                    )
                    session.add(changeset_event)

                session.commit()

                return changeset
        except VersionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to update changeset: {str(e)}") from e

    # Proposal operations

    def create_proposal(self, proposal: DomainProposal) -> DomainProposal:
        """
        Create a new proposal.

        Args:
            proposal: The Proposal domain entity to create

        Returns:
            The persisted Proposal domain entity

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_proposal = Proposal(
                    id=proposal.id,
                    changeset_id=proposal.changeset_id,
                    state=proposal.state.value,
                    submitted_at=proposal.submitted_at,
                    reviewed_at=proposal.reviewed_at,
                    reviewer_notes=proposal.reviewer_notes,
                )

                session.add(orm_proposal)
                session.commit()

                return proposal
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to create proposal: {str(e)}") from e

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

        Raises:
            VersionNotFoundError: If the proposal does not exist
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_proposal = session.get(Proposal, proposal.id)

                if not orm_proposal:
                    raise VersionNotFoundError(f"Proposal not found: {proposal.id}")

                orm_proposal.state = proposal.state.value
                orm_proposal.reviewed_at = proposal.reviewed_at
                orm_proposal.reviewer_notes = proposal.reviewer_notes

                session.commit()

                return proposal
        except VersionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to update proposal: {str(e)}") from e

    def update_changeset_and_proposal_on_submit(
        self, changeset: DomainChangeset, proposal: DomainProposal
    ) -> tuple[DomainChangeset, DomainProposal]:
        """
        Atomically create proposal and update changeset on submit.

        Both operations succeed or both fail together within a single transaction.

        Args:
            changeset: The Changeset domain entity to update
            proposal: The Proposal domain entity to create

        Returns:
            Tuple of (updated Changeset, created Proposal)

        Raises:
            VersionNotFoundError: If the changeset does not exist
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_changeset = session.get(Changeset, changeset.id)

                if not orm_changeset:
                    raise VersionNotFoundError(f"Changeset not found: {changeset.id}")

                # Update changeset state and timestamp only (submit doesn't change other fields)
                orm_changeset.state = changeset.state.value
                orm_changeset.updated_at = changeset.updated_at

                # Create proposal
                orm_proposal = Proposal(
                    id=proposal.id,
                    changeset_id=proposal.changeset_id,
                    state=proposal.state.value,
                    submitted_at=proposal.submitted_at,
                    reviewed_at=proposal.reviewed_at,
                    reviewer_notes=proposal.reviewer_notes,
                )
                session.add(orm_proposal)

                # Commit both changes atomically
                session.commit()

                return changeset, proposal
        except VersionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to submit changeset: {str(e)}") from e

    def atomic_update_changeset_and_proposal(
        self, changeset: DomainChangeset, proposal: DomainProposal
    ) -> tuple[DomainChangeset, DomainProposal]:
        """
        Atomically update changeset and proposal on approve, reject, or merge.

        Both operations succeed or both fail together within a single transaction.

        Args:
            changeset: The Changeset domain entity to update
            proposal: The Proposal domain entity to update

        Returns:
            Tuple of (updated Changeset, updated Proposal)

        Raises:
            VersionNotFoundError: If the changeset or proposal does not exist
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_changeset = session.get(Changeset, changeset.id)

                if not orm_changeset:
                    raise VersionNotFoundError(f"Changeset not found: {changeset.id}")

                orm_proposal = session.get(Proposal, proposal.id)

                if not orm_proposal:
                    raise VersionNotFoundError(f"Proposal not found: {proposal.id}")

                # Update changeset
                orm_changeset.state = changeset.state.value
                orm_changeset.updated_at = changeset.updated_at

                # Update proposal
                orm_proposal.state = proposal.state.value
                orm_proposal.reviewed_at = proposal.reviewed_at
                orm_proposal.reviewer_notes = proposal.reviewer_notes

                # Commit both changes atomically
                session.commit()

                return changeset, proposal
        except VersionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise RuntimeError(
                f"Failed to update changeset and proposal: {str(e)}"
            ) from e

    def atomic_update_on_merge(
        self,
        changeset: DomainChangeset,
        proposal: DomainProposal,
        versions: list[DomainEntityVersion],
    ) -> tuple[DomainChangeset, DomainProposal]:
        """
        Atomically update changeset, proposal, and save entity versions on merge.

        The changeset and proposal state transition, along with all entity version
        snapshots, are persisted within a single transaction. If any operation fails,
        all changes are rolled back to maintain consistency between the merge state
        and version snapshots.

        Args:
            changeset: The Changeset domain entity with transitioned state
            proposal: The Proposal domain entity with transitioned state
            versions: List of EntityVersion snapshots to persist for merged entities

        Returns:
            Tuple of (updated Changeset, updated Proposal)

        Raises:
            VersionNotFoundError: If the changeset or proposal does not exist
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_changeset = session.get(Changeset, changeset.id)

                if not orm_changeset:
                    raise VersionNotFoundError(f"Changeset not found: {changeset.id}")

                orm_proposal = session.get(Proposal, proposal.id)

                if not orm_proposal:
                    raise VersionNotFoundError(f"Proposal not found: {proposal.id}")

                # Update changeset
                orm_changeset.state = changeset.state.value
                orm_changeset.updated_at = changeset.updated_at

                # Update proposal
                orm_proposal.state = proposal.state.value
                orm_proposal.reviewed_at = proposal.reviewed_at
                orm_proposal.reviewer_notes = proposal.reviewer_notes

                # Save all entity versions within the same transaction
                for version in versions:
                    orm_version = EntityVersion(
                        entity_id=version.entity_id,
                        version=version.version,
                        state=version.state.value,
                        snapshot=version.snapshot,
                        created_at=version.created_at,
                        parent_version=version.parent_version,
                    )
                    session.add(orm_version)

                # Commit all changes atomically
                session.commit()

                return changeset, proposal
        except VersionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to complete merge transaction: {str(e)}") from e

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
            changeset_id=cast(Optional[str], orm_event.changeset_id),
            batch_run_id=cast(Optional[str], orm_event.batch_run_id),
            processed=cast(bool, orm_event.processed),
        )

    def _to_domain_entity_version(
        self, orm_version: EntityVersion
    ) -> DomainEntityVersion:
        """Convert ORM EntityVersion to domain entity."""
        return DomainEntityVersion(
            entity_id=cast(str, orm_version.entity_id),
            version=cast(int, orm_version.version),
            state=EntityVersionState(cast(str, orm_version.state)),
            snapshot=cast(dict, orm_version.snapshot),
            created_at=cast(datetime, orm_version.created_at),
            parent_version=cast(Optional[int], orm_version.parent_version),
        )

    def _to_domain_changeset(
        self, orm_changeset: Changeset, session: Session
    ) -> DomainChangeset:
        """Convert ORM Changeset to domain entity."""
        # Get event IDs for this changeset
        query = select(ChangesetEvent.change_event_id).where(
            ChangesetEvent.changeset_id == orm_changeset.id
        )
        event_ids = cast(list[str], [r[0] for r in session.execute(query).all()])

        return DomainChangeset(
            id=cast(str, orm_changeset.id),
            name=cast(str, orm_changeset.name),
            description=cast(Optional[str], orm_changeset.description),
            _state=ChangeState(cast(str, orm_changeset.state)),
            created_at=cast(datetime, orm_changeset.created_at),
            updated_at=cast(datetime, orm_changeset.updated_at),
            event_ids=event_ids,
        )

    def _to_domain_proposal(self, orm_proposal: Proposal) -> DomainProposal:
        """Convert ORM Proposal to domain entity."""
        return DomainProposal(
            id=cast(str, orm_proposal.id),
            changeset_id=cast(str, orm_proposal.changeset_id),
            _state=ProposalState(orm_proposal.state),
            submitted_at=cast(datetime, orm_proposal.submitted_at),
            reviewed_at=cast(Optional[datetime], orm_proposal.reviewed_at),
            reviewer_notes=cast(Optional[str], orm_proposal.reviewer_notes),
        )

    def save_conflict_resolutions(
        self, proposal_id: str, resolutions: dict[str, dict[str, object]]
    ) -> None:
        """
        Persist conflict resolutions for a proposal.

        Args:
            proposal_id: ID of the proposal
            resolutions: Dict mapping entity_id -> {field_name: resolved_value}

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                # Delete existing resolutions for this proposal
                delete_query = select(ConflictResolution).where(
                    ConflictResolution.proposal_id == proposal_id
                )
                existing = session.execute(delete_query).scalars().all()
                for resolution in existing:
                    session.delete(resolution)

                # Insert new resolutions
                for entity_id, fields in resolutions.items():
                    for field_name, resolved_value in fields.items():
                        resolution = ConflictResolution(
                            id=str(uuid.uuid4()),
                            proposal_id=proposal_id,
                            entity_id=entity_id,
                            field_name=field_name,
                            resolved_value=str(resolved_value),
                        )
                        session.add(resolution)

                session.commit()
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to save conflict resolutions: {str(e)}") from e

    def get_conflict_resolutions(
        self, proposal_id: str
    ) -> dict[str, dict[str, object]]:
        """
        Retrieve persisted conflict resolutions for a proposal.

        Args:
            proposal_id: ID of the proposal

        Returns:
            Dict mapping entity_id -> {field_name: resolved_value}
        """
        with self.session_factory() as session:
            query = select(ConflictResolution).where(
                ConflictResolution.proposal_id == proposal_id
            )
            resolutions = session.execute(query).scalars().all()

            result: dict[str, dict[str, object]] = {}
            for resolution in resolutions:
                entity_id = cast(str, resolution.entity_id)
                if entity_id not in result:
                    result[entity_id] = {}
                result[entity_id][cast(str, resolution.field_name)] = cast(
                    str, resolution.resolved_value
                )

            return result
