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
    ontology_repo = SQLiteOntologyRepository(session_factory=session_factory)
    change_repo = SQLiteChangeRepository(session_factory=session_factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(ontology_repo, FakeEmbeddingService(), publisher)
    service = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        ontology_repo,
        RevertService(change_repo=change_repo, ontology_repo=ontology_repo),
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
