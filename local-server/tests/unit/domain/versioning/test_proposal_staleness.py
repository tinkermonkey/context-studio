"""Unit tests for ProposalService.stale_operation_ids and the list pass-throughs (#1356)."""

import pytest

from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationType as T
from domain.versioning.proposals import ProposalSource, ProposalStatus
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository


class StubRevertService:
    def revert_with_summary(self, run_id: str, on_reverted=None) -> RevertResult:
        return RevertResult(run_id=run_id, events_reverted=0)


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def service(ontology):
    return ProposalService(
        FakeChangeProposalRepository(), ontology, ontology._repository, StubRevertService()
    )


@pytest.fixture()
def graph(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room", description="A room")
    den = ontology.create_individual(room.id, "Den")
    hall = ontology.create_individual(room.id, "Hall")
    return {
        "taxonomy": taxonomy.id,
        "vocab": vocab.id,
        "room": room.id,
        "den": den.id,
        "hall": hall.id,
    }


def _propose(service, graph):
    return service.propose(
        graph["taxonomy"],
        "Tidy",
        [
            OperationDraft(1, T.UPDATE, K.CLASS, graph["room"], fields={"description": "Any room"}),
            OperationDraft(2, T.DELETE, K.INDIVIDUAL, graph["den"]),
            OperationDraft(3, T.UPDATE, K.INDIVIDUAL, graph["hall"], fields={"title": "Hallway"}),
            OperationDraft(
                4, T.CREATE, K.CLASS, fields={"concept_scheme_id": graph["vocab"], "title": "Kit"}
            ),
        ],
        ProposalSource.USER,
    )


def test_nothing_is_stale_right_after_proposing(service, graph):
    proposal = _propose(service, graph)
    assert service.stale_operation_ids(proposal) == set()


def test_changed_and_missing_targets_are_stale(service, graph, ontology):
    proposal = _propose(service, graph)
    ops = {o.seq: o for o in proposal.operations}
    ontology.update_class(graph["room"], description="Edited meanwhile")
    ontology.delete_individual(graph["den"])
    ontology.update_individual(graph["hall"], description="Unrelated field")

    assert service.stale_operation_ids(proposal) == {ops[1].id, ops[2].id}


def test_decided_operations_are_never_stale(service, graph, ontology):
    proposal = _propose(service, graph)
    ops = {o.seq: o for o in proposal.operations}
    applied = service.apply(proposal.id, [ops[1].id])
    ontology.update_class(graph["room"], description="Edited after apply")
    rejected = service.reject(applied.id, [ops[2].id])
    ontology.delete_individual(graph["den"])

    assert service.stale_operation_ids(rejected) == set()


def test_failed_stale_operation_stays_stale(service, graph, ontology):
    proposal = _propose(service, graph)
    ops = {o.seq: o for o in proposal.operations}
    ontology.update_class(graph["room"], description="Edited meanwhile")
    failed = service.apply(proposal.id, [ops[1].id])

    assert service.stale_operation_ids(failed) == {ops[1].id}


def test_list_and_count_filter_through_the_repository(service, graph):
    proposal = _propose(service, graph)
    assert [p.id for p in service.list_proposals(taxonomy_id=graph["taxonomy"])] == [proposal.id]
    assert service.count_proposals(status=ProposalStatus.OPEN) == 1
    assert service.count_proposals(source=ProposalSource.MCP) == 0
    assert service.list_proposals(taxonomy_id="nope") == []
