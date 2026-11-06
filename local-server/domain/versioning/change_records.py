"""
Schema change records: what an applied proposal did to its relationship types,
in a shape that composes across proposals the way DR's change records do
(`applied-*.json`, folded by DR's generate-relationship-migration.ts).

One record per applied relationship-type (property) operation that changes
how relationships of the type read:

    create    a new type; from and to are the type
    rename    the same pair of classes under another key: its relationships keep
    reverse   the pair reversed: its relationships swapped ends (swap)
    retarget  another pair: its relationships stayed, moved or were deleted as
              the reviewer resolved them (see ProposalService.apply)
    delete    the type removed; to is the type its relationships moved to
              (swap when they swapped ends), or the type the delete names as
              its replacement when that links the same pair or the reverse;
              otherwise None, as its relationships were deleted or there were none

An update that changes neither the pair nor the key (wording, attributes)
makes no record. Records compose oldest first: a record whose `from` is an
earlier one's `to` continues it (A to B, then B to C, is A to C), and two swaps
cancel.

A type is named by a key computed from its fields as an entity snapshot
(`domain.ontology.snapshots`): its identifier by default; the DR export keys
it by its DR relationship id. Records read only the operation: an applied
update keeps the type's key fields as they were in its `base`, so a later
change to the type doesn't change what an earlier record says.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

from domain.versioning.gold import ProposalDecision
from domain.versioning.in_use import PairMatch, compare_pair
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposedOperation,
    ResolutionStrategy,
)

# The fields a type's pair and key are read from; an applied update keeps them in its base.
TYPE_KEY_FIELDS = (
    "identifier",
    "canonical_predicate",
    "domain_class_id",
    "range_class_id",
    "external_references",
)

TypeKey = Callable[[Mapping[str, Any]], "str | None"]


class SchemaChangeAction(str, Enum):
    """What an operation did to a relationship type."""

    CREATE = "create"
    RENAME = "rename"
    REVERSE = "reverse"
    RETARGET = "retarget"
    DELETE = "delete"


@dataclass(frozen=True)
class SchemaChangeRecord:
    """
    One relationship-type change, as a rewrite of the relationships using it.

    Attributes:
        action: What happened to the type
        from_: The type's key before (a create: the new type)
        to: Its key after; None for a delete whose relationships didn't move
        swap: Relationships of `from_` run the other way as `to`
        p: The proposer's confidence (1 when it gave none)
        proposal_id, operation_id: The applied operation
        applied_at: When it was decided (ISO 8601), None if no decision was recorded
    """

    action: SchemaChangeAction
    from_: str
    to: str | None
    swap: bool
    p: float
    proposal_id: str
    operation_id: str
    applied_at: str | None

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
        }


def identifier_key(fields: Mapping[str, Any]) -> str | None:
    """A type's key by default: its identifier."""
    identifier = fields.get("identifier")
    return identifier if isinstance(identifier, str) else None


def schema_change_records(
    proposal: ChangeProposal,
    decisions: Mapping[str, ProposalDecision] | None = None,
    key: TypeKey = identifier_key,
    type_of: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> list[SchemaChangeRecord]:
    """
    The schema change records of a proposal's applied relationship-type operations, in seq order.

    Args:
        decisions: Operation id -> its recorded decision, for applied_at
        key: A type's key from its fields; an operation whose type has none
            (before and after) makes no record
        type_of: A type's current fields by id, to key a delete's
            replacement; without it, a delete keys the type its relationships
            moved to by the identifier its resolution recorded
    """
    refs = {o.ref: o.result_entity_id for o in proposal.operations if o.ref}
    records = []
    for operation in proposal.operations:
        if operation.kind is not OperationKind.PROPERTY:
            continue
        if operation.status is not OperationStatus.APPLIED:
            continue
        found = _record(operation, refs, key, type_of)
        if found is None:
            continue
        action, from_, to, swap = found
        decision = (decisions or {}).get(operation.id)
        records.append(
            SchemaChangeRecord(
                action=action,
                from_=from_,
                to=to,
                swap=swap,
                p=operation.probability if operation.probability is not None else 1.0,
                proposal_id=proposal.id,
                operation_id=operation.id,
                applied_at=decision.decided_at.isoformat() if decision else None,
            )
        )
    return records


def _record(
    operation: ProposedOperation,
    refs: dict[str, str | None],
    key: TypeKey,
    type_of: Callable[[str], Mapping[str, Any] | None] | None,
) -> tuple[SchemaChangeAction, str, str | None, bool] | None:
    if operation.op is OperationType.CREATE:
        created = key(_resolved(operation.fields, refs))
        return (SchemaChangeAction.CREATE, created, created, False) if created else None
    if operation.op is OperationType.UPDATE or operation.applied_fields is not None:
        # An edited delete applied as an update.
        return _update(operation, refs, key)
    if operation.op is OperationType.DELETE:
        return _delete(operation, refs, key, type_of)
    return None


def _update(
    operation: ProposedOperation, refs: dict[str, str | None], key: TypeKey
) -> tuple[SchemaChangeAction, str, str | None, bool] | None:
    applied = operation.applied_fields if operation.applied_fields is not None else operation.fields
    before = dict(operation.base)
    after = {**before, **_resolved(applied, refs)}
    from_, to = key(before), key(after)
    if from_ is None:
        from_ = to
    if to is None:
        to = from_
    if from_ is None:
        return None
    pair = compare_pair(_pair(before), _pair(after))
    if pair is PairMatch.REVERSED:
        return SchemaChangeAction.REVERSE, from_, to, True
    if pair is PairMatch.DIFFERENT:
        return SchemaChangeAction.RETARGET, from_, to, False
    if from_ != to:
        return SchemaChangeAction.RENAME, from_, to, False
    return None


def _delete(
    operation: ProposedOperation,
    refs: dict[str, str | None],
    key: TypeKey,
    type_of: Callable[[str], Mapping[str, Any] | None] | None,
) -> tuple[SchemaChangeAction, str, str | None, bool] | None:
    from_ = key(operation.base)
    if from_ is None:
        return None
    resolution = operation.resolution
    if resolution is not None and resolution.strategy is ResolutionStrategy.MOVE:
        moved_to = resolution.replacement_property_id
        if type_of is None:
            return (
                SchemaChangeAction.DELETE,
                from_,
                resolution.replacement_identifier,
                resolution.reversed,
            )
        replacement = type_of(moved_to) if moved_to else None
        to = key(replacement) if replacement is not None else None
        return SchemaChangeAction.DELETE, from_, to, resolution.reversed if to else False
    if resolution is not None or type_of is None:
        return SchemaChangeAction.DELETE, from_, None, False
    named = operation.proposed_replacement_id
    if named and named.startswith("$"):
        named = refs.get(named[1:])
    replacement = type_of(named) if named else None
    if replacement is None:
        return SchemaChangeAction.DELETE, from_, None, False
    pair = compare_pair(_pair(operation.base), _pair(replacement))
    if pair is PairMatch.DIFFERENT:
        return SchemaChangeAction.DELETE, from_, None, False
    return SchemaChangeAction.DELETE, from_, key(replacement), pair is PairMatch.REVERSED


def _pair(fields: Mapping[str, Any]) -> tuple[Any, Any]:
    return fields.get("domain_class_id"), fields.get("range_class_id")


def _resolved(fields: Mapping[str, Any], refs: dict[str, str | None]) -> dict[str, Any]:
    """Fields with "$ref" class ids as the classes the proposal's creates made."""
    resolved = dict(fields)
    for name in ("domain_class_id", "range_class_id"):
        value = resolved.get(name)
        if isinstance(value, str) and value.startswith("$"):
            resolved[name] = refs.get(value[1:])
    return resolved
