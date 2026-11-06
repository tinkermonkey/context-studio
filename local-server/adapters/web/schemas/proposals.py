"""
Pydantic schemas for the change proposal API.

Names carry the ChangeProposal prefix, the domain's name for a proposal.
"""

from datetime import datetime
from typing import Any, Collection, Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.gold import DecisionKind, ProposalDecision
from domain.versioning.in_use import DeleteBlockers, PairMatch, ReplacementCheck
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
    replacement: Optional[str] = Field(
        None,
        description="A property (relationship type) delete only: the type that replaces it, "
        'by id, identifier or "$<ref>" of an earlier property create. Its domain and range '
        "are compared with the deleted type's (see replacement_check)",
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
        "blockers), or a property update that retargets (gives the type another domain and "
        "range pair) no longer fits. Moved or deleted in one transaction with the type; a "
        "misfit or any failing step fails only that operation, changing nothing. Not with an "
        "edit of the same delete; an update that renames or reverses the type takes none "
        "(a reverse always swaps the ends of its relationships)",
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
    reversed: bool = Field(
        False,
        description="Its domain and range are the deleted type's reversed: moving re-creates "
        "each relationship with its source and target swapped",
    )


class DeleteBlockersResponse(BaseModel):
    """What blocks a relationship-type delete: the relationships that still use the type."""

    model_config = ConfigDict(from_attributes=True)

    edges: list[BlockingEdgeResponse]
    replacements: list[ReplacementTypeResponse] = Field(
        default_factory=list,
        description="Types whose domain and range accept both ends of every edge "
        "(inheritance-aware; swapped, for a reversed type) and that allow their attributes; "
        "empty when none does",
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
    reversed: bool = Field(
        False,
        description="A move to a reversed type: each relationship was re-created with its "
        "ends swapped (edges keep the original ends)",
    )
    edges: list[ResolvedEdgeResponse] = Field(
        default_factory=list, description="The relationships moved or deleted"
    )


class ClassEndResponse(BaseModel):
    """A domain or range class (both null: untyped)."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    title: Optional[str] = None


class ChainLinkResponse(BaseModel):
    """One replacement in a chain of deletes."""

    model_config = ConfigDict(from_attributes=True)

    replacement_id: str = Field(..., description='The type: an id or "$<ref>"')
    identifier: Optional[str] = None
    deleted_by_seq: Optional[int] = Field(
        None, description="The delete of this proposal that removes it; null where the chain ends"
    )


class ReplacementCheckResponse(BaseModel):
    """A relationship-type delete's named replacement, compared with the deleted type."""

    model_config = ConfigDict(from_attributes=True)

    replacement_id: str = Field(..., description='The replacement as proposed: an id or "$<ref>"')
    property_id: Optional[str] = Field(
        None,
        description="The replacement type once it exists; null for a $ref whose create isn't "
        "applied yet, or a replacement since deleted",
    )
    identifier: Optional[str] = None
    title: Optional[str] = None
    pair: PairMatch = Field(
        ...,
        description="same: the same domain and range; reversed: the two swapped; different: "
        "a different pair of classes (flagged: it can't take over the deleted type's "
        "relationships as they are); missing: the replacement is gone or its create rejected",
    )
    deleted_domain: ClassEndResponse
    deleted_range: ClassEndResponse
    domain: Optional[ClassEndResponse] = Field(None, description="Null when missing")
    range: Optional[ClassEndResponse] = Field(None, description="Null when missing")
    replacement_deleted: bool = Field(
        False, description="The proposal also deletes the replacement (flagged)"
    )
    chain: list[ChainLinkResponse] = Field(
        default_factory=list,
        description="Empty unless replacement_deleted: each replacement in turn, following "
        "each delete's own replacement, to the type it ends at (the last link, with no "
        "deleted_by_seq) or until it comes back round",
    )
    cycle: bool = Field(
        False,
        description="The chain comes back round to a type already in it: every type in it "
        "is deleted, so nothing replaces this one",
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
        description="Set when a relationship-type delete or retarget was applied with a "
        "resolution: what happened to the relationships that used it. Null otherwise",
    )
    stale: bool = Field(
        False,
        description="Pending or failed, and its target is gone or a field it touches "
        "changed since proposed; applying it needs force_stale",
    )
    blockers: Optional[DeleteBlockersResponse] = Field(
        None,
        description="A pending or failed relationship-type delete whose type relationships "
        "still use: applying it as proposed fails; it needs a resolution. Null otherwise. "
        "The proposed replacement, when it fits, is listed first",
    )
    proposed_replacement_id: Optional[str] = Field(
        None,
        description="A relationship-type delete only: the type the proposer names as its "
        'replacement (a property definition id, or "$<ref>" of a create in this proposal)',
    )
    replacement_check: Optional[ReplacementCheckResponse] = Field(
        None, description="Set when proposed_replacement_id is: how its pair compares"
    )
    auto_apply: Optional[bool] = Field(
        None,
        description="A dry run only: eligible to auto-apply, i.e. the taxonomy's approval "
        "policy would apply it as soon as proposed and no in-use blockers stop it (applying "
        "can still fail). Null otherwise",
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
    dry_run: bool = Field(
        False,
        description="Validated only: nothing was stored or applied, and the ids are not kept",
    )
    operations: list[ProposedOperationResponse]

    @classmethod
    def from_domain(
        cls,
        proposal: ChangeProposal,
        stale_ids: set[str],
        blockers: Optional[dict[str, DeleteBlockers]] = None,
        replacement_checks: Optional[dict[str, ReplacementCheck]] = None,
        auto_apply_ids: Optional[Collection[str]] = None,
    ) -> "ChangeProposalResponse":
        """
        Build the response, flagging the operations in stale_ids, with their blockers.

        Args:
            auto_apply_ids: A dry run's auto-apply verdict (see
                ProposalService.auto_apply_operation_ids); given, the response
                is a dry run and each operation says whether it would auto-apply
        """
        blockers = blockers or {}
        checks = replacement_checks or {}
        response = cls(
            id=proposal.id,
            taxonomy_id=proposal.taxonomy_id,
            title=proposal.title,
            rationale=proposal.rationale,
            source=proposal.source,
            source_detail=proposal.source_detail,
            created_at=proposal.created_at,
            status=proposal.status,
            operations=[
                _operation(o, o.id in stale_ids, blockers.get(o.id), checks.get(o.id))
                for o in proposal.operations
            ],
        )
        if auto_apply_ids is not None:
            auto = set(auto_apply_ids)
            response.dry_run = True
            for operation in response.operations:
                operation.auto_apply = operation.id in auto
        return response


def _operation(
    operation: ProposedOperation,
    stale: bool,
    blockers: Optional[DeleteBlockers],
    check: Optional[ReplacementCheck],
) -> ProposedOperationResponse:
    response = ProposedOperationResponse.model_validate(operation)
    response.stale = stale
    if blockers is not None:
        response.blockers = DeleteBlockersResponse.model_validate(blockers)
    if check is not None:
        response.replacement_check = ReplacementCheckResponse.model_validate(check)
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
        description="Only on a delete or retarget applied with a resolution: the strategy, the "
        "replacement type and the relationships moved or deleted; absent (not null) otherwise",
    )
    reason: Optional[str] = None
    result_entity_id: Optional[str] = None
    decided_at: Optional[str] = Field(
        None, description="When the operation was decided (ISO 8601); null if undecided"
    )
    decided_by: Optional[str] = Field(
        None,
        description="Who decided: user, policy, an agent source, or unknown (decided "
        "before decisions were recorded); null if undecided",
    )


# ==================== Gold ====================


class GoldDecisionResponse(BaseModel):
    """
    One reviewer or policy decision on a proposal operation: gold.

    A revert supersedes the proposal's applied decisions (superseded_at,
    superseded_by) rather than deleting them; its rejections still stand.
    """

    id: str
    operation_id: str
    proposal_id: str
    taxonomy_id: str
    seq: int
    kind: OperationKind
    op: OperationType
    decision: DecisionKind = Field(..., description="applied, rejected or applied_with_edits")
    decided_at: datetime
    decided_by: str = Field(
        ...,
        description="user, policy, an agent source, or unknown (decided before decisions "
        "were recorded)",
    )
    proposed: dict[str, Any] = Field(
        ...,
        description="The operation as proposed: seq, op, kind, target_id, ref, fields, base, "
        "rationale, evidence, probability, scope, proposed_replacement_id",
    )
    applied_fields: Optional[dict[str, Any]] = Field(
        None, description="The fields finally applied (the edit, if edited); null when rejected"
    )
    result_entity_id: Optional[str] = None
    reason: Optional[str] = Field(None, description="Why (a reject note)")
    resolution: Optional[dict[str, Any]] = Field(
        None, description="An applied relationship-type delete's or retarget's in-use resolution"
    )
    chosen_alternative: Optional[dict[str, Any]] = Field(
        None, description="The alternative the reviewer chose, when there is one"
    )
    probability: Optional[float] = None
    model: Optional[str] = Field(
        None, description="The decision model that produced the probability, if one did"
    )
    superseded_at: Optional[datetime] = None
    superseded_by: Optional[str] = None

    @classmethod
    def from_domain(cls, decision: ProposalDecision) -> "GoldDecisionResponse":
        return cls(**vars(decision))


# ==================== Approval policy ====================


class AutoApplyRuleSchema(BaseModel):
    """Operations matching every key set here may apply as soon as they are proposed."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    op: Optional[OperationType] = Field(None, description="Only this operation type")
    kind: Optional[OperationKind] = Field(None, description="Only this kind of entity")
    class_: Optional[str] = Field(
        None,
        alias="class",
        description="Only entities typed by this class (id or identifier) or a subclass of "
        "it: an individual's classes (for a create, the class_ids it is given), an "
        "attribute's class, the class itself (for a class create, its proposed parent), or "
        "the classes of a relationship's source and target. Every class an entity is typed "
        "by must be covered, by a rule naming it or an ancestor, or by a rule with no class",
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
    """
    A taxonomy's approval policy; empty (nothing auto-applies) until one is set.

    A rule naming a class matches an operation on an entity typed by that class
    or any subclass of it: an individual (its current classes plus any it is
    given; for a create, its class_ids), an attribute (its class), a class (the
    class itself; for a create, its proposed parent, so a top-level class create
    matches only rules without a class) or a relationship (the classes of its
    source and of its target). Every class must be covered.
    """

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
