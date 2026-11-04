"""
Unit tests for resolving relationship-type deletes that are in use (#1393):
the blockers preflight, and applying a delete with the relationships moved to
another type or deleted too.
"""

from contextlib import contextmanager
from types import MappingProxyType

import pytest

from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference
from domain.versioning.in_use import InUseInspector
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    InUseResolution,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ResolutionStrategy,
)
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

T, K = OperationType, OperationKind
MOVE, DELETE = ResolutionStrategy.MOVE, ResolutionStrategy.DELETE


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        result = RevertResult(run_id=run_id, events_reverted=0)
        if on_reverted is not None:
            on_reverted(result)
        return result


class SnapshotScope:
    """
    TransactionScope over the fake repository: restores which entities it holds
    if the block raises (enough for creates and deletes).
    """

    def __init__(self, repo):
        self.repo = repo
        self.entered = 0

    @contextmanager
    def atomic(self):
        saved = {
            name: dict(value) if isinstance(value, dict) else value
            for name, value in self.repo.__dict__.items()
        }
        self.entered += 1
        try:
            yield
        except BaseException:
            self.repo.__dict__.clear()
            self.repo.__dict__.update(saved)
            raise


def edge_attributes(*names):
    return [
        ExternalReference(
            source="test",
            identifier="x",
            metadata=MappingProxyType({"edge_properties": list(names)}),
        )
    ]


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def repo(ontology):
    return ontology._repository


@pytest.fixture()
def graph(ontology):
    """
    The DR case: two BusinessEvent -> BusinessFunction relationships use
    businessevent_triggers_businessfunction; the "obvious" replacement
    businessevent_triggers_businessprocess has range BusinessProcess, so it doesn't fit.
    """
    taxonomy = ontology.create_taxonomy(title="DR", identifier="dr_spec")
    business = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Business")
    event = ontology.create_class(business.id, "BusinessEvent")
    sync_event = ontology.create_class(business.id, "SyncEvent", parent_class_id=event.id)
    function = ontology.create_class(business.id, "BusinessFunction")
    process = ontology.create_class(business.id, "BusinessProcess")
    triggers_function = ontology.create_property_definition(
        "businessevent_triggers_businessfunction",
        "triggers function",
        domain_class_id=event.id,
        range_class_id=function.id,
        external_references=edge_attributes("weight"),
    )
    triggers_process = ontology.create_property_definition(
        "businessevent_triggers_businessprocess",
        "triggers process",
        domain_class_id=event.id,
        range_class_id=process.id,
    )
    changed = ontology.create_individual(event.id, "Entity Changed Event")
    synced = ontology.create_individual(sync_event.id, "Sync Completed Event")
    enrichment = ontology.create_individual(function.id, "Entity Enrichment")
    conflicts = ontology.create_individual(function.id, "Conflict Resolution")
    first = ontology.create_relationship(
        changed.id, enrichment.id, triggers_function.id, attributes={"weight": 2}
    )
    second = ontology.create_relationship(synced.id, conflicts.id, triggers_function.id)
    return {
        "taxonomy": taxonomy.id,
        "event": event.id,
        "sync_event": sync_event.id,
        "function": function.id,
        "process": process.id,
        "triggers_function": triggers_function.id,
        "triggers_process": triggers_process.id,
        "changed": changed.id,
        "synced": synced.id,
        "enrichment": enrichment.id,
        "conflicts": conflicts.id,
        "first": first.id,
        "second": second.id,
    }


def add_fitting_type(ontology, graph, identifier="businessevent_serves_businessfunction"):
    """A type whose domain is BusinessEvent (a SyncEvent fits too) and range BusinessFunction."""
    return ontology.create_property_definition(
        identifier,
        "serves function",
        domain_class_id=graph["event"],
        range_class_id=graph["function"],
        external_references=edge_attributes("weight"),
    ).id


@pytest.fixture()
def scope(repo):
    return SnapshotScope(repo)


@pytest.fixture()
def service(ontology, repo, scope):
    return ProposalService(
        FakeChangeProposalRepository(), ontology, repo, StubRevertService(), transaction_scope=scope
    )


def propose_delete(service, graph, *extra):
    drafts = [
        OperationDraft(seq=1, op=T.DELETE, kind=K.PROPERTY, target_id=graph["triggers_function"])
    ]
    drafts += list(extra)
    return service.propose(graph["taxonomy"], "Business layer", drafts, ProposalSource.BUNDLE)


def the_op(proposal, seq=1):
    return next(o for o in proposal.operations if o.seq == seq)


def edges_of(repo, property_id):
    return repo.list_relationships(property_id=property_id, limit=None)


# ------------------------------------------------------------------ preflight


class TestBlockers:
    def test_lists_each_relationship_with_its_ends_and_their_classes(self, service, graph):
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert [e.relationship_id for e in blockers.edges] == [graph["first"], graph["second"]]
        first, second = blockers.edges
        assert (first.source.title, first.target.title) == (
            "Entity Changed Event",
            "Entity Enrichment",
        )
        assert first.source.class_titles == ("BusinessEvent",)
        assert first.target.class_ids == (graph["function"],)
        assert first.attributes == {"weight": 2}
        assert second.source.class_titles == ("SyncEvent",)

    def test_the_dr_case_has_no_replacement_and_says_why(self, service, graph):
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert blockers.replacements == ()
        reason = blockers.move_unavailable_reason
        assert "businessevent_triggers_businessprocess" in reason
        assert "none accepts BusinessFunction targets" in reason

    def test_offers_types_that_fit_every_relationship_inheritance_aware(
        self, service, graph, ontology
    ):
        serves = add_fitting_type(ontology, graph)
        # A domain or range left open accepts anything.
        open_type = ontology.create_property_definition(
            "relates_to", "relates to", external_references=edge_attributes("weight")
        ).id
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert [r.property_id for r in blockers.replacements] == [serves, open_type]
        assert blockers.move_unavailable_reason is None

    def test_a_type_that_doesnt_allow_an_edges_attributes_doesnt_fit(
        self, service, graph, ontology
    ):
        ontology.create_property_definition(
            "businessevent_serves_businessfunction",
            "serves",
            domain_class_id=graph["event"],
            range_class_id=graph["function"],
        )
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert blockers.replacements == ()
        assert "doesn't allow attributes ['weight']" in blockers.move_unavailable_reason

    def test_a_subclass_domain_doesnt_accept_its_parents_individuals(
        self, service, graph, ontology
    ):
        ontology.create_property_definition(
            "syncevent_serves_businessfunction",
            "sync serves",
            domain_class_id=graph["sync_event"],
            range_class_id=graph["function"],
            external_references=edge_attributes("weight"),
        )
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        # Entity Changed Event is a BusinessEvent, not a SyncEvent.
        assert blockers.replacements == ()
        assert blockers.move_unavailable_reason == (
            "1 type accepts BusinessEvent, SyncEvent sources "
            "(businessevent_triggers_businessprocess), but none accepts BusinessFunction targets"
        )

    def test_never_offers_a_type_the_proposal_also_deletes(self, service, graph, ontology):
        serves = add_fitting_type(ontology, graph)
        proposal = propose_delete(
            service, graph, OperationDraft(seq=2, op=T.DELETE, kind=K.PROPERTY, target_id=serves)
        )
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert blockers.replacements == ()

    def test_none_for_a_type_nothing_uses_or_an_operation_already_decided(
        self, service, graph, ontology
    ):
        unused = add_fitting_type(ontology, graph)
        proposal = propose_delete(
            service, graph, OperationDraft(seq=2, op=T.DELETE, kind=K.PROPERTY, target_id=unused)
        )
        blockers = service.in_use_blockers(proposal)
        assert set(blockers) == {the_op(proposal).id}

        rejected = service.reject(proposal.id, [the_op(proposal).id])
        assert service.in_use_blockers(rejected) == {}


# ---------------------------------------------------------------------- apply


class TestApply:
    def test_without_a_resolution_it_still_fails_as_in_use(self, service, graph, repo):
        proposal = propose_delete(service, graph)
        applied = service.apply(proposal.id, [the_op(proposal).id])

        op = the_op(applied)
        assert op.status is OperationStatus.FAILED
        assert "is in use by 2 relationship(s)" in op.reason
        assert op.resolution is None
        assert repo.get_property_definition(graph["triggers_function"]) is not None

    def test_delete_them_too_deletes_the_relationships_then_the_type(
        self, service, graph, repo, scope
    ):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        applied = service.apply(
            proposal.id, [op_id], resolutions={op_id: InUseResolution(strategy=DELETE)}
        )

        op = the_op(applied)
        assert op.status is OperationStatus.APPLIED, op.reason
        assert repo.get_property_definition(graph["triggers_function"]) is None
        assert repo.get_relationship(graph["first"]) is None
        assert repo.get_relationship(graph["second"]) is None
        assert op.resolution.strategy is DELETE
        assert [e.relationship_id for e in op.resolution.edges] == [graph["first"], graph["second"]]
        assert op.resolution.edges[0].source_title == "Entity Changed Event"
        assert all(e.moved_to_id is None for e in op.resolution.edges)
        assert scope.entered == 1
        assert service.in_use_blockers(applied) == {}

    def test_move_gives_each_relationship_the_replacement_type(
        self, service, graph, repo, ontology
    ):
        serves = add_fitting_type(ontology, graph)
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        resolution = InUseResolution(strategy=MOVE, replacement_property_id=serves)
        applied = service.apply(proposal.id, [op_id], resolutions={op_id: resolution})

        op = the_op(applied)
        assert op.status is OperationStatus.APPLIED, op.reason
        assert repo.get_property_definition(graph["triggers_function"]) is None
        moved = {(r.source_id, r.target_id): r for r in edges_of(repo, serves)}
        assert set(moved) == {
            (graph["changed"], graph["enrichment"]),
            (graph["synced"], graph["conflicts"]),
        }
        assert moved[(graph["changed"], graph["enrichment"])].attributes == {"weight": 2}
        assert moved[(graph["changed"], graph["enrichment"])].source_run_id == proposal.id
        assert op.resolution.replacement_identifier == "businessevent_serves_businessfunction"
        assert sorted(e.moved_to_id for e in op.resolution.edges) == sorted(
            r.id for r in moved.values()
        )

    def test_move_to_a_type_that_doesnt_fit_changes_nothing(self, service, graph, repo):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        resolution = InUseResolution(
            strategy=MOVE, replacement_property_id=graph["triggers_process"]
        )
        applied = service.apply(proposal.id, [op_id], resolutions={op_id: resolution})

        op = the_op(applied)
        assert op.status is OperationStatus.FAILED
        assert op.reason.startswith(
            "unresolvable: 2 of 2 relationship(s) don't fit businessevent_triggers_businessprocess"
        )
        assert "Entity Changed Event → Entity Enrichment: target is BusinessFunction" in op.reason
        assert op.resolution is None
        assert len(edges_of(repo, graph["triggers_function"])) == 2
        assert edges_of(repo, graph["triggers_process"]) == []

    def test_move_to_a_missing_type_fails(self, service, graph):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        resolution = InUseResolution(strategy=MOVE, replacement_property_id="nope")
        applied = service.apply(proposal.id, [op_id], resolutions={op_id: resolution})

        assert the_op(applied).reason == "unresolvable: no other relationship type nope"

    def test_a_failing_step_rolls_back_every_step(
        self, service, graph, repo, ontology, monkeypatch
    ):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id

        def refuse(property_id):
            raise ValueError("disk full")

        monkeypatch.setattr(ontology, "delete_property_definition", refuse)
        applied = service.apply(
            proposal.id, [op_id], resolutions={op_id: InUseResolution(strategy=DELETE)}
        )

        op = the_op(applied)
        assert op.status is OperationStatus.FAILED
        assert op.reason == "error: disk full"
        assert op.resolution is None
        assert repo.get_relationship(graph["first"]) is not None
        assert repo.get_relationship(graph["second"]) is not None

    def test_a_failed_resolution_applied_again_without_one_applies_as_proposed(
        self, service, graph
    ):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        resolution = InUseResolution(
            strategy=MOVE, replacement_property_id=graph["triggers_process"]
        )
        service.apply(proposal.id, [op_id], resolutions={op_id: resolution})
        again = service.apply(proposal.id, [op_id])

        assert "is in use by 2" in the_op(again).reason


class TestMisplacedResolutions:
    def test_only_for_a_property_delete_being_applied(self, service, graph):
        proposal = propose_delete(
            service,
            graph,
            OperationDraft(
                seq=2,
                op=T.UPDATE,
                kind=K.PROPERTY,
                target_id=graph["triggers_process"],
                fields={"title": "starts"},
            ),
        )
        delete, update = the_op(proposal, 1).id, the_op(proposal, 2).id
        resolution = InUseResolution(strategy=DELETE)

        with pytest.raises(ValueError, match="only a property delete takes a resolution"):
            service.apply(proposal.id, [update], resolutions={update: resolution})
        with pytest.raises(ValueError, match="not being applied"):
            service.apply(proposal.id, [update], resolutions={delete: resolution})
        with pytest.raises(ValueError, match="both an edit and a resolution"):
            service.apply(
                proposal.id,
                [delete],
                edits={delete: {"title": "x"}},
                resolutions={delete: resolution},
            )
        assert all(o.status is OperationStatus.PENDING for o in service.get(proposal.id).operations)


class TestResolution:
    def test_a_move_needs_a_replacement_and_a_delete_takes_none(self):
        with pytest.raises(ValueError, match="needs replacement_property_id"):
            InUseResolution(strategy=MOVE)
        with pytest.raises(ValueError, match="takes no replacement_property_id"):
            InUseResolution(strategy=DELETE, replacement_property_id="p")

    def test_round_trips_through_json(self, service, graph, ontology):
        serves = add_fitting_type(ontology, graph)
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        resolution = InUseResolution(strategy=MOVE, replacement_property_id=serves)
        stored = the_op(service.apply(proposal.id, [op_id], resolutions={op_id: resolution}))

        assert InUseResolution.from_json(stored.resolution.to_json()) == stored.resolution


class TestInspector:
    def test_ancestors_follow_parents_without_looping(self, repo, graph):
        inspector = InUseInspector(repo)
        assert inspector._ancestors_of(graph["sync_event"]) == {graph["sync_event"], graph["event"]}
