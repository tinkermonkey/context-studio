"""In-memory ChangeProposalRepository for domain tests."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Optional, Sequence

from domain.versioning.gold import DecisionFilter, DecisionKind, ProposalDecision
from domain.versioning.proposals import (
    ChangeProposal,
    Landing,
    OperationCount,
    ProposalFilter,
    ProposalStatus,
    ProposedOperation,
    count_operations,
)


class FakeChangeProposalRepository:
    """Stores proposals in a dict; returns copies so callers can't mutate stored state."""

    def __init__(self) -> None:
        self._proposals: dict[str, ChangeProposal] = {}
        self.decisions: list[ProposalDecision] = []

    def create(self, proposal: ChangeProposal) -> ChangeProposal:
        if proposal.id in self._proposals:
            raise ValueError(f"Proposal {proposal.id} already exists")
        self._proposals[proposal.id] = copy.deepcopy(proposal)
        return copy.deepcopy(proposal)

    def get(self, proposal_id: str) -> Optional[ChangeProposal]:
        found = self._proposals.get(proposal_id)
        return copy.deepcopy(found) if found else None

    def list_proposals(
        self,
        filters: ProposalFilter,
        limit: int = 50,
        offset: int = 0,
        with_operations: bool = True,
    ) -> list[ChangeProposal]:
        matches = sorted(
            (p for p in self._proposals.values() if filters.matches(p)),
            key=lambda p: (p.created_at, p.id),
            reverse=True,
        )
        found = [copy.deepcopy(p) for p in matches[offset : offset + limit]]
        if not with_operations:
            for proposal in found:
                proposal.operations = []
        return found

    def count_proposals(self, filters: ProposalFilter) -> int:
        return sum(1 for p in self._proposals.values() if filters.matches(p))

    def operation_tallies(self, proposal_ids: Sequence[str]) -> dict[str, list[OperationCount]]:
        return {
            proposal_id: count_operations(self._proposals[proposal_id].operations)
            for proposal_id in proposal_ids
            if proposal_id in self._proposals
        }

    def operation_counts(self, proposal_ids: Sequence[str]) -> dict[str, int]:
        return {
            proposal_id: len(self._proposals[proposal_id].operations)
            for proposal_id in proposal_ids
            if proposal_id in self._proposals
        }

    def set_landed(self, proposal_id: str, landed: Optional[Landing]) -> None:
        if proposal_id not in self._proposals:
            raise ValueError(f"No proposal {proposal_id}")
        self._proposals[proposal_id].landed = landed

    def add_operations(self, proposal_id: str, operations: Sequence[ProposedOperation]) -> None:
        if proposal_id not in self._proposals:
            raise ValueError(f"No proposal {proposal_id}")
        stored = self._proposals[proposal_id].operations
        taken = {o.seq for o in stored} & {o.seq for o in operations}
        if taken:
            raise ValueError(f"Proposal {proposal_id} already has seq {sorted(taken)}")
        stored.extend(copy.deepcopy(o) for o in operations)
        stored.sort(key=lambda o: o.seq)

    def save_operations(
        self,
        proposal_id: str,
        operations: Sequence[ProposedOperation],
        decisions: Sequence[ProposalDecision] = (),
    ) -> None:
        if proposal_id not in self._proposals:
            raise ValueError(f"No proposal {proposal_id}")
        stored = {o.id: o for o in self._proposals[proposal_id].operations}
        missing = [o.id for o in operations if o.id not in stored]
        if missing:
            raise ValueError(f"Proposal {proposal_id} has no operations {missing}")
        for operation in operations:
            target = stored[operation.id]
            target.status = operation.status
            target.result_entity_id = operation.result_entity_id
            target.reason = operation.reason
            target.reason_code = operation.reason_code
            target.scope = operation.scope
            target.applied_fields = copy.deepcopy(operation.applied_fields)
            target.resolution = copy.deepcopy(operation.resolution)
            target.type_change = copy.deepcopy(operation.type_change)
            target.base = copy.deepcopy(operation.base)
        self.decisions += [copy.deepcopy(d) for d in decisions]

    def set_decision_comparison(self, operation_id: str, comparison: dict) -> None:
        standing = [
            d for d in self.decisions if d.operation_id == operation_id and d.superseded_at is None
        ]
        if not standing:
            raise ValueError(f"Operation {operation_id} has no standing decision")
        standing[-1].comparison = copy.deepcopy(comparison)

    def supersede_decisions(self, proposal_id: str, superseded_at: datetime, by: str) -> int:
        standing = [
            d
            for d in self.decisions
            if d.proposal_id == proposal_id
            and d.superseded_at is None
            and d.decision is not DecisionKind.REJECTED
        ]
        for decision in standing:
            decision.superseded_at = superseded_at
            decision.superseded_by = by
        return len(standing)

    def supersede_operation_decisions(
        self, proposal_id: str, operation_ids, superseded_at: datetime, by: str
    ) -> int:
        standing = [
            d
            for d in self.decisions
            if d.proposal_id == proposal_id
            and d.operation_id in operation_ids
            and d.superseded_at is None
        ]
        for decision in standing:
            decision.superseded_at = superseded_at
            decision.superseded_by = by
        return len(standing)

    def list_decisions(
        self, filters: DecisionFilter, limit: Optional[int] = None, offset: int = 0
    ) -> list[ProposalDecision]:
        found = sorted(
            (d for d in self.decisions if _matches(d, filters)),
            key=lambda d: (d.decided_at, d.proposal_id, d.seq),
        )[offset:]
        return [copy.deepcopy(d) for d in (found if limit is None else found[:limit])]

    def count_decisions(self, filters: DecisionFilter) -> int:
        return len([d for d in self.decisions if _matches(d, filters)])

    def set_status(self, proposal_id: str, status: ProposalStatus) -> None:
        if proposal_id not in self._proposals:
            raise ValueError(f"No proposal {proposal_id}")
        self._proposals[proposal_id].status = status


def _matches(decision: ProposalDecision, f: DecisionFilter) -> bool:
    return (
        (f.taxonomy_id is None or decision.taxonomy_id == f.taxonomy_id)
        and (f.proposal_id is None or decision.proposal_id == f.proposal_id)
        and (f.kind is None or decision.kind is f.kind)
        and (f.op is None or decision.op is f.op)
        and (f.decision is None or decision.decision is f.decision)
        and (f.decided_by is None or decision.decided_by == f.decided_by)
        and (f.decided_from is None or decision.decided_at >= f.decided_from)
        and (f.decided_to is None or decision.decided_at < f.decided_to)
        and (f.include_superseded or decision.superseded_at is None)
    )
