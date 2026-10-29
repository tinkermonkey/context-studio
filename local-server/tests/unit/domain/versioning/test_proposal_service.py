"""Unit tests for ProposalService (#1354): propose, apply, staleness, reject, revert."""

import threading
import time

import pytest

from domain.events import DomainEvent
from domain.interchange.services import get_current_batch_run_id, set_batch_run_context
from domain.ontology.events import AttributeDefinitionCreated, ClassCreated, ClassUpdated
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
    ProposalValidationError,
)
from domain.versioning.proposal_service import (
    MAX_RATIONALE_CHARS,
    MAX_TITLE_CHARS,
    OperationDraft,
    ProposalService,
)
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

T, K = OperationType, OperationKind


class StubRevertService:
    """Records the runs it is asked to revert."""

    def __init__(self, error: Exception | None = None):
        self.reverted: list[str] = []
        self.error = error

    def revert_with_summary(self, run_id: str, on_reverted=None) -> RevertResult:
        if self.error is not None:
            raise self.error
        self.reverted.append(run_id)
        result = RevertResult(run_id=run_id, events_reverted=0)
        if on_reverted is not None:
            on_reverted(result)
        return result


class RunTagRecorder:
    """Every published ontology event with the batch run id current when it was published."""

    def __init__(self):
        self.tags: list[tuple[str, str | None]] = []

    def __call__(self, event: DomainEvent) -> None:
        self.tags.append((type(event).__name__, get_current_batch_run_id()))


@pytest.fixture()
def publisher():
    return FakeEventPublisher()


@pytest.fixture()
def ontology(publisher):
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), publisher)


@pytest.fixture()
def repo(ontology):
    return ontology._repository


@pytest.fixture()
def proposals():
    return FakeChangeProposalRepository()


@pytest.fixture()
def reverter():
    return StubRevertService()


@pytest.fixture()
def service(proposals, ontology, repo, reverter):
    return ProposalService(proposals, ontology, repo, reverter)


@pytest.fixture()
def graph(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    other = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Records")
    room = ontology.create_class(vocab.id, "Room", description="A room")
    kitchen_cls = ontology.create_class(vocab.id, "Kitchen", parent_class_id=room.id)
    place = ontology.create_class(other.id, "Place")
    near = ontology.create_property_definition(
        "near", "near", domain_class_id=room.id, range_class_id=room.id
    )
    ind = ontology.create_individual(room.id, "Den")
    return {
        "taxonomy": taxonomy.id,
        "vocab": vocab.id,
        "other": other.id,
        "room": room.id,
        "kitchen": kitchen_cls.id,
        "place": place.id,
        "near": near.id,
        "den": ind.id,
    }


def draft(seq, op, kind, target=None, ref=None, **fields):
    """An operation draft; keyword arguments other than ref are its fields."""
    return OperationDraft(seq=seq, op=op, kind=kind, target_id=target, ref=ref, fields=fields)


def propose(service, graph, *drafts):
    return service.propose(graph["taxonomy"], "Test", list(drafts), ProposalSource.USER)


def by_seq(proposal):
    return {o.seq: o for o in proposal.operations}


def ids(proposal, *seqs):
    ops = by_seq(proposal)
    return [ops[s].id for s in seqs]


# ---------------------------------------------------------------- propose


class TestPropose:
    def test_stores_pending_operations_with_scope_and_base(self, service, proposals, graph, repo):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room"),
            draft(2, T.CREATE, K.CLASS, ref="hall", concept_scheme_id=graph["vocab"], title="Hall"),
            draft(3, T.DELETE, K.INDIVIDUAL, graph["den"]),
            draft(4, T.UPDATE, K.PROPERTY, graph["near"], domain_class_id=None),
        )
        stored = proposals.get(proposal.id)
        ops = by_seq(stored)
        assert stored.status is ProposalStatus.OPEN
        assert all(o.status is OperationStatus.PENDING for o in stored.operations)
        assert ops[1].base == {"description": "A room"}
        assert ops[1].scope is ChangeScope.EDITORIAL
        assert ops[2].base == {} and ops[2].scope is ChangeScope.ADDITIVE
        assert ops[3].base["title"] == "Den" and ops[3].base["class_ids"] == [graph["room"]]
        assert ops[3].scope is ChangeScope.BREAKING
        assert ops[4].base == {"domain_class_id": graph["room"]}
        assert ops[4].scope is ChangeScope.BREAKING

    def test_claimed_scope_only_makes_it_stricter(self, service, graph):
        proposal = propose(
            service,
            graph,
            OperationDraft(
                seq=1,
                op="update",
                kind="class",
                target_id=graph["room"],
                fields={"title": "Chamber"},
                claimed_scope="breaking",
            ),
        )
        assert proposal.operations[0].scope is ChangeScope.BREAKING

    def test_all_or_nothing_with_an_error_per_operation(self, service, proposals, graph):
        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                graph,
                draft(1, T.UPDATE, K.CLASS, "missing", title="X"),
                draft(2, T.UPDATE, K.CLASS, graph["room"], identifier="room2"),
                draft(3, T.CREATE, K.CLASS, title="No scheme"),
                draft(
                    4,
                    T.CREATE,
                    K.ATTRIBUTE,
                    class_id="$later",
                    identifier="a",
                    title="A",
                    datatype="string",
                ),
                draft(
                    5,
                    T.CREATE,
                    K.CLASS,
                    ref="later",
                    concept_scheme_id=graph["vocab"],
                    title="Later",
                ),
                draft(
                    6,
                    T.CREATE,
                    K.RELATIONSHIP,
                    source_id=graph["den"],
                    target_id="nowhere",
                    property_definition_id=graph["near"],
                ),
                draft(7, "rename", K.CLASS, graph["room"]),
                draft(8, T.UPDATE, K.CLASS, graph["room"], title=None),
                draft(
                    9,
                    T.CREATE,
                    K.ATTRIBUTE,
                    class_id=graph["room"],
                    identifier="b",
                    title="B",
                    datatype="colour",
                ),
            )
        codes = {e.seq: e.code for e in caught.value.errors}
        assert codes == {
            1: "target_not_found",
            2: "unknown_field",
            3: "missing_field",
            4: "unknown_ref",
            6: "endpoint_not_found",
            7: "invalid",
            8: "invalid",
            9: "invalid",
        }
        assert proposals.count_proposals() == 0

    def test_refs_point_backwards_at_creates_of_the_right_kind(self, service, graph):
        proposal = propose(
            service,
            graph,
            draft(1, T.CREATE, K.CLASS, ref="kit", concept_scheme_id=graph["vocab"], title="Kit"),
            draft(
                2,
                T.CREATE,
                K.ATTRIBUTE,
                class_id="$kit",
                identifier="kit_size",
                title="Kit size",
                datatype="integer",
            ),
        )
        assert len(proposal.operations) == 2

        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                graph,
                draft(1, T.CREATE, K.SCHEME, ref="s", taxonomy_id=graph["taxonomy"], title="S"),
                draft(
                    2,
                    T.CREATE,
                    K.ATTRIBUTE,
                    class_id="$s",
                    identifier="x",
                    title="X",
                    datatype="string",
                ),
                draft(3, T.CREATE, K.CLASS, ref="s", concept_scheme_id="$s", title="Dup"),
            )
        assert [(e.seq, e.code) for e in caught.value.errors] == [
            (2, "endpoint_not_found"),
            (3, "duplicate_ref"),
        ]

    def test_operations_may_not_touch_the_same_field_or_a_deleted_target(self, service, graph):
        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                graph,
                draft(1, T.UPDATE, K.CLASS, graph["room"], title="Chamber"),
                draft(2, T.UPDATE, K.CLASS, graph["room"], title="Hall"),
                draft(3, T.UPDATE, K.CLASS, graph["room"], description="ok, other field"),
                draft(4, T.DELETE, K.CLASS, graph["room"]),
                draft(5, T.DELETE, K.INDIVIDUAL, graph["den"]),
                draft(6, T.DELETE, K.INDIVIDUAL, graph["den"]),
            )
        assert [(e.seq, e.code) for e in caught.value.errors] == [
            (2, "conflicting_op"),
            (4, "conflicting_op"),
            (6, "conflicting_op"),
        ]

    def test_class_scheme_move_needs_a_parent_in_that_scheme_and_no_subclasses(
        self, service, graph
    ):
        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                graph,
                draft(1, T.MOVE, K.CLASS, graph["kitchen"], concept_scheme_id=graph["other"]),
                draft(
                    2,
                    T.MOVE,
                    K.CLASS,
                    graph["room"],
                    concept_scheme_id=graph["other"],
                    parent_class_id=None,
                ),
            )
        assert [(e.seq, e.code) for e in caught.value.errors] == [
            (1, "missing_field"),
            (2, "invalid"),
        ]
        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                graph,
                draft(
                    1,
                    T.MOVE,
                    K.CLASS,
                    graph["kitchen"],
                    concept_scheme_id=graph["other"],
                    parent_class_id=graph["room"],
                ),
            )
        assert caught.value.errors[0].code == "invalid"

    def test_title_and_rationale_have_length_limits(self, service, graph):
        update = draft(1, T.UPDATE, K.CLASS, graph["room"], title="Chamber")
        with pytest.raises(ProposalValidationError) as caught:
            service.propose(
                graph["taxonomy"],
                "t" * (MAX_TITLE_CHARS + 1),
                [update],
                ProposalSource.CHAT,
                rationale="r" * (MAX_RATIONALE_CHARS + 1),
            )
        assert [(e.seq, e.code) for e in caught.value.errors] == [
            (None, "too_long"),
            (None, "too_long"),
        ]
        assert "title" in caught.value.errors[0].message

        stored = service.propose(
            graph["taxonomy"],
            "t" * MAX_TITLE_CHARS,
            [update],
            ProposalSource.CHAT,
            rationale="r" * MAX_RATIONALE_CHARS,
        )
        assert len(stored.title) == MAX_TITLE_CHARS

    def test_unknown_taxonomy_and_empty_proposal(self, service):
        with pytest.raises(ProposalValidationError) as caught:
            service.propose("nope", "Test", [], ProposalSource.USER)
        assert {e.code for e in caught.value.errors} == {"taxonomy_not_found", "invalid"}


# ------------------------------------------------------------------ apply


class TestApply:
    def test_applies_in_seq_order_under_the_run_and_restores_the_outer_context(
        self, service, graph, publisher, ontology
    ):
        recorder = RunTagRecorder()
        for event_type in (ClassCreated, AttributeDefinitionCreated, ClassUpdated):
            publisher.subscribe(event_type, recorder)
        proposal = propose(
            service,
            graph,
            draft(1, T.CREATE, K.CLASS, ref="kit", concept_scheme_id=graph["vocab"], title="Kit"),
            draft(
                2,
                T.CREATE,
                K.ATTRIBUTE,
                class_id="$kit",
                identifier="kit_size",
                title="Kit size",
                datatype="integer",
            ),
            draft(3, T.UPDATE, K.CLASS, graph["room"], description="Any room"),
        )
        set_batch_run_context("outer-run")
        try:
            # Ids passed out of order still apply by seq.
            applied = service.apply(proposal.id, list(reversed(ids(proposal, 1, 2, 3))))
            assert get_current_batch_run_id() == "outer-run"
        finally:
            set_batch_run_context(None)

        ops = by_seq(applied)
        assert all(o.status is OperationStatus.APPLIED for o in applied.operations)
        assert applied.status is ProposalStatus.DONE
        kit = ontology.get_class(ops[1].result_entity_id)
        assert kit.title == "Kit" and kit.source_run_id == proposal.id
        attribute = ontology.get_attribute_definition(ops[2].result_entity_id)
        assert attribute.class_id == kit.id
        assert ontology.get_class(graph["room"]).description == "Any room"
        assert recorder.tags == [
            ("ClassCreated", proposal.id),
            ("AttributeDefinitionCreated", proposal.id),
            ("ClassUpdated", proposal.id),
        ]

    def test_stale_target_fails_unless_forced_and_can_be_retried(self, service, graph, ontology):
        proposal = propose(
            service, graph, draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room")
        )
        ontology.update_class(graph["room"], description="Edited meanwhile")
        op_id = ids(proposal, 1)

        failed = service.apply(proposal.id, op_id)
        assert failed.operations[0].status is OperationStatus.FAILED
        assert failed.operations[0].reason == "target_changed: description changed since proposed"
        assert ontology.get_class(graph["room"]).description == "Edited meanwhile"

        forced = service.apply(proposal.id, op_id, force_stale=op_id)
        assert forced.operations[0].status is OperationStatus.APPLIED
        assert forced.operations[0].reason is None
        assert ontology.get_class(graph["room"]).description == "Any room"

    def test_unrelated_changes_do_not_make_an_update_stale(self, service, graph, ontology):
        proposal = propose(
            service, graph, draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room")
        )
        ontology.update_class(graph["room"], title="Chamber")
        applied = service.apply(proposal.id, ids(proposal, 1))
        assert applied.operations[0].status is OperationStatus.APPLIED

    def test_any_change_makes_a_delete_stale(self, service, graph, ontology):
        proposal = propose(service, graph, draft(1, T.DELETE, K.INDIVIDUAL, graph["den"]))
        ontology.update_individual(graph["den"], description="Changed")
        failed = service.apply(proposal.id, ids(proposal, 1))
        assert failed.operations[0].reason == "target_changed: description changed since proposed"

    def test_missing_target_fails(self, service, graph, ontology):
        proposal = propose(service, graph, draft(1, T.DELETE, K.INDIVIDUAL, graph["den"]))
        ontology.delete_individual(graph["den"])
        failed = service.apply(proposal.id, ids(proposal, 1))
        assert failed.operations[0].reason == f"target_missing: individual {graph['den']}"

    def test_failed_ref_source_leaves_dependents_unresolved(self, service, graph, ontology):
        proposal = propose(
            service,
            graph,
            # "Room" is taken in this scheme, so the create fails when applied.
            draft(1, T.CREATE, K.CLASS, ref="dup", concept_scheme_id=graph["vocab"], title="Room"),
            draft(
                2,
                T.CREATE,
                K.ATTRIBUTE,
                class_id="$dup",
                identifier="dup_size",
                title="Size",
                datatype="integer",
            ),
            draft(3, T.UPDATE, K.CLASS, graph["kitchen"], description="Cooking"),
        )
        result = by_seq(service.apply(proposal.id, ids(proposal, 1, 2, 3)))
        assert result[1].status is OperationStatus.FAILED
        assert result[1].reason.startswith("error: ")
        assert result[2].status is OperationStatus.FAILED
        assert result[2].reason == "unresolved_ref: $dup (seq 1) is failed, not applied"
        assert result[3].status is OperationStatus.APPLIED

    def test_partial_accept_across_calls_resolves_refs(self, service, graph, ontology):
        proposal = propose(
            service,
            graph,
            draft(1, T.CREATE, K.CLASS, ref="kit", concept_scheme_id=graph["vocab"], title="Kit"),
            draft(2, T.CREATE, K.INDIVIDUAL, class_ids=["$kit", graph["room"]], title="Toolbox"),
        )
        early = service.apply(proposal.id, ids(proposal, 2))
        assert by_seq(early)[2].reason == "unresolved_ref: $kit (seq 1) is pending, not applied"
        assert early.status is ProposalStatus.OPEN

        service.apply(proposal.id, ids(proposal, 1))
        done = service.apply(proposal.id, ids(proposal, 2))
        ops = by_seq(done)
        assert done.status is ProposalStatus.DONE
        toolbox = ontology.get_individual(ops[2].result_entity_id)
        assert toolbox.class_ids == [ops[1].result_entity_id, graph["room"]]

    def test_every_kind_dispatches_through_the_ontology_service(self, service, graph, ontology):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.TAXONOMY, graph["taxonomy"], vision="Tidy"),
            draft(2, T.UPDATE, K.SCHEME, graph["vocab"], description=None),
            draft(3, T.MOVE, K.CLASS, graph["kitchen"], parent_class_id=None),
            draft(
                4,
                T.MOVE,
                K.CLASS,
                graph["place"],
                concept_scheme_id=graph["vocab"],
                parent_class_id=graph["room"],
            ),
            draft(
                5,
                T.UPDATE,
                K.PROPERTY,
                graph["near"],
                domain_class_id=None,
                canonical_predicate="near-to",
                title="near to",
            ),
            draft(
                6,
                T.UPDATE,
                K.INDIVIDUAL,
                graph["den"],
                class_ids=[graph["kitchen"]],
                description=None,
            ),
            draft(
                7,
                T.CREATE,
                K.RELATIONSHIP,
                source_id=graph["den"],
                target_id=graph["room"],
                property_definition_id=graph["near"],
            ),
            draft(
                8,
                T.CREATE,
                K.PROPERTY,
                identifier="holds",
                title="holds",
                external_references=[{"source": "x", "identifier": "y"}],
            ),
        )
        result = by_seq(service.apply(proposal.id, [o.id for o in proposal.operations]))
        assert {s: o.status for s, o in result.items()} == {
            s: OperationStatus.APPLIED for s in range(1, 9)
        }, {s: o.reason for s, o in result.items()}
        assert ontology.get_taxonomy(graph["taxonomy"]).vision == "Tidy"
        assert not ontology.get_concept_scheme(graph["vocab"]).description
        assert ontology.get_class(graph["kitchen"]).parent_class_id is None
        place = ontology.get_class(graph["place"])
        assert (place.concept_scheme_id, place.parent_class_id) == (graph["vocab"], graph["room"])
        near = ontology.get_property_definition(graph["near"])
        assert near.domain_class_id is None and near.range_class_id == graph["room"]
        assert near.canonical_predicate == "near-to" and near.title == "near to"
        assert ontology.get_individual(graph["den"]).class_ids == [graph["kitchen"]]
        rel = ontology.get_relationship(result[7].result_entity_id)
        assert rel.source_run_id == proposal.id
        holds = ontology.get_property_definition(result[8].result_entity_id)
        assert holds.external_references[0].identifier == "y"

    def test_an_ontology_error_fails_only_that_operation(self, service, graph):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.CLASS, graph["kitchen"], title="Room"),  # duplicate title
            draft(2, T.UPDATE, K.CLASS, graph["room"], description="Any room"),
        )
        result = by_seq(service.apply(proposal.id, ids(proposal, 1, 2)))
        assert result[1].status is OperationStatus.FAILED and result[1].reason.startswith("error:")
        assert result[2].status is OperationStatus.APPLIED

    def test_input_checks_change_nothing(self, service, graph, ontology):
        proposal = propose(
            service, graph, draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room")
        )
        with pytest.raises(ValueError):
            service.apply(proposal.id, [*ids(proposal, 1), "not-an-op"])
        assert ontology.get_class(graph["room"]).description == "A room"
        with pytest.raises(ChangeProposalNotFoundError):
            service.apply("nope", [])

        service.apply(proposal.id, ids(proposal, 1))
        with pytest.raises(ChangeProposalStateError):
            service.apply(proposal.id, ids(proposal, 1))


# --------------------------------------------------------- reject / revert


class TestRejectAndRevert:
    def test_reject_records_the_note_and_settles(self, service, graph):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room"),
            draft(2, T.UPDATE, K.CLASS, graph["kitchen"], description="Cooking"),
        )
        partly = service.reject(proposal.id, ids(proposal, 1), note="Too vague")
        assert by_seq(partly)[1].status is OperationStatus.REJECTED
        assert by_seq(partly)[1].reason == "Too vague"
        assert partly.status is ProposalStatus.OPEN

        done = service.reject(proposal.id, ids(proposal, 2))
        assert done.status is ProposalStatus.DONE
        with pytest.raises(ChangeProposalStateError):
            service.apply(proposal.id, ids(proposal, 1))

    def test_failed_operation_can_be_rejected(self, service, graph, ontology):
        proposal = propose(service, graph, draft(1, T.DELETE, K.INDIVIDUAL, graph["den"]))
        ontology.update_individual(graph["den"], title="Study")
        service.apply(proposal.id, ids(proposal, 1))
        rejected = service.reject(proposal.id, ids(proposal, 1), note="Keep it")
        assert rejected.operations[0].status is OperationStatus.REJECTED

    def test_revert_delegates_rejects_pending_and_closes(self, service, graph, reverter):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room"),
            draft(2, T.UPDATE, K.CLASS, graph["kitchen"], description="Cooking"),
        )
        service.apply(proposal.id, ids(proposal, 1))
        result = service.revert(proposal.id)

        assert reverter.reverted == [proposal.id] and result.run_id == proposal.id
        reverted = service.get(proposal.id)
        assert reverted.status is ProposalStatus.REVERTED
        ops = by_seq(reverted)
        assert ops[1].status is OperationStatus.APPLIED
        assert (ops[2].status, ops[2].reason) == (OperationStatus.REJECTED, "proposal reverted")
        with pytest.raises(ChangeProposalStateError):
            service.apply(proposal.id, ids(proposal, 2))

    def test_a_refused_revert_leaves_the_proposal_as_it_was(self, proposals, ontology, repo, graph):
        service = ProposalService(
            proposals, ontology, repo, StubRevertService(ValueError("can't undo"))
        )
        proposal = propose(
            service, graph, draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room")
        )
        with pytest.raises(ValueError):
            service.revert(proposal.id)
        unchanged = service.get(proposal.id)
        assert unchanged.status is ProposalStatus.OPEN
        assert unchanged.operations[0].status is OperationStatus.PENDING


# ------------------------------------------------- review fixes (regressions)


class TestRefsOnlyInIdFields:
    def test_dollar_text_in_a_text_field_is_kept_as_written(self, service, graph, ontology):
        proposal = propose(
            service,
            graph,
            draft(1, T.CREATE, K.CLASS, ref="kit", concept_scheme_id=graph["vocab"], title="Kit"),
            draft(2, T.CREATE, K.INDIVIDUAL, class_ids=[graph["room"]], title="$kit"),
            draft(3, T.UPDATE, K.CLASS, graph["room"], description="$5 per night"),
        )
        result = by_seq(service.apply(proposal.id, ids(proposal, 1, 2, 3)))
        assert all(o.status is OperationStatus.APPLIED for o in result.values())
        assert ontology.get_individual(result[2].result_entity_id).title == "$kit"
        assert ontology.get_class(graph["room"]).description == "$5 per night"


class TestUnexpectedErrors:
    def test_any_exception_fails_only_its_operation(self, service, graph, ontology, monkeypatch):
        def broken(*args, **kwargs):
            raise RuntimeError("disk on fire")

        monkeypatch.setattr(ontology, "update_class", broken)
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room"),
            draft(2, T.UPDATE, K.INDIVIDUAL, graph["den"], description="Cosy"),
        )
        set_batch_run_context("outer-run")
        try:
            result = service.apply(proposal.id, ids(proposal, 1, 2))
            assert get_current_batch_run_id() == "outer-run"
        finally:
            set_batch_run_context(None)
        ops = by_seq(result)
        assert (ops[1].status, ops[1].reason) == (OperationStatus.FAILED, "error: disk on fire")
        assert ops[2].status is OperationStatus.APPLIED

    @pytest.mark.parametrize(
        "changes",
        [
            {"fields": {"title": 123}},
            {"fields": {"description": ["a"]}},
            {"fields": {"color": 7}},
            {"probability": "0.9"},
            {"probability": True},
            {"evidence": ["a quote"]},
            {"evidence": [3]},
            {"evidence": [{"quote": "q", "page": 4}]},
            {"evidence": [{"quote": ["q"]}]},
        ],
    )
    def test_wrong_value_types_are_refused_at_propose(self, service, graph, changes):
        values = {
            "seq": 1,
            "op": "update",
            "kind": "class",
            "target_id": graph["room"],
            "fields": {"title": "Chamber"},
        }
        values.update(changes)
        with pytest.raises(ProposalValidationError) as caught:
            service.propose(graph["taxonomy"], "T", [OperationDraft(**values)], ProposalSource.MCP)
        assert caught.value.errors[0].code == "invalid"

    def test_wrong_attribute_and_id_value_types_are_refused_at_propose(self, service, graph):
        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                graph,
                draft(
                    1,
                    T.CREATE,
                    K.ATTRIBUTE,
                    class_id=graph["room"],
                    identifier="a",
                    title="A",
                    datatype="string",
                    sort_order="x",
                ),
                draft(
                    2,
                    T.CREATE,
                    K.ATTRIBUTE,
                    class_id=graph["room"],
                    identifier="b",
                    title="B",
                    datatype="string",
                    allowed_values="abc",
                ),
                draft(
                    3,
                    T.CREATE,
                    K.ATTRIBUTE,
                    class_id=graph["room"],
                    identifier="c",
                    title="C",
                    datatype="string",
                    is_required="yes",
                ),
                draft(4, T.UPDATE, K.PROPERTY, graph["near"], domain_class_id=5),
            )
        assert [(e.seq, e.code) for e in caught.value.errors] == [
            (1, "invalid"),
            (2, "invalid"),
            (3, "invalid"),
            (4, "invalid"),
        ]


class TestClassIds:
    @pytest.mark.parametrize("duplicate", [False, True])
    def test_empty_or_duplicate_class_ids_are_refused(self, service, graph, duplicate):
        class_ids = [graph["room"], graph["room"]] if duplicate else []
        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                graph,
                draft(1, T.UPDATE, K.INDIVIDUAL, graph["den"], class_ids=class_ids),
                draft(2, T.CREATE, K.INDIVIDUAL, class_ids=class_ids, title="Hall"),
            )
        assert [(e.seq, e.code) for e in caught.value.errors] == [
            (1, "invalid"),
            (2, "invalid") if duplicate else (2, "missing_field"),
        ]

    def test_replacing_every_class_adds_before_removing(self, service, graph, ontology):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.INDIVIDUAL, graph["den"], class_ids=[graph["kitchen"]]),
        )
        result = service.apply(proposal.id, ids(proposal, 1))
        assert result.operations[0].status is OperationStatus.APPLIED, result.operations[0].reason
        assert ontology.get_individual(graph["den"]).class_ids == [graph["kitchen"]]


class TestDerivedFieldsAndStatus:
    def test_a_scheme_move_does_not_make_a_later_delete_of_its_class_stale(
        self, service, graph, ontology
    ):
        garden = ontology.create_taxonomy(title="Garden")
        proposal = propose(
            service,
            graph,
            draft(1, T.MOVE, K.SCHEME, graph["other"], taxonomy_id=garden.id),
            draft(2, T.DELETE, K.CLASS, graph["place"]),
        )
        result = by_seq(service.apply(proposal.id, ids(proposal, 1, 2)))
        assert result[2].status is OperationStatus.APPLIED, result[2].reason

    def test_a_failed_operation_keeps_the_proposal_open(self, service, graph, ontology):
        proposal = propose(
            service, graph, draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room")
        )
        ontology.update_class(graph["room"], description="Edited meanwhile")
        failed = service.apply(proposal.id, ids(proposal, 1))
        assert failed.status is ProposalStatus.OPEN

        rejected = service.reject(proposal.id, ids(proposal, 1), note="Leave it")
        assert rejected.status is ProposalStatus.DONE

    def test_revert_rejects_failed_operations_too(self, service, graph, ontology):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room"),
            draft(2, T.UPDATE, K.CLASS, graph["kitchen"], description="Cooking"),
        )
        ontology.update_class(graph["room"], description="Edited meanwhile")
        service.apply(proposal.id, ids(proposal, 1, 2))
        service.revert(proposal.id)
        ops = by_seq(service.get(proposal.id))
        assert (ops[1].status, ops[1].reason) == (OperationStatus.REJECTED, "proposal reverted")
        assert ops[2].status is OperationStatus.APPLIED

    def test_attribute_creates_carry_the_run_id(self, service, graph, ontology):
        proposal = propose(
            service,
            graph,
            draft(
                1,
                T.CREATE,
                K.ATTRIBUTE,
                class_id=graph["room"],
                identifier="area",
                title="Area",
                datatype="integer",
            ),
        )
        result = service.apply(proposal.id, ids(proposal, 1))
        made = ontology.get_attribute_definition(result.operations[0].result_entity_id)
        assert made.source_run_id == proposal.id


class TestConcurrency:
    def test_two_applies_of_one_operation_apply_it_once(
        self, service, graph, ontology, monkeypatch
    ):
        calls = []
        real_update = ontology.update_class

        def slow_update(*args, **kwargs):
            calls.append(args)
            time.sleep(0.05)
            return real_update(*args, **kwargs)

        monkeypatch.setattr(ontology, "update_class", slow_update)
        proposal = propose(
            service, graph, draft(1, T.UPDATE, K.CLASS, graph["room"], description="Any room")
        )
        outcomes = []

        def run():
            try:
                service.apply(proposal.id, ids(proposal, 1))
                outcomes.append("applied")
            except ChangeProposalStateError:
                outcomes.append("refused")

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(outcomes) == ["applied", "refused"]
        assert len(calls) == 1

    def test_unknown_proposals_get_no_lock(self, service):
        for action in (
            lambda: service.apply("nope", []),
            lambda: service.reject("nope", []),
            lambda: service.revert("nope"),
        ):
            with pytest.raises(ChangeProposalNotFoundError):
                action()
        assert service._locks == {}


class TestRelationshipAttributes:
    """#1365: relationships are created with attributes, and only those can be updated."""

    @pytest.fixture()
    def kit(self, ontology, graph):
        requires = ontology.create_property_definition(
            "requires",
            "requires",
            external_references=[
                ExternalReference(
                    source="house",
                    identifier="requires",
                    metadata={"edge_properties": ["quantity", "unit", "optional"]},
                )
            ],
        )
        hall = ontology.create_individual(graph["room"], "Hall")
        rel = ontology.create_relationship(
            graph["den"], hall.id, requires.id, attributes={"quantity": 2}
        )
        return {**graph, "requires": requires.id, "hall": hall.id, "rel": rel.id}

    def test_create_with_attributes_applies(self, service, ontology, kit):
        proposal = propose(
            service,
            kit,
            draft(
                1,
                T.CREATE,
                K.RELATIONSHIP,
                source_id=kit["hall"],
                target_id=kit["den"],
                property_definition_id=kit["requires"],
                attributes={"quantity": 1, "optional": True},
            ),
        )
        [op] = service.apply(proposal.id, ids(proposal, 1)).operations
        assert op.status is OperationStatus.APPLIED, op.reason
        assert ontology.get_relationship(op.result_entity_id).attributes == {
            "quantity": 1,
            "optional": True,
        }

    def test_attributes_update_captures_base_scope_and_applies(self, service, ontology, kit):
        proposal = propose(
            service,
            kit,
            draft(
                1, T.UPDATE, K.RELATIONSHIP, kit["rel"], attributes={"quantity": 2, "unit": "each"}
            ),
        )
        [op] = proposal.operations
        assert op.base == {"attributes": {"quantity": 2}}
        assert op.scope is ChangeScope.ADDITIVE

        [op] = service.apply(proposal.id, [op.id]).operations
        assert op.status is OperationStatus.APPLIED, op.reason
        assert ontology.get_relationship(kit["rel"]).attributes == {"quantity": 2, "unit": "each"}

    def test_attributes_changed_since_proposed_is_stale(self, service, ontology, kit):
        proposal = propose(
            service, kit, draft(1, T.UPDATE, K.RELATIONSHIP, kit["rel"], attributes={"quantity": 3})
        )
        assert proposal.operations[0].scope is ChangeScope.BREAKING
        ontology.update_relationship(kit["rel"], {"quantity": 5})

        [op] = service.apply(proposal.id, ids(proposal, 1)).operations
        assert op.status is OperationStatus.FAILED
        assert op.reason.startswith("target_changed: attributes")

    def test_endpoints_and_bad_attributes_are_refused(self, service, kit):
        with pytest.raises(ProposalValidationError) as caught:
            propose(
                service,
                kit,
                draft(1, T.UPDATE, K.RELATIONSHIP, kit["rel"], target_id=kit["room"]),
                draft(2, T.UPDATE, K.RELATIONSHIP, kit["rel"], attributes={"quantity": [2]}),
                draft(3, T.UPDATE, K.RELATIONSHIP, kit["rel"], attributes=None),
            )
        assert [(e.seq, e.code) for e in caught.value.errors] == [
            (1, "invalid"),
            (2, "invalid"),
            (3, "invalid"),
        ]

    def test_an_attribute_the_property_does_not_allow_fails_at_apply(self, service, kit):
        proposal = propose(
            service, kit, draft(1, T.UPDATE, K.RELATIONSHIP, kit["rel"], attributes={"brand": "x"})
        )
        [op] = service.apply(proposal.id, ids(proposal, 1)).operations
        assert op.status is OperationStatus.FAILED
        assert "does not allow attributes ['brand']" in op.reason
