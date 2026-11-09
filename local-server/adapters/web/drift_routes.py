"""
FastAPI route for re-importing the DR spec as a drift proposal (#1464).

POST /api/v1/interchange/dr-spec/drift compares the DR spec on disk with the
dr_spec taxonomy, matched by DR id (see `adapters/interchange/dr_drift.py`).
With dry_run (the default) it reports the drift and stores nothing; otherwise
it proposes what differs as one change proposal for review, superseding the
open proposal of an earlier re-import.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from adapters.serialization.views import proposal_response
from adapters.web.dependencies import get_drift_import_service, get_proposal_service
from adapters.web.proposals_routes import _http_error
from adapters.web.schemas.drift import DriftEntryResponse, DriftResponse, DrSpecDriftRequest
from adapters.web.schemas.ontology import SourceRevisionSchema
from domain.versioning.drift import DriftError, DriftImportService, DriftResult
from domain.versioning.proposal_service import ProposalService
from utils.async_executor import run_sync_in_executor

router = APIRouter(prefix="/api/v1/interchange", tags=["interchange"])


def drift_response(service: ProposalService, result: DriftResult) -> DriftResponse:
    """The REST view of a re-import; the MCP tool returns the same."""
    plan, proposal = result.plan, result.proposal
    return DriftResponse(
        taxonomy_id=plan.taxonomy_id,
        source_revision=SourceRevisionSchema.from_domain(plan.source_revision),
        dry_run=result.dry_run,
        entries=[DriftEntryResponse.model_validate(entry) for entry in plan.entries],
        proposal=(
            proposal_response(service, proposal, dry_run=result.dry_run)
            if proposal is not None
            else None
        ),
    )


@router.post(
    "/dr-spec/drift",
    response_model=DriftResponse,
    responses={
        422: {
            "description": (
                "The directory isn't a DR spec, the DR spec hasn't been imported yet, or"
                " the planned proposal doesn't validate; nothing is stored"
            )
        },
    },
)
async def dr_spec_drift(
    request: DrSpecDriftRequest,
    drift: DriftImportService = Depends(get_drift_import_service),
    proposals: ProposalService = Depends(get_proposal_service),
) -> DriftResponse:
    """Report, or propose, the drift between the DR spec and its taxonomy; see the module."""
    try:
        result = await run_sync_in_executor(
            drift.reimport, request.spec_dir, dry_run=request.dry_run
        )
        return await run_sync_in_executor(drift_response, proposals, result)
    except DriftError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        # Proposal validation errors (422 with every error), state conflicts, the rest.
        raise _http_error(exc) from exc
