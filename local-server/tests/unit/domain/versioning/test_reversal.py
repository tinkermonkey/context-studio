"""Unit tests for planning a reversal from change events (#1667)."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from datetime import datetime, timezone
from itertools import count

import pytest

from domain.versioning.proposals import (
    OperationKind,
    OperationType,
    ProposedOperation,
    ChangeScope,
)
from domain.versioning.proposal_service import DATA_FIELD, OPERATION_FIELDS
from domain.versioning.entities import ChangeEvent
from domain.versioning.reversal import plan_reversal
from domain.versioning.value_objects import ChangeOperation

_ids = count(1)


def _event(entity_id, entity_type, operation, new_state=None, previous_state=None):
    return ChangeEvent(
        id=f"e{next(_ids)}",
        entity_id=entity_id,
        entity_type=entity_type,
        operation=operation,
        new_state=new_state or {},
        previous_state=previous_state,
        timestamp=datetime.now(timezone.utc),
    )


def _plan(events, entities):
    """The plan for events (newest first) when `entities` are what exists now."""
    return plan_reversal(
        events,
        lambda kind, entity_id: entities.get((kind.value, entity_id)),
        DATA_FIELD,
        lambda kind: OPERATION_FIELDS[kind].update,
    )


def test_a_create_is_deleted_with_its_current_fields_as_the_base():
    now = {"id": "c1", "title": "Kit"}
    plan = _plan(
        [_event("c1", "class", ChangeOperation.CREATE, {"title": "Kit"})], {("class", "c1"): now}
    )

    [operation] = plan.operations
    assert (operation.seq, operation.op, operation.kind) == (
        1,
        OperationType.DELETE,
        OperationKind.CLASS,
    )
    assert (operation.target_id, operation.base) == ("c1", now)
    assert operation.scope is ChangeScope.BREAKING
    assert (plan.skipped, plan.unplanned) == (0, [])


def test_a_delete_is_restored_with_the_snapshots_id_and_fields():
    snapshot = {"id": "c1", "title": "Kit", "concept_scheme_id": "s1", "embedding": [0.1]}
    plan = _plan([_event("c1", "class", ChangeOperation.DELETE, previous_state=snapshot)], {})

    [operation] = plan.operations
    assert operation.restore
    assert (operation.op, operation.target_id) == (OperationType.CREATE, "c1")
    assert operation.fields == {"id": "c1", "title": "Kit", "concept_scheme_id": "s1"}


def test_an_update_is_set_back_to_its_previous_values_over_the_current_ones():
    plan = _plan(
        [
            _event(
                "c1",
                "class",
                ChangeOperation.UPDATE,
                {"description": "B"},
                {"description": "A"},
            )
        ],
        {("class", "c1"): {"id": "c1", "description": "B"}},
    )

    [operation] = plan.operations
    assert operation.op is OperationType.UPDATE
    assert operation.fields == {"description": "A"}
    assert operation.base == {"description": "B"}
    assert operation.scope is ChangeScope.EDITORIAL


def test_operations_run_newest_event_first_and_are_numbered_from_one():
    events = [
        _event("r1", "relationship", ChangeOperation.CREATE, {}),
        _event("c1", "class", ChangeOperation.CREATE, {}),
    ]
    entities = {("relationship", "r1"): {"id": "r1"}, ("class", "c1"): {"id": "c1"}}

    plan = _plan(events, entities)

    assert [(o.seq, o.kind) for o in plan.operations] == [
        (1, OperationKind.RELATIONSHIP),
        (2, OperationKind.CLASS),
    ]


def test_a_class_move_is_a_move_and_the_rest_of_an_update_an_update():
    event = _event(
        "c1",
        "class",
        ChangeOperation.UPDATE,
        {"parent_class_id": "p2", "description": "B"},
        {"parent_class_id": "p1", "description": "A"},
    )
    now = {"id": "c1", "parent_class_id": "p2", "description": "B"}

    plan = _plan([event], {("class", "c1"): now})

    moved, updated = plan.operations
    assert (moved.op, moved.fields, moved.base) == (
        OperationType.MOVE,
        {"parent_class_id": "p1"},
        {"parent_class_id": "p2"},
    )
    assert (updated.op, updated.fields) == (OperationType.UPDATE, {"description": "A"})


def test_attribute_values_an_update_added_are_removed_and_changed_ones_set_back():
    event = _event(
        "i1",
        "individual",
        ChangeOperation.UPDATE,
        {
            "data_properties": [
                {"property_identifier": "colour", "value": "red", "datatype": None},
                {"property_identifier": "size", "value": 3, "datatype": None},
            ]
        },
        {"data_properties": [{"property_identifier": "colour", "value": "blue", "datatype": None}]},
    )
    now = {
        "id": "i1",
        "data_properties": [
            {"property_identifier": "colour", "value": "red", "datatype": None},
            {"property_identifier": "size", "value": 3, "datatype": None},
        ],
    }

    plan = _plan([event], {("individual", "i1"): now})

    [operation] = plan.operations
    assert operation.fields == {DATA_FIELD: {"size": None, "colour": "blue"}}
    assert operation.base == {DATA_FIELD: {"size": 3, "colour": "red"}}


def test_what_is_already_undone_or_gone_is_skipped_not_planned():
    events = [
        _event("gone", "class", ChangeOperation.CREATE, {}),
        _event("back", "class", ChangeOperation.DELETE, previous_state={"id": "back"}),
        _event("same", "class", ChangeOperation.UPDATE, {"description": "B"}, {"description": "A"}),
    ]
    entities = {("class", "back"): {"id": "back"}, ("class", "same"): {"description": "A"}}

    plan = _plan(events, entities)

    assert plan.operations == []
    assert (plan.skipped, plan.unplanned) == (3, [])


def test_an_entity_the_run_made_and_deleted_again_is_left_alone():
    events = [
        _event("k", "class", ChangeOperation.DELETE, previous_state={"id": "k", "title": "Kit"}),
        _event("k", "class", ChangeOperation.UPDATE, {"description": "B"}, {"description": "A"}),
        _event("k", "class", ChangeOperation.CREATE, {"title": "Kit"}),
    ]

    plan = _plan(events, {})

    assert plan.operations == []
    assert plan.skipped == 3


def test_an_update_of_an_entity_the_run_made_is_left_to_its_deletion():
    events = [
        _event("k", "class", ChangeOperation.UPDATE, {"description": "B"}, {"description": "A"}),
        _event("k", "class", ChangeOperation.CREATE, {"title": "Kit"}),
    ]

    plan = _plan(events, {("class", "k"): {"id": "k", "description": "B"}})

    assert [o.op for o in plan.operations] == [OperationType.DELETE]
    assert plan.skipped == 1


@pytest.mark.parametrize(
    "event, reason",
    [
        (
            _event("x", "extraction_thing", ChangeOperation.CREATE, {}),
            "not a proposal's to change",
        ),
        (_event("c1", "class", ChangeOperation.DELETE), "no snapshot to restore"),
        (
            _event("c1", "class", ChangeOperation.UPDATE, {"version": 2, "nope": 1}, {"nope": 0}),
            "can't set nope",
        ),
        (
            _event(
                "r1", "relationship", ChangeOperation.UPDATE, {"source_id": "b"}, {"source_id": "a"}
            ),
            "can't set source_id",
        ),
    ],
)
def test_an_event_no_proposal_can_undo_is_listed_not_dropped(event, reason):
    entities = {("class", "c1"): {"id": "c1"}, ("relationship", "r1"): {"id": "r1"}}
    if event.entity_id == "c1" and event.operation == ChangeOperation.DELETE:
        entities = {}

    plan = _plan([event], entities)

    assert plan.operations == []
    [problem] = plan.unplanned
    assert reason in problem


def test_only_a_reversal_creates_with_a_target_id():
    assert ProposedOperation(
        seq=1, op=OperationType.CREATE, kind=OperationKind.CLASS, target_id="c1"
    ).restore
    assert not ProposedOperation(seq=1, op=OperationType.CREATE, kind=OperationKind.CLASS).restore
    with pytest.raises(ValueError, match="takes no ref"):
        ProposedOperation(
            seq=1, op=OperationType.CREATE, kind=OperationKind.CLASS, target_id="c1", ref="kit"
        )
