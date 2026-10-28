"""
Pydantic schemas for the change proposal API.

Names carry a ChangeProposal prefix because ProposalResponse and
RejectProposalRequest already name the changeset proposals in versioning.py.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)

# ==================== Requests ====================


class ProposedOperationRequest(BaseModel):
    """One operation as proposed."""

    seq: int = Field(..., description="Position in the proposal; operations apply in this order")
    op: OperationType = Field(..., description="create, update, move or delete")
    kind: OperationKind = Field(..., description="The kind of entity targeted")
    target_id: Optional[str] = Field(
        None, description="The existing entity (update, move, delete); omit for a create"
    )
    ref: Optional[str] = Field(
        None,
        description="A name a create gives its new entity; later operations point at it "
        'as "$<ref>"',
    )
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="For a create, every field; for an update, only the changed ones; "
        "for a move, the new parent, scheme or taxonomy",
    )
    rationale: Optional[str] = Field(None, description="Why this change")
    evidence: list[dict[str, Any]] = Field(
        default_factory=list, description='Supporting {"quote", "url", "entity_id"} items'
    )
    probability: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="The proposer's confidence, 0 to 1"
    )
    scope: Optional[ChangeScope] = Field(
        None, description="A claimed scope; it can only make the computed scope stricter"
    )


class ChangeProposalCreateRequest(BaseModel):
    """A new change proposal, validated as a whole; nothing is stored if any operation fails."""

    taxonomy_id: str = Field(..., description="The taxonomy the changes are about")
    title: str = Field(..., min_length=1, description="A short summary")
    rationale: Optional[str] = Field(None, description="Why these changes, as a whole")
    source: ProposalSource = Field(ProposalSource.USER, description="Who or what proposed them")
    source_detail: Optional[str] = Field(
        None, description="More about the source (MCP client, conversation id, bundle file)"
    )
    operations: list[ProposedOperationRequest] = Field(..., description="The operations")


class ChangeProposalApplyRequest(BaseModel):
    """Operations to apply, in seq order, under the proposal's run."""

    operation_ids: list[str] = Field(..., min_length=1, description="Operations to apply")
    force_stale: list[str] = Field(
        default_factory=list,
        description="Operations to apply even though their target changed since proposed",
    )


class ChangeProposalRejectRequest(BaseModel):
    """Operations to reject; without operation_ids, every pending or failed one."""

    operation_ids: Optional[list[str]] = Field(None, description="Operations to reject")
    note: Optional[str] = Field(None, description="Why; stored as each operation's reason")


# ==================== Responses ====================


class ProposedOperationResponse(BaseModel):
    """One proposed operation and its outcome."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    seq: int
    op: OperationType
    kind: OperationKind
    target_id: Optional[str] = None
    ref: Optional[str] = None
    fields: dict[str, Any] = Field(default_factory=dict)
    base: dict[str, Any] = Field(
        default_factory=dict,
        description="The touched fields' values when proposed (a delete: the whole entity)",
    )
    rationale: Optional[str] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    probability: Optional[float] = None
    scope: ChangeScope
    status: OperationStatus
    result_entity_id: Optional[str] = Field(None, description="The entity made or changed")
    reason: Optional[str] = Field(
        None, description='Why it failed ("<code>: <detail>") or was rejected'
    )
    stale: bool = Field(
        False,
        description="Pending or failed, and its target is gone or a field it touches "
        "changed since proposed; applying it needs force_stale",
    )


class ChangeProposalResponse(BaseModel):
    """A change proposal with its operations in seq order."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Also the batch run id its applied changes are tagged with")
    taxonomy_id: str
    title: str
    rationale: Optional[str] = None
    source: ProposalSource
    source_detail: Optional[str] = None
    created_at: datetime
    status: ProposalStatus
    operations: list[ProposedOperationResponse]

    @classmethod
    def from_domain(cls, proposal: ChangeProposal, stale_ids: set[str]) -> "ChangeProposalResponse":
        """Build the response, flagging the operations in stale_ids."""
        return cls(
            id=proposal.id,
            taxonomy_id=proposal.taxonomy_id,
            title=proposal.title,
            rationale=proposal.rationale,
            source=proposal.source,
            source_detail=proposal.source_detail,
            created_at=proposal.created_at,
            status=proposal.status,
            operations=[_operation(o, o.id in stale_ids) for o in proposal.operations],
        )


def _operation(operation: ProposedOperation, stale: bool) -> ProposedOperationResponse:
    response = ProposedOperationResponse.model_validate(operation)
    response.stale = stale
    return response


class OperationErrorResponse(BaseModel):
    """Why one proposed operation is invalid."""

    seq: Optional[int] = Field(None, description="The operation, or null for the whole proposal")
    code: str = Field(
        ..., description="Stable code, e.g. target_not_found, unknown_ref, missing_field"
    )
    message: str = Field(..., description="What is wrong and how to fix it")


class ChangeProposalValidationDetail(BaseModel):
    """Every problem found with a proposal; nothing was stored."""

    message: str
    errors: list[OperationErrorResponse]


class ChangeProposalValidationErrorResponse(BaseModel):
    """422 body of POST /api/proposals."""

    detail: ChangeProposalValidationDetail


class RevertBlocker(BaseModel):
    """An entity outside the proposal that depends on one the proposal created."""

    kind: str = Field(..., description="What depends (e.g. relationship, individual)")
    dependent_id: str
    referenced_id: str = Field(..., description="The entity the proposal created")


class ChangeProposalRevertConflictDetail(BaseModel):
    """Why a proposal can't be reverted; nothing was changed."""

    message: str
    blocking: list[RevertBlocker] = Field(default_factory=list)


class ChangeProposalRevertConflictResponse(BaseModel):
    """409 body of POST /api/proposals/{id}/revert."""

    detail: ChangeProposalRevertConflictDetail


class ChangeProposalRevertResponse(BaseModel):
    """What reverting a proposal undid, and the proposal afterwards."""

    events_reverted: int
    classes_deleted: int = 0
    individuals_deleted: int = 0
    relationships_deleted: int = 0
    properties_deleted: int = 0
    taxonomies_deleted: int = 0
    concept_schemes_deleted: int = 0
    entities_restored: int = 0
    proposal: ChangeProposalResponse
