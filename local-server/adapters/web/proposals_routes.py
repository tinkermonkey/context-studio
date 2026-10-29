"""
FastAPI routes for change proposals: list, get, propose, apply, reject, revert.

A proposal is a run: everything applied from it is tagged with its id, so
reverting it undoes them. Each route is a thin adapter over ProposalService;
service calls touch SQLite, so they run in the thread pool.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from adapters.persistence.sqlite.transaction import TransactionAbortedError
from adapters.web.dependencies import get_approval_policy_service, get_proposal_service
from adapters.web.schemas.ontology import ListResponse
from adapters.web.schemas.proposals import (
    ApprovalPolicyRequest,
    ApprovalPolicyResponse,
    ChangeProposalApplyRequest,
    ChangeProposalCreateRequest,
    ChangeProposalRejectRequest,
    ChangeProposalResponse,
    ChangeProposalRevertConflictResponse,
    ChangeProposalRevertResponse,
    ChangeProposalValidationErrorResponse,
)
from domain.ontology.exceptions import EntityNotFoundError
from domain.versioning.approval_policy import ApprovalPolicyService
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
    ProposalValidationError,
    RevertConflictError,
    RevertRefusedError,
)
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import ChangeProposal, ProposalSource, ProposalStatus
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["proposals"])

_logger = get_logger(__name__)

_NOT_FOUND = {404: {"description": "Change proposal not found"}}
_STATE_CONFLICT = {409: {"description": "An operation is already applied or rejected"}}


def _http_error(exc: Exception, unknown_ids_are_invalid: bool = False) -> HTTPException:
    """
    Map a domain exception to an HTTPException; anything unexpected is logged as a 500.

    Args:
        exc: The exception
        unknown_ids_are_invalid: The call checks its request's operation ids up
            front and raises ValueError for unknown ones (apply, reject): a 422
    """
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ChangeProposalNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ProposalValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": str(exc),
                "errors": [
                    {"seq": e.seq, "code": e.code, "message": e.message} for e in exc.errors
                ],
            },
        )
    if isinstance(exc, RevertConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "blocking": [
                    {"kind": kind, "dependent_id": dependent, "referenced_id": referenced}
                    for kind, dependent, referenced in exc.blocking
                ],
            },
        )
    if isinstance(exc, RevertRefusedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"message": str(exc), "blocking": []}
        )
    if isinstance(exc, ChangeProposalStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if unknown_ids_are_invalid and isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if isinstance(exc, TransactionAbortedError):
        _logger.error(f"Proposal transaction rolled back: {exc}", exc_info=exc)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The change was rolled back; nothing was changed",
        )
    _logger.error(f"Unexpected error in proposals endpoint: {exc}", exc_info=exc)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred"
    )


def _response(service: ProposalService, proposal: ChangeProposal) -> ChangeProposalResponse:
    return ChangeProposalResponse.from_domain(proposal, service.stale_operation_ids(proposal))


# ==================== Read ====================


@router.get("/proposals", response_model=ListResponse[ChangeProposalResponse])
async def list_proposals(
    taxonomy_id: Optional[str] = Query(None, description="Only proposals about this taxonomy"),
    proposal_status: Optional[ProposalStatus] = Query(
        None, alias="status", description="open, done or reverted"
    ),
    source: Optional[ProposalSource] = Query(None, description="Who or what proposed them"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: ProposalService = Depends(get_proposal_service),
) -> ListResponse[ChangeProposalResponse]:
    """List proposals, newest first, each operation with its stale flag."""

    def run() -> ListResponse[ChangeProposalResponse]:
        proposals = service.list_proposals(taxonomy_id, proposal_status, source, limit, offset)
        return ListResponse(
            items=[_response(service, p) for p in proposals],
            total=service.count_proposals(taxonomy_id, proposal_status, source),
            limit=limit,
            offset=offset,
        )

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/proposals/{proposal_id}", response_model=ChangeProposalResponse, responses=_NOT_FOUND)
async def get_proposal(
    proposal_id: str,
    service: ProposalService = Depends(get_proposal_service),
) -> ChangeProposalResponse:
    """A proposal; each pending or failed operation says whether it is stale."""
    try:
        return await run_sync_in_executor(lambda: _response(service, service.get(proposal_id)))
    except Exception as exc:
        raise _http_error(exc) from exc


# ==================== Propose ====================


@router.post(
    "/proposals",
    response_model=ChangeProposalResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {
            "model": ChangeProposalValidationErrorResponse,
            "description": (
                "The proposal is invalid; detail.errors lists every problem by "
                "operation seq, and nothing was stored"
            ),
        }
    },
)
async def create_proposal(
    request: ChangeProposalCreateRequest,
    service: ProposalService = Depends(get_proposal_service),
) -> ChangeProposalResponse:
    """
    Propose changes to a taxonomy; every operation starts pending.

    The proposal is validated as a whole against the current graph. If any
    operation is invalid nothing is stored and the 422 lists each problem with
    its operation's seq and a stable code.
    """
    drafts = [
        OperationDraft(
            seq=o.seq,
            op=o.op,
            kind=o.kind,
            target_id=o.target_id,
            ref=o.ref,
            fields=o.fields,
            rationale=o.rationale,
            evidence=o.evidence,
            probability=o.probability,
            claimed_scope=o.scope,
        )
        for o in request.operations
    ]

    def run() -> ChangeProposalResponse:
        proposal = service.propose(
            request.taxonomy_id,
            request.title,
            drafts,
            request.source,
            rationale=request.rationale,
            source_detail=request.source_detail,
        )
        return _response(service, proposal)

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc) from exc


# ==================== Decide ====================


@router.post(
    "/proposals/{proposal_id}/apply",
    response_model=ChangeProposalResponse,
    responses={
        **_NOT_FOUND,
        409: {"description": "The proposal is reverted, or an operation is already decided"},
        422: {
            "description": (
                "An operation id is not in the proposal, or an edit is misplaced "
                "(not in operation_ids, not a property update/delete, empty, or uses a $ref); "
                "nothing was applied"
            )
        },
    },
)
async def apply_proposal(
    proposal_id: str,
    request: ChangeProposalApplyRequest,
    service: ProposalService = Depends(get_proposal_service),
) -> ChangeProposalResponse:
    """
    Apply the chosen operations in seq order under the proposal's run.

    Each operation records its own outcome; one that fails (e.g. "target_changed")
    does not undo the others. Pass a stale operation in force_stale to apply it
    anyway (edited ones too).

    edits corrects property-definition updates and deletes before they apply:
    each replaces the operation's proposed fields, applied as an update. A field
    problem, or a breach of the taxonomy's rules (for dr_spec: both classes are
    DR spec classes, the predicate is one the spec uses, and no other
    relationship type or operation has the triple), fails only that operation
    with "invalid_edit: ..."; it stays open, to apply again with a corrected
    edit or reject. For dr_spec the identifier and DR external reference follow
    from the triple. What was applied is returned as the operation's
    applied_fields.
    """

    def run() -> ChangeProposalResponse:
        proposal = service.apply(
            proposal_id, request.operation_ids, request.force_stale, request.edits
        )
        return _response(service, proposal)

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc, unknown_ids_are_invalid=True) from exc


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=ChangeProposalResponse,
    responses={
        **_NOT_FOUND,
        **_STATE_CONFLICT,
        422: {"description": "An operation id is not in the proposal"},
    },
)
async def reject_proposal(
    proposal_id: str,
    request: ChangeProposalRejectRequest,
    service: ProposalService = Depends(get_proposal_service),
) -> ChangeProposalResponse:
    """Reject operations, or without operation_ids every pending or failed one."""

    def run() -> ChangeProposalResponse:
        operation_ids = request.operation_ids
        if operation_ids is None:
            operation_ids = [o.id for o in service.get(proposal_id).pending]
        proposal = service.reject(proposal_id, operation_ids, request.note)
        return _response(service, proposal)

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc, unknown_ids_are_invalid=True) from exc


@router.post(
    "/proposals/{proposal_id}/revert",
    response_model=ChangeProposalRevertResponse,
    responses={
        **_NOT_FOUND,
        409: {
            "model": ChangeProposalRevertConflictResponse,
            "description": (
                "Refused, nothing changed: entities outside the proposal depend on ones "
                "it created (detail.blocking lists them), or an event can't be undone "
                "(blocking is empty)"
            ),
        },
    },
)
async def revert_proposal(
    proposal_id: str,
    service: ProposalService = Depends(get_proposal_service),
) -> ChangeProposalRevertResponse:
    """
    Undo everything applied from the proposal and mark it reverted.

    Pending and failed operations are rejected, in the same transaction. A
    refused revert is a 409 and changes nothing: entities made outside the
    proposal depend on ones it created (detail.blocking names them), or an event
    can't be undone. Any other error (including an aborted transaction) is a
    logged 500; the revert's transaction is rolled back.
    """

    def run() -> ChangeProposalRevertResponse:
        result = service.revert(proposal_id)
        return ChangeProposalRevertResponse(
            events_reverted=result.events_reverted,
            classes_deleted=result.classes_deleted,
            individuals_deleted=result.individuals_deleted,
            relationships_deleted=result.relationships_deleted,
            properties_deleted=result.properties_deleted,
            taxonomies_deleted=result.taxonomies_deleted,
            concept_schemes_deleted=result.concept_schemes_deleted,
            entities_restored=result.entities_restored,
            proposal=_response(service, service.get(proposal_id)),
        )

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc) from exc


# ==================== Approval policy ====================
# Set by a person only: never exposed as an agent (chat or MCP) tool.

_TAXONOMY_NOT_FOUND = {404: {"description": "Taxonomy not found"}}


def _policy_error(exc: Exception) -> HTTPException:
    """A missing taxonomy is a 404; anything else is logged as a 500."""
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _http_error(exc)


@router.get(
    "/taxonomies/{taxonomy_id}/approval-policy",
    response_model=ApprovalPolicyResponse,
    response_model_exclude_none=True,
    responses=_TAXONOMY_NOT_FOUND,
)
async def get_approval_policy(
    taxonomy_id: str,
    service: ApprovalPolicyService = Depends(get_approval_policy_service),
) -> ApprovalPolicyResponse:
    """The taxonomy's approval policy; empty (nothing auto-applies) if none is set."""
    try:
        policy = await run_sync_in_executor(service.get, taxonomy_id)
    except Exception as exc:
        raise _policy_error(exc) from exc
    return ApprovalPolicyResponse.from_domain(policy)


@router.put(
    "/taxonomies/{taxonomy_id}/approval-policy",
    response_model=ApprovalPolicyResponse,
    response_model_exclude_none=True,
    responses=_TAXONOMY_NOT_FOUND,
)
async def set_approval_policy(
    taxonomy_id: str,
    request: ApprovalPolicyRequest,
    service: ApprovalPolicyService = Depends(get_approval_policy_service),
) -> ApprovalPolicyResponse:
    """
    Replace the taxonomy's approval policy.

    Operations proposed afterwards apply as soon as they are proposed, under the
    proposal's run, when they reach min_probability and matching rules cover
    every class their entity will have (a rule matches when every key it sets
    does; one without a class covers any). Never auto-applied: breaking
    operations, deletes, taxonomy creates, property-definition changes, and
    anything that touches or points at an entity outside this taxonomy.
    """
    try:
        policy = await run_sync_in_executor(service.set, taxonomy_id, request.to_rules())
    except ValueError as exc:  # rules the domain refuses
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise _policy_error(exc) from exc
    return ApprovalPolicyResponse.from_domain(policy)
