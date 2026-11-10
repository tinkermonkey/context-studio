"""Pydantic schemas for a taxonomy's claims (#1518)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from domain.versioning.claims import (
    Claim,
    ClaimTriage,
    ClaimVerdict,
    NoteSource,
    Validity,
)

SCORE = Field(None, ge=0, le=3, description="0 to 3")


class ClaimInput(BaseModel):
    """One claim to add, or to replace by key."""

    key: str = Field(..., min_length=1, max_length=255, description='"<note_ref>#<n>"')
    text: str = Field(..., min_length=1, description="The claim, in a sentence or two")
    note_ref: str = Field(..., min_length=1, max_length=255, description="The note it came from")
    note_source: NoteSource = Field(..., description="maintainer or reviewer")
    note_text: Optional[str] = Field(None, description="The note's full text")
    subject_id: Optional[str] = Field(None, description="The entity the note was about")
    category_hint: Optional[str] = Field(None, max_length=100)
    affected_ids: list[str] = Field(
        default_factory=list,
        description="Entities the claim names; ids that match none move to unresolved_refs",
    )
    unresolved_refs: list[str] = Field(default_factory=list)
    proposed_change: Optional[str] = None

    def to_domain(self, taxonomy_id: str, source_run_id: Optional[str] = None) -> Claim:
        return Claim(taxonomy_id=taxonomy_id, source_run_id=source_run_id, **self.model_dump())


class ClaimsSubmitRequest(BaseModel):
    """Claims to add or replace, matched by key within the taxonomy."""

    claims: list[ClaimInput] = Field(..., min_length=1, max_length=1000)


class ClaimTriageSchema(BaseModel):
    """A decision model's answers about a claim."""

    validity: Validity
    validity_probabilities: dict[str, float] = Field(default_factory=dict)
    category: Optional[str] = None
    category_probabilities: dict[str, float] = Field(default_factory=dict)
    severity: Optional[int] = Field(None, description="0 cosmetic to 3 blocking")
    fix_scope: Optional[int] = Field(None, description="0 wording to 3 roadmap")
    addressed_by_proposal: Optional[float] = Field(
        None, description="Probability the pending definition already resolves it"
    )
    model: str
    calibrated: bool
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    run_id: Optional[str] = None
    triaged_at: datetime

    @classmethod
    def from_domain(cls, triage: ClaimTriage) -> "ClaimTriageSchema":
        return cls(**asdict(triage))


class ClaimVerdictRequest(BaseModel):
    """A person's verdict on a claim."""

    validity: Validity
    category: Optional[str] = Field(None, max_length=100)
    severity: Optional[int] = SCORE
    fix_scope: Optional[int] = SCORE
    rationale: str = ""

    def to_domain(self, adjudicated_by: str) -> ClaimVerdict:
        return ClaimVerdict(adjudicated_by=adjudicated_by, **self.model_dump())


class ClaimVerdictSchema(ClaimVerdictRequest):
    """A recorded verdict: benchmark gold."""

    adjudicated_by: str
    adjudicated_at: datetime

    @classmethod
    def from_domain(cls, verdict: ClaimVerdict) -> "ClaimVerdictSchema":
        return cls(**asdict(verdict))


class ClaimResponse(ClaimInput):
    """A stored claim, with its triage and verdict once given."""

    id: str
    taxonomy_id: str
    source_run_id: Optional[str] = None
    triage: Optional[ClaimTriageSchema] = None
    verdict: Optional[ClaimVerdictSchema] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, claim: Claim) -> "ClaimResponse":
        return cls(
            id=claim.id,
            taxonomy_id=claim.taxonomy_id,
            key=claim.key,
            text=claim.text,
            note_ref=claim.note_ref,
            note_source=claim.note_source,
            note_text=claim.note_text,
            subject_id=claim.subject_id,
            category_hint=claim.category_hint,
            affected_ids=claim.affected_ids,
            unresolved_refs=claim.unresolved_refs,
            proposed_change=claim.proposed_change,
            source_run_id=claim.source_run_id,
            triage=ClaimTriageSchema.from_domain(claim.triage) if claim.triage else None,
            verdict=ClaimVerdictSchema.from_domain(claim.verdict) if claim.verdict else None,
            created_at=claim.created_at,
            updated_at=claim.updated_at,
        )
