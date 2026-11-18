"""
Request and response schemas for comparing two pipelines' proposals for the
same source (domain.pipelines.proposal_comparison).
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from adapters.web.schemas.proposals import ProposalOriginResponse
from domain.pipelines.proposal_comparison import (
    DEFAULT_SAMPLE_SIZE,
    ComparisonGroup,
    PairState,
    Verdict,
)
from domain.versioning.proposal_service import MAX_REVIEW_MS
from domain.versioning.proposals import CopyOutcome, OperationStatus, RejectionReason

# The largest sample the comparison draws
MAX_SAMPLE_SIZE = 500


class ComparedProposalResponse(BaseModel):
    """One of the two proposals compared."""

    proposal_id: str
    status: str = Field(..., description="open, done or reverted")
    origin: Optional[ProposalOriginResponse] = Field(
        None, description="The pipeline implementation and version that produced it"
    )


class ComparedClassResponse(BaseModel):
    """A class an operation gives its individual."""

    id: str
    title: str


class ComparedAlternativeResponse(BaseModel):
    """A near match the operation lists: an individual already in the dataset."""

    kind: Literal["existing"] = "existing"
    entity_id: str
    similarity: Optional[float] = None
    title: Optional[str] = Field(None, description="Its current title; null if it is gone")


class ComparedOperationResponse(BaseModel):
    """One proposal's copy of a pair's element: its individual create."""

    operation_id: str
    seq: int
    title: str = Field(..., description="The title it applies (an edit's, if edited)")
    classes: list[ComparedClassResponse] = Field(
        ..., description="The classes it applies (an edit's, if edited)"
    )
    status: OperationStatus
    reason: Optional[str] = None
    reason_code: Optional[RejectionReason] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    alternatives: list[ComparedAlternativeResponse] = Field(default_factory=list)
    lacks_passage: bool = Field(
        False, description="It cites no passage in the source: a person decides it"
    )
    comparison: Optional[dict[str, Any]] = Field(
        None,
        description="Its decision's comparison record, when it was decided comparing: "
        "{with_proposal_id, with_operation_id, verdict, sample, bulk}",
    )


class PairResponse(BaseModel):
    """One element as the two proposals propose it."""

    pair_id: str = Field(..., description="Stable id of the pair")
    group: ComparisonGroup
    in_sample: bool = Field(..., description="One of the agreements to check first")
    state: PairState
    a: Optional[ComparedOperationResponse] = Field(None, description="A's copy; null if none")
    b: Optional[ComparedOperationResponse] = Field(None, description="B's copy; null if none")


class SampleResponse(BaseModel):
    """How far the check of the agreements' sample has got."""

    size: int = Field(..., description="Same-class pairs in the sample")
    checked: int = Field(..., description="Of them, decided")
    changed: int = Field(
        ...,
        description="Of the decided, those whose decision changed what both pipelines agreed "
        "on (another class, not an element, an edit)",
    )


class ComparisonCountsResponse(BaseModel):
    same_class: int
    class_differs: int
    only_a: int
    only_b: int
    open: int = Field(..., description="Pairs not decided yet")


class ProposalComparisonResponse(BaseModel):
    """Two individual extractions of one source, their individual creates paired."""

    a: ComparedProposalResponse
    b: ComparedProposalResponse
    taxonomy_id: str
    dataset_id: Optional[str] = None
    source_id: str
    pairs: list[PairResponse] = Field(
        ..., description="Ordered by group (same_class, class_differs, only_a, only_b), then seq"
    )
    counts: ComparisonCountsResponse
    sample: SampleResponse


class PairDecisionRequest(BaseModel):
    """A decision on one pair, taken once for both proposals."""

    a_operation_id: Optional[str] = Field(
        None,
        description="A's copy (from the pair). Name both copies; one alone only when the "
        "pair has one, or the other is already decided",
    )
    b_operation_id: Optional[str] = Field(None, description="B's copy (from the pair)")
    verdict: Verdict = Field(
        ...,
        description="keep: land A's copy (or the only one given), whose classes the copies "
        "share; a_class / b_class: land that copy with its classes; not_element: reject every "
        "copy given. The other copy closes as a duplicate of the landed one",
    )
    reason_code: Optional[RejectionReason] = Field(
        None, description="not_element only: why (other when omitted)"
    )
    match_entity_id: Optional[str] = Field(
        None, description="A near match the landing copy lists, to apply it as instead"
    )
    review_ms: Optional[int] = Field(
        None,
        ge=0,
        le=MAX_REVIEW_MS,
        description="The time spent on the pair, recorded whole on the landed copy's decision",
    )


class PairDecisionResponse(BaseModel):
    """A decided pair, as it stands after the decision."""

    pair: PairResponse
    outcome: CopyOutcome = Field(
        ..., description="landed, rejected (not_element) or failed (the landing copy failed)"
    )
    failure_reason: Optional[str] = None
    sample: SampleResponse


class AcceptRestRequest(BaseModel):
    """Accept the agreements outside the sample, once the sample is checked."""

    sample_size: int = Field(
        DEFAULT_SAMPLE_SIZE,
        ge=0,
        le=MAX_SAMPLE_SIZE,
        description="The sample checked: at least 10, or every agreement when there are fewer",
    )


class PairFailureResponse(BaseModel):
    pair_id: str
    reason: str


class PairSkippedResponse(BaseModel):
    pair_id: str
    why: Literal["near_match", "no_passage"]


class AcceptRestResponse(BaseModel):
    """What accepting the rest of the agreements did."""

    landed: int
    failed: list[PairFailureResponse]
    skipped: list[PairSkippedResponse] = Field(
        ..., description="Left for a person: a copy lists near matches, or cites no passage"
    )
    sample: SampleResponse
