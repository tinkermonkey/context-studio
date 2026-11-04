"""
Pydantic schemas for the change proposal API.

Names carry a ChangeProposal prefix because ProposalResponse and
RejectProposalRequest already name the changeset proposals in versioning.py.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.in_use import DeleteBlockers
from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
    ResolutionStrategy,
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


class InUseResolutionRequest(BaseModel):
    """How to resolve the relationships still using a relationship type a delete removes."""

    strategy: ResolutionStrategy = Field(
        ...,
        description="move: give each relationship the replacement type instead; delete: "
        "delete them too. Either way the type is deleted afterwards",
    )
    replacement_property_id: Optional[str] = Field(
        None,
        description="The type they move to (a move only); every relationship must fit its "
        "domain and range (inheritance-aware) and allow its attributes",
    )
    relationship_ids: list[str] = Field(
        ...,
        description="The relationships the reviewer saw using the type (its blockers' "
        "edges); if those using it at apply time differ, the operation fails "
        "(unresolvable) and nothing changes",
    )


class ChangeProposalApplyRequest(BaseModel):
    """Operations to apply, in seq order, under the proposal's run."""

    operation_ids: list[str] = Field(..., min_length=1, description="Operations to apply")
    force_stale: list[str] = Field(
        default_factory=list,
        description="Operations to apply even though their target changed since proposed",
    )
    edits: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Operation id -> the complete Context Studio fields to apply as a "
        "property-definition update instead of the proposed ones; only for property "
        "update/delete ops in operation_ids (an edited delete applies as an update). For a "
        "dr_spec proposal the identifier and DR external reference follow from the triple "
        "(canonical_predicate, domain_class_id, range_class_id)",
    )
    resolutions: dict[str, InUseResolutionRequest] = Field(
        default_factory=dict,
        description="Operation id -> how to resolve the relationships still using the "
        "relationship type a property delete in operation_ids removes (see the operation's "
        "blockers). Moved or deleted in one transaction with the type; a misfit or any "
        "failing step fails only that operation, changing nothing. Not with an edit of the "
        "same operation",
    )


class ChangeProposalRejectRequest(BaseModel):
    """Operations to reject; without operation_ids, every pending or failed one."""

    operation_ids: Optional[list[str]] = Field(None, description="Operations to reject")
    note: Optional[str] = Field(None, description="Why; stored as each operation's reason")


# ==================== Responses ====================


class EdgeEndResponse(BaseModel):
    """One end of a relationship, with the classes it is typed by."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    class_ids: list[str] = Field(
        default_factory=list, description="An individual's classes, or a class end itself"
    )
    class_titles: list[str] = Field(default_factory=list)


class BlockingEdgeResponse(BaseModel):
    """A relationship that uses the relationship type being deleted."""

    model_config = ConfigDict(from_attributes=True)

    relationship_id: str
    source: EdgeEndResponse
    target: EdgeEndResponse
    attributes: dict[str, Any] = Field(default_factory=dict)


class ReplacementTypeResponse(BaseModel):
    """A relationship type every blocking relationship fits."""

    model_config = ConfigDict(from_attributes=True)

    property_id: str
    identifier: str
    title: str


class DeleteBlockersResponse(BaseModel):
    """What blocks a relationship-type delete: the relationships that still use the type."""

    model_config = ConfigDict(from_attributes=True)

    edges: list[BlockingEdgeResponse]
    replacements: list[ReplacementTypeResponse] = Field(
        default_factory=list,
        description="Types whose domain and range accept both ends of every edge "
        "(inheritance-aware) and that allow their attributes; empty when none does",
    )
    move_unavailable_reason: Optional[str] = Field(
        None, description="Why no type fits, when replacements is empty"
    )


class ResolvedEdgeResponse(BaseModel):
    """A relationship a resolved delete moved or deleted."""

    model_config = ConfigDict(from_attributes=True)

    relationship_id: str
    source_id: str
    target_id: str
    source_title: str
    target_title: str
    moved_to_id: Optional[str] = Field(
        None, description="The relationship of the replacement type made in its place (a move)"
    )


class InUseResolutionResponse(BaseModel):
    """How a relationship-type delete resolved the relationships that still used it."""

    model_config = ConfigDict(from_attributes=True)

    strategy: ResolutionStrategy
    replacement_property_id: Optional[str] = None
    replacement_identifier: Optional[str] = None
    edges: list[ResolvedEdgeResponse] = Field(
        default_factory=list, description="The relationships moved or deleted"
    )


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
    applied_fields: Optional[dict[str, Any]] = Field(
        None,
        description="Set when a reviewer edited the operation: the fields actually applied, "
        "always as an update (an edited delete applies as an update). Null = applied as "
        "proposed, or not applied",
    )
    resolution: Optional[InUseResolutionResponse] = Field(
        None,
        description="Set when a relationship-type delete was applied with a resolution: "
        "what happened to the relationships that used it. Null otherwise",
    )
    stale: bool = Field(
        False,
        description="Pending or failed, and its target is gone or a field it touches "
        "changed since proposed; applying it needs force_stale",
    )
    blockers: Optional[DeleteBlockersResponse] = Field(
        None,
        description="A pending or failed relationship-type delete whose type relationships "
        "still use: applying it as proposed fails; it needs a resolution. Null otherwise",
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
    def from_domain(
        cls,
        proposal: ChangeProposal,
        stale_ids: set[str],
        blockers: Optional[dict[str, DeleteBlockers]] = None,
    ) -> "ChangeProposalResponse":
        """Build the response, flagging the operations in stale_ids, with their blockers."""
        blockers = blockers or {}
        return cls(
            id=proposal.id,
            taxonomy_id=proposal.taxonomy_id,
            title=proposal.title,
            rationale=proposal.rationale,
            source=proposal.source,
            source_detail=proposal.source_detail,
            created_at=proposal.created_at,
            status=proposal.status,
            operations=[
                _operation(o, o.id in stale_ids, blockers.get(o.id)) for o in proposal.operations
            ],
        )


def _operation(
    operation: ProposedOperation, stale: bool, blockers: Optional[DeleteBlockers]
) -> ProposedOperationResponse:
    response = ProposedOperationResponse.model_validate(operation)
    response.stale = stale
    if blockers is not None:
        response.blockers = DeleteBlockersResponse.model_validate(blockers)
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


class DrTripleFields(BaseModel):
    """A DR relationship's triple in DR's vocabulary."""

    predicate: str
    source_spec_node_id: str
    destination_spec_node_id: str


class DrDecisionResponse(BaseModel):
    """
    One operation's decision, as DR's `proposal-import.ts --decisions` reads it.

    `fields` is present only on an operation a reviewer edited before applying
    it: the triple that was applied. `resolution` is present only on a
    relationship-type delete applied with the relationships using it moved or
    deleted.
    """

    seq: int
    op_id: str
    status: OperationStatus
    fields: Optional[DrTripleFields] = Field(
        None, description="Only on an edited operation; absent (not null) otherwise"
    )
    resolution: Optional[InUseResolutionResponse] = Field(
        None,
        description="Only on a delete applied with a resolution: the strategy, the "
        "replacement type and the relationships moved or deleted; absent (not null) otherwise",
    )
    reason: Optional[str] = None
    result_entity_id: Optional[str] = None


# ==================== Approval policy ====================


class AutoApplyRuleSchema(BaseModel):
    """Operations matching every key set here may apply as soon as they are proposed."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    op: Optional[OperationType] = Field(None, description="Only this operation type")
    kind: Optional[OperationKind] = Field(None, description="Only this kind of entity")
    class_: Optional[str] = Field(
        None,
        alias="class",
        description="Only entities typed by this class (id or identifier): an individual's "
        "classes, an attribute's class, or the class itself",
    )
    scope: Optional[ChangeScope] = Field(None, description="Only this scope")


class ApprovalPolicyRequest(BaseModel):
    """A taxonomy's approval policy; replaces the current one."""

    model_config = ConfigDict(extra="forbid")

    auto_apply: list[AutoApplyRuleSchema] = Field(
        default_factory=list,
        description="Operations the matching rules cover may auto-apply; breaking ones, "
        "deletes, taxonomy creates and anything outside this taxonomy never do",
    )
    min_probability: float = Field(
        0.0, ge=0.0, le=1.0, description="An operation also needs at least this probability"
    )

    def to_rules(self) -> dict[str, Any]:
        """The rules JSON the domain parses."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


class ApprovalPolicyResponse(BaseModel):
    """A taxonomy's approval policy; empty (nothing auto-applies) until one is set."""

    taxonomy_id: str
    auto_apply: list[AutoApplyRuleSchema]
    min_probability: float

    @classmethod
    def from_domain(cls, policy: ApprovalPolicy) -> "ApprovalPolicyResponse":
        rules = policy.to_rules()
        return cls(
            taxonomy_id=policy.taxonomy_id,
            auto_apply=[AutoApplyRuleSchema.model_validate(r) for r in rules["auto_apply"]],
            min_probability=rules["min_probability"],
        )
