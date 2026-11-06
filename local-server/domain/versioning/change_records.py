"""
Schema change records: what an applied proposal did to its relationship types,
in a shape that composes across proposals the way DR's change records do
(`applied-*.json`, folded by DR's generate-relationship-migration.ts).

One record per applied relationship-type (property) operation that recorded
a TypeChange as it applied:

    create    a new type; from and to are the type
    rename    the same pair of classes under another key: its relationships keep
    reverse   the pair reversed: its relationships swapped ends (swap)
    retarget  another pair: to is the type as retargeted; its relationships
              (if any) moved to moved_to (swap when they swapped ends) or were
              deleted (moved_to None)
    delete    the type removed; to is the type its relationships moved to
              (swap when they swapped ends), or the type the delete names as
              its replacement when that links the same pair or the reverse;
              otherwise None, as its relationships were deleted or there were none

An update whose key didn't change makes no record, nor does an operation
applied before TypeChange was recorded. A reverted proposal has none: its
changes were undone. Records compose oldest first: a record whose `from` is an
earlier one's `to` continues it (A to B, then B to C, is A to C), and two
swaps cancel.

A type is named by a key computed from its recorded fields (snapshot JSON):
its identifier by default; the DR export keys it by its DR relationship id.
Records read only what the operation recorded as it applied, never the
workspace or what was proposed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from domain.versioning.gold import ProposalDecision
from domain.versioning.proposals import (
    ChangeProposal,
    OperationStatus,
    ProposalStatus,
    SchemaChangeAction,
    TypeChange,
)

TypeKey = Callable[[Mapping[str, Any]], "str | None"]

__all__ = [
    "SchemaChangeAction",
    "SchemaChangeRecord",
    "identifier_key",
    "schema_change_records",
]


@dataclass(frozen=True)
class SchemaChangeRecord:
    """
    One relationship-type change, as a rewrite of the relationships using it.

    Attributes:
        action: What happened to the type
        from_: The type's key before (a create: the new type)
        to: Its key after; for a delete, the type its relationships moved to
            (None if they didn't)
        swap: Relationships of `from_` run the other way where they went
        p: The proposer's confidence (1 when it gave none)
        proposal_id, operation_id: The applied operation
        applied_at: When it was decided (ISO 8601), None if no decision was recorded
        moved_to: A retarget only: the type its relationships moved to (None
            if they were deleted or there were none)
    """

    action: SchemaChangeAction
    from_: str
    to: str | None
    swap: bool
    p: float
    proposal_id: str
    operation_id: str
    applied_at: str | None
    moved_to: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "from": self.from_,
            "to": self.to,
            "swap": self.swap,
            "p": self.p,
            "proposal_id": self.proposal_id,
            "operation_id": self.operation_id,
            "applied_at": self.applied_at,
            "moved_to": self.moved_to,
        }


def identifier_key(fields: Mapping[str, Any]) -> str | None:
    """A type's key by default: its identifier."""
    identifier = fields.get("identifier")
    return identifier if isinstance(identifier, str) else None


def schema_change_records(
    proposal: ChangeProposal,
    decisions: Mapping[str, ProposalDecision] | None = None,
    key: TypeKey = identifier_key,
) -> list[SchemaChangeRecord]:
    """
    The schema change records of a proposal's applied relationship-type operations, in seq order.

    Args:
        decisions: Operation id -> its recorded decision, for applied_at
        key: A type's key from its recorded fields; a change whose type has
            none makes no record
    """
    if proposal.status is ProposalStatus.REVERTED:
        return []
    records = []
    for operation in proposal.operations:
        change = operation.type_change
        if operation.status is not OperationStatus.APPLIED or change is None:
            continue
        found = _record(change, key)
        if found is None:
            continue
        decision = (decisions or {}).get(operation.id)
        records.append(
            SchemaChangeRecord(
                p=operation.probability if operation.probability is not None else 1.0,
                proposal_id=proposal.id,
                operation_id=operation.id,
                applied_at=decision.decided_at.isoformat() if decision else None,
                **found,
            )
        )
    return records


def _record(change: TypeChange, key: TypeKey) -> dict[str, Any] | None:
    before = key(change.before) if change.before is not None else None
    after = key(change.after) if change.after is not None else None
    replacement = key(change.replacement) if change.replacement is not None else None
    action = change.action
    if action is SchemaChangeAction.CREATE:
        return _fields(action, after, after) if after else None
    if before is None:
        return None
    if action is SchemaChangeAction.DELETE:
        return _fields(action, before, replacement, change.swap and replacement is not None)
    if after is None:
        return None
    if action is SchemaChangeAction.RETARGET:
        moved = replacement is not None
        return _fields(action, before, after, change.swap and moved, replacement)
    if action is SchemaChangeAction.RENAME and before == after:
        return None
    return _fields(action, before, after, change.swap)


def _fields(
    action: SchemaChangeAction,
    from_: str,
    to: str | None,
    swap: bool = False,
    moved_to: str | None = None,
) -> dict[str, Any]:
    return {"action": action, "from_": from_, "to": to, "swap": swap, "moved_to": moved_to}
