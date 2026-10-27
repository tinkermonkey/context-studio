"""In-memory ChangeProposalRepository for domain tests."""

from __future__ import annotations

import copy
from typing import Optional, Sequence

from domain.versioning.proposals import (
    ChangeProposal,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)


class FakeChangeProposalRepository:
    """Stores proposals in a dict; returns copies so callers can't mutate stored state."""

    def __init__(self) -> None:
        self._proposals: dict[str, ChangeProposal] = {}

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
        taxonomy_id: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        source: Optional[ProposalSource] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChangeProposal]:
        matches = sorted(
            self._matching(taxonomy_id, status, source),
            key=lambda p: (p.created_at, p.id),
            reverse=True,
        )
        return [copy.deepcopy(p) for p in matches[offset : offset + limit]]

    def count_proposals(
        self,
        taxonomy_id: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        source: Optional[ProposalSource] = None,
    ) -> int:
        return len(self._matching(taxonomy_id, status, source))

    def save_operations(self, proposal_id: str, operations: Sequence[ProposedOperation]) -> None:
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

    def set_status(self, proposal_id: str, status: ProposalStatus) -> None:
        if proposal_id not in self._proposals:
            raise ValueError(f"No proposal {proposal_id}")
        self._proposals[proposal_id].status = status

    def _matching(
        self,
        taxonomy_id: Optional[str],
        status: Optional[ProposalStatus],
        source: Optional[ProposalSource],
    ) -> list[ChangeProposal]:
        return [
            p
            for p in self._proposals.values()
            if (taxonomy_id is None or p.taxonomy_id == taxonomy_id)
            and (status is None or p.status == status)
            and (source is None or p.source == source)
        ]
