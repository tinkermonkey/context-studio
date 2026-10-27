"""
Integration tests for proposal storage (#1353): the SQLite repository and the
in-memory fake behave the same, and a proposal is a batch run that change
events can be tagged with.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import (
    Base,
    BatchRun,
    ChangeEvent,
    ChangeProposalRun,
    ProposalOperation,
)
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture(params=["sqlite", "fake"])
def repo(request, session_factory):
    if request.param == "sqlite":
        return SQLiteChangeProposalRepository(session_factory)
    return FakeChangeProposalRepository()


def _proposal(id="p1", taxonomy_id="t1", source=ProposalSource.MCP, created_at=NOW):
    return ChangeProposal(
        id=id,
        taxonomy_id=taxonomy_id,
        title="Add Furniture",
        rationale="2c decided furniture is a resource subkind.",
        source=source,
        source_detail="claude-code",
        created_at=created_at,
        operations=[
            ProposedOperation(
                seq=1,
                op=OperationType.CREATE,
                kind=OperationKind.INDIVIDUAL,
                ref="credenza",
                fields={"title": "Credenza", "class_ids": ["$furniture"]},
                evidence=[{"quote": "the credenza", "url": None, "entity_id": None}],
                probability=0.8,
                scope=ChangeScope.ADDITIVE,
            ),
            ProposedOperation(
                seq=0,
                op=OperationType.CREATE,
                kind=OperationKind.CLASS,
                ref="furniture",
                fields={"title": "Furniture", "identifier": "house_resource_furniture"},
                scope=ChangeScope.ADDITIVE,
            ),
            ProposedOperation(
                seq=2,
                op=OperationType.UPDATE,
                kind=OperationKind.CLASS,
                target_id="class-room",
                fields={"description": "A room on a floor."},
                base={"description": "A room."},
                scope=ChangeScope.EDITORIAL,
            ),
        ],
    )


def test_round_trip_keeps_every_field_in_seq_order(repo):
    repo.create(_proposal())

    stored = repo.get("p1")

    assert stored.title == "Add Furniture" and stored.source is ProposalSource.MCP
    assert stored.source_detail == "claude-code"
    assert stored.created_at == NOW
    assert stored.status is ProposalStatus.OPEN
    assert [o.seq for o in stored.operations] == [0, 1, 2]
    credenza = stored.operations[1]
    assert credenza.fields == {"title": "Credenza", "class_ids": ["$furniture"]}
    assert credenza.evidence == [{"quote": "the credenza", "url": None, "entity_id": None}]
    assert credenza.probability == 0.8 and credenza.ref == "credenza"
    assert stored.operations[2].base == {"description": "A room."}
    assert stored.operations[2].scope is ChangeScope.EDITORIAL


def test_get_unknown_is_none(repo):
    assert repo.get("missing") is None


def test_list_filters_and_orders_newest_first(repo):
    repo.create(_proposal("old", created_at=NOW - timedelta(hours=1)))
    repo.create(_proposal("new", created_at=NOW))
    repo.create(_proposal("chat", source=ProposalSource.CHAT))
    repo.create(_proposal("other", taxonomy_id="t2"))
    repo.set_status("old", ProposalStatus.DONE)

    assert [p.id for p in repo.list_proposals(taxonomy_id="t1", source=ProposalSource.MCP)] == [
        "new",
        "old",
    ]
    assert [p.id for p in repo.list_proposals(status=ProposalStatus.DONE)] == ["old"]
    assert repo.count_proposals(taxonomy_id="t1") == 3
    assert repo.count_proposals(source=ProposalSource.CHAT) == 1
    assert len(repo.list_proposals(limit=2)) == 2


def test_ties_on_created_at_order_by_id_descending(repo):
    for proposal_id in ("a", "b", "c"):
        repo.create(_proposal(proposal_id))

    assert [p.id for p in repo.list_proposals()] == ["c", "b", "a"]


def test_created_at_with_an_offset_keeps_its_instant(repo):
    pacific = timezone(timedelta(hours=-7))
    repo.create(_proposal(created_at=datetime(2026, 10, 26, 5, tzinfo=pacific)))

    assert repo.get("p1").created_at == datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def test_creating_an_existing_proposal_is_rejected(repo):
    repo.create(_proposal())

    with pytest.raises(ValueError, match="already exists"):
        repo.create(_proposal())


def test_save_operations_on_an_unknown_proposal_is_rejected(repo):
    with pytest.raises(ValueError, match="No proposal"):
        repo.save_operations("missing", [])


def test_save_operations_records_outcomes(repo):
    created = repo.create(_proposal())
    furniture, credenza, _ = created.operations
    furniture.status, furniture.result_entity_id = OperationStatus.APPLIED, "class-furniture"
    credenza.status, credenza.reason = OperationStatus.FAILED, "unresolved_ref"

    repo.save_operations("p1", [furniture, credenza])

    stored = repo.get("p1").operations
    assert (stored[0].status, stored[0].result_entity_id) == (
        OperationStatus.APPLIED,
        "class-furniture",
    )
    assert (stored[1].status, stored[1].reason) == (OperationStatus.FAILED, "unresolved_ref")
    assert stored[2].status is OperationStatus.PENDING


def test_save_operations_rejects_unknown_operations(repo):
    repo.create(_proposal())
    stranger = ProposedOperation(
        seq=9, op=OperationType.DELETE, kind=OperationKind.CLASS, target_id="c9"
    )

    with pytest.raises(ValueError, match="no operations"):
        repo.save_operations("p1", [stranger])


def test_a_proposal_is_a_batch_run_change_events_can_reference(session_factory):
    repo = SQLiteChangeProposalRepository(session_factory)
    repo.create(_proposal())

    with session_factory() as session:
        run = session.get(BatchRun, "p1")
        assert isinstance(run, ChangeProposalRun) and run.run_type == "proposal"
        session.add(
            ChangeEvent(
                id="e1",
                entity_id="class-furniture",
                entity_type="class",
                operation="create",
                new_state={},
                batch_run_id="p1",
            )
        )
        session.commit()
        assert session.query(ChangeEvent).filter_by(batch_run_id="p1").count() == 1


def test_deleting_the_run_deletes_the_proposal_and_its_operations(session_factory):
    repo = SQLiteChangeProposalRepository(session_factory)
    repo.create(_proposal())

    with session_factory() as session:
        session.delete(session.get(BatchRun, "p1"))
        session.commit()
        assert session.query(ProposalOperation).count() == 0
    assert repo.get("p1") is None
