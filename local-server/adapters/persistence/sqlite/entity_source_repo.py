"""SQLite repository for provenance rows (EntitySourceRepository port), in ``entity_sources``."""

from __future__ import annotations

from datetime import timezone
from typing import Sequence

from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import EntitySourceRecord
from domain.versioning.provenance import EntitySource


class SQLiteEntitySourceRepository:
    """EntitySourceRepository over local.db."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def add(self, sources: Sequence[EntitySource]) -> None:
        with self._session_factory() as session:
            session.add_all(_to_orm(source) for source in sources)
            session.commit()

    def list_for_entity(self, entity_id: str) -> list[EntitySource]:
        with self._session_factory() as session:
            rows = (
                session.query(EntitySourceRecord)
                .filter(EntitySourceRecord.entity_id == str(entity_id))
                .order_by(
                    EntitySourceRecord.created_at,
                    EntitySourceRecord.op_seq,
                    EntitySourceRecord.start,
                )
                .all()
            )
            return [_to_domain(row) for row in rows]

    def delete_for_proposal(self, proposal_id: str) -> int:
        with self._session_factory() as session:
            count = (
                session.query(EntitySourceRecord)
                .filter(EntitySourceRecord.proposal_id == str(proposal_id))
                .delete(synchronize_session=False)
            )
            session.commit()
            return count


def _to_orm(source: EntitySource) -> EntitySourceRecord:
    return EntitySourceRecord(
        id=source.id,
        entity_id=source.entity_id,
        entity_kind=source.entity_kind,
        source_id=source.source_id,
        proposal_id=source.proposal_id,
        op_seq=source.op_seq,
        page=source.page,
        start=source.start,
        end=source.end,
        quote=source.quote,
        created_at=source.created_at,
    )


def _to_domain(row: EntitySourceRecord) -> EntitySource:
    created_at = row.created_at
    if created_at is not None and created_at.tzinfo is None:  # stored as UTC, zone dropped
        created_at = created_at.replace(tzinfo=timezone.utc)
    return EntitySource(
        id=row.id,  # type: ignore[arg-type]
        entity_id=row.entity_id,  # type: ignore[arg-type]
        entity_kind=row.entity_kind,  # type: ignore[arg-type]
        source_id=row.source_id,  # type: ignore[arg-type]
        proposal_id=row.proposal_id,  # type: ignore[arg-type]
        op_seq=row.op_seq,  # type: ignore[arg-type]
        page=row.page,  # type: ignore[arg-type]
        start=row.start,  # type: ignore[arg-type]
        end=row.end,  # type: ignore[arg-type]
        quote=row.quote,  # type: ignore[arg-type]
        created_at=created_at,  # type: ignore[arg-type]
    )
