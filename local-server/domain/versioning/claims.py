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
        self.key = str(self.key or "").strip()
        self.note_ref = str(self.note_ref or "").strip()
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

        An `affected_ids` entry that names nothing in the taxonomy moves to
        `unresolved_refs`. A replaced claim keeps its id and creation time; it
        keeps its triage and verdict only if its text is unchanged.

        Raises:
            EntityNotFoundError: If the taxonomy doesn't exist
            ValueError: If a claim names another taxonomy or a subject outside
                this one, or two claims share a key
        """
        self._require_taxonomy(taxonomy_id)
        keys = [c.key for c in claims]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        if duplicates:
            raise ValueError(f"Claim keys repeat: {', '.join(duplicates)}")
        for claim in claims:
            if claim.taxonomy_id != taxonomy_id:
                raise ValueError(f"Claim {claim.key} names another taxonomy")
        known = self._in_taxonomy(
            taxonomy_id,
            {c.subject_id for c in claims if c.subject_id}
            | {i for c in claims for i in c.affected_ids},
        )
        for claim in claims:
            if claim.subject_id and claim.subject_id not in known:
                raise ValueError(
                    f"Claim {claim.key}: subject {claim.subject_id} is not in this taxonomy"
                )
        resolved = [
            replace(
                c,
                affected_ids=list(dict.fromkeys(i for i in c.affected_ids if i in known)),
                unresolved_refs=list(
                    dict.fromkeys(
                        [*c.unresolved_refs, *(i for i in c.affected_ids if i not in known)]
                    )
                ),
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

    def _in_taxonomy(self, taxonomy_id: str, ids: set[str]) -> set[str]:
        """
        The ids that name the taxonomy itself, or one of its schemes, classes,
        attribute definitions, or property definitions (a property definition
        belongs to the taxonomy of a class it joins; one joining none is shared).
        """
        repo = self._repo

        def class_in(class_id: Optional[str]) -> bool:
            cls = repo.get_class(class_id) if class_id else None
            return cls is not None and cls.taxonomy_id == taxonomy_id

        def belongs(entity_id: str) -> bool:
            if entity_id == taxonomy_id or class_in(entity_id):
                return True
            scheme = repo.get_concept_scheme(entity_id)
            if scheme is not None:
                return scheme.taxonomy_id == taxonomy_id
            attribute = repo.get_attribute_definition(entity_id)
            if attribute is not None:
                return class_in(attribute.class_id)
            prop = repo.get_property_definition(entity_id)
            if prop is not None:
                joined = [c for c in (prop.domain_class_id, prop.range_class_id) if c]
                return not joined or any(class_in(c) for c in joined)
            return False

        return {entity_id for entity_id in ids if belongs(entity_id)}


@dataclass(frozen=True)
class TriageScore:
    """
    How a decision model's triage compares with people's verdicts, with the
    metrics of DR's triage-bench.ts.

    Attributes:
        n: Claims with both a triage and a verdict
        validity_accuracy: Share whose triage validity matches the verdict
        mean_p_gold_validity: Mean probability the triage gave the verdict's validity
            (0 when the model gave no probability for it; DR's bench falls back to
            the answer's confidence, which a triage doesn't keep)
        category_accuracy: Share whose category matches (verdicts with a category)
        severity_mae, severity_within_1: Severity error (verdicts with a severity),
            on the saved 0-3 level where DR scores the expected (fractional) level
        fix_scope_mae: Fix-scope error (verdicts with a fix scope)
        median_latency_ms, mean_cost_usd: Per claim
        misses: Keys whose triage validity differs from the verdict
    """

    n: int
    validity_accuracy: Optional[float]
    mean_p_gold_validity: Optional[float]
    category_accuracy: Optional[float]
    severity_mae: Optional[float]
    severity_within_1: Optional[float]
    fix_scope_mae: Optional[float]
    median_latency_ms: Optional[float]
    mean_cost_usd: Optional[float]
    misses: tuple[str, ...] = ()


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def score_triage(claims: Sequence[Claim]) -> TriageScore:
    """Score the triage of the claims that have both a triage and a verdict."""
    rows = [(c, c.triage, c.verdict) for c in claims if c.triage and c.verdict]
    triages = [t for _, t, _ in rows]
    verdicts = [v for _, _, v in rows]
    pairs = list(zip(triages, verdicts))
    categorised = [(t, v) for t, v in pairs if v.category is not None]
    severities = [
        abs(t.severity - v.severity)
        for t, v in pairs
        if t.severity is not None and v.severity is not None
    ]
    fix_scopes = [
        abs(t.fix_scope - v.fix_scope)
        for t, v in pairs
        if t.fix_scope is not None and v.fix_scope is not None
    ]
    latencies = sorted(t.latency_ms for t in triages if t.latency_ms is not None)
    return TriageScore(
        n=len(rows),
        validity_accuracy=_mean([float(t.validity == v.validity) for t, v in pairs]),
        mean_p_gold_validity=_mean(
            [t.validity_probabilities.get(v.validity.value, 0.0) for t, v in pairs]
        ),
        category_accuracy=_mean([float(t.category == v.category) for t, v in categorised]),
        severity_mae=_mean([float(e) for e in severities]),
        severity_within_1=_mean([float(e <= 1) for e in severities]),
        fix_scope_mae=_mean([float(e) for e in fix_scopes]),
        median_latency_ms=latencies[len(latencies) // 2] if latencies else None,
        mean_cost_usd=_mean([t.cost_usd or 0.0 for t in triages]),
        misses=tuple(c.key for c, t, v in rows if t.validity != v.validity),
    )
