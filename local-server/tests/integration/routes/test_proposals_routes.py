"""
Route tests for the change proposal API (#1356) over real SQLite.

The ProposalService is wired as in app.py: OntologyService with the change
recorder on every ontology event, and a real RevertService.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging
import tempfile
from datetime import datetime, timezone
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
from adapters.persistence.sqlite.transaction import TransactionAbortedError
from adapters.web.proposals_routes import router
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from domain.versioning.exceptions import RevertRefusedError
from domain.versioning.proposal_service import ProposalService
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
def ontology(session_factory):
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    change_repo = SQLiteChangeRepository(session_factory=session_factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    service = OntologyService(repo, FakeEmbeddingService(), publisher)
    service.change_repo = change_repo  # handy for assertions
    return service


@pytest.fixture()
def client(session_factory, ontology):
    repo = ontology._repository
    app = FastAPI()
    app.include_router(router)
    app.state.proposal_service = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        repo,
        RevertService(change_repo=ontology.change_repo, ontology_repo=repo),
    )
    return TestClient(app)


@pytest.fixture()
def graph(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room", description="A room")
    den = ontology.create_individual(room.id, "Den")
    return {"taxonomy": taxonomy.id, "vocab": vocab.id, "room": room.id, "den": den.id}


def _body(graph, *operations, **extra):
    return {
        "taxonomy_id": graph["taxonomy"],
        "title": "Kits",
        "operations": list(operations),
        **extra,
    }


def _create_kit(seq=1, ref="kit", graph=None):
    return {
        "seq": seq,
        "op": "create",
        "kind": "class",
        "ref": ref,
        "fields": {"concept_scheme_id": graph["vocab"], "title": "Kit"},
        "probability": 0.9,
    }


def _describe_room(graph, seq=2, text="Any room"):
    return {
        "seq": seq,
        "op": "update",
        "kind": "class",
        "target_id": graph["room"],
        "fields": {"description": text},
        "rationale": "clearer",
    }


def _propose(client, graph, *operations, **extra):
    response = client.post("/api/proposals", json=_body(graph, *operations, **extra))
    assert response.status_code == 201, response.text
    return response.json()


def _op_ids(proposal, *seqs):
    by_seq = {o["seq"]: o["id"] for o in proposal["operations"]}
    return [by_seq[s] for s in seqs]


class TestPropose:
    def test_creates_an_open_proposal_with_pending_operations(self, client, graph):
        proposal = _propose(
            client,
            graph,
            _create_kit(graph=graph),
            _describe_room(graph),
            rationale="Tools",
            source="mcp",
            source_detail="claude-desktop",
        )
        assert proposal["status"] == "open"
        assert proposal["source"] == "mcp"
        assert proposal["source_detail"] == "claude-desktop"
        create, update = proposal["operations"]
        assert (create["op"], create["kind"], create["scope"], create["status"]) == (
            "create",
            "class",
            "additive",
            "pending",
        )
        assert create["probability"] == 0.9
        assert update["scope"] == "editorial"
        assert update["base"] == {"description": "A room"}
        assert update["stale"] is False

    def test_defaults_to_a_user_proposal(self, client, graph):
        assert _propose(client, graph, _describe_room(graph))["source"] == "user"

    def test_invalid_operations_get_a_422_an_agent_can_act_on(self, client, graph):
        response = client.post(
            "/api/proposals",
            json=_body(
                graph,
                _describe_room(graph, seq=1),
                {"seq": 2, "op": "delete", "kind": "individual", "target_id": "missing"},
                {
                    "seq": 3,
                    "op": "create",
                    "kind": "relationship",
                    "fields": {"source_id": "$nope", "target_id": graph["den"]},
                },
            ),
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "Invalid change proposal" in detail["message"]
        errors = {e["seq"]: e for e in detail["errors"]}
        assert set(errors) == {2, 3}
        assert errors[2]["code"] == "target_not_found"
        assert errors[3]["code"] == "missing_field"
        assert "property_definition_id" in errors[3]["message"]
        assert client.get("/api/proposals").json()["total"] == 0

    def test_unknown_taxonomy_is_a_proposal_level_error(self, client, graph):
        body = _body(graph, _describe_room(graph))
        body["taxonomy_id"] = "nope"
        response = client.post("/api/proposals", json=body)
        assert response.status_code == 422
        assert response.json()["detail"]["errors"] == [
            {"seq": None, "code": "taxonomy_not_found", "message": "No taxonomy nope"}
        ]

    def test_bad_enum_is_a_request_validation_error(self, client, graph):
        body = _body(graph, {**_describe_room(graph), "kind": "widget"})
        response = client.post("/api/proposals", json=body)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"][:3] == ["body", "operations", 0]


class TestRead:
    def test_get_and_list_with_filters(self, client, graph, ontology):
        first = _propose(client, graph, _describe_room(graph), source="mcp")
        other = ontology.create_taxonomy(title="Garden")
        second = client.post(
            "/api/proposals",
            json={
                "taxonomy_id": other.id,
                "title": "Rename",
                "operations": [
                    {
                        "seq": 1,
                        "op": "update",
                        "kind": "taxonomy",
                        "target_id": other.id,
                        "fields": {"title": "Yard"},
                    }
                ],
            },
        ).json()

        got = client.get(f"/api/proposals/{first['id']}")
        assert got.status_code == 200
        assert got.json() == first

        listed = client.get("/api/proposals").json()
        assert listed["total"] == 2
        assert [p["id"] for p in listed["items"]] == [second["id"], first["id"]]
        by_taxonomy = client.get("/api/proposals", params={"taxonomy_id": graph["taxonomy"]})
        assert [p["id"] for p in by_taxonomy.json()["items"]] == [first["id"]]
        by_source = client.get("/api/proposals", params={"source": "mcp"}).json()
        assert [p["id"] for p in by_source["items"]] == [first["id"]]
        assert client.get("/api/proposals", params={"status": "done"}).json()["total"] == 0
        page = client.get("/api/proposals", params={"limit": 1, "offset": 1}).json()
        assert ([p["id"] for p in page["items"]], page["total"]) == ([first["id"]], 2)

    def test_bad_filter_is_422(self, client):
        assert client.get("/api/proposals", params={"status": "maybe"}).status_code == 422

    def test_missing_proposal_is_404(self, client):
        response = client.get("/api/proposals/nope")
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    def test_stale_flag_follows_the_target(self, client, graph, ontology):
        proposal = _propose(
            client, graph, _describe_room(graph, seq=1), _create_kit(seq=2, graph=graph)
        )
        ontology.update_class(graph["room"], description="Edited meanwhile")

        operations = client.get(f"/api/proposals/{proposal['id']}").json()["operations"]
        assert [o["stale"] for o in operations] == [True, False]
        listed = client.get("/api/proposals").json()["items"][0]["operations"]
        assert [o["stale"] for o in listed] == [True, False]


class TestApply:
    def test_applies_chosen_operations_and_tags_their_changes(self, client, graph, ontology):
        proposal = _propose(client, graph, _create_kit(seq=1, graph=graph), _describe_room(graph))
        create_id, update_id = _op_ids(proposal, 1, 2)

        response = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [create_id]}
        )
        assert response.status_code == 200
        body = response.json()
        create, update = body["operations"]
        assert create["status"] == "applied"
        assert ontology.get_class(create["result_entity_id"]).title == "Kit"
        assert update["status"] == "pending"
        assert body["status"] == "open"
        events = ontology.change_repo.get_changes(batch_run_id=proposal["id"], limit=None).events
        assert [e.entity_id for e in events] == [create["result_entity_id"]]

        done = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [update_id]}
        ).json()
        assert done["status"] == "done"
        assert ontology.get_class(graph["room"]).description == "Any room"

    def test_stale_operation_fails_until_forced(self, client, graph, ontology):
        proposal = _propose(client, graph, _describe_room(graph, seq=1))
        [op_id] = _op_ids(proposal, 1)
        ontology.update_class(graph["room"], description="Edited meanwhile")

        failed = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [op_id]}
        ).json()["operations"][0]
        assert failed["status"] == "failed"
        assert failed["reason"] == "target_changed: description changed since proposed"
        assert failed["stale"] is True

        forced = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={"operation_ids": [op_id], "force_stale": [op_id]},
        ).json()["operations"][0]
        assert (forced["status"], forced["stale"]) == ("applied", False)
        assert ontology.get_class(graph["room"]).description == "Any room"

    def test_input_errors(self, client, graph):
        proposal = _propose(client, graph, _describe_room(graph, seq=1))
        [op_id] = _op_ids(proposal, 1)
        url = f"/api/proposals/{proposal['id']}/apply"

        assert (
            client.post("/api/proposals/nope/apply", json={"operation_ids": [op_id]}).status_code
            == 404
        )
        assert client.post(url, json={"operation_ids": []}).status_code == 422
        unknown = client.post(url, json={"operation_ids": ["other"]})
        assert unknown.status_code == 422
        assert "other" in unknown.json()["detail"]

        assert client.post(url, json={"operation_ids": [op_id]}).status_code == 200
        again = client.post(url, json={"operation_ids": [op_id]})
        assert again.status_code == 409
        assert "already applied or rejected" in again.json()["detail"]


class TestApplyWithEdits:
    @pytest.fixture()
    def near(self, ontology, graph):
        return ontology.create_property_definition(
            "near", "near", domain_class_id=graph["room"], range_class_id=graph["room"]
        ).id

    def _rename_near(self, near, seq=1):
        return {
            "seq": seq,
            "op": "update",
            "kind": "property",
            "target_id": near,
            "fields": {"identifier": "close_to", "title": "close to"},
        }

    def test_an_edit_applies_instead_and_is_returned(self, client, graph, ontology, near):
        hall = ontology.create_class(graph["vocab"], "Hall").id
        proposal = _propose(client, graph, self._rename_near(near))
        [op_id] = _op_ids(proposal, 1)
        edit = {"title": "next to", "range_class_id": hall}

        response = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={"operation_ids": [op_id], "edits": {op_id: edit}},
        )

        assert response.status_code == 200, response.text
        [op] = response.json()["operations"]
        assert op["status"] == "applied"
        assert op["applied_fields"] == edit
        assert op["fields"] == {"identifier": "close_to", "title": "close to"}
        prop = ontology.get_property_definition(near)
        assert (prop.identifier, prop.title, prop.range_class_id) == ("near", "next to", hall)
        got = client.get(f"/api/proposals/{proposal['id']}").json()["operations"][0]
        assert got["applied_fields"] == edit

    def test_a_reflection_operation_reads_its_plan_and_records_the_chosen_alternative(
        self, client, graph, near
    ):
        plan = {
            "quote": "Sorting answers: ...",
            "entity_id": near,
            "plan_kind": "rename-predicate",
            "p": "0.700",
            "alternatives": "predicate=close_to|0.70",
            "replacement": "Room close_to Room",
            "probabilities": json.dumps(
                {
                    "source_for": {"Room": 0.9, "none": 0.1},
                    "target_for": {"Room": 0.95},
                    "predicate_for": {"close_to": 0.7, "near": 0.2, "adjacent": 0.1},
                }
            ),
            "current": json.dumps({"source": "Room", "predicate": "near", "target": "Room"}),
            "picks": json.dumps(
                {"source_for": "Room", "target_for": "Room", "predicate_for": "close_to"}
            ),
            "class_ids": json.dumps({"Room": graph["room"]}),
        }
        pack = {
            "quote": "Design intent: rooms\n\nRelationship types: near",
            "label": "Evidence pack",
        }
        operation = {**self._rename_near(near), "evidence": [plan, pack], "probability": 0.7}
        proposal = _propose(client, graph, operation)
        [op_id] = _op_ids(proposal, 1)

        reflection = proposal["operations"][0]["reflection"]
        assert reflection["plan_kind"] == "rename-predicate" and reflection["p"] == 0.7
        assert reflection["current"] == {"source": "Room", "predicate": "near", "target": "Room"}
        assert reflection["evidence_pack"] == ["Design intent: rooms", "Relationship types: near"]
        questions = {q["question"]: q["options"] for q in reflection["questions"]}
        assert [o["option"] for o in questions["predicate_for"]] == ["close_to", "near", "adjacent"]
        assert questions["predicate_for"][0]["plan"] and questions["predicate_for"][1]["current"]
        assert questions["source_for"][0] == {
            "option": "Room",
            "probability": 0.9,
            "class_id": graph["room"],
            "current": True,
            "plan": True,
        }
        assert questions["source_for"][1]["class_id"] is None  # none

        alternative = {"predicate_for": "adjacent", "triple": "Room adjacent Room"}
        response = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={
                "operation_ids": [op_id],
                "edits": {op_id: {"canonical_predicate": "adjacent"}},
                "chosen_alternatives": {op_id: alternative},
            },
        )
        assert response.status_code == 200, response.text
        [decision] = client.get(f"/api/taxonomies/{graph['taxonomy']}/gold").json()["items"]
        assert decision["decision"] == "applied_with_edits"
        assert decision["chosen_alternative"] == alternative

    @pytest.mark.parametrize(
        "plan",
        [
            {"plan_kind": "reverse", "probabilities": json.dumps({"predicate_for": {"a": "x"}})},
            {"plan_kind": "reverse", "current": json.dumps({"source": 1, "target": None})},
            {"plan_kind": "reverse", "class_ids": "[1, 2]", "probabilities": "{"},
        ],
        ids=["probability", "triple", "class-ids"],
    )
    def test_malformed_reflection_evidence_never_fails_the_proposal(
        self, client, graph, near, plan
    ):
        operation = {**self._rename_near(near), "evidence": [plan]}
        proposal = _propose(client, graph, operation)

        got = client.get(f"/api/proposals/{proposal['id']}")
        assert got.status_code == 200
        reflection = got.json()["operations"][0]["reflection"]
        assert reflection["plan_kind"] == "reverse" and reflection["current"] is None

    def test_an_unreadable_plan_row_is_left_out(self, client, graph, near, monkeypatch, caplog):
        def broken(evidence):
            raise RuntimeError("boom")

        monkeypatch.setattr("adapters.web.schemas.proposals.reflection_view", broken)
        proposal = _propose(client, graph, self._rename_near(near))
        assert proposal["operations"][0]["reflection"] is None
        assert "Unreadable reflection evidence" in caplog.text

    def test_other_operations_have_no_reflection(self, client, graph, near):
        proposal = _propose(client, graph, self._rename_near(near))
        assert proposal["operations"][0]["reflection"] is None

    def test_unedited_operations_return_null_applied_fields(self, client, graph, near):
        proposal = _propose(client, graph, self._rename_near(near))
        [op_id] = _op_ids(proposal, 1)

        op = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [op_id]}
        ).json()["operations"][0]

        assert op["status"] == "applied" and op["applied_fields"] is None

    def test_an_invalid_edit_fails_that_operation_in_a_200(self, client, graph, near):
        proposal = _propose(client, graph, self._rename_near(near), _describe_room(graph))
        rename_id, describe_id = _op_ids(proposal, 1, 2)

        response = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={
                "operation_ids": [rename_id, describe_id],
                "edits": {rename_id: {"range_class_id": "nope"}},
            },
        )

        assert response.status_code == 200
        rename, describe = response.json()["operations"]
        assert rename["status"] == "failed"
        assert rename["reason"].startswith("invalid_edit: range_class_id nope")
        assert rename["applied_fields"] is None
        assert describe["status"] == "applied"

    def test_a_misplaced_edit_is_422_and_nothing_applies(self, client, graph, near):
        proposal = _propose(client, graph, self._rename_near(near), _describe_room(graph))
        rename_id, describe_id = _op_ids(proposal, 1, 2)
        url = f"/api/proposals/{proposal['id']}/apply"

        for edits in (
            {describe_id: {"description": "Any"}},  # a class update
            {rename_id: {}},  # empty
            {"other": {"title": "x"}},  # not being applied
        ):
            response = client.post(
                url, json={"operation_ids": [rename_id, describe_id], "edits": edits}
            )
            assert response.status_code == 422, edits
        operations = client.get(f"/api/proposals/{proposal['id']}").json()["operations"]
        assert all(o["status"] == "pending" for o in operations)


class TestReject:
    def test_rejects_chosen_operations_with_a_note(self, client, graph):
        proposal = _propose(client, graph, _create_kit(seq=1, graph=graph), _describe_room(graph))
        [create_id] = _op_ids(proposal, 1)

        body = client.post(
            f"/api/proposals/{proposal['id']}/reject",
            json={"operation_ids": [create_id], "note": "not needed"},
        ).json()
        create, update = body["operations"]
        assert (create["status"], create["reason"]) == ("rejected", "not needed")
        assert update["status"] == "pending"
        assert body["status"] == "open"

    def test_without_ids_rejects_every_pending_and_failed_operation(self, client, graph, ontology):
        proposal = _propose(
            client, graph, _describe_room(graph, seq=1), _create_kit(seq=2, graph=graph)
        )
        update_id, _ = _op_ids(proposal, 1, 2)
        ontology.update_class(graph["room"], description="Edited meanwhile")
        client.post(f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [update_id]})

        body = client.post(f"/api/proposals/{proposal['id']}/reject", json={}).json()
        assert [o["status"] for o in body["operations"]] == ["rejected", "rejected"]
        assert body["status"] == "done"

    def test_decided_operation_is_409(self, client, graph):
        proposal = _propose(client, graph, _describe_room(graph, seq=1))
        ids = _op_ids(proposal, 1)
        client.post(f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": ids})
        response = client.post(
            f"/api/proposals/{proposal['id']}/reject", json={"operation_ids": ids}
        )
        assert response.status_code == 409


class TestRevert:
    def test_revert_undoes_applied_operations_and_closes_the_proposal(
        self, client, graph, ontology
    ):
        proposal = _propose(client, graph, _create_kit(seq=1, graph=graph), _describe_room(graph))
        create_id, _ = _op_ids(proposal, 1, 2)
        applied = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [create_id]}
        ).json()
        kit_id = applied["operations"][0]["result_entity_id"]

        response = client.post(f"/api/proposals/{proposal['id']}/revert")
        assert response.status_code == 200
        body = response.json()
        assert body["events_reverted"] == 1
        assert body["classes_deleted"] == 1
        assert body["proposal"]["status"] == "reverted"
        assert [o["status"] for o in body["proposal"]["operations"]] == ["applied", "rejected"]
        assert body["proposal"]["operations"][1]["reason"] == "proposal reverted"
        assert ontology._repository.get_class(kit_id) is None

        refused = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [create_id]}
        )
        assert refused.status_code == 409

    def test_conflict_is_409_and_names_the_blockers(self, client, graph, ontology):
        proposal = _propose(client, graph, _create_kit(seq=1, graph=graph))
        applied = client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={"operation_ids": _op_ids(proposal, 1)},
        ).json()
        kit_id = applied["operations"][0]["result_entity_id"]
        hammer = ontology.create_individual(kit_id, "Hammer")

        response = client.post(f"/api/proposals/{proposal['id']}/revert")
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "depend on entities it created" in detail["message"]
        assert {"dependent_id": hammer.id, "referenced_id": kit_id} == {
            k: v for k, v in detail["blocking"][0].items() if k != "kind"
        }
        still_open = client.get(f"/api/proposals/{proposal['id']}").json()
        assert still_open["status"] == "done"
        assert ontology.get_class(kit_id).title == "Kit"

    def test_missing_proposal_is_404(self, client):
        assert client.post("/api/proposals/nope/revert").status_code == 404


class TestDecisions:
    """GET /api/proposals/{id}/decisions: DR's decisions file (scripts/export_dr_decisions.py)."""

    def test_one_decision_per_operation_in_seq_order(self, client, graph):
        proposal = _propose(
            client,
            graph,
            _create_kit(seq=1, graph=graph),
            _describe_room(graph, seq=2),
            {
                **_create_kit(seq=3, ref="box", graph=graph),
                "fields": {"concept_scheme_id": graph["vocab"], "title": "Box"},
            },
        )
        create_id, describe_id, other_id = _op_ids(proposal, 1, 2, 3)
        applied = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [create_id]}
        ).json()
        client.post(
            f"/api/proposals/{proposal['id']}/reject",
            json={"operation_ids": [describe_id], "note": "not now"},
        )

        response = client.get(f"/api/proposals/{proposal['id']}/decisions")

        assert response.status_code == 200
        decisions = response.json()
        decided_at = [d.pop("decided_at") for d in decisions]
        assert [datetime.fromisoformat(d).tzinfo for d in decided_at[:2]] == [timezone.utc] * 2
        assert decided_at[2] is None
        # Exactly the script's shape: no "fields" key on an operation applied as proposed.
        assert decisions == [
            {
                "seq": 1,
                "op_id": create_id,
                "status": "applied",
                "reason": None,
                "result_entity_id": applied["operations"][0]["result_entity_id"],
                "decided_by": "user",
            },
            {
                "seq": 2,
                "op_id": describe_id,
                "status": "rejected",
                "reason": "not now",
                "result_entity_id": None,
                "decided_by": "user",
            },
            {
                "seq": 3,
                "op_id": other_id,
                "status": "pending",
                "reason": None,
                "result_entity_id": None,
                "decided_by": None,
            },
        ]

    def test_reverted_proposal_is_409(self, client, graph):
        proposal = _propose(client, graph, _create_kit(seq=1, graph=graph))
        client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": _op_ids(proposal, 1)}
        )
        assert client.post(f"/api/proposals/{proposal['id']}/revert").status_code == 200

        response = client.get(f"/api/proposals/{proposal['id']}/decisions")
        assert response.status_code == 409
        assert "reverted" in response.json()["detail"]


class TestGold:
    """GET /api/taxonomies/{id}/gold and its JSONL export."""

    def _decide(self, client, graph):
        proposal = _propose(
            client, graph, _create_kit(seq=1, graph=graph), _describe_room(graph, seq=2)
        )
        create_id, describe_id = _op_ids(proposal, 1, 2)
        client.post(f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [create_id]})
        client.post(
            f"/api/proposals/{proposal['id']}/reject",
            json={"operation_ids": [describe_id], "note": "not now"},
        )
        return proposal

    def test_lists_each_decision(self, client, graph):
        proposal = self._decide(client, graph)

        response = client.get(f"/api/taxonomies/{graph['taxonomy']}/gold")

        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["limit"], body["offset"]) == (2, 50, 0)
        applied, rejected = body["items"]
        assert (applied["seq"], applied["decision"]) == (1, "applied")
        assert applied["decided_by"] == "user"
        assert applied["proposal_id"] == proposal["id"]
        assert applied["kind"] == "class" and applied["op"] == "create"
        assert applied["proposed"]["fields"] == applied["applied_fields"]
        assert (rejected["decision"], rejected["reason"]) == ("rejected", "not now")
        assert rejected["applied_fields"] is None and rejected["superseded_at"] is None

    def test_filters_and_pages(self, client, graph):
        self._decide(client, graph)
        url = f"/api/taxonomies/{graph['taxonomy']}/gold"

        def seqs(**params):
            return [d["seq"] for d in client.get(url, params=params).json()["items"]]

        assert seqs(op="update") == [2]
        assert seqs(kind="class", decision="applied") == [1]
        assert seqs(decided_by="policy") == []
        assert seqs(decided_to="2000-01-01T00:00:00Z") == []
        assert seqs(decided_from="2000-01-01T00:00:00Z") == [1, 2]
        assert seqs(limit=1, offset=1) == [2]
        assert client.get(url, params={"decision": "maybe"}).status_code == 422

    def test_filters_by_proposal(self, client, graph):
        first = self._decide(client, graph)
        second = _propose(client, graph, _describe_room(graph, seq=1, text="Every room"))
        client.post(
            f"/api/proposals/{second['id']}/apply", json={"operation_ids": _op_ids(second, 1)}
        )
        url = f"/api/taxonomies/{graph['taxonomy']}/gold"

        def proposal_ids(**params):
            return [d["proposal_id"] for d in client.get(url, params=params).json()["items"]]

        assert proposal_ids(proposal_id=first["id"]) == [first["id"], first["id"]]
        assert proposal_ids(proposal_id=second["id"]) == [second["id"]]
        assert proposal_ids(proposal_id="nope") == []
        assert client.get(url, params={"proposal_id": first["id"]}).json()["total"] == 2

    def test_a_revert_supersedes(self, client, graph):
        proposal = self._decide(client, graph)
        assert client.post(f"/api/proposals/{proposal['id']}/revert").status_code == 200
        url = f"/api/taxonomies/{graph['taxonomy']}/gold"

        # The rejection still stands; the applied decision is superseded.
        assert [d["decision"] for d in client.get(url).json()["items"]] == ["rejected"]
        items = client.get(url, params={"include_superseded": True}).json()["items"]
        assert [d["superseded_by"] for d in items] == ["user", None]

    def test_exports_jsonl(self, client, graph):
        self._decide(client, graph)

        response = client.get(
            f"/api/taxonomies/{graph['taxonomy']}/gold/export", params={"decision": "rejected"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        assert "attachment" in response.headers["content-disposition"]
        lines = response.text.splitlines()
        assert [json.loads(line)["seq"] for line in lines] == [2]
        listed = client.get(
            f"/api/taxonomies/{graph['taxonomy']}/gold", params={"decision": "rejected"}
        ).json()["items"]
        assert [json.loads(line) for line in lines] == listed

    def test_unknown_taxonomy_is_404(self, client):
        assert client.get("/api/taxonomies/nope/gold").status_code == 404
        assert client.get("/api/taxonomies/nope/gold/export").status_code == 404

    def test_an_edit_without_a_dr_relationship_id_is_409(self, client, graph, ontology):
        near = ontology.create_property_definition(
            "near", "near", domain_class_id=graph["room"], range_class_id=graph["room"]
        ).id
        proposal = _propose(
            client,
            graph,
            {
                "seq": 1,
                "op": "update",
                "kind": "property",
                "target_id": near,
                "fields": {"title": "close to"},
            },
        )
        [op_id] = _op_ids(proposal, 1)
        client.post(
            f"/api/proposals/{proposal['id']}/apply",
            json={"operation_ids": [op_id], "edits": {op_id: {"title": "next to"}}},
        )

        response = client.get(f"/api/proposals/{proposal['id']}/decisions")
        assert response.status_code == 409
        assert "no DR relationship id" in response.json()["detail"]

    def test_missing_proposal_is_404(self, client):
        assert client.get("/api/proposals/nope/decisions").status_code == 404


class FailingRevertService:
    """A RevertService stand-in that raises the given error."""

    def __init__(self, error):
        self.error = error

    def revert_with_summary(self, run_id, on_reverted=None):
        raise self.error


def _client_reverting_with(session_factory, ontology, error):
    app = FastAPI()
    app.include_router(router)
    app.state.proposal_service = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        ontology._repository,
        FailingRevertService(error),
    )
    return TestClient(app)


class TestRevertErrors:
    def test_a_refused_revert_is_409_nothing_changed(self, session_factory, ontology, graph):
        message = "Cannot revert batch run x; nothing was changed. event: no state"
        client = _client_reverting_with(session_factory, ontology, RevertRefusedError(message))
        proposal = _propose(client, graph, _describe_room(graph, seq=1))

        response = client.post(f"/api/proposals/{proposal['id']}/revert")

        assert response.status_code == 409
        assert response.json()["detail"] == {"message": message, "blocking": []}
        assert client.get(f"/api/proposals/{proposal['id']}").json()["status"] == "open"

    @pytest.mark.parametrize(
        "error, detail",
        [
            (ValueError("Could not restore field title"), "An unexpected error occurred"),
            (EntityNotFoundError("Class", "gone"), "An unexpected error occurred"),
            (
                TransactionAbortedError("scope rolled back"),
                "The change was rolled back; nothing was changed",
            ),
        ],
    )
    def test_any_other_revert_error_is_a_logged_500(
        self, session_factory, ontology, graph, error, detail, caplog
    ):
        client = _client_reverting_with(session_factory, ontology, error)
        proposal = _propose(client, graph, _describe_room(graph, seq=1))

        with caplog.at_level(logging.ERROR):
            response = client.post(f"/api/proposals/{proposal['id']}/revert")

        assert response.status_code == 500
        assert response.json()["detail"] == detail
        assert str(error) in caplog.text
        assert client.get(f"/api/proposals/{proposal['id']}").json()["status"] == "open"
