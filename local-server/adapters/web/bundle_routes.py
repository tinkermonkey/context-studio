"""
FastAPI route for importing a Context Studio bundle as a change proposal.

POST /api/v1/interchange/bundles takes a bundle (JSON body), plans it against
the workspace and proposes the plan (source=bundle) for review. The taxonomy's
approval policy applies what it allows; `apply=true` applies every other
non-breaking operation too; `dry_run=true` plans and validates without storing
anything. A bundle that matches the workspace proposes nothing.
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from adapters.web.dependencies import get_bundle_import_service, get_proposal_service
from adapters.web.proposals_routes import _http_error
from adapters.web.schemas.bundles import BundleImportResponse, BundleKindCounts
from adapters.web.schemas.proposals import ChangeProposalResponse
from domain.interchange.bundle import BundleError
from domain.ontology.exceptions import OntologyError
from domain.versioning.bundle_import import BundleImportResult, BundleImportService
from domain.versioning.proposal_service import ProposalService
from utils.async_executor import run_sync_in_executor

router = APIRouter(prefix="/api/v1/interchange", tags=["interchange"])


def _response(service: ProposalService, result: BundleImportResult) -> BundleImportResponse:
    plan, proposal = result.plan, result.proposal
    return BundleImportResponse(
        source=plan.source,
        taxonomy_id=plan.taxonomy_id,
        taxonomy_created=result.taxonomy_created,
        dry_run=result.dry_run,
        operation_count=len(plan.operations),
        counts={
            kind: BundleKindCounts(
                created=c.created, updated=c.updated, deleted=c.deleted, unchanged=c.unchanged
            )
            for kind, c in plan.counts.items()
        },
        deletes=plan.deletes,
        proposal=(
            ChangeProposalResponse.from_domain(proposal, service.stale_operation_ids(proposal))
            if proposal is not None
            else None
        ),
    )


@router.post(
    "/bundles",
    response_model=BundleImportResponse,
    responses={
        422: {
            "description": (
                "The bundle is malformed, conflicts with the workspace, or its plan"
                " does not validate; nothing is stored"
            )
        }
    },
)
async def import_bundle(
    bundle: dict[str, Any] = Body(..., description="A context-studio-bundle v0 document"),
    apply: bool = Query(False, description="Also apply every non-breaking operation"),
    dry_run: bool = Query(False, description="Plan and validate only; store nothing"),
    source_detail: str | None = Query(
        None, max_length=255, description="Where the bundle came from (a file name)"
    ),
    importer: BundleImportService = Depends(get_bundle_import_service),
    proposals: ProposalService = Depends(get_proposal_service),
) -> BundleImportResponse:
    """Plan a bundle and propose it; see the module docstring."""
    try:
        result = await run_sync_in_executor(
            importer.import_bundle,
            bundle,
            apply=apply,
            dry_run=dry_run,
            source_detail=source_detail,
        )
        return await run_sync_in_executor(_response, proposals, result)
    except (BundleError, OntologyError, ValueError) as exc:
        # The bundle is malformed or conflicts with the workspace (a taxonomy title, say).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        # Proposal validation errors (422 with every error), state conflicts, the rest.
        raise _http_error(exc) from exc
