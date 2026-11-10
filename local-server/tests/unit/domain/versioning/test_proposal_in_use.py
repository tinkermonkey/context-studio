"""
Unit tests for resolving relationship-type deletes that are in use (#1393):
the blockers preflight, and applying a delete with the relationships moved to
another type or deleted too. And (#1417) an applied relationship-type update
migrating the relationships using the type in the same transaction (a reverse
swaps their ends, a rename keeps them, a retarget keeps, moves or deletes them
as resolved), with a schema change record for every applied type operation.
"""

from contextlib import contextmanager
from types import MappingProxyType

import pytest

import domain.versioning.proposal_service as proposal_service_module
from domain.ontology.events import GraphInvalidated
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference
from domain.versioning.change_records import (
    SchemaChangeAction,
    identifier_key,
    schema_change_records,
)
from domain.versioning.in_use import InUseInspector
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    InUseResolution,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
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


_EDGE_SOURCE = "test-edge-attributes"


def edge_attributes(*names):
    """
    A marker reference: the `ontology` fixture gives a relationship type created
    with it a number edge attribute per name (#1482: edge attributes are
    attribute definitions owned by the type).
    """
    return [ExternalReference(source=_EDGE_SOURCE, identifier=",".join(names))]


class _EdgeAttributeOntology(OntologyService):
    """OntologyService whose relationship types made with edge_attributes(...) get them."""

    def create_property_definition(self, *args, **kwargs):
        prop = super().create_property_definition(*args, **kwargs)
        for ref in kwargs.get("external_references") or []:
            if ref.source == _EDGE_SOURCE:
                for name in ref.identifier.split(","):
                    self.create_attribute_definition(
                        None, name, name, "number", property_definition_id=prop.id
                    )
        return prop


@pytest.fixture()
def ontology():
    return _EdgeAttributeOntology(
        FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher()
    )


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
    for predicate in ("starts", "serves", *(f"p{i}" for i in range(7))):
        ontology.create_predicate(taxonomy.id, predicate)
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
def publisher():
    return FakeEventPublisher()


@pytest.fixture()
def service(ontology, repo, scope, publisher):
    return ProposalService(
        FakeChangeProposalRepository(),
        ontology,
        repo,
        StubRevertService(),
        transaction_scope=scope,
        event_publisher=publisher,
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
        # A range left open accepts any target.
        open_range = ontology.create_property_definition(
            "businessevent_relates_to",
            "relates to",
            domain_class_id=graph["event"],
            external_references=edge_attributes("weight"),
        ).id
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert [r.property_id for r in blockers.replacements] == [open_range, serves]
        assert blockers.move_unavailable_reason is None

    def test_never_offers_an_untyped_type_from_outside_the_taxonomy(self, service, graph, ontology):
        """A generic type with no domain or range fits anything, but isn't the DR catalog's."""
        ontology.create_property_definition(
            "causes", "causes", external_references=edge_attributes("weight")
        )
        other = ontology.create_taxonomy(title="Other", identifier="other")
        scheme = ontology.create_scheme(taxonomy_id=other.id, title="Things")
        thing = ontology.create_class(scheme.id, "Thing")
        ontology.create_property_definition(
            "thing_involves",
            "involves",
            domain_class_id=thing.id,
            external_references=edge_attributes("weight"),
        )
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert blockers.replacements == ()
        assert "none accepts BusinessFunction targets" in blockers.move_unavailable_reason

    def test_an_untyped_type_being_deleted_may_move_to_any_type(self, service, graph, ontology):
        untyped = ontology.create_property_definition("related", "related").id
        generic = ontology.create_property_definition("causes", "causes").id
        ontology.create_relationship(graph["changed"], graph["conflicts"], untyped)
        proposal = service.propose(
            graph["taxonomy"],
            "Untyped",
            [OperationDraft(seq=1, op=T.DELETE, kind=K.PROPERTY, target_id=untyped)],
            ProposalSource.USER,
        )
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        assert generic in [r.property_id for r in blockers.replacements]

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
        assert "does not allow attributes ['weight']" in blockers.move_unavailable_reason

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

        with pytest.raises(ValueError, match="not being applied"):
            service.apply(proposal.id, [update], resolutions={delete: resolution})
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
        assert inspector.ancestors_of(graph["sync_event"]) == {graph["sync_event"], graph["event"]}


class TestReviewFindings:
    def test_relationships_the_proposal_deletes_dont_block(self, service, graph, repo):
        """A bundle import plans the relationship deletes before their type's delete."""
        rel_deletes = [
            OperationDraft(seq=1, op=T.DELETE, kind=K.RELATIONSHIP, target_id=graph["first"]),
            OperationDraft(seq=2, op=T.DELETE, kind=K.RELATIONSHIP, target_id=graph["second"]),
        ]
        drafts = [
            rel_deletes[0],
            rel_deletes[1],
            OperationDraft(
                seq=9, op=T.DELETE, kind=K.PROPERTY, target_id=graph["triggers_function"]
            ),
        ]
        proposal = service.propose(graph["taxonomy"], "Bundle", drafts, ProposalSource.BUNDLE)
        assert service.in_use_blockers(proposal) == {}

        applied = service.apply(proposal.id, [o.id for o in proposal.operations])
        assert all(o.status is OperationStatus.APPLIED for o in applied.operations)
        assert repo.get_property_definition(graph["triggers_function"]) is None

    def test_only_the_relationships_left_block(self, service, graph):
        drafts = [
            OperationDraft(seq=1, op=T.DELETE, kind=K.RELATIONSHIP, target_id=graph["first"]),
            OperationDraft(
                seq=2, op=T.DELETE, kind=K.PROPERTY, target_id=graph["triggers_function"]
            ),
        ]
        proposal = service.propose(graph["taxonomy"], "Bundle", drafts, ProposalSource.BUNDLE)
        blockers = service.in_use_blockers(proposal)[the_op(proposal, 2).id]
        assert [e.relationship_id for e in blockers.edges] == [graph["second"]]

    def test_fails_when_the_relationships_changed_since_reviewed(self, service, graph, repo):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        seen = InUseResolution(strategy=DELETE, relationship_ids=[graph["first"]])
        applied = service.apply(proposal.id, [op_id], resolutions={op_id: seen})

        op = the_op(applied)
        assert op.status is OperationStatus.FAILED
        assert op.reason == (
            "unresolvable: the relationships using the type changed since reviewed: "
            "2 now, 1 reviewed; review them again"
        )
        assert len(edges_of(repo, graph["triggers_function"])) == 2

    def test_applies_when_the_reviewed_relationships_still_stand(self, service, graph):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        seen = InUseResolution(strategy=DELETE, relationship_ids=[graph["second"], graph["first"]])
        applied = service.apply(proposal.id, [op_id], resolutions={op_id: seen})
        assert the_op(applied).status is OperationStatus.APPLIED

    def test_invalidates_the_graph_after_the_transaction(self, service, graph, publisher):
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        service.apply(proposal.id, [op_id], resolutions={op_id: InUseResolution(strategy=DELETE)})

        last = publisher.get_events_of_type(GraphInvalidated)[-1]
        assert (last.taxonomy_id, last.reason) == (graph["taxonomy"], "proposal_resolution")

    def test_refuses_a_move_to_a_type_the_proposal_deletes(self, service, graph, ontology):
        serves = add_fitting_type(ontology, graph)
        proposal = propose_delete(
            service, graph, OperationDraft(seq=2, op=T.DELETE, kind=K.PROPERTY, target_id=serves)
        )
        op_id = the_op(proposal).id
        move = InUseResolution(strategy=MOVE, replacement_property_id=serves)
        with pytest.raises(ValueError, match="which seq 2 deletes"):
            service.apply(proposal.id, [op_id], resolutions={op_id: move})

    def test_a_resolution_for_an_unused_type_records_none(self, service, graph, ontology):
        unused = add_fitting_type(ontology, graph)
        proposal = service.propose(
            graph["taxonomy"],
            "Unused",
            [OperationDraft(seq=1, op=T.DELETE, kind=K.PROPERTY, target_id=unused)],
            ProposalSource.USER,
        )
        op_id = the_op(proposal).id
        applied = service.apply(
            proposal.id, [op_id], resolutions={op_id: InUseResolution(strategy=DELETE)}
        )
        assert the_op(applied).status is OperationStatus.APPLIED
        assert the_op(applied).resolution is None

    def test_lists_relationship_types_once_per_preflight(self, service, graph, ontology, repo):
        serves = add_fitting_type(ontology, graph)
        drafts = [
            OperationDraft(
                seq=1, op=T.DELETE, kind=K.PROPERTY, target_id=graph["triggers_function"]
            ),
            OperationDraft(
                seq=2, op=T.DELETE, kind=K.PROPERTY, target_id=graph["triggers_process"]
            ),
        ]
        ontology.create_relationship(graph["changed"], graph["enrichment"], serves)
        # triggers_process needs a user too, to be blocked.
        process_individual = ontology.create_individual(graph["process"], "Billing")
        ontology.create_relationship(
            graph["changed"], process_individual.id, graph["triggers_process"]
        )
        proposal = service.propose(graph["taxonomy"], "Two", drafts, ProposalSource.USER)
        calls = []
        original = repo.list_property_definitions
        repo.list_property_definitions = lambda *a, **k: calls.append(1) or original(*a, **k)

        assert len(service.in_use_blockers(proposal)) == 2
        assert len(calls) == 1


# ------------------------------------------------------ pair of the replacement (#1412)


def add_reversed_type(ontology, graph):
    """BusinessFunction -> BusinessEvent: the deleted type's pair reversed."""
    return ontology.create_property_definition(
        "businessfunction_triggered_by_businessevent",
        "triggered by",
        domain_class_id=graph["function"],
        range_class_id=graph["event"],
        external_references=edge_attributes("weight"),
    ).id


def move_to(service, graph, replacement_id):
    proposal = propose_delete(service, graph)
    op_id = the_op(proposal).id
    resolution = InUseResolution(strategy=MOVE, replacement_property_id=replacement_id)
    return proposal, the_op(service.apply(proposal.id, [op_id], resolutions={op_id: resolution}))


class TestMoveByPair:
    def test_a_same_pair_replacement_keeps_each_relationships_ends(
        self, service, graph, repo, ontology
    ):
        serves = add_fitting_type(ontology, graph)
        _, op = move_to(service, graph, serves)

        assert op.status is OperationStatus.APPLIED, op.reason
        assert op.resolution.reversed is False
        assert {(r.source_id, r.target_id) for r in edges_of(repo, serves)} == {
            (graph["changed"], graph["enrichment"]),
            (graph["synced"], graph["conflicts"]),
        }

    def test_a_reversed_replacement_takes_each_relationship_with_its_ends_swapped(
        self, service, graph, repo, ontology, scope
    ):
        reversed_type = add_reversed_type(ontology, graph)
        proposal, op = move_to(service, graph, reversed_type)

        assert op.status is OperationStatus.APPLIED, op.reason
        assert repo.get_property_definition(graph["triggers_function"]) is None
        moved = {(r.source_id, r.target_id): r for r in edges_of(repo, reversed_type)}
        assert set(moved) == {
            (graph["enrichment"], graph["changed"]),
            (graph["conflicts"], graph["synced"]),
        }
        assert moved[(graph["enrichment"], graph["changed"])].attributes == {"weight": 2}
        assert moved[(graph["enrichment"], graph["changed"])].source_run_id == proposal.id
        assert op.resolution.reversed is True
        # The record keeps each original relationship's ends.
        first = op.resolution.edges[0]
        assert (first.source_id, first.target_id) == (graph["changed"], graph["enrichment"])
        assert first.moved_to_id == moved[(graph["enrichment"], graph["changed"])].id
        assert scope.entered == 1

    def test_a_different_pair_replacement_misfits_and_changes_nothing(self, service, graph, repo):
        _, op = move_to(service, graph, graph["triggers_process"])

        assert op.status is OperationStatus.FAILED
        assert op.reason.startswith("unresolvable: 2 of 2 relationship(s) don't fit")
        assert len(edges_of(repo, graph["triggers_function"])) == 2

    def test_blockers_offer_a_reversed_type_and_say_so(self, service, graph, ontology):
        reversed_type = add_reversed_type(ontology, graph)
        serves = add_fitting_type(ontology, graph)
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]

        offered = {r.property_id: r.reversed for r in blockers.replacements}
        assert offered == {serves: False, reversed_type: True}

    def test_a_reversed_move_checks_duplicates_the_swapped_way_round(
        self, service, graph, repo, ontology
    ):
        reversed_type = add_reversed_type(ontology, graph)
        ontology.create_relationship(graph["enrichment"], graph["changed"], reversed_type)
        proposal = propose_delete(service, graph)
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]
        assert blockers.replacements == ()

        _, op = move_to(service, graph, reversed_type)
        assert op.status is OperationStatus.FAILED
        assert (
            "Entity Enrichment → Entity Changed Event: already related by "
            "businessfunction_triggered_by_businessevent"
        ) in op.reason
        assert len(edges_of(repo, graph["triggers_function"])) == 2

    def test_the_reversed_flag_round_trips_through_json(self, service, graph, ontology):
        reversed_type = add_reversed_type(ontology, graph)
        _, op = move_to(service, graph, reversed_type)

        assert InUseResolution.from_json(op.resolution.to_json()) == op.resolution
        assert InUseResolution.from_json({"strategy": "delete"}).reversed is False

    def test_a_reversed_move_is_stale_once_the_deleted_types_pair_changes(
        self, service, graph, repo, ontology
    ):
        reversed_type = add_reversed_type(ontology, graph)
        proposal = propose_delete(service, graph)
        op_id = the_op(proposal).id
        ontology.update_property_definition(
            graph["triggers_function"], range_class_id=graph["process"], update_range_class_id=True
        )
        resolution = InUseResolution(strategy=MOVE, replacement_property_id=reversed_type)

        op = the_op(service.apply(proposal.id, [op_id], resolutions={op_id: resolution}))

        assert op.status is OperationStatus.FAILED
        assert op.reason == "target_changed: range_class_id changed since proposed"
        assert len(edges_of(repo, graph["triggers_function"])) == 2
        assert edges_of(repo, reversed_type) == []


# ------------------------------------------------------- type updates (#1417)


def propose_update(service, graph, **fields):
    draft = OperationDraft(
        seq=1, op=T.UPDATE, kind=K.PROPERTY, target_id=graph["triggers_function"], fields=fields
    )
    return service.propose(graph["taxonomy"], "Refine", [draft], ProposalSource.MCP)


def apply(service, proposal, **kwargs):
    op_id = the_op(proposal).id
    return the_op(service.apply(proposal.id, [op_id], **kwargs))


def ends(repo, property_id):
    return {
        (r.id, r.source_id, r.target_id, tuple(sorted(r.attributes.items())))
        for r in edges_of(repo, property_id)
    }


def swapped(found):
    return {(i, t, s, a) for i, s, t, a in found}


def reverse_fields(graph):
    return {"domain_class_id": graph["function"], "range_class_id": graph["event"]}


def unused_type(ontology, graph, identifier="businessevent_follows_businessfunction"):
    return ontology.create_property_definition(
        identifier,
        identifier.replace("_", " "),
        domain_class_id=graph["event"],
        range_class_id=graph["function"],
    ).id


def test_a_reverse_swaps_every_relationships_ends_in_place_in_one_transaction(
    service, graph, repo, scope
):
    before = ends(repo, graph["triggers_function"])
    proposal = propose_update(service, graph, **reverse_fields(graph))

    op = apply(service, proposal)

    assert op.status is OperationStatus.APPLIED, op.reason
    # Same ids and attributes, ends swapped.
    assert ends(repo, graph["triggers_function"]) == swapped(before)
    assert scope.entered == 1
    change = op.type_change
    assert change.action is SchemaChangeAction.REVERSE
    assert change.swap is True
    assert change.before["domain_class_id"] == graph["event"]
    assert change.after["domain_class_id"] == graph["function"]
    (record,) = schema_change_records(service.get(proposal.id), service.decisions_of(proposal.id))
    assert record.action is SchemaChangeAction.REVERSE
    assert record.swap is True
    assert record.from_ == record.to == "businessevent_triggers_businessfunction"
    assert record.applied_at is not None
    assert record.p == 1.0


def test_a_reverse_keeps_a_pair_running_both_ways(service, graph, repo, ontology):
    """a -> b and b -> a of one type swap to b -> a and a -> b, each keeping its id."""
    first = repo.get_relationship(graph["first"])
    mirror = ontology.create_relationship(
        first.target_id, first.source_id, graph["triggers_function"]
    )
    before = ends(repo, graph["triggers_function"])
    proposal = propose_update(service, graph, **reverse_fields(graph))

    op = apply(service, proposal)

    assert op.status is OperationStatus.APPLIED, op.reason
    assert ends(repo, graph["triggers_function"]) == swapped(before)
    assert repo.get_relationship(mirror.id).source_id == first.source_id


def test_an_edited_update_that_reverses_swaps_them_too(service, graph, repo):
    before = ends(repo, graph["triggers_function"])
    proposal = propose_update(service, graph, title="triggered by")
    op_id = the_op(proposal).id

    op = apply(service, proposal, edits={op_id: reverse_fields(graph)})

    assert op.status is OperationStatus.APPLIED, op.reason
    assert ends(repo, graph["triggers_function"]) == swapped(before)


def test_a_reverse_keeps_the_edge_attributes_its_relationships_carry(service, graph, repo):
    """#1482: edge attributes belong to the type, so references don't drop them."""
    proposal = propose_update(service, graph, **reverse_fields(graph), external_references=[])

    op = apply(service, proposal)

    assert op.status is OperationStatus.APPLIED, op.reason
    attributes = [
        r.attributes for r in repo.list_relationships(property_id=graph["triggers_function"])
    ]
    assert {"weight": 2} in attributes


def test_a_rename_keeps_the_relationships_as_they_are(service, graph, repo):
    before = ends(repo, graph["triggers_function"])
    proposal = propose_update(service, graph, identifier="businessevent_starts_businessfunction")

    op = apply(service, proposal)

    assert op.status is OperationStatus.APPLIED, op.reason
    assert ends(repo, graph["triggers_function"]) == before
    (record,) = schema_change_records(service.get(proposal.id))
    assert (record.action, record.from_, record.to, record.swap) == (
        SchemaChangeAction.RENAME,
        "businessevent_triggers_businessfunction",
        "businessevent_starts_businessfunction",
        False,
    )


def test_a_wording_update_records_nothing(service, graph):
    proposal = propose_update(service, graph, title="sets off")
    op = apply(service, proposal)
    assert op.type_change is None
    assert schema_change_records(service.get(proposal.id)) == []


def test_a_forced_rename_records_what_it_replaced_as_applied(service, graph):
    """
    Two renames of one type can't share a proposal (conflicting_op), but two
    proposals can: the second, proposed against the original identifier and
    forced past the first, records the identifier it actually replaced, so
    the two records chain.
    """
    first = propose_update(service, graph, identifier="starts_function")
    second = propose_update(service, graph, identifier="launches_function")
    apply(service, first)
    apply(service, second, force_stale=[the_op(second).id])

    (renamed,) = schema_change_records(service.get(first.id))
    (again,) = schema_change_records(service.get(second.id))
    assert (renamed.from_, renamed.to) == (
        "businessevent_triggers_businessfunction",
        "starts_function",
    )
    assert (again.from_, again.to) == ("starts_function", "launches_function")
    assert the_op(service.get(second.id)).base["identifier"] == (
        "businessevent_triggers_businessfunction"
    )


def test_an_in_use_retarget_is_blocked_until_resolved(service, graph, repo):
    before = ends(repo, graph["triggers_function"])
    proposal = propose_update(service, graph, range_class_id=graph["process"])

    blockers = service.in_use_blockers(proposal)[the_op(proposal).id]
    op = apply(service, proposal)

    assert [e.relationship_id for e in blockers.edges] == [graph["first"], graph["second"]]
    assert op.status is OperationStatus.FAILED
    assert "a retarget needs a resolution" in op.reason
    assert ends(repo, graph["triggers_function"]) == before
    assert (
        repo.get_property_definition(graph["triggers_function"]).range_class_id == graph["function"]
    )


def test_a_retarget_of_an_unused_type_needs_no_resolution(service, graph, ontology, repo):
    unused = unused_type(ontology, graph)
    draft = OperationDraft(
        seq=1,
        op=T.UPDATE,
        kind=K.PROPERTY,
        target_id=unused,
        fields={"range_class_id": graph["process"]},
    )
    proposal = service.propose(graph["taxonomy"], "Retarget", [draft], ProposalSource.MCP)

    assert service.in_use_blockers(proposal) == {}
    op = apply(service, proposal)

    assert op.status is OperationStatus.APPLIED, op.reason
    (record,) = schema_change_records(service.get(proposal.id))
    assert (record.action, record.moved_to, record.swap) == (
        SchemaChangeAction.RETARGET,
        None,
        False,
    )


def test_a_retarget_can_delete_its_relationships_first(service, graph, repo):
    proposal = propose_update(service, graph, range_class_id=graph["process"])

    op = apply(
        service,
        proposal,
        resolutions={the_op(proposal).id: InUseResolution(strategy=DELETE)},
    )

    assert op.status is OperationStatus.APPLIED, op.reason
    assert edges_of(repo, graph["triggers_function"]) == []
    assert [e.relationship_id for e in op.resolution.edges] == [graph["first"], graph["second"]]
    assert (
        repo.get_property_definition(graph["triggers_function"]).range_class_id == graph["process"]
    )
    (record,) = schema_change_records(service.get(proposal.id))
    assert (record.action, record.moved_to) == (SchemaChangeAction.RETARGET, None)


def test_a_retarget_can_move_its_relationships_to_a_type_they_fit(service, graph, repo, ontology):
    serves = add_fitting_type(ontology, graph)
    before = {(s, t, a) for _, s, t, a in ends(repo, graph["triggers_function"])}
    proposal = propose_update(service, graph, range_class_id=graph["process"])
    resolution = InUseResolution(strategy=MOVE, replacement_property_id=serves)

    op = apply(service, proposal, resolutions={the_op(proposal).id: resolution})

    assert op.status is OperationStatus.APPLIED, op.reason
    assert edges_of(repo, graph["triggers_function"]) == []
    assert {(s, t, a) for _, s, t, a in ends(repo, serves)} == before
    assert op.resolution.replacement_identifier == "businessevent_serves_businessfunction"
    assert op.type_change.replacement["id"] == serves
    (record,) = schema_change_records(service.get(proposal.id))
    assert (record.action, record.to, record.moved_to, record.swap) == (
        SchemaChangeAction.RETARGET,
        "businessevent_triggers_businessfunction",
        "businessevent_serves_businessfunction",
        False,
    )


def test_a_move_that_doesnt_fit_changes_nothing(service, graph, repo):
    before = ends(repo, graph["triggers_function"])
    proposal = propose_update(service, graph, domain_class_id=graph["function"])
    resolution = InUseResolution(strategy=MOVE, replacement_property_id=graph["triggers_process"])

    op = apply(service, proposal, resolutions={the_op(proposal).id: resolution})

    assert op.status is OperationStatus.FAILED
    assert op.reason.startswith("unresolvable")
    assert ends(repo, graph["triggers_function"]) == before
    assert (
        repo.get_property_definition(graph["triggers_function"]).domain_class_id == graph["event"]
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"identifier": "businessevent_starts_businessfunction"},
        {"domain_class_id": "function", "range_class_id": "event"},
    ],
    ids=["rename", "reverse"],
)
def test_only_a_retarget_takes_a_resolution(service, graph, repo, fields):
    fields = {name: graph.get(value, value) for name, value in fields.items()}
    before = ends(repo, graph["triggers_function"])
    proposal = propose_update(service, graph, **fields)

    op = apply(
        service,
        proposal,
        resolutions={the_op(proposal).id: InUseResolution(strategy=DELETE)},
    )

    assert op.status is OperationStatus.FAILED
    assert "only a retarget takes a resolution" in op.reason
    assert ends(repo, graph["triggers_function"]) == before


def test_a_delete_record_names_where_its_relationships_moved(service, graph, ontology):
    serves = add_fitting_type(ontology, graph)
    draft = OperationDraft(
        seq=1, op=T.DELETE, kind=K.PROPERTY, target_id=graph["triggers_function"]
    )
    proposal = service.propose(graph["taxonomy"], "Merge", [draft], ProposalSource.MCP)
    resolution = InUseResolution(strategy=MOVE, replacement_property_id=serves)
    apply(service, proposal, resolutions={the_op(proposal).id: resolution})

    (record,) = schema_change_records(service.get(proposal.id))
    assert (record.action, record.from_, record.to, record.swap) == (
        SchemaChangeAction.DELETE,
        "businessevent_triggers_businessfunction",
        "businessevent_serves_businessfunction",
        False,
    )
    assert record.to_json()["from"] == record.from_


def test_an_unused_delete_records_its_named_replacement_when_the_pair_matches(
    service, graph, ontology
):
    unused = unused_type(ontology, graph)
    drafts = [
        OperationDraft(
            seq=1,
            op=T.DELETE,
            kind=K.PROPERTY,
            target_id=unused,
            replacement=graph["triggers_function"],
        ),
        OperationDraft(
            seq=2,
            op=T.DELETE,
            kind=K.PROPERTY,
            target_id=graph["triggers_process"],
            replacement=graph["triggers_function"],
        ),
    ]
    proposal = service.propose(graph["taxonomy"], "Merge", drafts, ProposalSource.MCP)
    service.apply(proposal.id, [o.id for o in proposal.operations])

    same, different = schema_change_records(service.get(proposal.id))
    assert (same.from_, same.to) == (
        "businessevent_follows_businessfunction",
        "businessevent_triggers_businessfunction",
    )
    # BusinessEvent -> BusinessProcess against -> BusinessFunction: dropped.
    assert (different.from_, different.to) == ("businessevent_triggers_businessprocess", None)


def test_a_create_record_and_unapplied_operations(service, graph):
    drafts = [
        OperationDraft(
            seq=1,
            op=T.CREATE,
            kind=K.PROPERTY,
            fields={"identifier": "process_follows_event", "title": "follows"},
            probability=0.7,
        ),
        OperationDraft(
            seq=2,
            op=T.UPDATE,
            kind=K.PROPERTY,
            target_id=graph["triggers_function"],
            fields={"identifier": "never_applied"},
        ),
    ]
    proposal = service.propose(graph["taxonomy"], "Add", drafts, ProposalSource.MCP)
    service.apply(proposal.id, [the_op(proposal).id])

    (record,) = schema_change_records(service.get(proposal.id), key=identifier_key)
    assert (record.action, record.from_, record.to, record.p) == (
        SchemaChangeAction.CREATE,
        "process_follows_event",
        "process_follows_event",
        0.7,
    )


def test_a_reverted_proposal_has_no_records(service, graph):
    proposal = propose_update(service, graph, identifier="businessevent_starts_businessfunction")
    apply(service, proposal)
    reverted = service.get(proposal.id)
    reverted.status = ProposalStatus.REVERTED
    assert schema_change_records(reverted) == []


def test_an_edited_delete_that_retargets_takes_a_resolution(service, graph, repo):
    """A reviewer's edit turns a blocked delete into a retarget: it resolves as one."""
    proposal = propose_delete(service, graph)
    op_id = the_op(proposal).id

    op = apply(
        service,
        proposal,
        edits={op_id: {"range_class_id": graph["process"]}},
        resolutions={op_id: InUseResolution(strategy=DELETE)},
    )

    assert op.status is OperationStatus.APPLIED, op.reason
    assert op.applied_fields == {"range_class_id": graph["process"]}
    assert edges_of(repo, graph["triggers_function"]) == []
    assert (
        repo.get_property_definition(graph["triggers_function"]).range_class_id == graph["process"]
    )


def test_an_edited_delete_that_renames_takes_none(service, graph, repo):
    before = ends(repo, graph["triggers_function"])
    proposal = propose_delete(service, graph)
    op_id = the_op(proposal).id

    op = apply(service, proposal, edits={op_id: {"canonical_predicate": "starts"}})

    assert op.status is OperationStatus.APPLIED, op.reason
    assert ends(repo, graph["triggers_function"]) == before


def test_one_inspector_and_one_type_listing_serve_every_operation(
    service, graph, ontology, repo, monkeypatch
):
    """The detail view's in-use pass doesn't scale with operations x inspectors (#1411)."""

    step = ontology.create_individual(graph["process"], "Enrich Step")
    ontology.create_relationship(graph["changed"], step.id, graph["triggers_process"])
    targets = [graph["triggers_process"]]
    targets += [unused_type(ontology, graph, f"unused_{i}") for i in range(6)]
    drafts = [
        OperationDraft(
            seq=i + 1,
            op=T.UPDATE,
            kind=K.PROPERTY,
            target_id=target,
            fields={"canonical_predicate": f"p{i}"},
        )
        for i, target in enumerate(targets)
    ]
    drafts.append(
        OperationDraft(
            seq=len(drafts) + 1, op=T.DELETE, kind=K.PROPERTY, target_id=graph["triggers_function"]
        )
    )
    proposal = service.propose(graph["taxonomy"], "Renames", drafts, ProposalSource.MCP)
    inspectors, listings = [], []
    original_inspector, original_list = (
        proposal_service_module.InUseInspector,
        repo.list_property_definitions,
    )

    def counting_inspector(*args, **kwargs):
        inspectors.append(1)
        return original_inspector(*args, **kwargs)

    def counting_list(*args, **kwargs):
        listings.append(1)
        return original_list(*args, **kwargs)

    monkeypatch.setattr(proposal_service_module, "InUseInspector", counting_inspector)
    monkeypatch.setattr(repo, "list_property_definitions", counting_list)

    blockers, usage = service.in_use(proposal)

    assert len(blockers) == 1 and len(usage) == 1  # the delete; the in-use rename
    assert len(inspectors) == 1
    assert len(listings) == 1
    _, none = service.in_use(proposal, with_usage=False)
    assert none == {}


def test_type_usage_lists_the_relationships_a_rename_keeps(service, graph, ontology):
    unused = unused_type(ontology, graph)
    proposal = service.propose(
        graph["taxonomy"],
        "Renames",
        [
            OperationDraft(
                seq=1,
                op=T.UPDATE,
                kind=K.PROPERTY,
                target_id=graph["triggers_function"],
                fields={"canonical_predicate": "starts"},
            ),
            OperationDraft(
                seq=2,
                op=T.UPDATE,
                kind=K.PROPERTY,
                target_id=unused,
                fields={"canonical_predicate": "starts"},
            ),
            OperationDraft(
                seq=3,
                op=T.UPDATE,
                kind=K.PROPERTY,
                target_id=graph["triggers_process"],
                fields={"range_class_id": graph["function"]},
            ),
        ],
        ProposalSource.MCP,
    )

    usage = service.type_usage(proposal)

    assert list(usage) == [the_op(proposal, 1).id]  # not the unused type, nor a retarget
    assert [e.relationship_id for e in usage[the_op(proposal, 1).id].edges] == [
        graph["first"],
        graph["second"],
    ]
    assert service.in_use_blockers(proposal) == {}


# ------------------------------------- covered edges and edited-delete targets (#1438)


def rel_delete(seq, relationship_id):
    return OperationDraft(seq=seq, op=T.DELETE, kind=K.RELATIONSHIP, target_id=relationship_id)


def type_delete(seq, property_id):
    return OperationDraft(seq=seq, op=T.DELETE, kind=K.PROPERTY, target_id=property_id)


def propose(service, graph, *drafts):
    return service.propose(graph["taxonomy"], "Cleanup", list(drafts), ProposalSource.BUNDLE)


COVERED_REASON = (
    "unresolvable: relationships using the type are deleted by seq 1 of this proposal,"
    " not applied yet; apply or reject those first"
)


class TestCoveredRelationships:
    """A type operation whose type has some relationships the same proposal deletes."""

    def reviewed(self, service, proposal, seq=2):
        """The resolution a reviewer sends: the relationships the blockers listed."""
        blockers = service.in_use_blockers(proposal)[the_op(proposal, seq).id]
        return [e.relationship_id for e in blockers.edges]

    def test_applies_with_the_reviewed_set_once_the_relationship_delete_runs_first(
        self, service, graph, repo
    ):
        proposal = propose(
            service,
            graph,
            rel_delete(1, graph["first"]),
            type_delete(2, graph["triggers_function"]),
        )
        reviewed = self.reviewed(service, proposal)
        assert reviewed == [graph["second"]]

        op_ids = [o.id for o in proposal.operations]
        resolution = InUseResolution(strategy=DELETE, relationship_ids=reviewed)
        applied = service.apply(proposal.id, op_ids, resolutions={op_ids[1]: resolution})

        assert [o.status for o in applied.operations] == [OperationStatus.APPLIED] * 2
        assert [e.relationship_id for e in the_op(applied, 2).resolution.edges] == reviewed
        assert repo.get_property_definition(graph["triggers_function"]) is None

    def test_a_move_takes_only_the_reviewed_relationships(self, service, graph, repo, ontology):
        serves = add_fitting_type(ontology, graph)
        proposal = propose(
            service,
            graph,
            rel_delete(1, graph["first"]),
            type_delete(2, graph["triggers_function"]),
        )
        reviewed = self.reviewed(service, proposal)
        op_ids = [o.id for o in proposal.operations]
        move = InUseResolution(
            strategy=MOVE, replacement_property_id=serves, relationship_ids=reviewed
        )

        applied = service.apply(proposal.id, op_ids, resolutions={op_ids[1]: move})

        assert the_op(applied, 2).status is OperationStatus.APPLIED, the_op(applied, 2).reason
        moved = edges_of(repo, serves)
        assert [(r.source_id, r.target_id) for r in moved] == [
            (graph["synced"], graph["conflicts"])
        ]

    def test_waits_while_the_relationship_delete_is_unapplied(self, service, graph, repo):
        proposal = propose(
            service,
            graph,
            rel_delete(1, graph["first"]),
            type_delete(2, graph["triggers_function"]),
        )
        reviewed = self.reviewed(service, proposal)
        op_id = the_op(proposal, 2).id
        resolution = InUseResolution(strategy=DELETE, relationship_ids=reviewed)

        applied = service.apply(proposal.id, [op_id], resolutions={op_id: resolution})

        assert the_op(applied, 2).status is OperationStatus.FAILED
        assert the_op(applied, 2).reason == COVERED_REASON
        assert len(edges_of(repo, graph["triggers_function"])) == 2

        # Once the relationship delete applies, the same reviewed resolution goes through.
        service.apply(proposal.id, [the_op(proposal, 1).id])
        applied = service.apply(proposal.id, [op_id], resolutions={op_id: resolution})
        assert the_op(applied, 2).status is OperationStatus.APPLIED, the_op(applied, 2).reason

    def test_waits_when_the_relationship_delete_comes_later_in_the_same_apply(
        self, service, graph, repo
    ):
        proposal = propose(
            service,
            graph,
            type_delete(1, graph["triggers_function"]),
            rel_delete(2, graph["first"]),
        )
        reviewed = self.reviewed(service, proposal, seq=1)
        op_ids = [o.id for o in proposal.operations]
        resolution = InUseResolution(strategy=DELETE, relationship_ids=reviewed)

        applied = service.apply(proposal.id, op_ids, resolutions={op_ids[0]: resolution})

        assert the_op(applied, 1).reason == COVERED_REASON.replace("seq 1", "seq 2")
        assert the_op(applied, 2).status is OperationStatus.APPLIED
        assert repo.get_property_definition(graph["triggers_function"]) is not None

    def test_rejecting_the_relationship_delete_after_review_needs_another_review(
        self, service, graph, repo
    ):
        proposal = propose(
            service,
            graph,
            rel_delete(1, graph["first"]),
            type_delete(2, graph["triggers_function"]),
        )
        reviewed = self.reviewed(service, proposal)
        service.reject(proposal.id, [the_op(proposal, 1).id])
        op_id = the_op(proposal, 2).id
        resolution = InUseResolution(strategy=DELETE, relationship_ids=reviewed)

        applied = service.apply(proposal.id, [op_id], resolutions={op_id: resolution})

        assert "changed since reviewed: 2 now, 1 reviewed" in the_op(applied, 2).reason
        assert len(edges_of(repo, graph["triggers_function"])) == 2

    def test_a_delete_they_all_cover_says_why_it_waits(self, service, graph, repo):
        proposal = propose(
            service,
            graph,
            rel_delete(1, graph["first"]),
            rel_delete(2, graph["second"]),
            type_delete(3, graph["triggers_function"]),
        )
        assert service.in_use_blockers(proposal) == {}

        applied = service.apply(proposal.id, [the_op(proposal, 3).id])

        assert the_op(applied, 3).reason == COVERED_REASON.replace("seq 1", "seq 1, 2")
        assert repo.get_property_definition(graph["triggers_function"]) is not None

    def test_a_delete_without_a_resolution_says_the_others_need_one(self, service, graph):
        proposal = propose(
            service,
            graph,
            rel_delete(1, graph["first"]),
            type_delete(2, graph["triggers_function"]),
        )

        applied = service.apply(proposal.id, [the_op(proposal, 2).id])

        assert the_op(applied, 2).reason == (
            COVERED_REASON + "; the other 1 relationship(s) using it need a resolution too"
        )

    def test_a_reverse_leaves_covered_relationships_alone(self, service, graph, repo):
        """A reverse later in seq than the relationship delete would swap its ends first."""
        reverse = OperationDraft(
            seq=1,
            op=T.UPDATE,
            kind=K.PROPERTY,
            target_id=graph["triggers_function"],
            fields=reverse_fields(graph),
        )
        proposal = propose(service, graph, reverse, rel_delete(2, graph["first"]))
        usage = service.type_usage(proposal)[the_op(proposal, 1).id]
        assert [e.relationship_id for e in usage.edges] == [graph["second"]]
        op_ids = [o.id for o in proposal.operations]

        applied = service.apply(proposal.id, op_ids)

        assert the_op(applied, 1).reason == COVERED_REASON.replace("seq 1", "seq 2")
        assert the_op(applied, 2).status is OperationStatus.APPLIED, the_op(applied, 2).reason
        applied = service.apply(proposal.id, [op_ids[0]])
        assert the_op(applied, 1).status is OperationStatus.APPLIED, the_op(applied, 1).reason
        [left] = edges_of(repo, graph["triggers_function"])
        assert (left.id, left.source_id, left.target_id) == (
            graph["second"],
            graph["conflicts"],
            graph["synced"],
        )

    def test_a_retarget_uses_the_reviewed_set_too(self, service, graph, repo):
        retarget = OperationDraft(
            seq=2,
            op=T.UPDATE,
            kind=K.PROPERTY,
            target_id=graph["triggers_function"],
            fields={"range_class_id": graph["process"]},
        )
        proposal = propose(service, graph, rel_delete(1, graph["first"]), retarget)
        reviewed = self.reviewed(service, proposal)
        assert reviewed == [graph["second"]]
        op_ids = [o.id for o in proposal.operations]
        resolution = InUseResolution(strategy=DELETE, relationship_ids=reviewed)

        alone = service.apply(proposal.id, [op_ids[1]], resolutions={op_ids[1]: resolution})
        assert the_op(alone, 2).reason == COVERED_REASON

        applied = service.apply(proposal.id, op_ids, resolutions={op_ids[1]: resolution})
        assert the_op(applied, 2).status is OperationStatus.APPLIED, the_op(applied, 2).reason
        assert edges_of(repo, graph["triggers_function"]) == []
        assert (
            repo.get_property_definition(graph["triggers_function"]).range_class_id
            == graph["process"]
        )


class TestEditedDeleteTargets:
    """An edited delete applies as an update, so its type survives to take relationships."""

    def test_relationships_can_move_to_a_type_another_operation_edits_instead_of_deleting(
        self, service, graph, repo, ontology
    ):
        serves = add_fitting_type(ontology, graph)
        proposal = propose_delete(service, graph, type_delete(2, serves))
        op_ids = [o.id for o in proposal.operations]
        move = InUseResolution(strategy=MOVE, replacement_property_id=serves)

        applied = service.apply(
            proposal.id,
            op_ids,
            edits={op_ids[1]: {"canonical_predicate": "serves"}},
            resolutions={op_ids[0]: move},
        )

        assert [o.status for o in applied.operations] == [OperationStatus.APPLIED] * 2, [
            o.reason for o in applied.operations
        ]
        assert repo.get_property_definition(graph["triggers_function"]) is None
        assert repo.get_property_definition(serves).canonical_predicate == "serves"
        assert len(edges_of(repo, serves)) == 2

    def test_a_delete_applied_without_an_edit_still_refuses_the_move(
        self, service, graph, ontology
    ):
        serves = add_fitting_type(ontology, graph)
        proposal = propose_delete(service, graph, type_delete(2, serves))
        op_ids = [o.id for o in proposal.operations]
        move = InUseResolution(strategy=MOVE, replacement_property_id=serves)

        with pytest.raises(ValueError, match="which seq 2 deletes"):
            service.apply(proposal.id, op_ids, resolutions={op_ids[0]: move})
