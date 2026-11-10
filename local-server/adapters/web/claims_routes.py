"""
FastAPI routes for a taxonomy's claims (#1518): atomic statements split from
reviewer and maintainer notes, with a decision model's triage and a person's
verdict. Claims change nothing in the taxonomy.

- GET    /api/taxonomies/{taxonomy_id}/claims          List, with filters
- POST   /api/taxonomies/{taxonomy_id}/claims          Add or replace by key
- GET    /api/taxonomies/{taxonomy_id}/claims/export   JSONL
- GET    /api/claims/{claim_id}                        One claim
- PUT    /api/claims/{claim_id}/verdict                Record a person's verdict
- DELETE /api/claims/{claim_id}/verdict                Clear it
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from adapters.web.dependencies import get_claim_service
from adapters.web.schemas.claims import ClaimResponse, ClaimsSubmitRequest, ClaimVerdictRequest
from adapters.web.schemas.ontology import ListResponse
from domain.ontology.exceptions import EntityNotFoundError
from domain.versioning.claims import ClaimFilter, ClaimService, Validity
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["claims"])

# A verdict given through the API is a person's.
VERDICT_BY_USER = "user"

_NOT_FOUND = {404: {"description": "Taxonomy or claim not found"}}


def _http_error(exc: Exception) -> HTTPException:
    """404 for a missing taxonomy or claim, 422 for an invalid claim, else 500."""
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    logger.exception("Claims request failed")
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def _claim_filter(
    taxonomy_id: str,
    subject_id: Optional[str] = Query(None, description="Only claims about this entity"),
    note_ref: Optional[str] = Query(None, description="Only claims from this note"),
    triaged: Optional[bool] = Query(None, description="Only triaged (true) or untriaged (false)"),
    has_verdict: Optional[bool] = Query(None, description="Only with (true) or without a verdict"),
    validity: Optional[Validity] = Query(None, description="Only claims triaged as this"),
) -> ClaimFilter:
    """The list and export routes' filters."""
    return ClaimFilter(
        taxonomy_id=taxonomy_id,
        subject_id=subject_id,
        note_ref=note_ref,
        triaged=triaged,
        has_verdict=has_verdict,
        validity=validity,
    )


@router.get(
    "/taxonomies/{taxonomy_id}/claims",
    response_model=ListResponse[ClaimResponse],
    responses=_NOT_FOUND,
)
async def list_claims(
    filters: ClaimFilter = Depends(_claim_filter),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: ClaimService = Depends(get_claim_service),
) -> ListResponse[ClaimResponse]:
    """The taxonomy's claims, oldest first."""

    def run() -> ListResponse[ClaimResponse]:
        return ListResponse(
            items=[
                ClaimResponse.from_domain(c) for c in service.list_claims(filters, limit, offset)
            ],
            total=service.count_claims(filters),
            limit=limit,
            offset=offset,
        )

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/taxonomies/{taxonomy_id}/claims",
    response_model=list[ClaimResponse],
    responses={**_NOT_FOUND, 422: {"description": "Invalid claims"}},
)
async def submit_claims(
    taxonomy_id: str,
    request: ClaimsSubmitRequest,
    service: ClaimService = Depends(get_claim_service),
) -> list[ClaimResponse]:
    """
    Add claims, or replace those whose key the taxonomy already has. A replaced
    claim keeps its triage and verdict only if its text is unchanged. Affected
    ids that match no entity move to unresolved_refs.
    """

    def run() -> list[ClaimResponse]:
        claims = [c.to_domain(taxonomy_id) for c in request.claims]
        return [ClaimResponse.from_domain(c) for c in service.submit(taxonomy_id, claims)]

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/taxonomies/{taxonomy_id}/claims/export",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"application/x-ndjson": {"schema": {"type": "string"}}},
            "description": "Every matching claim, one ClaimResponse JSON object per line",
        },
        **_NOT_FOUND,
    },
)
async def export_claims(
    filters: ClaimFilter = Depends(_claim_filter),
    service: ClaimService = Depends(get_claim_service),
) -> StreamingResponse:
    """The taxonomy's claims as JSONL: the list route's claims and filters, all of them."""

    def run() -> list[str]:
        return [
            ClaimResponse.from_domain(c).model_dump_json() + "\n"
            for c in service.list_claims(filters)
        ]

    try:
        lines = await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc) from exc
    return StreamingResponse(
        iter(lines),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="claims-{filters.taxonomy_id}.jsonl"'
        },
    )


@router.get("/claims/{claim_id}", response_model=ClaimResponse, responses=_NOT_FOUND)
async def get_claim(
    claim_id: str, service: ClaimService = Depends(get_claim_service)
) -> ClaimResponse:
    """One claim, with its triage and verdict."""
    try:
        return ClaimResponse.from_domain(await run_sync_in_executor(service.get, claim_id))
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/claims/{claim_id}/verdict", response_model=ClaimResponse, responses=_NOT_FOUND)
async def set_claim_verdict(
    claim_id: str,
    request: ClaimVerdictRequest,
    service: ClaimService = Depends(get_claim_service),
) -> ClaimResponse:
    """Record a person's verdict on a claim, replacing any earlier one: benchmark gold."""
    try:
        claim = await run_sync_in_executor(
            service.set_verdict, claim_id, request.to_domain(VERDICT_BY_USER)
        )
        return ClaimResponse.from_domain(claim)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.delete("/claims/{claim_id}/verdict", response_model=ClaimResponse, responses=_NOT_FOUND)
async def clear_claim_verdict(
    claim_id: str, service: ClaimService = Depends(get_claim_service)
) -> ClaimResponse:
    """Clear a claim's verdict."""
    try:
        return ClaimResponse.from_domain(
            await run_sync_in_executor(service.set_verdict, claim_id, None)
        )
    except Exception as exc:
        raise _http_error(exc) from exc
