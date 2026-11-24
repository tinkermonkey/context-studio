"""
Plan the reversal of a landed proposal from its run's change events (#1667).

A landed proposal can't be undone in place: the client's source already holds
it and would bring the change back. So a new proposal is drafted that does the
opposite, from what the run actually changed (its change events, not the
operations proposed): a create is deleted, an update is set back to its
previous values, a move is moved back, and a delete is restored, with the
snapshot's id. Operations come newest event first, the exact inverse of the
order the run applied them in, so an entity is restored before what depends on
it and deleted after it.

The planner reads no repository: the current state of an entity comes in
through `current`, and nothing is stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from domain.versioning.entities import ChangeEvent
from domain.versioning.proposals import (
    MOVE_FIELDS,
    OperationKind,
    OperationType,
    ProposedOperation,
    classify_scope,
)
from domain.versioning.value_objects import ChangeOperation

# The kind a change event's entity type is proposed as
_KINDS = {
    "taxonomy": OperationKind.TAXONOMY,
    "concept_scheme": OperationKind.SCHEME,
    "class": OperationKind.CLASS,
    "property_definition": OperationKind.PROPERTY,
    "attribute_definition": OperationKind.ATTRIBUTE,
    "predicate": OperationKind.PREDICATE,
    "individual": OperationKind.INDIVIDUAL,
    "relationship": OperationKind.RELATIONSHIP,
}

# An individual's attribute values: a list of values in an event, a mapping of
# property identifier to value (None removes one) in an operation
_EVENT_DATA = "data_properties"

# Fields an event records that a proposal never sets
_NOT_PROPOSED = frozenset({"last_modified", "version", "created_at", "embedding", "id"})

CurrentState = Callable[[OperationKind, str], "dict[str, Any] | None"]


@dataclass(frozen=True)
class ReversalPlan:
    """
    The operations that undo a run, in the order to apply them.

    Attributes:
        operations: Pending operations, seq 1..n
        skipped: Events with nothing left to undo: the entity is already gone
            (or back), the run made it and removed it again, or it already has
            the values the event changed
        unplanned: Events the planner can't turn into an operation, each as a
            sentence (an entity type or field a proposal doesn't change)
    """

    operations: list[ProposedOperation]
    skipped: int
    unplanned: list[str]


def plan_reversal(
    events: Iterable[ChangeEvent],
    current: CurrentState,
    data_field: str,
    updatable: Callable[[OperationKind], frozenset[str]],
) -> ReversalPlan:
    """
    The reversal of the run these events recorded.

    Args:
        events: The run's reversible events, newest first
        current: An entity's fields as they are now (an `entity_snapshot`), or
            None when it doesn't exist
        data_field: The name an operation gives an individual's attribute values
        updatable: The fields an update of this kind may set

    Returns:
        The plan; `unplanned` lists what it left out for want of an operation
    """
    events = list(events)
    made = {e.entity_id for e in events if e.operation == ChangeOperation.CREATE and e.entity_id}
    drafts: list[ProposedOperation] = []
    skipped = 0
    unplanned: list[str] = []
    for event in events:
        kind = _KINDS.get(_entity_type(event))
        label = f"{_entity_type(event)} {event.entity_id}"
        if kind is None:
            unplanned.append(f"{label}: a {_entity_type(event)} is not a proposal's to change")
            continue
        now = current(kind, event.entity_id)
        if event.operation == ChangeOperation.CREATE:
            if now is None:
                skipped += 1
                continue
            drafts.append(_delete(kind, event.entity_id, now))
        elif event.operation == ChangeOperation.DELETE:
            snapshot = event.new_state or event.previous_state or {}
            if now is not None or event.entity_id in made:
                skipped += 1
            elif not snapshot:
                unplanned.append(f"{label}: its delete recorded no snapshot to restore")
            else:
                drafts.append(_restore(kind, event.entity_id, snapshot))
        else:
            if now is None or event.entity_id in made:
                # Gone, or made by the run: undoing the create deletes it whole.
                skipped += 1
                continue
            steps, problem = _update_back(kind, event, now, data_field, updatable(kind), label)
            if problem:
                unplanned.append(problem)
            elif not steps:
                skipped += 1
            drafts.extend(steps)
    for seq, operation in enumerate(drafts, start=1):
        operation.seq = seq
    return ReversalPlan(drafts, skipped, unplanned)


def _entity_type(event: ChangeEvent) -> str:
    entity_type = (event.entity_type or "").lower()
    entity_type = entity_type.replace("conceptscheme", "concept_scheme")
    entity_type = entity_type.replace("propertydefinition", "property_definition")
    return entity_type.replace("attributedefinition", "attribute_definition")


def _delete(kind: OperationKind, entity_id: str, now: dict[str, Any]) -> ProposedOperation:
    return ProposedOperation(
        seq=0,
        op=OperationType.DELETE,
        kind=kind,
        target_id=entity_id,
        base=now,
        scope=classify_scope(OperationType.DELETE, {}, now),
        rationale="Undoes a create: the entity did not exist before the proposal.",
    )


def _restore(kind: OperationKind, entity_id: str, snapshot: dict[str, Any]) -> ProposedOperation:
    fields = {k: v for k, v in snapshot.items() if k != "embedding"}
    return ProposedOperation(
        seq=0,
        op=OperationType.CREATE,
        kind=kind,
        target_id=entity_id,
        fields=fields,
        scope=classify_scope(OperationType.CREATE, fields),
        rationale="Undoes a delete: restores the entity with its old id.",
    )


def _update_back(
    kind: OperationKind,
    event: ChangeEvent,
    now: dict[str, Any],
    data_field: str,
    allowed: frozenset[str],
    label: str,
) -> tuple[list[ProposedOperation], str | None]:
    """
    The operations that set an updated entity's fields back: a move for the
    fields a move sets, an update for the rest.
    """
    previous = {k: v for k, v in (event.previous_state or {}).items() if k not in _NOT_PROPOSED}
    if not previous:
        return [], f"{label}: its update recorded no previous values"
    moves = MOVE_FIELDS.get(kind, frozenset())
    moved = {k: v for k, v in previous.items() if k in moves}
    plain = {k: v for k, v in previous.items() if k not in moves}
    values: dict[str, Any] = {}
    for name, value in plain.items():
        if name == _EVENT_DATA:
            values[data_field] = _data_values(value, (event.new_state or {}).get(_EVENT_DATA))
        elif name in allowed:
            values[name] = value
        else:
            return [], f"{label}: a proposal can't set {name} on a {kind.value}"
    steps: list[ProposedOperation] = []
    if moved and any(now.get(k) != v for k, v in moved.items()):
        steps.append(
            ProposedOperation(
                seq=0,
                op=OperationType.MOVE,
                kind=kind,
                target_id=event.entity_id,
                fields=moved,
                base={k: now.get(k) for k in moved},
                scope=classify_scope(OperationType.MOVE, moved),
                rationale="Undoes a move.",
            )
        )
    if values:
        base = {name: _current_value(name, now, data_field, values) for name in values}
        if any(base[name] != value for name, value in values.items()):
            others = {k: v for k, v in values.items() if k != data_field}
            steps.append(
                ProposedOperation(
                    seq=0,
                    op=OperationType.UPDATE,
                    kind=kind,
                    target_id=event.entity_id,
                    fields=values,
                    base=base,
                    scope=classify_scope(
                        OperationType.UPDATE,
                        others,
                        {k: v for k, v in base.items() if k != data_field},
                    ),
                    rationale="Undoes an update: sets the fields back to what they were.",
                )
            )
    return steps, None


def _data_values(previous: Any, new: Any) -> dict[str, Any]:
    """
    An individual's attribute values as an update sets them: each one it had
    (as it was), and None for each the update added, so setting them back
    removes it.
    """
    before = {v["property_identifier"]: v["value"] for v in previous or []}
    after = {v["property_identifier"]: v["value"] for v in new or []}
    return {**{key: None for key in after if key not in before}, **before}


def _current_value(name: str, now: dict[str, Any], data_field: str, values: dict[str, Any]) -> Any:
    if name != data_field:
        return now.get(name)
    held = {v["property_identifier"]: v["value"] for v in now.get(data_field) or []}
    return {key: held.get(key) for key in values[data_field]}
