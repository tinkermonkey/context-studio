"""
Integration test (#1354): a proposal applied in two goes on real SQLite tags
every change event with its id, and reverting it puts the graph back.

Foreign keys are enforced and the ChangeEventRecorder is wired for every
ontology event, as in app.py.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dataclasses
import tempfile
import time
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.services import OntologyService
from domain.versioning.exceptions import RevertConflictError
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationStatus, ProposalSource, ProposalStatus
from domain.versioning.proposals import OperationType as T
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

_VOLATILE = {"last_modified", "version", "embedding"}


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def parts(session_factory):
    """Wired as in app.py: both repositories share one transaction while a revert runs."""
    shared = SharedSessionFactory(session_factory)
    ontology_repo = SQLiteOntologyRepository(session_factory=shared)
    change_repo = SQLiteChangeRepository(session_factory=shared)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(ontology_repo, FakeEmbeddingService(), publisher)
    service = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        ontology_repo,
        RevertService(
            change_repo=change_repo,
            ontology_repo=ontology_repo,
            transaction_scope=SqliteTransactionScope(shared),
        ),
    )
    return ontology, ontology_repo, change_repo, service


def snap(entity):
    return {k: v for k, v in dataclasses.asdict(entity).items() if k not in _VOLATILE}


def test_apply_in_two_goes_then_revert_restores_the_graph(parts):
    ontology, repo, change_repo, service = parts
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room", description="A room")
    tool = ontology.create_class(vocab.id, "Tool")
    near = ontology.create_property_definition("near", "near", domain_class_id=room.id)
    den = ontology.create_individual(room.id, "Den")
    hall = ontology.create_individual(room.id, "Hall")
    link = ontology.create_relationship(den.id, hall.id, near.id)
    watched = {
        "room": (repo.get_class, room.id),
        "near": (repo.get_property_definition, near.id),
        "den": (repo.get_individual, den.id),
        "hall": (repo.get_individual, hall.id),
        "link": (repo.get_relationship, link.id),
    }
    before = {name: snap(get(i)) for name, (get, i) in watched.items()}

    proposal = service.propose(
        taxonomy.id,
        "Kits",
        [
            OperationDraft(1, T.UPDATE, K.CLASS, room.id, fields={"description": "Any room"}),
            OperationDraft(
                2,
                T.CREATE,
                K.CLASS,
                ref="kit",
                fields={"concept_scheme_id": vocab.id, "title": "Kit"},
            ),
            OperationDraft(
                3,
                T.CREATE,
                K.ATTRIBUTE,
                fields={
                    "class_id": "$kit",
                    "identifier": "kit_size",
                    "title": "Kit size",
                    "datatype": "integer",
                },
            ),
            OperationDraft(
                4,
                T.UPDATE,
                K.PROPERTY,
                near.id,
                fields={"range_class_id": room.id, "title": "is near"},
            ),
            OperationDraft(5, T.DELETE, K.INDIVIDUAL, hall.id),
            OperationDraft(
                6, T.UPDATE, K.INDIVIDUAL, den.id, fields={"class_ids": [room.id, "$kit"]}
            ),
            OperationDraft(7, T.UPDATE, K.CLASS, tool.id, fields={"title": "Implement"}),
        ],
        ProposalSource.MCP,
    )
    ops = {o.seq: o for o in proposal.operations}

    first = service.apply(proposal.id, [ops[s].id for s in (1, 2, 3)])
    assert [o.status for o in first.operations[:3]] == [OperationStatus.APPLIED] * 3
    second = service.apply(proposal.id, [ops[s].id for s in (4, 5, 6)])
    result = {o.seq: o for o in second.operations}
    assert all(result[s].status is OperationStatus.APPLIED for s in (4, 5, 6)), [
        result[s].reason for s in (4, 5, 6)
    ]
    assert second.status is ProposalStatus.OPEN  # seq 7 still pending

    kit_id = result[2].result_entity_id
    assert repo.get_individual(den.id).class_ids == [room.id, kit_id]
    assert repo.get_individual(hall.id) is None
    assert repo.get_relationship(link.id) is None  # cascaded with Hall
    events = change_repo.get_changes(batch_run_id=proposal.id, limit=None).events
    assert {e.batch_run_id for e in events} == {proposal.id}
    assert {e.entity_id for e in events} >= {room.id, kit_id, near.id, hall.id, den.id}

    summary = service.revert(proposal.id)
    assert summary.events_reverted == len(events)

    after = {name: snap(get(i)) for name, (get, i) in watched.items()}
    assert after == before
    assert repo.get_class(kit_id) is None
    assert repo.get_attribute_definition(result[3].result_entity_id) is None

    closed = service.get(proposal.id)
    assert closed.status is ProposalStatus.REVERTED
    seven = next(o for o in closed.operations if o.seq == 7)
    assert (seven.status, seven.reason) == (OperationStatus.REJECTED, "proposal reverted")
    assert repo.get_class(tool.id).title == "Tool"


# A revert may let an outside dependent through only when undoing the run's own
# update removes the reference BEFORE the entity it references is deleted.


def apply_in_order(service, proposal, *seqs):
    """Apply one op per call, a moment apart, so their change events are ordered by seq."""
    ops = {o.seq: o for o in proposal.operations}
    result = None
    for seq in seqs:
        time.sleep(0.01)
        result = service.apply(proposal.id, [ops[seq].id])
    time.sleep(0.01)
    return {o.seq: o for o in result.operations}


def test_revert_refused_when_an_outside_move_puts_a_class_in_a_scheme_the_run_made(parts):
    """Seq 1 moves X; seq 2 creates a scheme; then X is moved into it outside the proposal."""
    ontology, repo, _, service = parts
    tax = ontology.create_taxonomy(title="House")
    s0 = ontology.create_scheme(taxonomy_id=tax.id, title="S0")
    s1 = ontology.create_scheme(taxonomy_id=tax.id, title="S1")
    x = ontology.create_class(s0.id, "X")
    den = ontology.create_individual(x.id, "Den")
    proposal = service.propose(
        tax.id,
        "Reorg",
        [
            OperationDraft(
                1,
                T.MOVE,
                K.CLASS,
                x.id,
                fields={"concept_scheme_id": s1.id, "parent_class_id": None},
            ),
            OperationDraft(
                2, T.CREATE, K.SCHEME, ref="new", fields={"taxonomy_id": tax.id, "title": "New"}
            ),
        ],
        ProposalSource.USER,
    )
    ops = apply_in_order(service, proposal, 1, 2)
    ontology.move_class_to_scheme(x.id, ops[2].result_entity_id)

    with pytest.raises(RevertConflictError) as caught:
        service.revert(proposal.id)

    assert ("class", x.id, ops[2].result_entity_id) in caught.value.blocking
    assert repo.get_class(x.id).concept_scheme_id == ops[2].result_entity_id
    assert repo.get_individual(den.id).class_ids == [x.id]
    assert service.get(proposal.id).status is ProposalStatus.DONE


def test_revert_refused_when_an_outside_retype_uses_a_class_the_run_made(parts):
    """Seq 1 retypes Den A -> B; seq 2 creates C; outside, Den becomes only a C."""
    ontology, repo, _, service = parts
    tax = ontology.create_taxonomy(title="House")
    s0 = ontology.create_scheme(taxonomy_id=tax.id, title="S0")
    a = ontology.create_class(s0.id, "A")
    b = ontology.create_class(s0.id, "B")
    den = ontology.create_individual(a.id, "Den")
    proposal = service.propose(
        tax.id,
        "Retype",
        [
            OperationDraft(1, T.UPDATE, K.INDIVIDUAL, den.id, fields={"class_ids": [b.id]}),
            OperationDraft(
                2, T.CREATE, K.CLASS, ref="c", fields={"concept_scheme_id": s0.id, "title": "C"}
            ),
        ],
        ProposalSource.USER,
    )
    ops = apply_in_order(service, proposal, 1, 2)
    c_id = ops[2].result_entity_id
    ontology.add_class_to_individual(den.id, c_id)
    ontology.remove_class_from_individual(den.id, b.id)

    with pytest.raises(RevertConflictError):
        service.revert(proposal.id)

    assert repo.get_class(c_id) is not None
    assert repo.get_individual(den.id).class_ids == [c_id]
    assert service.get(proposal.id).status is ProposalStatus.DONE


def test_revert_refused_when_an_outside_move_puts_a_scheme_in_a_taxonomy_the_run_made(parts):
    """Seq 1 moves scheme S to T1; seq 2 creates taxonomy $t; outside, S moves into $t."""
    ontology, repo, _, service = parts
    t0 = ontology.create_taxonomy(title="House")
    t1 = ontology.create_taxonomy(title="Garden")
    scheme = ontology.create_scheme(taxonomy_id=t0.id, title="Plants")
    plant = ontology.create_class(scheme.id, "Plant")
    proposal = service.propose(
        t0.id,
        "Split",
        [
            OperationDraft(1, T.MOVE, K.SCHEME, scheme.id, fields={"taxonomy_id": t1.id}),
            OperationDraft(2, T.CREATE, K.TAXONOMY, ref="t", fields={"title": "Orchard"}),
        ],
        ProposalSource.USER,
    )
    ops = apply_in_order(service, proposal, 1, 2)
    ontology.update_concept_scheme(scheme.id, taxonomy_id=ops[2].result_entity_id)

    with pytest.raises(RevertConflictError):
        service.revert(proposal.id)

    assert repo.get_concept_scheme(scheme.id).taxonomy_id == ops[2].result_entity_id
    assert repo.get_class(plant.id) is not None


def test_new_taxonomy_plus_moving_a_non_empty_scheme_into_it_reverts(parts):
    """Undoing the scheme move takes its classes back too, so deleting the taxonomy is safe."""
    ontology, repo, _, service = parts
    tax = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=tax.id, title="Plants")
    plant = ontology.create_class(scheme.id, "Plant")
    proposal = service.propose(
        tax.id,
        "Split",
        [
            OperationDraft(1, T.CREATE, K.TAXONOMY, ref="t", fields={"title": "Garden"}),
            OperationDraft(2, T.MOVE, K.SCHEME, scheme.id, fields={"taxonomy_id": "$t"}),
        ],
        ProposalSource.USER,
    )
    ops = apply_in_order(service, proposal, 1, 2)
    assert repo.get_class(plant.id).taxonomy_id == ops[1].result_entity_id

    service.revert(proposal.id)

    assert repo.get_taxonomy(ops[1].result_entity_id) is None
    assert repo.get_concept_scheme(scheme.id).taxonomy_id == tax.id
    assert repo.get_class(plant.id).taxonomy_id == tax.id


# References the revert itself puts back must be gone before what they point at
# is deleted (review round 3).


def apply_seq(service, proposal, seq, force=False):
    time.sleep(0.01)
    op = {o.seq: o for o in service.get(proposal.id).operations}[seq]
    result = service.apply(proposal.id, [op.id], force_stale=[op.id] if force else ())
    time.sleep(0.01)
    return {o.seq: o for o in result.operations}


def graph_state(repo, change_repo):
    """Every ontology entity and relationship, and the number of change events."""
    entities, relationships = repo.get_all_entities_and_relationships()
    return (
        sorted(str(snap(entity)) for entity in entities),
        sorted(str(snap(rel)) for rel in relationships),
        sorted(str(snap(prop)) for prop in repo.list_property_definitions(limit=None)),
        change_repo.get_changes(limit=None).total,
    )


def test_a_restored_class_follows_its_scheme_not_its_snapshot(parts):
    """
    The run deleted X while an outside move had put X's scheme under the run's
    new taxonomy; the scheme has since moved back. X comes back under its
    scheme's taxonomy, so undoing the taxonomy's create can't take X with it.
    """
    ontology, repo, _, service = parts
    tax = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=tax.id, title="Rooms")
    x = ontology.create_class(scheme.id, "X")
    proposal = service.propose(
        tax.id,
        "Tidy",
        [
            OperationDraft(1, T.CREATE, K.TAXONOMY, ref="t", fields={"title": "Garden"}),
            OperationDraft(2, T.DELETE, K.CLASS, x.id),
        ],
        ProposalSource.USER,
    )
    garden = apply_seq(service, proposal, 1)[1].result_entity_id
    ontology.update_concept_scheme(scheme.id, taxonomy_id=garden)
    assert apply_seq(service, proposal, 2)[2].status is OperationStatus.APPLIED
    ontology.update_concept_scheme(scheme.id, taxonomy_id=tax.id)

    service.revert(proposal.id)

    restored = repo.get_class(x.id)
    assert restored is not None
    assert (restored.concept_scheme_id, restored.taxonomy_id) == (scheme.id, tax.id)
    assert repo.get_taxonomy(garden) is None


def test_revert_refused_when_it_would_put_back_a_reference_to_what_it_then_deletes(parts):
    """
    Seq 1 creates C; outside, Den becomes only a C; seq 2 (forced) retypes Den
    to B. Undoing seq 2 gives Den [C] back, and undoing seq 1 would then delete C.
    """
    ontology, repo, change_repo, service = parts
    tax = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=tax.id, title="Rooms")
    a = ontology.create_class(scheme.id, "A")
    b = ontology.create_class(scheme.id, "B")
    den = ontology.create_individual(a.id, "Den")
    proposal = service.propose(
        tax.id,
        "Retype",
        [
            OperationDraft(
                1, T.CREATE, K.CLASS, ref="c", fields={"concept_scheme_id": scheme.id, "title": "C"}
            ),
            OperationDraft(2, T.UPDATE, K.INDIVIDUAL, den.id, fields={"class_ids": [b.id]}),
        ],
        ProposalSource.USER,
    )
    c_id = apply_seq(service, proposal, 1)[1].result_entity_id
    ontology.add_class_to_individual(den.id, c_id)
    ontology.remove_class_from_individual(den.id, a.id)
    assert apply_seq(service, proposal, 2)[2].reason.startswith("target_changed")
    assert apply_seq(service, proposal, 2, force=True)[2].status is OperationStatus.APPLIED
    before = graph_state(repo, change_repo)

    with pytest.raises(RevertConflictError) as caught:
        service.revert(proposal.id)

    assert ("individual", den.id, c_id) in caught.value.blocking
    assert graph_state(repo, change_repo) == before
    assert service.get(proposal.id).status is ProposalStatus.DONE


# Atomic revert: a failure partway rolls every inverse back.


def test_a_revert_that_fails_partway_changes_nothing(parts, monkeypatch):
    ontology, repo, change_repo, service = parts
    tax = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=tax.id, title="Rooms")
    room = ontology.create_class(scheme.id, "Room", description="A room")
    hall = ontology.create_class(scheme.id, "Hall", description="A hall")
    proposal = service.propose(
        tax.id,
        "Edit",
        [
            OperationDraft(1, T.UPDATE, K.CLASS, room.id, fields={"description": "Any room"}),
            OperationDraft(2, T.UPDATE, K.CLASS, hall.id, fields={"description": "Any hall"}),
            OperationDraft(
                3, T.CREATE, K.CLASS, fields={"concept_scheme_id": scheme.id, "title": "Den"}
            ),
        ],
        ProposalSource.USER,
    )
    service.apply(proposal.id, [o.id for o in proposal.operations])
    before = graph_state(repo, change_repo)

    real_save = repo.save_class
    calls = []

    def fail_on_second(cls):
        calls.append(cls.id)
        if len(calls) == 2:
            raise RuntimeError("disk full")
        return real_save(cls)

    monkeypatch.setattr(repo, "save_class", fail_on_second)
    with pytest.raises(RuntimeError, match="disk full"):
        service.revert(proposal.id)

    assert len(calls) == 2  # the class create was undone and one update restored first
    assert graph_state(repo, change_repo) == before
    assert service.get(proposal.id).status is ProposalStatus.DONE


def test_the_execution_time_check_refuses_and_rolls_back_what_the_walk_missed(parts, monkeypatch):
    """
    With the predictive check switched off, deleting a scheme someone else has
    since put a class in is still refused, and the update undone before it is
    rolled back.
    """
    ontology, repo, change_repo, service = parts
    tax = ontology.create_taxonomy(title="House")
    s0 = ontology.create_scheme(taxonomy_id=tax.id, title="S0")
    keep = ontology.create_class(s0.id, "Keep", description="Before")
    proposal = service.propose(
        tax.id,
        "Reorg",
        [
            OperationDraft(
                1, T.CREATE, K.SCHEME, ref="new", fields={"taxonomy_id": tax.id, "title": "New"}
            ),
            OperationDraft(2, T.UPDATE, K.CLASS, keep.id, fields={"description": "After"}),
        ],
        ProposalSource.USER,
    )
    new_id = apply_seq(service, proposal, 1)[1].result_entity_id
    apply_seq(service, proposal, 2)
    outsider = ontology.create_class(new_id, "Outsider")
    before = graph_state(repo, change_repo)
    monkeypatch.setattr(RevertService, "_check_no_outside_dependents", lambda *args: None)

    with pytest.raises(RevertConflictError) as caught:
        service.revert(proposal.id)

    assert ("class", outsider.id, new_id) in caught.value.blocking
    assert graph_state(repo, change_repo) == before
    assert repo.get_class(keep.id).description == "After"
