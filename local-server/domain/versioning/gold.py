"""
Gold: every reviewer or policy decision on a proposal operation, kept as data.

A decision is recorded when an operation is applied (as proposed or with a
reviewer's edits) or rejected, with when, by whom, the operation as proposed
and what was finally applied. Reverting a proposal supersedes its applied
decisions (kept, marked, not deleted); its rejections still stand. Closing
an operation that nobody judged (a revert rejecting what was still
undecided, a bundle import superseding an older plan) records no decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposedOperation,
)

DECIDED_BY_USER = "user"
DECIDED_BY_POLICY = "policy"
# A bundle import applying its non-breaking operations (apply=true).
DECIDED_BY_BUNDLE = "bundle"
# Decisions backfilled from operations decided before decisions were recorded.
DECIDED_BY_UNKNOWN = "unknown"


class DecisionKind(str, Enum):
    """What was decided."""

    APPLIED = "applied"
    REJECTED = "rejected"
    APPLIED_WITH_EDITS = "applied_with_edits"


@dataclass
class ProposalDecision:
    """
    One decision on one proposal operation.

    Attributes:
        operation_id, proposal_id, taxonomy_id: What was decided, where
        seq, kind, op: The operation's position, entity kind and type
        decision: Applied, rejected or applied with edits
        decided_at: When (timezone-aware)
        decided_by: "user", "policy", "bundle", an agent source, or "unknown"
            (backfilled)
        proposed: The operation as proposed (see `proposed_snapshot`)
        applied_fields: The fields finally applied (the edit, if edited); None
            when rejected; empty when a create was matched to an existing
            individual (it applied nothing)
        result_entity_id: The entity created or changed, when applied
        reason: Why (a reject note)
        resolution: How an applied relationship-type delete resolved the
            relationships still using the type, if it did
        chosen_alternative: The alternative the reviewer chose, when there is one
        probability: The operation's probability, if it had one
        model: The decision model that produced the probability, if one did
        superseded_at, superseded_by: Set when a revert undid the (applied) decision
        id: Unique id
    """

    operation_id: str
    proposal_id: str
    taxonomy_id: str
    seq: int
    kind: OperationKind
    op: OperationType
    decision: DecisionKind
    decided_at: datetime
    decided_by: str
    proposed: dict[str, Any] = field(default_factory=dict)
    applied_fields: dict[str, Any] | None = None
    result_entity_id: str | None = None
    reason: str | None = None
    resolution: dict[str, Any] | None = None
    chosen_alternative: dict[str, Any] | None = None
    probability: float | None = None
    model: str | None = None
    superseded_at: datetime | None = None
    superseded_by: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.decided_at.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware")
        if not self.decided_by:
            raise ValueError("A decision needs decided_by")


def proposed_snapshot(operation: ProposedOperation) -> dict[str, Any]:
    """The operation as proposed, before any reviewer edit or apply changed it."""
    return {
        "seq": operation.seq,
        "op": operation.op.value,
        "kind": operation.kind.value,
        "target_id": operation.target_id,
        "ref": operation.ref,
        "fields": dict(operation.fields),
        "base": dict(operation.base),
        "rationale": operation.rationale,
        "notes": operation.notes,
        "evidence": list(operation.evidence),
        "probability": operation.probability,
        "scope": operation.scope.value,
        "proposed_replacement_id": operation.proposed_replacement_id,
        "alternatives": [dict(a) for a in operation.alternatives],
    }


def decision_of(
    proposal: ChangeProposal,
    operation: ProposedOperation,
    decided_by: str,
    decided_at: datetime,
    proposed: dict[str, Any] | None = None,
    chosen_alternative: dict[str, Any] | None = None,
) -> ProposalDecision:
    """
    The decision an applied or rejected operation records.

    Args:
        proposed: The operation as proposed, taken before applying it (an edit
            rewrites its base); defaults to a snapshot of it as it is now
        chosen_alternative: The alternative the reviewer chose, when there is one

    Raises:
        ValueError: If the operation is neither applied nor rejected
    """
    if operation.status is OperationStatus.REJECTED:
        decision, applied = DecisionKind.REJECTED, None
    elif operation.status is OperationStatus.APPLIED:
        edited = operation.applied_fields is not None
        decision = DecisionKind.APPLIED_WITH_EDITS if edited else DecisionKind.APPLIED
        applied = dict(operation.applied_fields if edited else operation.fields)  # type: ignore[arg-type]
        if operation.matched:
            applied = {}
    else:
        raise ValueError(f"seq {operation.seq} is {operation.status.value}, not decided")
    return ProposalDecision(
        operation_id=operation.id,
        proposal_id=proposal.id,
        taxonomy_id=proposal.taxonomy_id,
        seq=operation.seq,
        kind=operation.kind,
        op=operation.op,
        decision=decision,
        decided_at=decided_at,
        decided_by=decided_by,
        proposed=proposed if proposed is not None else proposed_snapshot(operation),
        applied_fields=applied,
        result_entity_id=(
            operation.result_entity_id if operation.status is OperationStatus.APPLIED else None
        ),
        reason=operation.reason,
        resolution=operation.resolution.to_json() if operation.resolution else None,
        chosen_alternative=dict(chosen_alternative) if chosen_alternative is not None else None,
        probability=operation.probability,
    )


def by_operation(decisions: list[ProposalDecision]) -> dict[str, ProposalDecision]:
    """Operation id -> its latest decision, of decisions listed oldest first."""
    return {d.operation_id: d for d in decisions}


@dataclass(frozen=True)
class DecisionFilter:
    """
    Which decisions to list; None leaves a filter out.

    Attributes:
        decided_from: Decided at or after (inclusive)
        decided_to: Decided before (exclusive)
        include_superseded: Also decisions a revert superseded
    """

    taxonomy_id: str | None = None
    proposal_id: str | None = None
    kind: OperationKind | None = None
    op: OperationType | None = None
    decision: DecisionKind | None = None
    decided_by: str | None = None
    decided_from: datetime | None = None
    decided_to: datetime | None = None
    include_superseded: bool = False
