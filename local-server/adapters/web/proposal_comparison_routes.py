"""
FastAPI routes comparing two pipelines' proposals for the same source: the
pairs, a decision on one pair taken once for both proposals, and accepting the
rest of the agreements once their sample is checked.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from adapters.web.dependencies import get_proposal_comparison_service
from adapters.web.schemas.proposal_comparison import (
    MAX_SAMPLE_SIZE,
    AcceptRestRequest,
    AcceptRestResponse,
    ComparedAlternativeResponse,
    ComparedClassResponse,
    ComparedOperationResponse,
    ComparedProposalResponse,
    ComparisonCountsResponse,
    PairDecisionRequest,
    PairDecisionResponse,
    PairFailureResponse,
    PairResponse,
    PairSkippedResponse,
    ProposalComparisonResponse,
    SampleResponse,
)
from adapters.web.schemas.proposals import ProposalOriginResponse
from domain.pipelines.proposal_comparison import (
    DEFAULT_SAMPLE_SIZE,
    Comparison,
    InvalidPairDecisionError,
    Pair,
    PairDecision,
    ProposalComparisonService,
    ProposalsNotComparableError,
    SampleStats,
    SampleUncheckedError,
    comparison_lacks_passage,
)
from domain.versioning.exceptions import ChangeProposalNotFoundError, ChangeProposalStateError
from domain.versioning.proposals import ChangeProposal, ProposedOperation
from domain.versioning.provenance import SOURCE_ID
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

_logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["proposals"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"description": "A proposal does not exist"},
    422: {
        "description": (
            "not_comparable: the same proposal twice, or not two individual "
            "extractions of one source in one dataset of one taxonomy; or a malformed request"
        )
    },
}
_PATH = "/proposals/{a_id}/compare/{b_id}"


def _error(exc: Exception) -> HTTPException:
    """Map a domain exception to an HTTPException; anything unexpected is a logged 500."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ChangeProposalNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ProposalsNotComparableError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "not_comparable", "message": str(exc)},
        )
    if isinstance(exc, InvalidPairDecisionError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_decision", "message": str(exc)},
        )
    if isinstance(exc, SampleUncheckedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "sample_unchecked", "message": str(exc)},
        )
    if isinstance(exc, ChangeProposalStateError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_decided", "message": str(exc)},
        )
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    _logger.error(f"Proposal comparison failed: {exc}", exc_info=exc)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
    )


def _sample(stats: SampleStats) -> SampleResponse:
    return SampleResponse(size=stats.size, checked=stats.checked, changed=stats.changed)


def _proposal(proposal: ChangeProposal) -> ComparedProposalResponse:
    return ComparedProposalResponse(
        proposal_id=proposal.id,
        status=proposal.status.value,
        origin=ProposalOriginResponse.from_domain(proposal.origin),
    )


class _Views:
    """Builds pair responses, reading class and near-match titles once per comparison."""

    def __init__(self, service: ProposalComparisonService, comparison: Comparison) -> None:
        self._comparison = comparison
        self._classes = service.class_titles(comparison)
        self._alternatives = service.alternative_titles(comparison)
        self._sample = set(comparison.sample)

    def operation(self, operation: Optional[ProposedOperation]) -> Optional[Any]:
        if operation is None:
            return None
        fields = operation.applied_fields or operation.fields
        decision = self._comparison.decisions.get(operation.id)
        return ComparedOperationResponse(
            operation_id=operation.id,
            seq=operation.seq,
            title=str(fields.get("title") or operation.fields.get("title") or ""),
            classes=[
                ComparedClassResponse(id=c, title=self._classes.get(c, c))
                for c in fields.get("class_ids") or operation.fields.get("class_ids") or ()
            ],
            status=operation.status,
            reason=operation.reason,
            reason_code=operation.reason_code,
            evidence=list(operation.evidence),
            alternatives=[
                ComparedAlternativeResponse(
                    entity_id=a["entity_id"],
                    similarity=a.get("similarity"),
                    title=self._alternatives.get(a["entity_id"]),
                )
                for a in operation.alternatives
            ],
            lacks_passage=comparison_lacks_passage(self._comparison, operation),
            comparison=decision.comparison if decision is not None else None,
        )

    def pair(self, pair: Pair) -> PairResponse:
        return PairResponse(
            pair_id=pair.pair_id,
            group=pair.group,
            in_sample=pair.pair_id in self._sample,
            state=pair.state,
            a=self.operation(pair.a),
            b=self.operation(pair.b),
        )


def _comparison(
    service: ProposalComparisonService, comparison: Comparison
) -> ProposalComparisonResponse:
    views = _Views(service, comparison)
    return ProposalComparisonResponse(
        a=_proposal(comparison.a),
        b=_proposal(comparison.b),
        taxonomy_id=comparison.a.taxonomy_id,
        dataset_id=comparison.a.dataset_id,
        source_id=str((comparison.a.client_metadata or {}).get(SOURCE_ID)),
        pairs=[views.pair(p) for p in comparison.pairs],
        counts=ComparisonCountsResponse(**comparison.counts()),
        sample=_sample(comparison.sample_stats),
    )


@router.get(_PATH, response_model=ProposalComparisonResponse, responses=_ERRORS)
async def compare_proposals(
    a_id: str,
    b_id: str,
    sample_size: int = Query(
        DEFAULT_SAMPLE_SIZE,
        ge=0,
        le=MAX_SAMPLE_SIZE,
        description="How many same-class pairs to check before accepting the rest",
    ),
    service: ProposalComparisonService = Depends(get_proposal_comparison_service),
) -> ProposalComparisonResponse:
    """
    Two individual extractions of one source, their individual creates paired
    by normalised title: same class, class differs, only in A, only in B. A
    stable random sample of the same-class pairs is marked to check first.
    """

    def run() -> ProposalComparisonResponse:
        return _comparison(service, service.compare(a_id, b_id, sample_size))

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    f"{_PATH}/decide",
    response_model=PairDecisionResponse,
    responses={
        **_ERRORS,
        409: {"description": "A copy is already decided, or a proposal is reverted or superseded"},
    },
)
async def decide_pair(
    a_id: str,
    b_id: str,
    request: PairDecisionRequest,
    sample_size: int = Query(DEFAULT_SAMPLE_SIZE, ge=0, le=MAX_SAMPLE_SIZE),
    service: ProposalComparisonService = Depends(get_proposal_comparison_service),
) -> PairDecisionResponse:
    """
    Decide one pair once for both proposals: the chosen copy lands (keep: A's,
    or the only one given; a_class: A's; b_class: B's) and the other closes as
    its duplicate, so relationships naming it follow the landed individual;
    not_element rejects both. A failed landing (outcome failed) leaves the
    other copy as it was. Both copies' decisions record the comparison, and the
    landed one the review time.
    """

    def run() -> PairDecisionResponse:
        result = service.decide(
            a_id,
            b_id,
            PairDecision(
                verdict=request.verdict,
                a_operation_id=request.a_operation_id,
                b_operation_id=request.b_operation_id,
                reason_code=request.reason_code,
                match_entity_id=request.match_entity_id,
                review_ms=request.review_ms,
            ),
            sample_size,
        )
        views = _Views(service, result.comparison)
        return PairDecisionResponse(
            pair=views.pair(result.pair),
            outcome=result.outcome,
            failure_reason=result.failure_reason,
            sample=_sample(result.comparison.sample_stats),
        )

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    f"{_PATH}/accept-rest",
    response_model=AcceptRestResponse,
    responses={
        **_ERRORS,
        409: {
            "description": (
                "sample_unchecked: a sample pair is not decided yet; or a proposal "
                "is reverted or superseded"
            )
        },
    },
)
async def accept_rest(
    a_id: str,
    b_id: str,
    request: AcceptRestRequest,
    service: ProposalComparisonService = Depends(get_proposal_comparison_service),
) -> AcceptRestResponse:
    """
    Accept every same-class pair outside the sample whose copies are both
    pending: A's lands, B's closes as its duplicate. Pairs whose copy lists near
    matches or cites no passage are skipped, for a person. Each decision records
    the sample's size and how many of it were changed. Calling it again changes
    nothing more.
    """

    def run() -> AcceptRestResponse:
        result = service.accept_rest(a_id, b_id, request.sample_size)
        return AcceptRestResponse(
            landed=result.landed,
            failed=[PairFailureResponse(pair_id=p, reason=r) for p, r in result.failed],
            skipped=[PairSkippedResponse(pair_id=p, why=w) for p, w in result.skipped],  # type: ignore[arg-type]
            sample=_sample(result.sample),
        )

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _error(exc) from exc
