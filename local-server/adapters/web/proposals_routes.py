"""
FastAPI routes for change proposals: list, get, propose, apply, reject, revert,
the decisions export for DR reflection plans, and each taxonomy's gold (every
recorded decision).

A proposal is a run: everything applied from it is tagged with its id, so
reverting it undoes them. Each route is a thin adapter over ProposalService;
service calls touch SQLite, so they run in the thread pool.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from adapters.interchange.dr_decisions import decisions_for
from adapters.persistence.sqlite.transaction import TransactionAbortedError
from adapters.serialization.views import proposal_response
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
    DrDecisionResponse,
    GoldDecisionResponse,
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
from domain.versioning.gold import DecisionFilter, DecisionKind
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    InUseResolution,
    OperationKind,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
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
            items=[proposal_response(service, p) for p in proposals],
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
        return await run_sync_in_executor(
            lambda: proposal_response(service, service.get(proposal_id))
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/proposals/{proposal_id}/decisions",
    response_model=None,
    responses={
        200: {
            "model": list[DrDecisionResponse],
            "description": "The decisions, one per operation in seq order",
        },
        **_NOT_FOUND,
        409: {
            "description": (
                "The proposal was reverted, so none of its decisions stand, or an edited "
                "operation's applied fields carry no DR relationship id"
            )
        },
    },
)
async def get_proposal_decisions(
    proposal_id: str,
    service: ProposalService = Depends(get_proposal_service),
) -> JSONResponse:
    """
    The decisions on a DR reflection-plan proposal, for DR's
    `proposal-import.ts --decisions`: the same JSON as
    `scripts/export_dr_decisions.py` writes, joined to DR's plan by seq.
    """

    def run() -> list[dict]:
        proposal = service.get(proposal_id)
        return decisions_for(proposal, service.decisions_of(proposal.id))

    try:
        decisions = await run_sync_in_executor(run)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _http_error(exc) from exc
    return JSONResponse(content=decisions)


# ==================== Propose ====================


@router.post(
    "/proposals",
    response_model=ChangeProposalResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": ChangeProposalResponse,
            "description": "A dry run: the proposal as it would be stored, nothing stored",
        },
        422: {
            "model": ChangeProposalValidationErrorResponse,
            "description": (
                "The proposal is invalid; detail.errors lists every problem by "
                "operation seq, and nothing was stored"
            ),
        },
    },
)
async def create_proposal(
    request: ChangeProposalCreateRequest,
    response: Response,
    dry_run: bool = Query(
        False,
        description="Validate only (200): return the computed scopes, "
        "stale flags, blockers, replacement checks and which operations are eligible to "
        "auto-apply; store and apply nothing",
    ),
    service: ProposalService = Depends(get_proposal_service),
) -> ChangeProposalResponse:
    """
    Propose changes to a taxonomy; every operation starts pending.

    The proposal is validated as a whole against the current graph. If any
    operation is invalid nothing is stored and the 422 lists each problem with
    its operation's seq and a stable code. Source "bundle" is refused (code
    invalid_source): bundle proposals come from the bundle import route, and
    are exempt from the approval policy's min_probability.
    """
    if request.source is ProposalSource.BUNDLE:
        message = "bundle proposals come from the bundle import route"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": message,
                "errors": [{"seq": None, "code": "invalid_source", "message": message}],
            },
        )
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
            replacement=o.replacement,
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
            dry_run=dry_run,
        )
        return proposal_response(service, proposal, dry_run=dry_run)

    if dry_run:
        response.status_code = status.HTTP_200_OK
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
                "(not in operation_ids, not a property update/delete, empty, or uses a $ref), "
                "or a resolution is (not in operation_ids, not a property delete, also "
                "edited, a move without replacement_property_id, or a move to a type the "
                "proposal deletes); nothing was applied"
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
    DR spec classes, the predicate is in its predicate catalog, and no other
    relationship type or operation has the triple), fails only that operation
    with "invalid_edit: ..."; it stays open, to apply again with a corrected
    edit or reject. For dr_spec the identifier and DR external reference follow
    from the triple. What was applied is returned as the operation's
    applied_fields.

    resolutions lets a relationship-type delete apply although relationships
    still use the type (its blockers list them): "move" gives each the
    replacement type instead (all must fit its domain and range, inheritance-
    aware, and allow their attributes, or nothing moves), "delete" deletes them
    too. The relationships and the type change in one transaction tagged with
    the proposal's run, so Revert restores them together; a failure fails only
    that operation ("unresolvable: ..." for a misfit) and changes nothing.
    Without a resolution such a delete fails as in use. What was moved or
    deleted is returned as the operation's resolution.
    """

    def run() -> ChangeProposalResponse:
        resolutions = {
            op_id: InUseResolution(
                strategy=r.strategy,
                replacement_property_id=r.replacement_property_id,
                relationship_ids=list(r.relationship_ids),
            )
            for op_id, r in request.resolutions.items()
        }
        proposal = service.apply(
            proposal_id, request.operation_ids, request.force_stale, request.edits, resolutions
        )
        return proposal_response(service, proposal)

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
        return proposal_response(service, proposal)

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
            proposal=proposal_response(service, service.get(proposal_id)),
        )

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _http_error(exc) from exc


# ==================== Gold ====================


def _gold_filter(
    taxonomy_id: str,
    kind: Optional[OperationKind] = Query(None, description="Only operations on this kind"),
    op: Optional[OperationType] = Query(
        None, description="Only this operation: create, update, move or delete"
    ),
    decision: Optional[DecisionKind] = Query(
        None, description="Only applied, rejected or applied_with_edits"
    ),
    decided_by: Optional[str] = Query(
        None, description="Only decisions by user, policy, an agent source or unknown"
    ),
    decided_from: Optional[datetime] = Query(None, description="Decided at or after"),
    decided_to: Optional[datetime] = Query(None, description="Decided before"),
    include_superseded: bool = Query(False, description="Also decisions a revert superseded"),
) -> DecisionFilter:
    """The gold routes' filters."""
    return DecisionFilter(
        taxonomy_id=taxonomy_id,
        kind=kind,
        op=op,
        decision=decision,
        decided_by=decided_by,
        decided_from=decided_from,
        decided_to=decided_to,
        include_superseded=include_superseded,
    )


@router.get(
    "/taxonomies/{taxonomy_id}/gold",
    response_model=ListResponse[GoldDecisionResponse],
    responses={404: {"description": "Taxonomy not found"}},
)
async def list_gold(
    filters: DecisionFilter = Depends(_gold_filter),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: ProposalService = Depends(get_proposal_service),
) -> ListResponse[GoldDecisionResponse]:
    """
    The taxonomy's gold: every reviewer or policy decision on its proposals'
    operations, oldest first. Decisions a revert superseded are left out unless
    include_superseded.
    """

    def run() -> ListResponse[GoldDecisionResponse]:
        decisions = service.list_decisions(filters, limit, offset)
        return ListResponse(
            items=[GoldDecisionResponse.from_domain(d) for d in decisions],
            total=service.count_decisions(filters),
            limit=limit,
            offset=offset,
        )

    try:
        return await run_sync_in_executor(run)
    except Exception as exc:
        raise _policy_error(exc) from exc


@router.get(
    "/taxonomies/{taxonomy_id}/gold/export",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"application/x-ndjson": {"schema": {"type": "string"}}},
            "description": "Every matching decision, one GoldDecisionResponse JSON object per line",
        },
        404: {"description": "Taxonomy not found"},
    },
)
async def export_gold(
    filters: DecisionFilter = Depends(_gold_filter),
    service: ProposalService = Depends(get_proposal_service),
) -> StreamingResponse:
    """The taxonomy's gold as JSONL: the list route's decisions and filters, all of them."""

    def run() -> list[str]:
        return [
            GoldDecisionResponse.from_domain(d).model_dump_json() + "\n"
            for d in service.list_decisions(filters)
        ]

    try:
        lines = await run_sync_in_executor(run)
    except Exception as exc:
        raise _policy_error(exc) from exc
    return StreamingResponse(
        iter(lines),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="gold-{filters.taxonomy_id}.jsonl"'},
    )


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
    """
    The taxonomy's approval policy; empty (nothing auto-applies) if none is set.

    A rule naming a class matches entities typed by it or any subclass of it:
    individuals, attributes, the class itself, class creates under it (by the
    proposed parent) and relationships (by the source's and target's classes).
    """
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
    does; one without a class covers any, and one naming a class covers its
    subclasses, class creates under it and relationships between entities of
    it; see ApprovalPolicyResponse). Never auto-applied: breaking
    operations, deletes, taxonomy creates, changes to the taxonomy's vision,
    property-definition changes, and anything that touches or points at an
    entity outside this taxonomy.
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
