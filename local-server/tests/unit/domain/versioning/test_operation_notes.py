"""Unit tests for notes on proposal operations (#1514): kept with the operation, never applied."""

import pytest

from domain.ontology.services import OntologyService
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

T, K = OperationType, OperationKind
NOTES = "Maintainer: rooms are spaces, not furniture.\nSee the 2024 review."


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        raise AssertionError("not used")


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def proposals():
    return FakeChangeProposalRepository()


@pytest.fixture()
def service(proposals, ontology):
    return ProposalService(proposals, ontology, ontology._repository, StubRevertService())


@pytest.fixture()
def graph(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room", description="A room")
    return {"taxonomy": taxonomy.id, "vocab": vocab.id, "room": room.id}


def propose(service, graph, *drafts):
    return service.propose(graph["taxonomy"], "Test", list(drafts), ProposalSource.USER)


def update_room(graph, notes, fields=None):
    return OperationDraft(
        seq=1,
        op=T.UPDATE,
        kind=K.CLASS,
        target_id=graph["room"],
        fields=fields or {"description": "Any room"},
        notes=notes,
    )


class TestPropose:
    def test_notes_are_stored_as_given(self, service, graph):
        proposal = propose(service, graph, update_room(graph, NOTES))
        assert proposal.operations[0].notes == NOTES

    @pytest.mark.parametrize("blank", [None, "", "   ", "\n\t "])
    def test_blank_notes_are_none(self, service, graph, blank):
        proposal = propose(service, graph, update_room(graph, blank))
        assert proposal.operations[0].notes is None

    def test_notes_that_are_not_text_are_invalid(self, service, graph):
        with pytest.raises(ProposalValidationError) as exc:
            propose(service, graph, update_room(graph, ["a", "b"]))
        assert [(e.seq, e.code) for e in exc.value.errors] == [(1, "invalid")]
        assert "notes must be text" in exc.value.errors[0].message

    def test_notes_are_not_an_entity_field(self, service, graph):
        with pytest.raises(ProposalValidationError) as exc:
            propose(service, graph, update_room(graph, None, {"notes": NOTES}))
        assert [(e.seq, e.code) for e in exc.value.errors] == [(1, "unknown_field")]

    def test_notes_change_neither_scope_nor_base(self, service, graph):
        proposal = propose(service, graph, update_room(graph, NOTES))
        operation = proposal.operations[0]
        assert operation.scope is ChangeScope.EDITORIAL
        assert operation.base == {"description": "A room"}
        assert operation.fields == {"description": "Any room"}


class TestApply:
    def test_applying_leaves_the_entity_untouched_by_notes(self, service, graph, ontology):
        proposal = propose(service, graph, update_room(graph, NOTES))
        applied = service.apply(proposal.id, [proposal.operations[0].id])
        assert applied.operations[0].status is OperationStatus.APPLIED
        room = ontology.get_class(graph["room"])
        assert room.description == "Any room"
        assert not hasattr(room, "notes")
        assert NOTES not in repr(room)

    def test_a_create_with_notes_makes_the_entity_from_its_fields_only(
        self, service, graph, ontology
    ):
        create = OperationDraft(
            seq=1,
            op=T.CREATE,
            kind=K.CLASS,
            fields={"concept_scheme_id": graph["vocab"], "title": "Hall"},
            notes=NOTES,
        )
        proposal = propose(service, graph, create)
        applied = service.apply(proposal.id, [proposal.operations[0].id])
        hall = ontology.get_class(applied.operations[0].result_entity_id)
        assert hall.title == "Hall"
        assert hall.description is None
        assert NOTES not in repr(hall)

    def test_notes_are_not_stale_checked(self, service, graph):
        proposal = propose(service, graph, update_room(graph, NOTES))
        assert service.stale_operation_ids(proposal) == set()

    def test_the_decision_keeps_the_notes_as_proposed(self, service, graph, proposals):
        proposal = propose(service, graph, update_room(graph, NOTES))
        service.apply(proposal.id, [proposal.operations[0].id])
        [decision] = proposals.decisions
        assert decision.proposed["notes"] == NOTES
        assert "notes" not in decision.applied_fields

    def test_a_rejection_keeps_the_notes_as_proposed(self, service, graph, proposals):
        proposal = propose(service, graph, update_room(graph, NOTES))
        service.reject(proposal.id, [proposal.operations[0].id], note="No")
        [decision] = proposals.decisions
        assert decision.proposed["notes"] == NOTES
        assert decision.reason == "No"
