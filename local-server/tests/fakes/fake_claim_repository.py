"""In-memory ClaimRepository for domain tests; behaves like the SQLite one."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional, Sequence

from domain.versioning.claims import Claim, ClaimFilter, ClaimTriage, ClaimVerdict


class FakeClaimRepository:
    """Stores claims in a dict keyed by id."""

    def __init__(self) -> None:
        self.claims: dict[str, Claim] = {}

    def upsert(self, claims: Sequence[Claim]) -> list[Claim]:
        now = datetime.now(timezone.utc)
        stored = []
        for claim in claims:
            existing = self._by_key(claim.taxonomy_id, claim.key)
            if existing is None:
                saved = replace(claim, updated_at=now)
            else:
                same_text = existing.text == claim.text
                saved = replace(
                    claim,
                    id=existing.id,
                    created_at=existing.created_at,
                    updated_at=now,
                    triage=existing.triage if same_text else None,
                    verdict=existing.verdict if same_text else None,
                )
            self.claims[saved.id] = saved
            stored.append(saved)
        return stored

    def delete_for_note(self, taxonomy_id: str, note_ref: str) -> int:
        doomed = [
            c.id
            for c in self.claims.values()
            if c.taxonomy_id == taxonomy_id and c.note_ref == note_ref
        ]
        for claim_id in doomed:
            del self.claims[claim_id]
        return len(doomed)

    def get(self, claim_id: str) -> Optional[Claim]:
        return self.claims.get(claim_id)

    def list_claims(
        self, filters: ClaimFilter, limit: Optional[int] = None, offset: int = 0
    ) -> list[Claim]:
        matching = sorted(
            (c for c in self.claims.values() if self._matches(c, filters)),
            key=lambda c: (c.created_at, c.key),
        )
        end = None if limit is None else offset + limit
        return matching[offset:end]

    def count_claims(self, filters: ClaimFilter) -> int:
        return len(self.list_claims(filters))

    def save_triage(self, claim_id: str, triage: ClaimTriage) -> None:
        self._set(claim_id, triage=triage)

    def set_verdict(self, claim_id: str, verdict: Optional[ClaimVerdict]) -> None:
        self._set(claim_id, verdict=verdict)

    def _set(self, claim_id: str, **values) -> None:
        if claim_id in self.claims:
            self.claims[claim_id] = replace(
                self.claims[claim_id], updated_at=datetime.now(timezone.utc), **values
            )

    def _by_key(self, taxonomy_id: str, key: str) -> Optional[Claim]:
        return next(
            (c for c in self.claims.values() if c.taxonomy_id == taxonomy_id and c.key == key),
            None,
        )

    @staticmethod
    def _matches(claim: Claim, f: ClaimFilter) -> bool:
        return (
            claim.taxonomy_id == f.taxonomy_id
            and (f.subject_id is None or claim.subject_id == f.subject_id)
            and (f.note_ref is None or claim.note_ref == f.note_ref)
            and (f.keys is None or claim.key in f.keys)
            and (f.triaged is None or (claim.triage is not None) == f.triaged)
            and (f.has_verdict is None or (claim.verdict is not None) == f.has_verdict)
            and (
                f.validity is None
                or (claim.triage is not None and claim.triage.validity == f.validity)
            )
        )
