"""In-memory EntitySourceRepository for domain tests."""

from __future__ import annotations

from typing import Sequence

from domain.versioning.provenance import EntitySource


class FakeEntitySourceRepository:
    """Keeps provenance rows in a list, in the order added."""

    def __init__(self) -> None:
        self.rows: list[EntitySource] = []

    def add(self, sources: Sequence[EntitySource]) -> None:
        self.rows.extend(sources)

    def list_for_entity(self, entity_id: str) -> list[EntitySource]:
        return [row for row in self.rows if row.entity_id == entity_id]

    def delete_for_proposal(self, proposal_id: str) -> int:
        kept = [row for row in self.rows if row.proposal_id != proposal_id]
        removed = len(self.rows) - len(kept)
        self.rows = kept
        return removed
