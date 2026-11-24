"""
Integration tests (#1407): every reviewer or policy decision on a proposal
operation is recorded as gold on real SQLite; a revert supersedes them; the
backfill records the decisions made before, once.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.approval_policy_repo import SQLiteApprovalPolicyRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.entity_source_repo import SQLiteEntitySourceRepository
from adapters.persistence.sqlite.models import Base, ProposalDecisionRecord
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from domain.versioning.approval_policy import ApprovalPolicy, AutoApplyRule
from domain.versioning.bundle_import import SUPERSEDED_REASON
from domain.versioning.gold import DecisionFilter, DecisionKind
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationDraft, OperationKind as K
from domain.versioning.proposals import OperationStatus, ProposalSource, RejectionReason
from domain.versioning.proposals import OperationType as T
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def parts(session_factory):
    """Wired as in app.py, with an approval policy repository."""
    shared = SharedSessionFactory(session_factory)
    ontology_repo = SQLiteOntologyRepository(session_factory=shared)
    change_repo = SQLiteChangeRepository(session_factory=shared)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(ontology_repo, FakeEmbeddingService(), publisher)
    policies = SQLiteApprovalPolicyRepository(shared)
    proposals = SQLiteChangeProposalRepository(shared)
    service = ProposalService(
        proposals,
        ontology,
        ontology_repo,
        RevertService(
            change_repo=change_repo,
            ontology_repo=ontology_repo,
            transaction_scope=SqliteTransactionScope(shared),
        ),
        approval_policies=policies,
        transaction_scope=SqliteTransactionScope(shared),
    )
    return ontology, proposals, policies, service, session_factory


@pytest.fixture()
def house(parts):
    ontology = parts[0]
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room", description="A room")
    near = ontology.create_property_definition("near", "near", domain_class_id=room.id)
    return {"taxonomy": taxonomy.id, "vocab": vocab.id, "room": room.id, "near": near.id}


def propose(service, house, source=ProposalSource.MCP):
    return service.propose(
        house["taxonomy"],
        "Kits",
        [
            OperationDraft(
                1,
                T.CREATE,
                K.CLASS,
                fields={"concept_scheme_id": house["vocab"], "title": "Kit"},
                probability=0.9,
            ),
            OperationDraft(2, T.UPDATE, K.CLASS, house["room"], fields={"description": "Any"}),
            OperationDraft(3, T.UPDATE, K.PROPERTY, house["near"], fields={"title": "is near"}),
            OperationDraft(4, T.UPDATE, K.CLASS, house["room"], fields={"title": "Chamber"}),
        ],
        source,
    )


def gold(service, house, **filters):
    return service.list_decisions(DecisionFilter(taxonomy_id=house["taxonomy"], **filters))


def test_accepting_records_an_applied_decision(parts, house):
    service = parts[3]
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}
    before = datetime.now(timezone.utc)

    applied = service.apply(proposal.id, [ops[1].id])

    [decision] = gold(service, house)
    created = next(o for o in applied.operations if o.seq == 1)
    assert decision.decision is DecisionKind.APPLIED
    assert (decision.operation_id, decision.proposal_id) == (ops[1].id, proposal.id)
    assert (decision.taxonomy_id, decision.seq, decision.kind, decision.op) == (
        house["taxonomy"],
        1,
        K.CLASS,
        T.CREATE,
    )
    assert decision.decided_by == "user"
    assert before <= decision.decided_at <= datetime.now(timezone.utc)
    assert decision.proposed["fields"] == {"concept_scheme_id": house["vocab"], "title": "Kit"}
    assert decision.proposed["op"] == "create" and decision.proposed["scope"] == "additive"
    assert decision.applied_fields == decision.proposed["fields"]
    assert decision.result_entity_id == created.result_entity_id
    assert decision.probability == 0.9
    assert decision.model is None and decision.chosen_alternative is None
    assert decision.superseded_at is None and decision.reason is None


def test_editing_records_applied_with_edits_and_both_versions(parts, house):
    service = parts[3]
    proposal = propose(service, house)
    op = next(o for o in proposal.operations if o.seq == 3)

    service.apply(proposal.id, [op.id], edits={op.id: {"title": "next to"}})

    [decision] = gold(service, house)
    assert decision.decision is DecisionKind.APPLIED_WITH_EDITS
    assert decision.proposed["fields"] == {"title": "is near"}
    assert decision.proposed["base"] == {"title": "near"}  # as proposed, before the edit
    assert decision.applied_fields == {"title": "next to"}
    assert decision.result_entity_id == house["near"]


def test_a_chosen_alternative_lands_in_gold_with_the_edit(parts, house):
    service = parts[3]
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}
    alternative = {"predicate_for": "next_to", "triple": "Room next_to Room"}

    service.apply(
        proposal.id,
        [ops[3].id, ops[2].id],
        edits={ops[3].id: {"title": "next to"}},
        chosen_alternatives={ops[3].id: alternative},
    )

    decisions = {d.seq: d for d in gold(service, house)}
    assert decisions[3].decision is DecisionKind.APPLIED_WITH_EDITS
    assert decisions[3].chosen_alternative == alternative
    assert decisions[2].chosen_alternative is None
    # read back from SQLite as stored
    with parts[4]() as session:
        row = session.query(ProposalDecisionRecord).filter_by(operation_id=ops[3].id).one()
        assert row.chosen_alternative == alternative


def test_a_chosen_alternative_for_an_operation_not_applied_is_refused(parts, house):
    service = parts[3]
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}

    with pytest.raises(ValueError, match="Chosen alternatives"):
        service.apply(proposal.id, [ops[2].id], chosen_alternatives={ops[3].id: {"x": 1}})
    # an alternative records what an edit applies: it needs one, and isn't empty
    with pytest.raises(ValueError, match="needs the edit"):
        service.apply(proposal.id, [ops[3].id], chosen_alternatives={ops[3].id: {"x": 1}})
    with pytest.raises(ValueError, match="is empty"):
        service.apply(
            proposal.id,
            [ops[3].id],
            edits={ops[3].id: {"title": "next to"}},
            chosen_alternatives={ops[3].id: {}},
        )
    assert gold(service, house) == []


def test_rejecting_records_a_rejected_decision_with_its_note(parts, house):
    service = parts[3]
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}

    service.reject(proposal.id, [ops[2].id, ops[4].id], note="not now")

    decisions = gold(service, house)
    assert [d.seq for d in decisions] == [2, 4]
    assert all(d.decision is DecisionKind.REJECTED for d in decisions)
    assert all(d.reason == "not now" and d.applied_fields is None for d in decisions)
    assert all(d.result_entity_id is None and d.decided_by == "user" for d in decisions)


def test_a_failed_apply_records_nothing_until_it_applies(parts, house):
    ontology, _, _, service, _ = parts
    proposal = propose(service, house)
    op = next(o for o in proposal.operations if o.seq == 2)
    ontology.update_class(house["room"], description="Edited meanwhile")

    failed = service.apply(proposal.id, [op.id])
    assert failed.operations[1].status is OperationStatus.FAILED
    assert gold(service, house) == []

    service.apply(proposal.id, [op.id], force_stale=[op.id])
    assert [d.decision for d in gold(service, house)] == [DecisionKind.APPLIED]


def test_reverting_supersedes_the_applied_decisions_and_records_none_of_its_own(parts, house):
    service = parts[3]
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}
    service.apply(proposal.id, [ops[1].id, ops[2].id])
    service.reject(proposal.id, [ops[4].id])

    service.revert(proposal.id)

    # Superseded decisions are left out by default; the rejection still stands.
    [standing] = gold(service, house)
    assert (standing.seq, standing.decision, standing.superseded_at) == (
        4,
        DecisionKind.REJECTED,
        None,
    )
    decisions = gold(service, house, include_superseded=True)
    assert [d.seq for d in decisions] == [1, 2, 4]  # seq 3, rejected by the revert: none
    undone = [d for d in decisions if d.seq != 4]
    assert all(d.superseded_by == "user" for d in undone)
    assert all(d.superseded_at >= d.decided_at for d in undone)
    reverted = service.get(proposal.id).operations[2]
    assert (reverted.seq, reverted.status) == (3, OperationStatus.REJECTED)


def test_policy_auto_apply_is_decided_by_policy(parts, house):
    _, _, policies, service, _ = parts
    policies.save(
        ApprovalPolicy(
            taxonomy_id=house["taxonomy"],
            auto_apply=(AutoApplyRule(op=T.CREATE, kind=K.CLASS),),
        )
    )

    propose(service, house)

    [decision] = gold(service, house)
    assert (decision.seq, decision.decided_by) == (1, "policy")
    assert decision.decision is DecisionKind.APPLIED


def test_filters(parts, house):
    service = parts[3]
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}
    service.apply(proposal.id, [ops[1].id, ops[2].id])
    service.reject(proposal.id, [ops[4].id])
    now = datetime.now(timezone.utc)

    assert [d.seq for d in gold(service, house, kind=K.CLASS)] == [1, 2, 4]
    assert [d.seq for d in gold(service, house, op=T.UPDATE)] == [2, 4]
    assert [d.seq for d in gold(service, house, decision=DecisionKind.REJECTED)] == [4]
    assert gold(service, house, decided_by="policy") == []
    assert len(gold(service, house, decided_from=now - timedelta(minutes=1))) == 3
    assert gold(service, house, decided_from=now + timedelta(seconds=1)) == []
    assert gold(service, house, decided_to=now - timedelta(minutes=1)) == []
    assert service.count_decisions(DecisionFilter(taxonomy_id=house["taxonomy"])) == 3
    assert [d.seq for d in service.list_decisions(DecisionFilter(), limit=1, offset=1)] == [2]
    with pytest.raises(EntityNotFoundError):
        service.list_decisions(DecisionFilter(taxonomy_id="no-such-taxonomy"))


def test_backfill_records_earlier_decisions_once(parts, house):
    _, proposals, _, service, session_factory = parts
    done = propose(service, house)
    ops = {o.seq: o for o in done.operations}
    service.apply(done.id, [ops[1].id])
    service.reject(done.id, [ops[2].id], note="no")
    reverted = propose(service, house)
    service.apply(reverted.id, [reverted.operations[1].id])
    # A reviewer's own note that happens to start like a bundle's: still judged.
    service.reject(reverted.id, [reverted.operations[3].id], note="superseded by my plan")
    service.revert(reverted.id)  # rejects seqs 1 and 3 of it: nobody judged those
    # A newer bundle import rejecting an older one's operations: nobody judged those.
    bundle = propose(service, house, source=ProposalSource.BUNDLE)
    service.reject(
        bundle.id,
        [o.id for o in bundle.operations],
        note=SUPERSEDED_REASON.format("newer"),
        decided_by=None,
    )
    recorded = {d.operation_id: d for d in gold(service, house, include_superseded=True)}
    # As if decided before decisions were recorded.
    with session_factory() as session:
        session.query(ProposalDecisionRecord).delete()
        session.commit()

    assert proposals.backfill_decisions() == 4
    assert proposals.backfill_decisions() == 0

    decisions = {d.operation_id: d for d in gold(service, house, include_superseded=True)}
    assert set(decisions) == set(recorded)
    assert all(d.decided_by == "unknown" for d in decisions.values())
    applied = decisions[ops[1].id]
    assert applied.decision is DecisionKind.APPLIED
    # When its change was made (its first change event), not when proposed.
    assert applied.decided_at > done.created_at
    assert abs(applied.decided_at - recorded[ops[1].id].decided_at) < timedelta(seconds=1)
    rejected = decisions[ops[2].id]
    assert (rejected.decision, rejected.reason) == (DecisionKind.REJECTED, "no")
    assert rejected.decided_at == done.created_at  # no change event: when proposed
    undone = decisions[reverted.operations[1].id]
    assert undone.superseded_by == "unknown"
    assert undone.superseded_at >= undone.decided_at
    noted = decisions[reverted.operations[3].id]
    assert (noted.decision, noted.reason) == (DecisionKind.REJECTED, "superseded by my plan")
    assert noted.superseded_at is None  # a revert leaves rejections standing
    assert not {o.id for o in bundle.operations} & set(decisions)
    standing = {d.operation_id for d in gold(service, house)}
    assert standing == {ops[1].id, ops[2].id, reverted.operations[3].id}


def test_a_reason_code_and_review_time_round_trip(parts, house):
    """#1609: stored on SQLite and read back on the operation and its decision."""
    _, proposals, _, service, session_factory = parts
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}

    service.apply(proposal.id, [ops[1].id], review_ms={ops[1].id: 3100})
    service.reject(
        proposal.id,
        [ops[2].id],
        note="the text says nothing of it",
        reason_code=RejectionReason.NOT_IN_TEXT,
        review_ms={ops[2].id: 0},
    )

    decisions = {d.seq: d for d in gold(service, house)}
    assert (decisions[1].reason_code, decisions[1].review_ms) == (None, 3100)
    assert (decisions[2].reason_code, decisions[2].review_ms) == (RejectionReason.NOT_IN_TEXT, 0)
    stored = {o.seq: o for o in proposals.get(proposal.id).operations}
    assert stored[2].reason_code is RejectionReason.NOT_IN_TEXT
    assert stored[1].reason_code is None
    with session_factory() as session:
        row = session.query(ProposalDecisionRecord).filter_by(operation_id=ops[2].id).one()
        assert (row.reason_code, row.review_ms) == ("not_in_text", 0)


def test_an_edited_individual_create_records_both_classes(parts, house):
    """#1609: an individual create accepted with another class and title."""
    ontology, _, _, service, _ = parts
    hall = ontology.create_class(house["vocab"], "Hall", parent_class_id=house["room"])
    proposal = service.propose(
        house["taxonomy"],
        "Extracted",
        [
            OperationDraft(
                1, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [house["room"]], "title": "Foyer"}
            )
        ],
        ProposalSource.PIPELINE,
    )
    op = proposal.operations[0]

    applied = service.apply(
        proposal.id, [op.id], edits={op.id: {"class_ids": [hall.id], "title": "Entry hall"}}
    ).operations[0]

    [decision] = gold(service, house)
    assert decision.decision is DecisionKind.APPLIED_WITH_EDITS
    assert decision.proposed["fields"] == {"class_ids": [house["room"]], "title": "Foyer"}
    assert decision.applied_fields == {"class_ids": [hall.id], "title": "Entry hall"}
    individual = ontology.get_individual(applied.result_entity_id)
    assert individual.class_ids == [hall.id] and individual.title == "Entry hall"


def test_an_added_element_round_trips_as_added(parts, house):
    """#1610: the reviewer's addition is stored, flagged, on its operation and decision."""
    _, proposals, _, service, session_factory = parts
    proposal = service.propose(
        house["taxonomy"],
        "Extracted",
        [
            OperationDraft(
                1, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [house["room"]], "title": "Study"}
            )
        ],
        ProposalSource.PIPELINE,
        client_metadata={"source_id": "src-1", "pipeline": "individual_extraction"},
    )
    passage = {"source_id": "src-1", "start": 4, "end": 10, "quote": "Pantry"}

    added = service.add_individual(proposal.id, "Pantry", [house["room"]], passage, review_ms=700)

    stored = {o.seq: o for o in proposals.get(proposal.id).operations}
    assert stored[2].added_by_reviewer and not stored[1].added_by_reviewer
    assert stored[2].status is OperationStatus.APPLIED
    assert stored[2].evidence == [{**passage, "page": None}]
    [decision] = gold(service, house)
    assert (decision.seq, decision.added, decision.review_ms) == (2, True, 700)
    with session_factory() as session:
        row = session.query(ProposalDecisionRecord).filter_by(operation_id=stored[2].id).one()
        assert row.added is True
    assert added.operations[-1].id == stored[2].id
    # a seq the proposal has is refused
    with pytest.raises(ValueError, match="already has seq"):
        proposals.add_operations(proposal.id, [stored[1]])


def test_reverting_undoes_an_added_element_and_its_provenance(parts, house):
    """#1610: a revert removes the added individual and its passage; its decision is superseded."""
    session_factory = parts[4]
    # Wired as `parts` is, with entity sources, on one shared session factory
    shared = SharedSessionFactory(session_factory)
    ontology_repo = SQLiteOntologyRepository(session_factory=shared)
    change_repo = SQLiteChangeRepository(session_factory=shared)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(ontology_repo, FakeEmbeddingService(), publisher)
    entity_sources = SQLiteEntitySourceRepository(shared)
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
        entity_sources=entity_sources,
    )
    proposal = service.propose(
        house["taxonomy"],
        "Extracted",
        [
            OperationDraft(
                1, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [house["room"]], "title": "Study"}
            )
        ],
        ProposalSource.PIPELINE,
        client_metadata={"source_id": "src-1", "pipeline": "individual_extraction"},
    )
    passage = {"source_id": "src-1", "start": 4, "end": 10, "quote": "Pantry"}
    added = service.add_individual(proposal.id, "Pantry", [house["room"]], passage)
    individual_id = added.operations[-1].result_entity_id
    assert len(entity_sources.list_for_entity(individual_id)) == 1

    service.revert(proposal.id)

    with pytest.raises(EntityNotFoundError):
        ontology.get_individual(individual_id)
    assert entity_sources.list_for_entity(individual_id) == []
    [decision] = gold(service, house, include_superseded=True)
    assert decision.added and decision.superseded_at is not None


def test_review_annotations_round_trip(parts, house):
    """#1613: what a reviewer notes for gold is stored on the decision."""
    ontology, _, _, service, session_factory = parts
    hall = ontology.create_class(house["vocab"], "Hall", parent_class_id=house["room"])
    proposal = propose(service, house)
    ops = {o.seq: o for o in proposal.operations}
    note = {"tier": "core", "also_defensible": [hall.id]}

    service.apply(proposal.id, [ops[1].id], annotations={ops[1].id: note})
    service.reject(proposal.id, [ops[2].id], annotations={ops[2].id: {"tier": "supporting"}})

    decisions = {d.seq: d for d in gold(service, house)}
    assert decisions[1].annotations == note
    assert decisions[2].annotations == {"tier": "supporting"}
    with session_factory() as session:
        row = session.query(ProposalDecisionRecord).filter_by(operation_id=ops[1].id).one()
        assert row.annotations == note
