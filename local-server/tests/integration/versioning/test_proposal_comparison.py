"""
Integration tests (#1615): deciding two pipelines' copies of an element once,
on real SQLite: what the decisions record, and how a revert sees the copies.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.entity_source_repo import SQLiteEntitySourceRepository
from adapters.persistence.sqlite.models import Base, ProposalDecisionRecord
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from domain.pipelines.proposal_comparison import (
    PairDecision,
    ProposalComparisonService,
    Verdict,
)
from domain.versioning.exceptions import RevertConflictError
from domain.versioning.gold import DecisionFilter
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationStatus, ProposalSource, RejectionReason
from domain.versioning.proposals import OperationType as T
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

SOURCE = "src-1"


@pytest.fixture()
def parts():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        shared = SharedSessionFactory(session_factory)
        ontology_repo = SQLiteOntologyRepository(session_factory=shared)
        change_repo = SQLiteChangeRepository(session_factory=shared)
        publisher = InProcessEventPublisher()
        wire_change_recorder(publisher, change_repo)
        ontology = OntologyService(ontology_repo, FakeEmbeddingService(), publisher)
        service = ProposalService(
            SQLiteChangeProposalRepository(shared),
            ontology,
            ontology_repo,
            RevertService(
                change_repo=change_repo,
                ontology_repo=ontology_repo,
                transaction_scope=SqliteTransactionScope(shared),
            ),
            transaction_scope=SqliteTransactionScope(shared),
            entity_sources=SQLiteEntitySourceRepository(shared),
        )
        yield ontology, service, ProposalComparisonService(service, ontology_repo), session_factory
        engine.dispose()


@pytest.fixture()
def house(parts):
    ontology = parts[0]
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room")
    hall = ontology.create_class(vocab.id, "Hall", parent_class_id=room.id)
    near = ontology.create_property_definition(
        "near", "near", domain_class_id=room.id, range_class_id=room.id
    )
    den = ontology.create_individual(room.id, "Den")
    return {
        "taxonomy": taxonomy.id,
        "room": room.id,
        "hall": hall.id,
        "near": near.id,
        "den": den.id,
    }


def extraction(service, house, class_id, implementation):
    passage = {"source_id": SOURCE, "page": 1, "start": 0, "end": 5, "quote": "Study"}
    return service.propose(
        house["taxonomy"],
        implementation,
        [
            OperationDraft(
                1,
                T.CREATE,
                K.INDIVIDUAL,
                ref="study",
                fields={"title": "Study", "class_ids": [class_id]},
                evidence=[passage],
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": "$study",
                    "target_id": house["den"],
                    "property_definition_id": house["near"],
                },
            ),
        ],
        ProposalSource.PIPELINE,
        client_metadata={"source_id": SOURCE, "pipeline": "individual_extraction"},
    )


def test_both_copies_record_the_comparison_and_the_duplicate_its_individual(parts, house):
    _, service, comparisons, session_factory = parts
    a = extraction(service, house, house["room"], "single_call")
    b = extraction(service, house, house["hall"], "find_then_type")

    comparisons.decide(
        a.id,
        b.id,
        PairDecision(
            Verdict.B_CLASS,
            a_operation_id=a.operations[0].id,
            b_operation_id=b.operations[0].id,
            review_ms=1500,
        ),
    )

    landed = service.get(b.id).operations[0]
    closed = service.get(a.id).operations[0]
    assert landed.status is OperationStatus.APPLIED
    assert (closed.status, closed.reason_code, closed.result_entity_id) == (
        OperationStatus.REJECTED,
        RejectionReason.DUPLICATE,
        landed.result_entity_id,
    )
    decisions = {
        d.operation_id: d
        for d in service.list_decisions(DecisionFilter(taxonomy_id=house["taxonomy"]))
    }
    assert decisions[landed.id].comparison["verdict"] == "kept"
    assert decisions[landed.id].review_ms == 1500
    assert decisions[closed.id].comparison == {
        "with_proposal_id": b.id,
        "with_operation_id": landed.id,
        "verdict": "class_changed",
        "sample": decisions[closed.id].comparison["sample"],
        "bulk": None,
    }
    assert decisions[closed.id].result_entity_id == landed.result_entity_id
    with session_factory() as session:
        row = session.query(ProposalDecisionRecord).filter_by(operation_id=closed.id).one()
        assert row.comparison["verdict"] == "class_changed"


def test_reverting_the_landed_copy_conflicts_with_the_others_relationship(parts, house):
    """A's individual is used by B's relationship (its $ref followed the duplicate)."""
    _, service, comparisons, _ = parts
    a = extraction(service, house, house["room"], "single_call")
    b = extraction(service, house, house["room"], "find_then_type")
    comparisons.decide(
        a.id,
        b.id,
        PairDecision(
            Verdict.KEEP, a_operation_id=a.operations[0].id, b_operation_id=b.operations[0].id
        ),
    )
    relationship = service.apply(b.id, [b.operations[1].id]).operations[1]
    assert relationship.status is OperationStatus.APPLIED

    with pytest.raises(RevertConflictError):
        service.revert(a.id)

    assert service.get(a.id).operations[0].status is OperationStatus.APPLIED


def test_reverting_the_landed_copy_reopens_the_other_and_its_relationship_resolves_again(
    parts, house
):
    ontology, service, comparisons, _ = parts
    a = extraction(service, house, house["room"], "single_call")
    b = extraction(service, house, house["room"], "find_then_type")
    comparisons.decide(
        a.id,
        b.id,
        PairDecision(
            Verdict.KEEP, a_operation_id=a.operations[0].id, b_operation_id=b.operations[0].id
        ),
    )
    landed = service.get(a.id).operations[0].result_entity_id

    service.revert(a.id)

    reopened = service.get(b.id).operations[0]
    assert reopened.status is OperationStatus.PENDING and reopened.result_entity_id is None
    with pytest.raises(EntityNotFoundError):
        ontology.get_individual(landed)
    decisions = {
        d.operation_id: d
        for d in service.list_decisions(
            DecisionFilter(taxonomy_id=house["taxonomy"], include_superseded=True)
        )
    }
    assert decisions[reopened.id].superseded_at is not None
    assert reopened.id not in {
        d.operation_id
        for d in service.list_decisions(DecisionFilter(taxonomy_id=house["taxonomy"]))
    }

    applied = service.apply(b.id, [reopened.id, b.operations[1].id]).operations
    assert [o.status for o in applied] == [OperationStatus.APPLIED, OperationStatus.APPLIED]
