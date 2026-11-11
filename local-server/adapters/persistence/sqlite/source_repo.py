"""SQLite repository for sources (SourceRepository port, #1551)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, defer, sessionmaker

from adapters.persistence.sqlite.models import SourceRecord
from domain.extraction.sources import Source, SourceHeading, SourceStatus


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite drops the zone; every stored time is UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _to_domain(row: SourceRecord, with_text: bool = True) -> Source:
    """A row as a Source; without its text (deferred in lists) when with_text is False."""
    return Source(
        id=str(row.id),
        taxonomy_id=str(row.taxonomy_id),
        dataset_id=str(row.dataset_id),
        kind=row.kind,  # type: ignore[arg-type]
        title=str(row.title),
        origin=row.origin,  # type: ignore[arg-type]
        content_type=row.content_type,  # type: ignore[arg-type]
        bytes=int(row.bytes),  # type: ignore[arg-type]
        pages=int(row.pages),  # type: ignore[arg-type]
        chars=int(row.chars),  # type: ignore[arg-type]
        text=str(row.text) if with_text else "",
        page_starts=[int(s) for s in row.page_starts or []],  # type: ignore[union-attr]
        headings=[SourceHeading(**h) for h in row.headings or []],  # type: ignore[union-attr]
        status=row.status,  # type: ignore[arg-type]
        failure=row.failure,  # type: ignore[arg-type]
        failure_detail=row.failure_detail,  # type: ignore[arg-type]
        created_at=_utc(row.created_at),  # type: ignore[arg-type]
        updated_at=_utc(row.updated_at),  # type: ignore[arg-type]
        removed_at=_utc(row.removed_at),  # type: ignore[arg-type]
    )


def _columns(source: Source) -> dict:
    return {
        "taxonomy_id": source.taxonomy_id,
        "dataset_id": source.dataset_id,
        "kind": source.kind.value,
        "title": source.title,
        "origin": source.origin,
        "content_type": source.content_type,
        "bytes": source.bytes,
        "pages": source.pages,
        "chars": source.chars,
        "text": source.text,
        "page_starts": list(source.page_starts),
        "headings": [
            {"start": h.start, "title": h.title, "level": h.level} for h in source.headings
        ],
        "status": source.status.value,
        "failure": source.failure.value if source.failure else None,
        "failure_detail": source.failure_detail,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
        "removed_at": source.removed_at,
    }


class SQLiteSourceRepository:
    """SourceRepository over local.db's sources table."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def save(self, source: Source) -> Source:
        with self._session_factory() as session:
            row = session.get(SourceRecord, source.id)
            if row is None:
                row = SourceRecord(id=source.id, **_columns(source))
                session.add(row)
            else:
                for name, value in _columns(source).items():
                    setattr(row, name, value)
            session.commit()
            return _to_domain(row)

    def get(self, source_id: str) -> Optional[Source]:
        with self._session_factory() as session:
            row = session.get(SourceRecord, str(source_id))
            return _to_domain(row) if row else None

    def list_sources(
        self,
        taxonomy_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        status: Optional[SourceStatus] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Source]:
        with self._session_factory() as session:
            query = (
                self._filtered(session, taxonomy_id, dataset_id, status)
                .options(defer(SourceRecord.text))
                .order_by(SourceRecord.created_at.desc(), SourceRecord.id)
            )
            if offset:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            return [_to_domain(row, with_text=False) for row in query]

    def count_sources(
        self,
        taxonomy_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        status: Optional[SourceStatus] = None,
    ) -> int:
        with self._session_factory() as session:
            query = self._filtered(session, taxonomy_id, dataset_id, status)
            return int(query.with_entities(func.count(SourceRecord.id)).scalar())

    @staticmethod
    def _filtered(
        session: Session,
        taxonomy_id: Optional[str],
        dataset_id: Optional[str],
        status: Optional[SourceStatus],
    ) -> Query:
        query = session.query(SourceRecord).filter(SourceRecord.removed_at.is_(None))
        if taxonomy_id is not None:
            query = query.filter(SourceRecord.taxonomy_id == str(taxonomy_id))
        if dataset_id is not None:
            query = query.filter(SourceRecord.dataset_id == str(dataset_id))
        if status is not None:
            query = query.filter(SourceRecord.status == SourceStatus(status).value)
        return query
