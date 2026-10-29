"""Unit tests for accept-with-edit (#1383): applying a reviewer's correction of an operation."""

import pytest

from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    classify_scope,
)
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

T, K = OperationType, OperationKind


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        result = RevertResult(run_id=run_id, events_reverted=0)
        if on_reverted is not None:
            on_reverted(result)
        return result


class RecordingRules:
    """ProposalApplyRules that records its calls, then refuses or completes."""

    def __init__(self, refuse=None, add=None, governed=None):
        self.calls = []
        self.refuse = refuse
        self.add = add or {}
        self.governed = governed  # target ids it governs; None: every one

    def governs(self, operation, fields):
        return self.governed is None or operation.target_id in self.governed

    def check(self, operation, fields):
        self.calls.append(("check", operation.seq, dict(fields)))
        if self.refuse:
            raise ValueError(self.refuse)

    def prepare(self, proposal, operation, fields, other_edits):
        self.calls.append((proposal.id, operation.seq, dict(fields), dict(other_edits)))
        if self.refuse:
            raise ValueError(self.refuse)
        return {**fields, **self.add}


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def repo(ontology):
    return ontology._repository


@pytest.fixture()
def graph(ontology):
    taxonomy = ontology.create_taxonomy(title="House", identifier="house")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room")
    hall = ontology.create_class(vocab.id, "Hall")
    near = ontology.create_property_definition(
        "near", "near", domain_class_id=room.id, range_class_id=room.id
    )
    far = ontology.create_property_definition("far", "far")
    return {
        "taxonomy": taxonomy.id,
        "vocab": vocab.id,
        "room": room.id,
        "hall": hall.id,
        "near": near.id,
        "far": far.id,
    }


def make_service(ontology, repo, rules=None):
    return ProposalService(
        FakeChangeProposalRepository(),
        ontology,
        repo,
        StubRevertService(),
        apply_rules=[rules] if rules else (),
    )


@pytest.fixture()
def service(ontology, repo):
    return make_service(ontology, repo)


def draft(seq, op, kind, target=None, **fields):
    return OperationDraft(seq=seq, op=op, kind=kind, target_id=target, fields=fields)


def propose(service, graph, *drafts):
    return service.propose(graph["taxonomy"], "Edits", list(drafts), ProposalSource.USER)


def by_seq(proposal):
    return {o.seq: o for o in proposal.operations}


# ------------------------------------------------------------------ applied


def test_an_edited_update_applies_the_edit_and_records_it(service, graph, ontology):
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], identifier="close_to", title="close to"),
    )
    op = proposal.operations[0]
    assert op.scope is ChangeScope.BREAKING

    edit = {"title": "next to", "range_class_id": graph["hall"]}
    result = service.apply(proposal.id, [op.id], edits={op.id: edit})

    applied = result.operations[0]
    assert applied.status is OperationStatus.APPLIED, applied.reason
    assert applied.applied_fields == edit
    assert applied.fields == {"identifier": "close_to", "title": "close to"}  # as proposed
    assert applied.op is T.UPDATE and applied.result_entity_id == graph["near"]
    near = ontology.get_property_definition(graph["near"])
    assert near.identifier == "near" and near.title == "next to"
    assert near.range_class_id == graph["hall"]
    assert applied.scope is ChangeScope.BREAKING  # a range change


def test_scope_is_recomputed_from_the_edit(service, graph):
    proposal = propose(
        service, graph, draft(1, T.UPDATE, K.PROPERTY, graph["near"], identifier="close_to")
    )
    op = proposal.operations[0]

    result = service.apply(proposal.id, [op.id], edits={op.id: {"title": "near by"}})

    assert result.operations[0].scope is ChangeScope.EDITORIAL


def test_a_delete_replaced_by_an_update_keeps_its_seq_and_target(service, graph, ontology):
    proposal = propose(service, graph, draft(7, T.DELETE, K.PROPERTY, graph["far"]))
    op = proposal.operations[0]

    edit = {"domain_class_id": graph["room"], "range_class_id": graph["hall"]}
    result = service.apply(proposal.id, [op.id], edits={op.id: edit})

    applied = result.operations[0]
    assert applied.status is OperationStatus.APPLIED, applied.reason
    assert (applied.seq, applied.op, applied.fields) == (7, T.DELETE, {})
    assert applied.applied_fields == edit
    assert applied.result_entity_id == graph["far"]
    far = ontology.get_property_definition(graph["far"])
    assert (far.domain_class_id, far.range_class_id) == (graph["room"], graph["hall"])
    assert applied.scope is ChangeScope.BREAKING


def test_applied_fields_are_stored(service, graph):
    proposal = propose(service, graph, draft(1, T.DELETE, K.PROPERTY, graph["far"]))
    op = proposal.operations[0]
    service.apply(proposal.id, [op.id], edits={op.id: {"title": "distant"}})

    stored = service.get(proposal.id).operations[0]
    assert stored.applied_fields == {"title": "distant"}
    assert stored.scope is ChangeScope.EDITORIAL


def test_unedited_operations_of_the_same_apply_apply_as_proposed(service, graph, ontology):
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="close"),
        draft(2, T.UPDATE, K.PROPERTY, graph["far"], title="distant"),
    )
    ops = by_seq(proposal)

    result = by_seq(
        service.apply(proposal.id, [ops[1].id, ops[2].id], edits={ops[2].id: {"title": "remote"}})
    )

    assert result[1].applied_fields is None
    assert ontology.get_property_definition(graph["near"]).title == "close"
    assert ontology.get_property_definition(graph["far"]).title == "remote"


# ------------------------------------------------------------------ refused


@pytest.mark.parametrize(
    "edit, reason",
    [
        ({"cardinality": "many"}, "invalid_edit: A property update can't set ['cardinality']"),
        ({"domain_class_id": "nope"}, "invalid_edit: domain_class_id nope is not an existing"),
        ({"title": 5}, "invalid_edit: title has the wrong type"),
        ({"title": None}, "invalid_edit: ['title'] can't be cleared"),
    ],
)
def test_an_invalid_edit_fails_only_its_operation(service, graph, ontology, edit, reason):
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], identifier="close_to"),
        draft(2, T.UPDATE, K.PROPERTY, graph["far"], title="distant"),
    )
    ops = by_seq(proposal)

    result = by_seq(service.apply(proposal.id, [ops[1].id, ops[2].id], edits={ops[1].id: edit}))

    assert result[1].status is OperationStatus.FAILED
    assert result[1].reason.startswith(reason), result[1].reason
    assert result[1].applied_fields is None
    assert result[1].scope is ChangeScope.BREAKING  # unchanged
    assert ontology.get_property_definition(graph["near"]).identifier == "near"
    assert result[2].status is OperationStatus.APPLIED


def test_a_failed_edit_can_be_applied_again_as_proposed(service, graph, ontology):
    proposal = propose(service, graph, draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="x"))
    op = proposal.operations[0]
    failed = service.apply(proposal.id, [op.id], edits={op.id: {"bogus": 1}})
    assert failed.operations[0].status is OperationStatus.FAILED

    again = service.apply(proposal.id, [op.id]).operations[0]

    assert again.status is OperationStatus.APPLIED and again.applied_fields is None
    assert again.reason is None
    assert ontology.get_property_definition(graph["near"]).title == "x"


def test_an_edited_stale_target_fails_unless_forced(service, graph, ontology):
    proposal = propose(service, graph, draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="x"))
    op = proposal.operations[0]
    ontology.update_property_definition(graph["near"], title="changed meanwhile")

    stale = service.apply(proposal.id, [op.id], edits={op.id: {"title": "y"}}).operations[0]
    assert stale.status is OperationStatus.FAILED
    assert stale.reason.startswith("target_changed:")

    forced = service.apply(
        proposal.id, [op.id], force_stale=[op.id], edits={op.id: {"title": "y"}}
    ).operations[0]
    assert forced.status is OperationStatus.APPLIED
    assert ontology.get_property_definition(graph["near"]).title == "y"


@pytest.mark.parametrize(
    "case, message",
    [
        ("not_applied", "not being applied"),
        ("class_update", "only a property update or delete can be edited"),
        ("create", "only a property update or delete can be edited"),
        ("empty", "an edit needs at least one field"),
        ("ref", "can't point at a $ref"),
    ],
)
def test_a_misplaced_edit_is_refused_and_nothing_applies(service, graph, ontology, case, message):
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="close"),
        draft(2, T.UPDATE, K.CLASS, graph["room"], title="Chamber"),
        draft(3, T.CREATE, K.PROPERTY, None, identifier="by", title="by"),
        draft(4, T.UPDATE, K.PROPERTY, graph["far"], title="distant"),
    )
    ops = by_seq(proposal)
    apply_ids = [ops[1].id, ops[2].id, ops[3].id]
    edits = {
        "not_applied": {ops[4].id: {"title": "remote"}},
        "class_update": {ops[2].id: {"title": "Hallway"}},
        "create": {ops[3].id: {"title": "beside"}},
        "empty": {ops[1].id: {}},
        "ref": {ops[1].id: {"domain_class_id": "$kit"}},
    }[case]

    with pytest.raises(ValueError, match=message.replace("$", r"\$")):
        service.apply(proposal.id, apply_ids, edits=edits)

    assert all(o.status is OperationStatus.PENDING for o in service.get(proposal.id).operations)
    assert ontology.get_property_definition(graph["near"]).title == "near"


def test_text_starting_with_a_dollar_is_not_a_ref(service, graph, ontology):
    proposal = propose(service, graph, draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="x"))
    op = proposal.operations[0]

    result = service.apply(proposal.id, [op.id], edits={op.id: {"title": "$5 attic"}})

    assert result.operations[0].status is OperationStatus.APPLIED, result.operations[0].reason
    assert ontology.get_property_definition(graph["near"]).title == "$5 attic"


# -------------------------------------------------------------------- rules


def test_the_taxonomys_rules_complete_the_edit(ontology, repo, graph):
    rules = RecordingRules(add={"identifier": "next_to"})
    service = make_service(ontology, repo, rules)
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="close"),
        draft(2, T.DELETE, K.PROPERTY, graph["far"]),
    )
    ops = by_seq(proposal)
    edits = {ops[1].id: {"title": "next to"}, ops[2].id: {"title": "remote"}}

    result = by_seq(service.apply(proposal.id, [ops[1].id, ops[2].id], edits=edits))

    assert result[1].applied_fields == {"title": "next to", "identifier": "next_to"}
    assert ontology.get_property_definition(graph["near"]).identifier == "next_to"
    assert rules.calls[0] == (
        proposal.id,
        1,
        {"title": "next to"},
        {ops[2].id: {"title": "remote"}},
    )
    assert rules.calls[1][1] == 2 and rules.calls[1][3] == {ops[1].id: {"title": "next to"}}


def test_a_refusal_by_the_rules_fails_only_that_operation(ontology, repo, graph):
    rules = RecordingRules(refuse="that triple already exists", governed={graph["near"]})
    service = make_service(ontology, repo, rules)
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="close"),
        draft(2, T.UPDATE, K.PROPERTY, graph["far"], title="distant"),
    )
    ops = by_seq(proposal)

    result = by_seq(
        service.apply(proposal.id, [ops[1].id, ops[2].id], edits={ops[1].id: {"title": "y"}})
    )

    assert result[1].status is OperationStatus.FAILED
    assert result[1].reason == "invalid_edit: that triple already exists"
    assert result[2].status is OperationStatus.APPLIED
    assert ontology.get_property_definition(graph["near"]).title == "near"


def test_what_the_rules_add_is_checked_too(ontology, repo, graph):
    service = make_service(ontology, repo, RecordingRules(add={"range_class_id": "gone"}))
    proposal = propose(service, graph, draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="x"))
    op = proposal.operations[0]

    result = service.apply(proposal.id, [op.id], edits={op.id: {"title": "y"}}).operations[0]

    assert result.status is OperationStatus.FAILED
    assert result.reason.startswith("invalid_edit: range_class_id gone is not an existing")


def test_rules_are_asked_only_for_targets_they_govern(ontology, repo, graph):
    rules = RecordingRules(refuse="no", governed={graph["far"]})
    service = make_service(ontology, repo, rules)
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="x"),
        draft(2, T.UPDATE, K.PROPERTY, graph["far"], title="y"),
    )
    ops = by_seq(proposal)
    edits = {ops[1].id: {"title": "close"}, ops[2].id: {"title": "remote"}}

    result = by_seq(service.apply(proposal.id, [ops[1].id, ops[2].id], edits=edits))

    assert result[1].status is OperationStatus.APPLIED
    assert result[2].reason == "invalid_edit: no"
    assert [call[1] for call in rules.calls] == [2]


def test_unedited_property_changes_are_checked_by_the_rules_that_govern_them(ontology, repo, graph):
    rules = RecordingRules(refuse="X already exists", governed={graph["far"], None})
    service = make_service(ontology, repo, rules)
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="close"),
        draft(2, T.UPDATE, K.PROPERTY, graph["far"], title="distant"),
        draft(3, T.CREATE, K.PROPERTY, None, identifier="by", title="by"),
        draft(4, T.UPDATE, K.CLASS, graph["room"], title="Chamber"),
    )
    ops = by_seq(proposal)

    result = by_seq(service.apply(proposal.id, [o.id for o in ops.values()]))

    assert result[1].status is OperationStatus.APPLIED  # not governed
    assert result[2].status is OperationStatus.FAILED
    assert result[2].reason == "refused: X already exists"
    assert result[3].reason == "refused: X already exists"  # a create, governed (no target)
    assert result[4].status is OperationStatus.APPLIED  # not a property
    assert [(c[0], c[1]) for c in rules.calls] == [("check", 2), ("check", 3)]
    assert ontology.get_property_definition(graph["far"]).title == "far"


# -------------------------------------------------------------------- scope


def test_a_field_set_to_its_current_value_changes_nothing():
    base = {"identifier": "near", "external_references": [{"source": "x", "identifier": "1"}]}
    assert classify_scope(T.UPDATE, dict(base), base) is ChangeScope.EDITORIAL
    assert classify_scope(T.UPDATE, {**base, "title": "t"}, base) is ChangeScope.EDITORIAL
    assert classify_scope(T.UPDATE, {"identifier": "far"}, base) is ChangeScope.BREAKING


def test_a_proposed_update_to_the_current_value_is_editorial(service, graph):
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], identifier="near", title="close"),
    )
    assert proposal.operations[0].scope is ChangeScope.EDITORIAL
