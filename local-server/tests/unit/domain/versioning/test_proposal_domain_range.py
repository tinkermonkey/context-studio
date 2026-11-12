"""
Unit tests (#1574): a relationship create whose ends don't fit its type's
domain and range is flagged, never auto-applied, and fails when applied.
Fitting is inheritance-aware (a subclass's individual fits), and open where
the type or an end is untyped.

The graph: `near` runs Room -> Room; Kitchen is a subclass of Room; Place is
not. Den is a Room.
"""

import pytest

from domain.versioning.approval_policy import ApprovalPolicy, AutoApplyRule
from domain.versioning.proposal_service import DOMAIN_RANGE_MISMATCH, ProposalService
from domain.versioning.proposals import OperationStatus
from tests.fakes.fake_approval_policy_repository import FakeApprovalPolicyRepository
from tests.unit.domain.versioning.test_proposal_service import (  # noqa: F401 - fixtures
    K,
    T,
    by_seq,
    draft,
    graph,
    ontology,
    proposals,
    propose,
    publisher,
    repo,
    reverter,
    service,
)


@pytest.fixture()
def ends(ontology, graph):
    """A Kitchen (fits Room) and a Garden (a Place: doesn't)."""
    galley = ontology.create_individual(graph["kitchen"], "Galley")
    garden = ontology.create_individual(graph["place"], "Garden")
    return {"galley": galley.id, "garden": garden.id}


def near(seq, source, target, property_id):
    return draft(
        seq,
        T.CREATE,
        K.RELATIONSHIP,
        source_id=source,
        target_id=target,
        property_definition_id=property_id,
    )


def test_a_target_outside_the_range_is_flagged_and_fails_to_apply(service, graph, ends, repo):
    proposal = propose(service, graph, near(1, graph["den"], ends["garden"], graph["near"]))
    [operation] = proposal.operations

    assert service.domain_range_mismatches(proposal) == {operation.id: "target is Place, not Room"}

    applied = service.apply(proposal.id, [operation.id])

    [failed] = applied.operations
    assert failed.status is OperationStatus.FAILED
    assert failed.reason.startswith(f"{DOMAIN_RANGE_MISMATCH}: target is Place, not Room")
    assert repo.list_relationships(property_id=graph["near"], limit=None) == []
    # Still awaiting a decision, so still flagged.
    assert service.domain_range_mismatches(applied) == {failed.id: "target is Place, not Room"}


def test_a_source_outside_the_domain_is_flagged(service, graph, ends):
    proposal = propose(service, graph, near(1, ends["garden"], graph["den"], graph["near"]))

    assert list(service.domain_range_mismatches(proposal).values()) == ["source is Place, not Room"]


def test_an_individual_of_a_subclass_fits_and_applies(service, graph, ends, repo):
    proposal = propose(service, graph, near(1, graph["den"], ends["galley"], graph["near"]))

    assert service.domain_range_mismatches(proposal) == {}
    applied = service.apply(proposal.id, [proposal.operations[0].id])

    assert applied.operations[0].status is OperationStatus.APPLIED
    assert len(repo.list_relationships(property_id=graph["near"], limit=None)) == 1


def test_a_class_end_fits_as_its_own_class(service, graph):
    proposal = propose(service, graph, near(1, graph["kitchen"], graph["den"], graph["near"]))

    assert service.domain_range_mismatches(proposal) == {}


def test_an_untyped_type_accepts_any_ends(service, ontology, graph, ends):
    loose = ontology.create_property_definition("beside", "beside")
    proposal = propose(service, graph, near(1, graph["den"], ends["garden"], loose.id))

    assert service.domain_range_mismatches(proposal) == {}
    applied = service.apply(proposal.id, [proposal.operations[0].id])
    assert applied.operations[0].status is OperationStatus.APPLIED


def test_individuals_the_proposal_creates_are_judged_by_their_classes(service, graph):
    proposal = propose(
        service,
        graph,
        draft(1, T.CREATE, K.INDIVIDUAL, ref="lawn", class_ids=[graph["place"]], title="Lawn"),
        draft(
            2, T.CREATE, K.INDIVIDUAL, ref="pantry", class_ids=[graph["kitchen"]], title="Pantry"
        ),
        near(3, graph["den"], "$lawn", graph["near"]),
        near(4, graph["den"], "$pantry", graph["near"]),
    )
    ops = by_seq(proposal)

    assert service.domain_range_mismatches(proposal) == {ops[3].id: "target is Place, not Room"}

    applied = by_seq(service.apply(proposal.id, [o.id for o in proposal.operations]))
    assert applied[3].status is OperationStatus.FAILED
    assert applied[3].reason.startswith(DOMAIN_RANGE_MISMATCH)
    assert applied[4].status is OperationStatus.APPLIED


def test_a_type_the_proposal_retargets_is_not_flagged_and_applies_once_retargeted(
    service, graph, ends
):
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], range_class_id=graph["place"]),
        near(2, graph["den"], ends["garden"], graph["near"]),
    )

    assert service.domain_range_mismatches(proposal) == {}
    applied = by_seq(service.apply(proposal.id, [o.id for o in proposal.operations]))
    assert applied[2].status is OperationStatus.APPLIED


def test_the_approval_policy_never_auto_applies_a_mismatch(
    proposals, ontology, repo, reverter, graph, ends
):
    policies = FakeApprovalPolicyRepository()
    policies.save(ApprovalPolicy(graph["taxonomy"], (AutoApplyRule(op=T.CREATE),)))
    service = ProposalService(proposals, ontology, repo, reverter, approval_policies=policies)

    proposal = propose(
        service,
        graph,
        near(1, graph["den"], ends["garden"], graph["near"]),
        near(2, graph["den"], ends["galley"], graph["near"]),
    )
    ops = by_seq(proposal)

    assert ops[1].status is OperationStatus.PENDING
    assert ops[2].status is OperationStatus.APPLIED


def test_a_create_waiting_on_a_type_update_is_not_auto_applied_before_it(
    proposals, ontology, repo, reverter, graph, ends
):
    policies = FakeApprovalPolicyRepository()
    policies.save(ApprovalPolicy(graph["taxonomy"], (AutoApplyRule(op=T.CREATE),)))
    service = ProposalService(proposals, ontology, repo, reverter, approval_policies=policies)

    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], range_class_id=graph["place"]),
        near(2, graph["den"], ends["garden"], graph["near"]),
    )
    ops = by_seq(proposal)

    # Neither applied at once: the create waits for the retarget it needs.
    assert [ops[1].status, ops[2].status] == [OperationStatus.PENDING, OperationStatus.PENDING]
    assert service.auto_apply_operation_ids(proposal) == []
    applied = by_seq(service.apply(proposal.id, [ops[1].id, ops[2].id]))
    assert applied[2].status is OperationStatus.APPLIED


def test_a_reparent_in_the_proposal_defers_the_verdict_and_then_applies(service, ontology, graph):
    # A Nook is not a Room until the proposal moves it under Room.
    nook = ontology.create_class(graph["vocab"], "Nook")
    reading = ontology.create_individual(nook.id, "Reading nook")
    proposal = propose(
        service,
        graph,
        draft(1, T.MOVE, K.CLASS, nook.id, parent_class_id=graph["room"]),
        near(2, graph["den"], reading.id, graph["near"]),
    )
    ops = by_seq(proposal)

    assert service.domain_range_mismatches(proposal) == {}
    applied = by_seq(service.apply(proposal.id, [ops[1].id, ops[2].id]))
    assert applied[1].status is OperationStatus.APPLIED
    assert applied[2].status is OperationStatus.APPLIED


def test_a_reparent_elsewhere_in_the_graph_leaves_the_flag(service, ontology, graph, ends):
    shed = ontology.create_class(graph["vocab"], "Shed")
    proposal = propose(
        service,
        graph,
        draft(1, T.MOVE, K.CLASS, shed.id, parent_class_id=graph["room"]),
        near(2, graph["den"], ends["garden"], graph["near"]),
    )

    assert list(service.domain_range_mismatches(proposal).values()) == ["target is Place, not Room"]
