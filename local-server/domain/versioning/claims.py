"""
Claims: atomic statements about a taxonomy, split from reviewer and maintainer notes.

A note often mixes several points ("the definition overlaps X, and attribute y
should be required"). A claim is one of them, naming the entities it affects.
Triage asks a decision model about each claim (is it a real defect, how severe,
how big a fix), and a person may record a verdict that becomes benchmark gold.

A claim changes nothing. It is not a proposal operation: it can name several
entities and outlives any one proposal. Changes come from proposals, which a
claim may later point to.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional, Sequence
from uuid import uuid4

from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.ports import OntologyRepository

if TYPE_CHECKING:
    # The port module imports the entities below
    from domain.versioning.ports import ClaimRepository

# Severity and fix scope are DR's four-level scores, 0 to 3.
#   severity:  0 cosmetic, 1 minor, 2 significant, 3 blocking
#   fix_scope: 0 wording, 1 additive, 2 breaking, 3 roadmap
SCORE_LEVELS = range(0, 4)


class NoteSource(str, Enum):
    """Whose note a claim came from."""

    MAINTAINER = "maintainer"
    REVIEWER = "reviewer"


class Validity(str, Enum):
    """Whether a claim points at a real problem."""

    REAL_DEFECT = "real_defect"
    WORKS_AS_DESIGNED = "works_as_designed"
    JUDGMENT_CALL = "judgment_call"
    OUT_OF_SCOPE = "out_of_scope"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_score(name: str, value: Optional[int]) -> None:
    if value is not None and value not in SCORE_LEVELS:
        raise ValueError(f"{name} must be 0 to 3, not {value}")


@dataclass
class ClaimTriage:
    """
    A decision model's answers about one claim.

    Attributes:
        validity: The most likely validity
        validity_probabilities: Probability per validity option
        category: The most likely category (the taxonomy's own vocabulary)
        category_probabilities: Probability per category
        severity, fix_scope: Scores 0 to 3
        addressed_by_proposal: Probability that the pending definition already
            resolves the claim; None when there was no pending definition
        model: The decision model instance that answered
        calibrated: False when the probabilities came from an uncalibrated model
        cost_usd, latency_ms: What the answer cost
        run_id: The triage run, if one produced it
        triaged_at: When
    """

    validity: Validity
    model: str
    validity_probabilities: dict[str, float] = field(default_factory=dict)
    category: Optional[str] = None
    category_probabilities: dict[str, float] = field(default_factory=dict)
    severity: Optional[int] = None
    fix_scope: Optional[int] = None
    addressed_by_proposal: Optional[float] = None
    calibrated: bool = True
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    run_id: Optional[str] = None
    triaged_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validity = Validity(self.validity)
        _check_score("severity", self.severity)
        _check_score("fix_scope", self.fix_scope)


@dataclass
class ClaimVerdict:
    """
    A person's judgment of a claim: the gold triage is scored against.

    Attributes:
        validity, category, severity, fix_scope: As in ClaimTriage
        rationale: Why
        adjudicated_by: Who: "user", or an import's name such as "dr-bench-gold"
        adjudicated_at: When
    """

    validity: Validity
    adjudicated_by: str
    rationale: str = ""
    category: Optional[str] = None
    severity: Optional[int] = None
    fix_scope: Optional[int] = None
    adjudicated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validity = Validity(self.validity)
        _check_score("severity", self.severity)
        _check_score("fix_scope", self.fix_scope)
        if not self.adjudicated_by.strip():
            raise ValueError("adjudicated_by is required")


@dataclass
class Claim:
    """
    One atomic claim about a taxonomy.

    Attributes:
        taxonomy_id: The taxonomy it is about
        key: Stable within the taxonomy: "<note_ref>#<n>" (DR's claim_id)
        text: The claim, in one sentence or two
        note_ref: The note it came from (a client's note id, an operation or a decision)
        note_source: A maintainer's or a reviewer's note
        note_text: The note's full text
        subject_id: The entity the note was about, if any
        category_hint: The splitter's guess at a category
        affected_ids: The entities the claim names
        unresolved_refs: Names in the claim that matched no entity
        proposed_change: The change the note suggests, if it suggests one
        source_run_id: The run that split it, if one did
        triage: The decision model's answers, once triaged
        verdict: A person's judgment, once given
        id, created_at, updated_at: Identity and timestamps
    """

    taxonomy_id: str
    key: str
    text: str
    note_ref: str
    note_source: NoteSource
    note_text: Optional[str] = None
    subject_id: Optional[str] = None
    category_hint: Optional[str] = None
    affected_ids: list[str] = field(default_factory=list)
    unresolved_refs: list[str] = field(default_factory=list)
    proposed_change: Optional[str] = None
    source_run_id: Optional[str] = None
    triage: Optional[ClaimTriage] = None
    verdict: Optional[ClaimVerdict] = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.note_source = NoteSource(self.note_source)
        for name in ("key", "text", "note_ref"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"A claim's {name} is required")


@dataclass(frozen=True)
class ClaimFilter:
    """
    Which of a taxonomy's claims to list. Unset fields don't filter.

    Attributes:
        taxonomy_id: The taxonomy
        subject_id: Only claims about this entity
        note_ref: Only claims from this note
        triaged: Only triaged (True) or untriaged (False) claims
        has_verdict: Only claims with (True) or without (False) a verdict
        validity: Only claims whose triage found this validity
        keys: Only these claim keys
    """

    taxonomy_id: str
    subject_id: Optional[str] = None
    note_ref: Optional[str] = None
    triaged: Optional[bool] = None
    has_verdict: Optional[bool] = None
    validity: Optional[Validity] = None
    keys: Optional[tuple[str, ...]] = None


class ClaimService:
    """Submit, list, triage and judge a taxonomy's claims."""

    def __init__(self, claims: ClaimRepository, ontology_repo: OntologyRepository) -> None:
        self._claims = claims
        self._repo = ontology_repo

    def submit(self, taxonomy_id: str, claims: Sequence[Claim]) -> list[Claim]:
        """
        Add or replace claims, matched by key within the taxonomy.

        An `affected_ids` entry that names no entity moves to `unresolved_refs`.
        A replaced claim keeps its id and creation time; it keeps its triage and
        verdict only if its text is unchanged.

        Raises:
            EntityNotFoundError: If the taxonomy or a subject_id doesn't exist
            ValueError: If a claim names another taxonomy, or two share a key
        """
        self._require_taxonomy(taxonomy_id)
        keys = [c.key for c in claims]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        if duplicates:
            raise ValueError(f"Claim keys repeat: {', '.join(duplicates)}")
        for claim in claims:
            if claim.taxonomy_id != taxonomy_id:
                raise ValueError(f"Claim {claim.key} names another taxonomy")
        subjects = {c.subject_id for c in claims if c.subject_id}
        missing_subjects = sorted(subjects - self._existing(subjects))
        if missing_subjects:
            raise EntityNotFoundError("Entity", missing_subjects[0])
        affected = {i for c in claims for i in c.affected_ids}
        existing = self._existing(affected)
        resolved = [
            replace(
                c,
                affected_ids=[i for i in c.affected_ids if i in existing],
                unresolved_refs=[
                    *c.unresolved_refs,
                    *(i for i in c.affected_ids if i not in existing),
                ],
            )
            for c in claims
        ]
        return self._claims.upsert(resolved)

    def get(self, claim_id: str) -> Claim:
        """
        Raises:
            EntityNotFoundError: If there is no such claim
        """
        claim = self._claims.get(claim_id)
        if claim is None:
            raise EntityNotFoundError("Claim", claim_id)
        return claim

    def list_claims(
        self, filters: ClaimFilter, limit: Optional[int] = None, offset: int = 0
    ) -> list[Claim]:
        """
        The taxonomy's claims, oldest first.

        Raises:
            EntityNotFoundError: If the taxonomy doesn't exist
        """
        self._require_taxonomy(filters.taxonomy_id)
        return self._claims.list_claims(filters, limit, offset)

    def count_claims(self, filters: ClaimFilter) -> int:
        """How many claims `list_claims` would return without a limit."""
        self._require_taxonomy(filters.taxonomy_id)
        return self._claims.count_claims(filters)

    def save_triage(self, claim_id: str, triage: ClaimTriage) -> Claim:
        """
        Record a decision model's answers on a claim.

        Raises:
            EntityNotFoundError: If there is no such claim
        """
        self.get(claim_id)
        self._claims.save_triage(claim_id, triage)
        return self.get(claim_id)

    def set_verdict(self, claim_id: str, verdict: Optional[ClaimVerdict]) -> Claim:
        """
        Record (or, with None, clear) a person's verdict on a claim.

        Raises:
            EntityNotFoundError: If there is no such claim
        """
        self.get(claim_id)
        self._claims.set_verdict(claim_id, verdict)
        return self.get(claim_id)

    def _require_taxonomy(self, taxonomy_id: str) -> None:
        if self._repo.get_taxonomy(taxonomy_id) is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

    def _existing(self, ids: set[str]) -> set[str]:
        """The ids that name an ontology entity, property or attribute definition."""
        if not ids:
            return set()
        found = set(self._repo.get_entity_titles(sorted(ids)))
        for entity_id in ids - found:
            if self._repo.get_property_definition(entity_id) or self._repo.get_attribute_definition(
                entity_id
            ):
                found.add(entity_id)
        return found
