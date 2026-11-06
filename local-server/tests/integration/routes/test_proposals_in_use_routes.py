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
            "operations": [
                {"seq": 8, "op": "delete", "kind": "property", "target_id": graph["blocked"]}
            ],
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    return proposal, proposal["operations"][0]


def _apply(client, proposal, op, resolution=None):
    """Apply one op; a resolution names the relationships its blockers listed, as the UI does."""
    body = {"operation_ids": [op["id"]]}
    if resolution is not None:
        seen = [e["relationship_id"] for e in (op.get("blockers") or {}).get("edges", [])]
        body["resolutions"] = {op["id"]: {"relationship_ids": seen, **resolution}}
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

    def test_untyped_generic_types_are_not_offered_for_a_dr_type(self, client, graph, ontology):
        """The real DR case: generic types outside dr_spec fit anything but aren't offered."""
        for identifier in ("causes", "complements", "uses", "variant_of"):
            ontology.create_property_definition(identifier, identifier)
        _, op = _propose_delete(client, graph)

        assert op["blockers"]["replacements"] == []
        assert op["blockers"]["move_unavailable_reason"] == (
            "1 type accepts BusinessEvent sources (businessevent_triggers_businessprocess), "
            "but none accepts BusinessFunction targets"
        )

    def test_a_fitting_type_is_offered(self, client, graph, ontology):
        serves = _serves(ontology, graph)
        _, op = _propose_delete(client, graph)

        assert op["blockers"]["replacements"] == [
            {
                "property_id": serves,
                "identifier": "businessevent_serves_businessfunction",
                "title": "serves",
                "reversed": False,
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

    def test_an_edited_delete_resolved_as_a_retarget_then_revert_restores_both(
        self, client, graph, ontology
    ):
        """A reviewer's picks turn a blocked delete into a retarget (#1411)."""
        proposal, op = _propose_delete(client, graph)
        process = ontology._repository.get_property_definition(graph["blocked"])
        process_id = next(
            p.range_class_id
            for p in ontology._repository.list_property_definitions(limit=None)
            if p.identifier == "businessevent_triggers_businessprocess"
        )
        seen = [e["relationship_id"] for e in op["blockers"]["edges"]]

        response = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={
                "operation_ids": [op["id"]],
                "edits": {op["id"]: {"range_class_id": process_id}},
                "resolutions": {op["id"]: {"strategy": "delete", "relationship_ids": seen}},
                "chosen_alternatives": {op["id"]: {"target_for": "BusinessProcess"}},
            },
        )

        applied = response.json()["operations"][0]
        assert applied["status"] == "applied", applied["reason"]
        assert applied["applied_fields"] == {"range_class_id": process_id}
        assert applied["resolution"]["strategy"] == "delete"
        retargeted = ontology._repository.get_property_definition(graph["blocked"])
        assert retargeted.range_class_id == process_id
        assert _ends(ontology, graph["blocked"]) == set()

        reverted = client.post(f"/api/proposals/{proposal['id']}/revert")
        assert reverted.status_code == 200, reverted.text
        restored = ontology._repository.get_property_definition(graph["blocked"])
        assert restored.range_class_id == process.range_class_id == graph["function"]
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

    def test_a_reversed_move_swaps_the_ends_then_revert_restores_the_originals(
        self, client, graph, ontology
    ):
        """#1412: a replacement with the pair reversed takes the relationships the other way."""
        triggered_by = ontology.create_property_definition(
            "businessfunction_triggered_by_businessevent",
            "triggered by",
            domain_class_id=graph["function"],
            range_class_id=graph["event"],
        ).id
        proposal, op = _propose_delete(client, graph)
        assert op["blockers"]["replacements"] == [
            {
                "property_id": triggered_by,
                "identifier": "businessfunction_triggered_by_businessevent",
                "title": "triggered by",
                "reversed": True,
            }
        ]

        response = _apply(
            client, proposal, op, {"strategy": "move", "replacement_property_id": triggered_by}
        )

        applied = response.json()["operations"][0]
        assert applied["status"] == "applied", applied["reason"]
        assert applied["resolution"]["reversed"] is True
        swapped = {(target, source) for source, target in graph["ends"]}
        assert _ends(ontology, triggered_by) == swapped
        assert ontology._repository.get_property_definition(graph["blocked"]) is None

        reverted = client.post(f"/api/proposals/{proposal['id']}/revert")
        assert reverted.status_code == 200, reverted.text
        assert _ends(ontology, graph["blocked"]) == graph["ends"]
        assert {
            r.id for r in ontology.list_relationships(property_id=graph["blocked"], limit=None)
        } == {graph["first"], graph["second"]}
        assert _ends(ontology, triggered_by) == set()

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


class TestReviewFindings:
    def test_a_bundle_shaped_proposal_deleting_the_relationships_first_isnt_blocked(
        self, client, graph, ontology
    ):
        response = client.post(
            "/api/proposals",
            json={
                "taxonomy_id": graph["taxonomy"],
                "title": "Bundle",
                "operations": [
                    {"seq": 1, "op": "delete", "kind": "relationship", "target_id": graph["first"]},
                    {
                        "seq": 2,
                        "op": "delete",
                        "kind": "relationship",
                        "target_id": graph["second"],
                    },
                    {"seq": 3, "op": "delete", "kind": "property", "target_id": graph["blocked"]},
                ],
            },
        )
        proposal = response.json()
        assert [o["blockers"] for o in proposal["operations"]] == [None, None, None]

        applied = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={"operation_ids": [o["id"] for o in proposal["operations"]]},
        ).json()
        assert [o["status"] for o in applied["operations"]] == ["applied"] * 3
        assert ontology._repository.get_property_definition(graph["blocked"]) is None

    def test_resolution_ids_are_required(self, client, graph):
        proposal, op = _propose_delete(client, graph)

        response = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={"operation_ids": [op["id"]], "resolutions": {op["id"]: {"strategy": "delete"}}},
        )

        assert response.status_code == 422

    def test_a_relationship_added_since_review_fails_the_resolution(self, client, graph, ontology):
        proposal, op = _propose_delete(client, graph)
        extra = ontology.create_individual(graph["function"], "Late Function")
        changed = next(e["source"]["id"] for e in op["blockers"]["edges"])
        ontology.create_relationship(changed, extra.id, graph["blocked"])

        applied = _apply(client, proposal, op, {"strategy": "delete"}).json()["operations"][0]

        assert applied["status"] == "failed"
        assert "changed since reviewed: 3 now, 2 reviewed" in applied["reason"]
        assert len(_ends(ontology, graph["blocked"])) == 3


class TestNamedReplacement:
    """#1398: a delete names its replacement; REST stores it and flags its pair."""

    def _propose(self, client, graph, replacement):
        return client.post(
            "/api/proposals",
            json={
                "taxonomy_id": graph["taxonomy"],
                "title": "Business layer",
                "operations": [
                    {
                        "seq": 1,
                        "op": "delete",
                        "kind": "property",
                        "target_id": graph["blocked"],
                        "replacement": replacement,
                    }
                ],
            },
        )

    def test_a_different_pair_is_flagged_and_a_fitting_one_is_offered_first(
        self, client, graph, ontology
    ):
        response = self._propose(client, graph, "businessevent_triggers_businessprocess")
        assert response.status_code == 201, response.text
        op = response.json()["operations"][0]
        check = op["replacement_check"]
        assert check["pair"] == "different"
        assert op["proposed_replacement_id"] == check["property_id"]
        assert (check["range"]["title"], check["deleted_range"]["title"]) == (
            "BusinessProcess",
            "BusinessFunction",
        )
        # Read back from storage, it says the same.
        stored = client.get(f"/api/proposals/{response.json()['id']}").json()["operations"][0]
        assert stored["replacement_check"] == check

        serves = _serves(ontology, graph)
        ontology.create_property_definition(
            "businessevent_assigned_to_businessfunction",
            "assigned to",
            domain_class_id=graph["event"],
            range_class_id=graph["function"],
        )
        same = self._propose(client, graph, serves).json()["operations"][0]
        assert same["replacement_check"]["pair"] == "same"
        assert same["blockers"]["replacements"][0]["property_id"] == serves

    def test_an_unknown_replacement_is_422_by_seq(self, client, graph):
        response = self._propose(client, graph, "no_such_type")

        assert response.status_code == 422
        (error,) = response.json()["detail"]["errors"]
        assert (error["seq"], error["code"]) == (1, "replacement_not_found")


def test_rest_refuses_a_bundle_source(client, graph):
    """#1399: bundle proposals skip min_probability, so only the bundle import makes them."""
    response = client.post(
        "/api/proposals",
        json={
            "taxonomy_id": graph["taxonomy"],
            "title": "Not a bundle",
            "source": "bundle",
            "operations": [
                {"seq": 1, "op": "delete", "kind": "property", "target_id": graph["blocked"]}
            ],
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "bundle proposals come from the bundle import route"
    assert detail["errors"][0]["code"] == "invalid_source"
    assert client.get("/api/proposals").json()["total"] == 0
