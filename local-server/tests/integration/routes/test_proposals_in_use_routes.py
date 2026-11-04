"""
Route tests for resolving relationship-type deletes that are in use (#1393),
over real SQLite wired as in app.py: every repository on one
SharedSessionFactory, and ProposalService and RevertService on its
transaction scope.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from adapters.web.proposals_routes import router
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import ProposalService
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder


@pytest.fixture()
def factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield SharedSessionFactory(sessionmaker(bind=engine))
        engine.dispose()


@pytest.fixture()
def ontology(factory):
    repo = SQLiteOntologyRepository(session_factory=factory)
    change_repo = SQLiteChangeRepository(session_factory=factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    service = OntologyService(repo, FakeEmbeddingService(), publisher)
    service.change_repo = change_repo
    return service


@pytest.fixture()
def client(factory, ontology):
    repo = ontology._repository
    scope = SqliteTransactionScope(factory)
    app = FastAPI()
    app.include_router(router)
    app.state.proposal_service = ProposalService(
        SQLiteChangeProposalRepository(factory),
        ontology,
        repo,
        RevertService(
            change_repo=ontology.change_repo, ontology_repo=repo, transaction_scope=scope
        ),
        transaction_scope=scope,
    )
    return TestClient(app)


@pytest.fixture()
def graph(ontology):
    """The DR case: two BusinessEvent -> BusinessFunction relationships use the type."""
    taxonomy = ontology.create_taxonomy(title="DR", identifier="dr_spec")
    business = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Business")
    event = ontology.create_class(business.id, "BusinessEvent")
    function = ontology.create_class(business.id, "BusinessFunction")
    process = ontology.create_class(business.id, "BusinessProcess")
    blocked = ontology.create_property_definition(
        "businessevent_triggers_businessfunction",
        "triggers function",
        domain_class_id=event.id,
        range_class_id=function.id,
    )
    ontology.create_property_definition(
        "businessevent_triggers_businessprocess",
        "triggers process",
        domain_class_id=event.id,
        range_class_id=process.id,
    )
    changed = ontology.create_individual(event.id, "Entity Changed Event")
    synced = ontology.create_individual(event.id, "Sync Completed Event")
    enrichment = ontology.create_individual(function.id, "Entity Enrichment")
    conflicts = ontology.create_individual(function.id, "Conflict Resolution")
    first = ontology.create_relationship(changed.id, enrichment.id, blocked.id)
    second = ontology.create_relationship(synced.id, conflicts.id, blocked.id)
    return {
        "taxonomy": taxonomy.id,
        "event": event.id,
        "function": function.id,
        "blocked": blocked.id,
        "first": first.id,
        "second": second.id,
        "ends": {(changed.id, enrichment.id), (synced.id, conflicts.id)},
    }


def _propose_delete(client, graph):
    response = client.post(
        "/api/proposals",
        json={
            "taxonomy_id": graph["taxonomy"],
            "title": "Business layer",
            "source": "bundle",
            "operations": [
                {"seq": 8, "op": "delete", "kind": "property", "target_id": graph["blocked"]}
            ],
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    return proposal, proposal["operations"][0]


def _apply(client, proposal, op, resolution=None):
    body = {"operation_ids": [op["id"]]}
    if resolution is not None:
        body["resolutions"] = {op["id"]: resolution}
    return client.post(f"/api/proposals/{proposal['id']}/apply", json=body)


def _serves(ontology, graph):
    return ontology.create_property_definition(
        "businessevent_serves_businessfunction",
        "serves",
        domain_class_id=graph["event"],
        range_class_id=graph["function"],
    ).id


def _ends(ontology, property_id):
    return {
        (r.source_id, r.target_id)
        for r in ontology.list_relationships(property_id=property_id, limit=None)
    }


class TestBlockers:
    def test_the_proposal_lists_what_uses_the_type_before_apply(self, client, graph):
        _, op = _propose_delete(client, graph)

        blockers = op["blockers"]
        assert [e["relationship_id"] for e in blockers["edges"]] == [
            graph["first"],
            graph["second"],
        ]
        first = blockers["edges"][0]
        assert first["source"]["title"] == "Entity Changed Event"
        assert first["source"]["class_titles"] == ["BusinessEvent"]
        assert first["target"]["class_titles"] == ["BusinessFunction"]
        assert blockers["replacements"] == []
        assert "none accepts BusinessFunction targets" in blockers["move_unavailable_reason"]
        assert op["resolution"] is None

    def test_a_fitting_type_is_offered(self, client, graph, ontology):
        serves = _serves(ontology, graph)
        _, op = _propose_delete(client, graph)

        assert op["blockers"]["replacements"] == [
            {
                "property_id": serves,
                "identifier": "businessevent_serves_businessfunction",
                "title": "serves",
            }
        ]
        assert op["blockers"]["move_unavailable_reason"] is None


class TestApply:
    def test_without_a_resolution_it_fails_as_in_use(self, client, graph):
        proposal, op = _propose_delete(client, graph)

        applied = _apply(client, proposal, op).json()["operations"][0]

        assert applied["status"] == "failed"
        assert "is in use by 2 relationship(s)" in applied["reason"]
        assert applied["blockers"] is not None

    def test_delete_them_too_then_revert_restores_the_type_and_its_relationships(
        self, client, graph, ontology
    ):
        proposal, op = _propose_delete(client, graph)

        applied = _apply(client, proposal, op, {"strategy": "delete"}).json()["operations"][0]

        assert applied["status"] == "applied", applied["reason"]
        assert applied["blockers"] is None
        resolution = applied["resolution"]
        assert resolution["strategy"] == "delete"
        assert [e["relationship_id"] for e in resolution["edges"]] == [
            graph["first"],
            graph["second"],
        ]
        assert ontology._repository.get_property_definition(graph["blocked"]) is None
        assert ontology._repository.get_relationship(graph["first"]) is None

        reverted = client.post(f"/api/proposals/{proposal['id']}/revert")
        assert reverted.status_code == 200, reverted.text
        assert reverted.json()["properties_deleted"] == 0
        restored = ontology._repository.get_property_definition(graph["blocked"])
        assert restored is not None
        assert _ends(ontology, graph["blocked"]) == graph["ends"]

    def test_move_then_revert_puts_the_relationships_back_on_the_type(
        self, client, graph, ontology
    ):
        serves = _serves(ontology, graph)
        proposal, op = _propose_delete(client, graph)

        response = _apply(
            client, proposal, op, {"strategy": "move", "replacement_property_id": serves}
        )

        applied = response.json()["operations"][0]
        assert applied["status"] == "applied", applied["reason"]
        assert applied["resolution"]["replacement_identifier"] == (
            "businessevent_serves_businessfunction"
        )
        assert all(e["moved_to_id"] for e in applied["resolution"]["edges"])
        assert _ends(ontology, serves) == graph["ends"]
        assert ontology._repository.get_property_definition(graph["blocked"]) is None

        reverted = client.post(f"/api/proposals/{proposal['id']}/revert")
        assert reverted.status_code == 200, reverted.text
        assert _ends(ontology, graph["blocked"]) == graph["ends"]
        assert _ends(ontology, serves) == set()

    def test_a_failing_step_rolls_back_in_the_database(self, client, graph, ontology, monkeypatch):
        proposal, op = _propose_delete(client, graph)
        original = ontology.delete_relationship
        calls = []

        def fail_on_second(relationship_id):
            calls.append(relationship_id)
            if len(calls) == 2:
                raise ValueError("disk full")
            original(relationship_id)

        monkeypatch.setattr(ontology, "delete_relationship", fail_on_second)
        applied = _apply(client, proposal, op, {"strategy": "delete"}).json()["operations"][0]

        assert applied["status"] == "failed"
        assert applied["reason"] == "error: disk full"
        assert applied["resolution"] is None
        # The first relationship's delete was rolled back with the rest.
        assert _ends(ontology, graph["blocked"]) == graph["ends"]
        events = ontology.change_repo.get_changes(batch_run_id=proposal["id"], limit=None)
        assert list(events.events) == []

    def test_a_move_without_a_replacement_is_422(self, client, graph):
        proposal, op = _propose_delete(client, graph)

        response = _apply(client, proposal, op, {"strategy": "move"})

        assert response.status_code == 422
        assert "needs replacement_property_id" in response.json()["detail"]


class TestDecisions:
    def test_the_export_carries_the_resolution_and_the_affected_relationships(self, client, graph):
        proposal, op = _propose_delete(client, graph)
        _apply(client, proposal, op, {"strategy": "delete"})

        decision = client.get(f"/api/proposals/{proposal['id']}/decisions").json()[0]

        assert decision["status"] == "applied"
        assert decision["resolution"]["strategy"] == "delete"
        assert [e["source_title"] for e in decision["resolution"]["edges"]] == [
            "Entity Changed Event",
            "Sync Completed Event",
        ]

    def test_a_kept_type_is_a_rejection_with_its_reason(self, client, graph):
        proposal, op = _propose_delete(client, graph)
        client.post(
            f"/api/proposals/{proposal['id']}/reject",
            json={"operation_ids": [op["id"]], "note": "Still used by two events"},
        )

        decision = client.get(f"/api/proposals/{proposal['id']}/decisions").json()[0]

        assert decision["status"] == "rejected"
        assert decision["reason"] == "Still used by two events"
        assert "resolution" not in decision
