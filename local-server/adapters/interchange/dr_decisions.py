"""
The decisions on a DR reflection-plan proposal, as DR's
`proposal-import.ts --decisions` reads them.

One `{seq, op_id, status, fields?, reason, result_entity_id}` per operation,
joined to DR's plan by seq. Shared by `scripts/export_dr_decisions.py` and
`GET /api/proposals/{id}/decisions`.
"""

from __future__ import annotations

from typing import Any

from adapters.interchange.dr_relationships import Triple, dr_relationship_id
from domain.versioning.proposals import ChangeProposal, OperationStatus, ProposalStatus


def decisions_for(proposal: ChangeProposal) -> list[dict[str, Any]]:
    """
    The decisions file for DR's `proposal-import.ts --decisions`, joined by seq.

    Pending operations are included with status "pending", which DR skips. An
    operation a reviewer edited before applying it also carries `fields`: the
    whole applied triple in DR's vocabulary (`predicate`,
    `source_spec_node_id`, `destination_spec_node_id`); without it, an applied
    operation was applied as proposed. An edited delete is applied with fields.

    Raises:
        ValueError: If the proposal was reverted, so none of it stands, or an
            edited operation's applied fields carry no DR relationship id
    """
    if proposal.status is ProposalStatus.REVERTED:
        raise ValueError(
            f"Change proposal {proposal.id} was reverted; its decisions no longer hold"
        )
    decisions = []
    for operation in proposal.operations:
        decision: dict[str, Any] = {
            "seq": operation.seq,
            "op_id": operation.id,
            "status": operation.status.value,
        }
        if operation.status is OperationStatus.APPLIED and operation.applied_fields is not None:
            decision["fields"] = _applied_triple(operation.seq, operation.applied_fields).fields()
        decision["reason"] = operation.reason
        decision["result_entity_id"] = operation.result_entity_id
        decisions.append(decision)
    return decisions


def _applied_triple(seq: int, applied_fields: dict[str, Any]) -> Triple:
    relationship_id = dr_relationship_id(applied_fields.get("external_references") or [])
    if relationship_id is None:
        raise ValueError(f"seq {seq} was edited, but its applied fields have no DR relationship id")
    return Triple.parse(relationship_id)
