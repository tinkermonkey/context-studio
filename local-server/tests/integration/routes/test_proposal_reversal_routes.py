"""
Route tests for reversal proposals (#1667) over real SQLite.

A landed proposal can't be reverted in place, so a reversal proposal is built
from its run's change events, decided like any proposal, and linked to it; when
the reversal lands the original is reversed, also when only some of its changes
were undone.
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
from adapters.web.proposals_routes import router
from domain.ontology.services import OntologyService
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
    service.change_repo = change_repo
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
    hall = ontology.create_class(vocab.id, "Hall", description="A hall")
    return {
        "taxonomy": taxonomy.id,
        "vocab": vocab.id,
        "room": room.id,
        "hall": hall.id,
        "hall_identifier": hall.identifier,
    }


def _propose(client, graph, *operations, title="Edits"):
    response = client.post(
        "/api/proposals",
        json={"taxonomy_id": graph["taxonomy"], "title": title, "operations": list(operations)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _describe(class_id, text, seq=1):
    return {
        "seq": seq,
        "op": "update",
        "kind": "class",
        "target_id": class_id,
        "fields": {"description": text},
        "rationale": "clearer",
    }


def _delete(class_id, seq=1):
    return {
        "seq": seq,
        "op": "delete",
        "kind": "class",
        "target_id": class_id,
        "rationale": "unused",
    }


def _create(title, seq=1, graph=None):
    return {
        "seq": seq,
        "op": "create",
        "kind": "class",
        "ref": title.lower(),
        "fields": {"concept_scheme_id": graph["vocab"], "title": title},
    }


def _apply_all(client, proposal):
    ids = [o["id"] for o in proposal["operations"]]
    response = client.post(f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": ids})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [o["status"] for o in body["operations"]] == ["applied"] * len(ids)
    return body


def _land(client, proposal_id):
    response = client.put(f"/api/proposals/{proposal_id}/landed", json={"commit": "abc123"})
    assert response.status_code == 200, response.text
    return response.json()


def _landed(client, graph, *operations):
    proposal = _propose(client, graph, *operations)
    _apply_all(client, proposal)
    return _land(client, proposal["id"])


def _reverse(client, proposal_id):
    return client.post(f"/api/proposals/{proposal_id}/reversal")


class TestPlanning:
    def test_an_update_is_set_back_a_create_deleted_a_delete_restored(
        self, client, graph, ontology
    ):
        original = _landed(
            client,
            graph,
            _describe(graph["room"], "Where people sit", seq=1),
            _create("Kit", seq=2, graph=graph),
            _delete(graph["hall"], seq=3),
        )

        response = _reverse(client, original["id"])

        assert response.status_code == 201, response.text
        reversal = response.json()
        assert reversal["status"] == "open"
        assert reversal["review_only"] is True
        assert reversal["title"] == "Reversal of: Edits"
        # Newest change first: the delete is undone first, the update last.
        ops = [(o["op"], o["kind"], o["status"]) for o in reversal["operations"]]
        assert ops == [
            ("create", "class", "pending"),
            ("delete", "class", "pending"),
            ("update", "class", "pending"),
        ]
        restore, remove, set_back = reversal["operations"]
        assert restore["target_id"] == graph["hall"]
        assert restore["fields"]["title"] == "Hall"
        assert remove["target_id"] != graph["hall"]
        assert set_back["target_id"] == graph["room"]
        assert set_back["fields"] == {"description": "A room"}
        assert set_back["base"] == {"description": "Where people sit"}

    def test_it_applies_like_any_proposal_and_restores_the_old_id(self, client, graph, ontology):
        original = _landed(
            client,
            graph,
            _describe(graph["room"], "Where people sit", seq=1),
            _delete(graph["hall"], seq=2),
        )
        repo = ontology._repository
        assert repo.get_class(graph["hall"]) is None
        reversal = _reverse(client, original["id"]).json()

        applied = _apply_all(client, reversal)

        restored = repo.get_class(graph["hall"])
        assert restored is not None
        assert (restored.title, restored.description) == ("Hall", "A hall")
        assert restored.concept_scheme_id == graph["vocab"]
        assert repo.get_class(graph["room"]).description == "A room"
        # The restore names the entity it made, with its old id
        assert applied["operations"][0]["result_entity_id"] == graph["hall"]
        # Reverting the reversal in place deletes the restored entity again
        assert client.post(f"/api/proposals/{reversal['id']}/revert").status_code == 200
        assert repo.get_class(graph["hall"]) is None

    def test_a_restore_whose_id_was_taken_fails_and_changes_nothing(self, client, graph, ontology):
        original = _landed(client, graph, _delete(graph["hall"]))
        reversal = _reverse(client, original["id"]).json()
        # Another class takes the identifier the deleted one had
        taker = ontology.create_class(graph["vocab"], "Foyer", identifier=graph["hall_identifier"])

        # The id is free, but the identifier it had is now in use.
        response = client.post(
            f"/api/proposals/{reversal['id']}/apply",
            json={"operation_ids": [reversal["operations"][0]["id"]]},
        )

        assert response.status_code == 200
        [operation] = response.json()["operations"]
        assert operation["status"] == "failed"
        assert taker.id in operation["reason"]
        assert ontology._repository.get_class(graph["hall"]) is None

    def test_a_proposal_that_has_not_landed_is_409(self, client, graph):
        proposal = _propose(client, graph, _describe(graph["room"], "Where people sit"))
        _apply_all(client, proposal)

        response = _reverse(client, proposal["id"])

        assert response.status_code == 409
        assert "has not landed" in response.json()["detail"]

    def test_a_missing_proposal_is_404(self, client):
        assert _reverse(client, "nope").status_code == 404

    def test_changes_already_undone_are_left_out_and_nothing_left_is_409(
        self, client, graph, ontology
    ):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        ontology.update_class(graph["room"], description="A room")  # put back by hand

        response = _reverse(client, original["id"])

        assert response.status_code == 409
        assert "Nothing is left to undo" in response.json()["detail"]


class TestOneOpenReversal:
    def test_a_second_open_reversal_is_refused_and_creates_nothing(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        first = _reverse(client, original["id"]).json()

        second = _reverse(client, original["id"])

        assert second.status_code == 409
        assert first["id"] in second.json()["detail"]
        listed = client.get("/api/proposals").json()
        assert len(listed["items"] if isinstance(listed, dict) else listed) == 2

    def test_the_two_proposals_link_each_other(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        reversal = _reverse(client, original["id"]).json()

        [to_original] = reversal["links"]
        assert (to_original["kind"], to_original["proposal_id"]) == ("reverses", original["id"])
        [to_reversal] = client.get(f"/api/proposals/{original['id']}").json()["links"]
        assert (to_reversal["kind"], to_reversal["proposal_id"]) == ("reversed_by", reversal["id"])
        assert to_reversal["status"] == "open"


class TestMarkingTheOriginalReversed:
    def test_a_partial_reversal_marks_it_reversed_and_counts_what_was_undone(
        self, client, graph, ontology
    ):
        original = _landed(
            client,
            graph,
            _describe(graph["room"], "Where people sit", seq=1),
            _describe(graph["hall"], "Where people walk", seq=2),
        )
        reversal = _reverse(client, original["id"]).json()
        first, second = (o["id"] for o in reversal["operations"])
        url = f"/api/proposals/{reversal['id']}"
        client.post(f"{url}/apply", json={"operation_ids": [first]})
        client.post(f"{url}/reject", json={"operation_ids": [second], "reason_code": "other"})
        assert client.get(f"/api/proposals/{original['id']}").json()["status"] == "done"

        assert client.put(f"{url}/landed", json={"commit": "def456"}).status_code == 200

        marked = client.get(f"/api/proposals/{original['id']}").json()
        assert marked["status"] == "reversed"
        [link] = marked["links"]
        assert (link["kind"], link["operations_applied"], link["operations_total"]) == (
            "reversed_by",
            1,
            2,
        )
        # Only what the reviewer accepted was undone.
        assert ontology._repository.get_class(graph["hall"]).description == "A hall"
        assert ontology._repository.get_class(graph["room"]).description == "Where people sit"

    def test_a_reversed_proposal_takes_no_more_decisions_or_reversals(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        reversal = _reverse(client, original["id"]).json()
        _apply_all(client, reversal)
        _land(client, reversal["id"])

        assert client.get(f"/api/proposals/{original['id']}").json()["status"] == "reversed"
        assert _reverse(client, original["id"]).status_code == 409
        assert client.post(f"/api/proposals/{original['id']}/revert").status_code == 409
        reopen = client.post(
            f"/api/proposals/{original['id']}/reopen",
            json={"operation_ids": [original["operations"][0]["id"]]},
        )
        assert reopen.status_code == 409

    def test_the_list_filters_by_reversed(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        reversal = _reverse(client, original["id"]).json()
        _apply_all(client, reversal)
        _land(client, reversal["id"])

        response = client.get("/api/proposals", params={"status": "reversed"})

        assert response.status_code == 200
        items = response.json()["items"]
        assert [p["id"] for p in items] == [original["id"]]

    def test_a_reversal_that_has_not_landed_leaves_the_original_done(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        reversal = _reverse(client, original["id"]).json()
        _apply_all(client, reversal)

        assert client.get(f"/api/proposals/{original['id']}").json()["status"] == "done"


class TestDraftsCannotRestore:
    def test_a_proposed_create_may_not_name_its_id(self, client, graph):
        response = client.post(
            "/api/proposals",
            json={
                "taxonomy_id": graph["taxonomy"],
                "title": "Sneaky",
                "operations": [
                    {
                        "seq": 1,
                        "op": "create",
                        "kind": "class",
                        "target_id": "chosen-id",
                        "fields": {"concept_scheme_id": graph["vocab"], "title": "Kit"},
                    }
                ],
            },
        )

        assert response.status_code == 422
        assert "A create has no target_id" in response.text


class TestFollowUps:
    """Review of #1741: the original's status, what is counted, refusals up front."""

    def test_clearing_the_reversals_landing_makes_the_original_done_again(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        reversal = _reverse(client, original["id"]).json()
        _apply_all(client, reversal)
        _land(client, reversal["id"])
        assert client.get(f"/api/proposals/{original['id']}").json()["status"] == "reversed"

        cleared = client.delete(f"/api/proposals/{reversal['id']}/landed")

        assert cleared.status_code == 200
        assert client.get(f"/api/proposals/{original['id']}").json()["status"] == "done"

    def test_a_reversal_cannot_itself_be_reversed(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        reversal = _reverse(client, original["id"]).json()
        _apply_all(client, reversal)
        _land(client, reversal["id"])

        response = _reverse(client, reversal["id"])

        assert response.status_code == 409
        assert "is itself a reversal" in response.json()["detail"]
        assert "propose the changes again" in response.json()["detail"]
        assert client.get(f"/api/proposals/{original['id']}").json()["status"] == "reversed"

    def test_a_reverted_original_says_it_is_already_undone_not_that_it_has_not_landed(
        self, client, graph
    ):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        assert client.post(f"/api/proposals/{original['id']}/revert").status_code == 200

        response = _reverse(client, original["id"])

        assert response.status_code == 409
        assert "is reverted: what it applied is already undone" in response.json()["detail"]

    def test_changes_are_counted_only_while_the_reversal_stands(self, client, graph):
        original = _landed(client, graph, _describe(graph["room"], "Where people sit"))
        reversal = _reverse(client, original["id"]).json()
        _apply_all(client, reversal)
        [link] = client.get(f"/api/proposals/{original['id']}").json()["links"]
        assert (link["operations_applied"], link["operations_total"]) == (1, 1)

        assert client.post(f"/api/proposals/{reversal['id']}/revert").status_code == 200

        [link] = client.get(f"/api/proposals/{original['id']}").json()["links"]
        assert link["status"] == "reverted"
        assert (link["operations_applied"], link["operations_total"]) == (None, None)

    def test_a_restore_cannot_be_edited_and_nothing_is_applied(self, client, graph, ontology):
        original = _landed(client, graph, _delete(graph["hall"]))
        reversal = _reverse(client, original["id"]).json()
        [restore] = reversal["operations"]

        response = client.post(
            f"/api/proposals/{reversal['id']}/apply",
            json={"operation_ids": [restore["id"]], "edits": {restore["id"]: {"title": "Foyer"}}},
        )

        assert response.status_code == 422
        assert "restores a deleted entity as it was and can't be edited" in response.text
        assert ontology._repository.get_class(graph["hall"]) is None
        [pending] = client.get(f"/api/proposals/{reversal['id']}").json()["operations"]
        assert pending["status"] == "pending"

    def test_a_restore_runs_no_client_rules_and_records_no_type_change(
        self, client, graph, ontology
    ):
        """
        A restore puts back what was there: it skips the dataset check and the
        rules a proposer's operation is under, and a restored relationship type
        records no type_change (the delete that removed it did).
        """
        prop = ontology.create_property_definition("uses", "Uses", taxonomy_id=graph["taxonomy"])
        original = _landed(
            client,
            graph,
            {"seq": 1, "op": "delete", "kind": "property", "target_id": prop.id},
        )
        reversal = _reverse(client, original["id"]).json()
        [restore] = reversal["operations"]
        assert restore["op"] == "create" and restore["target_id"] == prop.id

        [applied] = _apply_all(client, reversal)["operations"]

        assert applied["result_entity_id"] == prop.id
        service = client.app.state.proposal_service
        [stored] = service.get(reversal["id"]).operations
        assert stored.type_change is None
        [deleted] = service.get(original["id"]).operations
        assert deleted.type_change is not None
        assert ontology._repository.get_property_definition(prop.id) is not None
