"""SQLite repository for claims (ClaimRepository port)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, sessionmaker

from adapters.persistence.sqlite.models import ClaimRecord
from domain.versioning.claims import Claim, ClaimFilter, ClaimTriage, ClaimVerdict


def _utc(value: datetime) -> datetime:
    """SQLite drops the zone; every stored time is UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def triage_to_json(triage: ClaimTriage) -> dict[str, Any]:
    """A triage as stored: enums as values, the time as ISO 8601."""
    data = asdict(triage)
    data["validity"] = triage.validity.value
    data["triaged_at"] = triage.triaged_at.isoformat()
    return data


def triage_from_json(data: dict[str, Any]) -> ClaimTriage:
    return ClaimTriage(**{**data, "triaged_at": datetime.fromisoformat(data["triaged_at"])})


def verdict_to_json(verdict: ClaimVerdict) -> dict[str, Any]:
    """A verdict as stored: enums as values, the time as ISO 8601."""
    data = asdict(verdict)
    data["validity"] = verdict.validity.value
    data["adjudicated_at"] = verdict.adjudicated_at.isoformat()
    return data


def verdict_from_json(data: dict[str, Any]) -> ClaimVerdict:
    return ClaimVerdict(
        **{**data, "adjudicated_at": datetime.fromisoformat(data["adjudicated_at"])}
    )


def _to_domain(row: ClaimRecord) -> Claim:
    return Claim(
        id=str(row.id),
        taxonomy_id=str(row.taxonomy_id),
        key=str(row.key),
        text=str(row.text),
        note_ref=str(row.note_ref),
        note_source=row.note_source,  # type: ignore[arg-type]
        note_text=row.note_text,  # type: ignore[arg-type]
        subject_id=row.subject_id,  # type: ignore[arg-type]
        category_hint=row.category_hint,  # type: ignore[arg-type]
        affected_ids=list(row.affected_ids or []),
        unresolved_refs=list(row.unresolved_refs or []),
        proposed_change=row.proposed_change,  # type: ignore[arg-type]
        source_run_id=row.source_run_id,  # type: ignore[arg-type]
        triage=triage_from_json(row.triage) if row.triage else None,  # type: ignore[arg-type]
        verdict=verdict_from_json(row.verdict) if row.verdict else None,  # type: ignore[arg-type]
        created_at=_utc(row.created_at),  # type: ignore[arg-type]
        updated_at=_utc(row.updated_at),  # type: ignore[arg-type]
    )


def _content(claim: Claim) -> dict[str, Any]:
    """The fields a re-submitted claim replaces."""
    return {
        "text": claim.text,
        "note_ref": claim.note_ref,
        "note_source": claim.note_source.value,
        "note_text": claim.note_text,
        "subject_id": claim.subject_id,
        "category_hint": claim.category_hint,
        "affected_ids": list(claim.affected_ids),
        "unresolved_refs": list(claim.unresolved_refs),
        "proposed_change": claim.proposed_change,
        "source_run_id": claim.source_run_id,
    }


class SQLiteClaimRepository:
    """ClaimRepository over local.db's claims table."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def upsert(self, claims: Sequence[Claim]) -> list[Claim]:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            ids = []
            for claim in claims:
                row = (
                    session.query(ClaimRecord)
                    .filter_by(taxonomy_id=claim.taxonomy_id, key=claim.key)
                    .one_or_none()
                )
                if row is None:
                    row = ClaimRecord(
                        id=claim.id,
                        taxonomy_id=claim.taxonomy_id,
                        key=claim.key,
                        triage=triage_to_json(claim.triage) if claim.triage else None,
                        verdict=verdict_to_json(claim.verdict) if claim.verdict else None,
                        created_at=claim.created_at,
                        updated_at=now,
                        **_content(claim),
                    )
                    session.add(row)
                else:
                    if row.text != claim.text:
                        # Answers about the old wording don't hold for the new one
                        row.triage = None  # type: ignore[assignment]
                        row.verdict = None  # type: ignore[assignment]
                    for name, value in _content(claim).items():
                        setattr(row, name, value)
                    row.updated_at = now  # type: ignore[assignment]
                ids.append(str(row.id))
            session.commit()
            rows = {
                str(r.id): r for r in session.query(ClaimRecord).filter(ClaimRecord.id.in_(ids))
            }
            return [_to_domain(rows[i]) for i in ids]

    def delete_for_note(
        self, taxonomy_id: str, note_ref: str, keep_keys: Sequence[str] = ()
    ) -> int:
        with self._session_factory() as session:
            query = session.query(ClaimRecord).filter_by(
                taxonomy_id=str(taxonomy_id), note_ref=note_ref
            )
            if keep_keys:
                query = query.filter(ClaimRecord.key.notin_(list(keep_keys)))
            deleted = query.delete(synchronize_session=False)
            session.commit()
            return int(deleted)

    def get(self, claim_id: str) -> Optional[Claim]:
        with self._session_factory() as session:
            row = session.get(ClaimRecord, str(claim_id))
            return _to_domain(row) if row else None

    def list_claims(
        self, filters: ClaimFilter, limit: Optional[int] = None, offset: int = 0
    ) -> list[Claim]:
        with self._session_factory() as session:
            query = self._filtered(session, filters).order_by(
                ClaimRecord.created_at, ClaimRecord.key
            )
            if offset:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            return [_to_domain(row) for row in query]

    def count_claims(self, filters: ClaimFilter) -> int:
        with self._session_factory() as session:
            return int(self._filtered(session, filters).with_entities(func.count()).scalar())

    def save_triage(self, claim_id: str, triage: ClaimTriage) -> None:
        self._set(claim_id, triage=triage_to_json(triage))

    def set_verdict(self, claim_id: str, verdict: Optional[ClaimVerdict]) -> None:
        self._set(claim_id, verdict=verdict_to_json(verdict) if verdict else None)

    def _set(self, claim_id: str, **values: Any) -> None:
        with self._session_factory() as session:
            row = session.get(ClaimRecord, str(claim_id))
            if row is None:
                return
            for name, value in values.items():
                setattr(row, name, value)
            row.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            session.commit()

    @staticmethod
    def _filtered(session: Session, filters: ClaimFilter) -> Query:
        query = session.query(ClaimRecord).filter(
            ClaimRecord.taxonomy_id == str(filters.taxonomy_id)
        )
        if filters.subject_id is not None:
            query = query.filter(ClaimRecord.subject_id == str(filters.subject_id))
        if filters.note_ref is not None:
            query = query.filter(ClaimRecord.note_ref == filters.note_ref)
        if filters.keys is not None:
            query = query.filter(ClaimRecord.key.in_(filters.keys))
        if filters.triaged is not None:
            query = query.filter(
                ClaimRecord.triage.isnot(None) if filters.triaged else ClaimRecord.triage.is_(None)
            )
        if filters.has_verdict is not None:
            query = query.filter(
                ClaimRecord.verdict.isnot(None)
                if filters.has_verdict
                else ClaimRecord.verdict.is_(None)
            )
        if filters.validity is not None:
            query = query.filter(
                func.json_extract(ClaimRecord.triage, "$.validity") == filters.validity.value
            )
        return query
