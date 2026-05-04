"""
SQLite adapter implementing interchange domain persistence.

Handles persistence of ImportRun entities and their associated
change event correlations for the Data Interchange bounded context.
"""

from datetime import datetime
from typing import Optional, cast

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import (
    ImportRun as ImportRunORM,
    ChangeEvent as ChangeEventORM,
)
from domain.interchange.entities import (
    ImportRun,
    ImportRunStatus,
    ResolutionRecord,
)
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    SerializationFormat,
    MatchKind,
    ResolutionKind,
    ChangeEvent,
)


class SQLiteInterchangeRepository:
    """
    SQLAlchemy-based repository for interchange domain persistence.

    Concrete adapter implementing the ImportRunRepository port.

    Implements persistence operations for ImportRun entities and their
    change event correlations using SQLite.

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

    # ImportRun operations

    def create(self, import_run: ImportRun) -> ImportRun:
        """
        Persist an ImportRun entity.

        Args:
            import_run: The ImportRun to persist

        Returns:
            The persisted ImportRun

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_run = self._domain_to_orm(import_run)
                session.add(orm_run)
                session.commit()
                return import_run
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to create import run: {str(e)}") from e

    def get(self, import_run_id: str) -> Optional[ImportRun]:
        """
        Retrieve an ImportRun by ID.

        Args:
            import_run_id: The ID of the ImportRun to retrieve

        Returns:
            The ImportRun if found, None otherwise
        """
        try:
            with self.session_factory() as session:
                orm_run = session.get(ImportRunORM, import_run_id)
                if orm_run:
                    return self._orm_to_domain(orm_run)
                return None
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to get import run: {str(e)}") from e

    def list_all(self, limit: int = 100, offset: int = 0) -> list[ImportRun]:
        """
        Retrieve all ImportRuns with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of ImportRun entities
        """
        try:
            with self.session_factory() as session:
                query = (
                    select(ImportRunORM)
                    .order_by(ImportRunORM.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                orm_runs = session.execute(query).scalars().all()
                return [self._orm_to_domain(r) for r in orm_runs]
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to list import runs: {str(e)}") from e

    def list_by_status(
        self, status: ImportRunStatus, limit: int = 100, offset: int = 0
    ) -> list[ImportRun]:
        """
        Retrieve ImportRuns filtered by status.

        Args:
            status: The status to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of ImportRun entities with the given status
        """
        try:
            with self.session_factory() as session:
                query = (
                    select(ImportRunORM)
                    .where(ImportRunORM.status == status.value)
                    .order_by(ImportRunORM.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                orm_runs = session.execute(query).scalars().all()
                return [self._orm_to_domain(r) for r in orm_runs]
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to list import runs by status: {str(e)}") from e

    def count_all(self) -> int:
        """
        Count total number of import runs.

        Returns:
            Total count of all import runs
        """
        try:
            with self.session_factory() as session:
                query = select(func.count(ImportRunORM.id))
                count = session.execute(query).scalar()
                return count or 0
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to count import runs: {str(e)}") from e

    def count_by_status(self, status: ImportRunStatus) -> int:
        """
        Count import runs filtered by status.

        Args:
            status: The status to filter by

        Returns:
            Total count of import runs with the given status
        """
        try:
            with self.session_factory() as session:
                query = select(func.count(ImportRunORM.id)).where(
                    ImportRunORM.status == status.value
                )
                count = session.execute(query).scalar()
                return count or 0
        except SQLAlchemyError as e:
            raise RuntimeError(
                f"Failed to count import runs by status: {str(e)}"
            ) from e

    def update(self, import_run: ImportRun) -> ImportRun:
        """
        Update an existing ImportRun.

        Args:
            import_run: The ImportRun to update (with updated status and other fields)

        Returns:
            The updated ImportRun

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            with self.session_factory() as session:
                orm_run = session.get(ImportRunORM, import_run.id)
                if not orm_run:
                    raise RuntimeError(f"ImportRun not found: {import_run.id}")

                # Update fields
                orm_run.status = import_run.status.value
                orm_run.resolutions = self._serialize_resolutions(
                    import_run.resolutions
                )
                orm_run.affected_entity_ids = import_run.affected_entity_ids

                session.commit()
                return import_run
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to update import run: {str(e)}") from e

    def get_change_events_for_run(self, import_run_id: str) -> list[ChangeEvent]:
        """
        Retrieve all change events associated with an import run.

        Args:
            import_run_id: The ID of the import run

        Returns:
            List of ChangeEvent domain objects
        """
        try:
            with self.session_factory() as session:
                query = (
                    select(ChangeEventORM)
                    .where(ChangeEventORM.import_run_id == import_run_id)
                    .order_by(ChangeEventORM.timestamp.asc())
                )
                orm_events = session.execute(query).scalars().all()
                return [
                    ChangeEvent(
                        id=e.id,
                        timestamp=e.timestamp,
                        entity_id=e.entity_id,
                        entity_type=e.entity_type,
                        operation=e.operation,
                        new_state=e.new_state,
                        previous_state=e.previous_state,
                    )
                    for e in orm_events
                ]
        except SQLAlchemyError as e:
            raise RuntimeError(
                f"Failed to get change events for import run: {str(e)}"
            ) from e

    # Helper methods

    def _domain_to_orm(self, import_run: ImportRun) -> ImportRunORM:
        """Convert domain ImportRun to ORM model."""
        scope = import_run.scope

        return ImportRunORM(
            id=import_run.id,
            created_at=import_run.created_at,
            created_by=import_run.created_by,
            format=import_run.format.value,
            source_uri=import_run.source_uri,
            source_hash=import_run.source_hash,
            scope_type=scope.scope_type.value,
            scope_taxonomy_id=scope.taxonomy_id,
            scope_scheme_id=scope.scheme_id,
            scope_include_descendants=scope.include_descendants,
            scope_entity_ids=list(scope.entity_ids) if scope.entity_ids else None,
            resolutions=self._serialize_resolutions(import_run.resolutions),
            affected_entity_ids=import_run.affected_entity_ids,
            status=import_run.status.value,
        )

    def _orm_to_domain(self, orm_run: ImportRunORM) -> ImportRun:
        """Convert ORM ImportRun to domain entity.

        Raises:
            RuntimeError: If resolutions data is corrupted or invalid
        """
        # Reconstruct scope
        scope_type = SerializationScopeType(orm_run.scope_type)
        scope = SerializationScope(
            scope_type=scope_type,
            taxonomy_id=cast(str | None, orm_run.scope_taxonomy_id),
            scheme_id=cast(str | None, orm_run.scope_scheme_id),
            include_descendants=cast(bool, orm_run.scope_include_descendants or False),
            entity_ids=tuple(orm_run.scope_entity_ids or []),
        )

        # Reconstruct resolutions with error handling for corrupted data
        try:
            resolutions = self._deserialize_resolutions(
                cast(list[dict], orm_run.resolutions or [])
            )
        except ValueError as e:
            raise RuntimeError(
                f"Failed to deserialize resolutions for import run {orm_run.id}: {str(e)}"
            ) from e

        return ImportRun(
            id=cast(str, orm_run.id),
            created_at=cast(datetime, orm_run.created_at),
            created_by=cast(Optional[str], orm_run.created_by),
            format=SerializationFormat(cast(str, orm_run.format)),
            source_uri=cast(Optional[str], orm_run.source_uri),
            source_hash=cast(str, orm_run.source_hash),
            scope=scope,
            resolutions=resolutions,
            affected_entity_ids=cast(list[str], orm_run.affected_entity_ids or []),
            status=ImportRunStatus(orm_run.status),
        )

    @staticmethod
    def _serialize_resolutions(resolutions: list[ResolutionRecord]) -> list[dict]:
        """Serialize ResolutionRecords to JSON-compatible dicts."""
        return [
            {
                "match_kind": r.match_kind.value,
                "entity_id": r.entity_id,
                "resolution_chosen": r.resolution_chosen.value,
            }
            for r in resolutions
        ]

    @staticmethod
    def _deserialize_resolutions(
        resolutions_data: list[dict],
    ) -> list[ResolutionRecord]:
        """Deserialize JSON resolutions to ResolutionRecord objects.

        Raises:
            ValueError: If resolution data is corrupted or missing required fields
        """
        result = []
        for i, r in enumerate(resolutions_data):
            try:
                result.append(
                    ResolutionRecord(
                        match_kind=MatchKind(r["match_kind"]),
                        entity_id=r["entity_id"],
                        resolution_chosen=ResolutionKind(r["resolution_chosen"]),
                    )
                )
            except KeyError as e:
                raise ValueError(
                    f"Corrupted resolution record at index {i}: missing required field {str(e)}"
                ) from e
            except ValueError as e:
                raise ValueError(
                    f"Corrupted resolution record at index {i}: invalid enum value in {str(e)}"
                ) from e
        return result
