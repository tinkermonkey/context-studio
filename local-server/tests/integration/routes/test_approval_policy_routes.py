"""
Route tests for a taxonomy's approval policy (#1355) over real SQLite, and
auto-apply through POST /api/proposals.
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
from adapters.persistence.sqlite.approval_policy_repo import SQLiteApprovalPolicyRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import ApprovalPolicyRecord, Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.web.proposals_routes import router
from domain.ontology.services import OntologyService
from domain.versioning.approval_policy import ApprovalPolicyService
from domain.versioning.proposal_service import ProposalService
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

HOUSE_RULES = {
    "auto_apply": [
        {"op": "create", "kind": "individual", "class": "house_activity"},
        {"scope": "editorial"},
    ],
    "min_probability": 0.5,
}


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
    policies = SQLiteApprovalPolicyRepository(session_factory)
    app = FastAPI()
    app.include_router(router)
    app.state.proposal_service = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        repo,
        RevertService(change_repo=ontology.change_repo, ontology_repo=repo),
        approval_policies=policies,
    )
    app.state.approval_policy_service = ApprovalPolicyService(policies, repo)
    return TestClient(app)


@pytest.fixture()
def house(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Life")
    activity = ontology.create_class(scheme.id, "House activity", identifier="house_activity")
    place = ontology.create_class(scheme.id, "Place", identifier="place")
    attic = ontology.create_individual(place.id, "Attic")
    return {
        "taxonomy": taxonomy.id,
        "activity": activity.id,
        "place": place.id,
        "attic": attic.id,
    }


def _url(taxonomy_id):
    return f"/api/taxonomies/{taxonomy_id}/approval-policy"


class TestPolicyRoutes:
    def test_get_without_a_policy_is_empty(self, client, house):
        response = client.get(_url(house["taxonomy"]))
        assert response.status_code == 200
        assert response.json() == {
            "taxonomy_id": house["taxonomy"],
            "auto_apply": [],
            "min_probability": 0.0,
        }

    def test_put_replaces_and_get_reads_it_back(self, client, house):
        response = client.put(_url(house["taxonomy"]), json=HOUSE_RULES)
        assert response.status_code == 200
        assert response.json() == {"taxonomy_id": house["taxonomy"], **HOUSE_RULES}
        assert client.get(_url(house["taxonomy"])).json() == response.json()

        cleared = client.put(_url(house["taxonomy"]), json={"auto_apply": []}).json()
        assert cleared == {
            "taxonomy_id": house["taxonomy"],
            "auto_apply": [],
            "min_probability": 0.0,
        }

    def test_unknown_taxonomy_is_404(self, client):
        assert client.get(_url("nope")).status_code == 404
        assert client.put(_url("nope"), json=HOUSE_RULES).status_code == 404

    @pytest.mark.parametrize(
        "body",
        [
            {"auto_apply": [{"op": "replace"}]},
            {"auto_apply": [{"colour": "red"}]},
            {"auto_apply": [{}]},
            {"auto_apply": [], "min_probability": 2},
            {"auto_apply": [], "max_probability": 1},
        ],
    )
    def test_invalid_rules_are_422_and_change_nothing(self, client, house, body):
        client.put(_url(house["taxonomy"]), json=HOUSE_RULES)
        assert client.put(_url(house["taxonomy"]), json=body).status_code == 422
        assert client.get(_url(house["taxonomy"])).json()["auto_apply"] == HOUSE_RULES["auto_apply"]

    def test_deleting_the_taxonomy_deletes_its_policy(
        self, client, house, ontology, session_factory
    ):
        client.put(_url(house["taxonomy"]), json=HOUSE_RULES)
        ontology.delete_individual(house["attic"])
        for class_id in (house["activity"], house["place"]):
            ontology.delete_class(class_id)
        for scheme in ontology.list_concept_schemes(taxonomy_id=house["taxonomy"]):
            ontology.delete_scheme(scheme.id)
        ontology.delete_taxonomy(house["taxonomy"])
        assert SQLiteApprovalPolicyRepository(session_factory).get(house["taxonomy"]) is None


class TestAutoApply:
    def test_matching_operations_apply_when_proposed(self, client, house, ontology):
        client.put(_url(house["taxonomy"]), json=HOUSE_RULES)
        response = client.post(
            "/api/proposals",
            json={
                "taxonomy_id": house["taxonomy"],
                "title": "Chores",
                "source": "mcp",
                "operations": [
                    {
                        "seq": 1,
                        "op": "create",
                        "kind": "individual",
                        "fields": {"class_ids": [house["activity"]], "title": "Dust"},
                        "probability": 0.9,
                    },
                    {
                        "seq": 2,
                        "op": "create",
                        "kind": "individual",
                        "fields": {"class_ids": [house["activity"]], "title": "Guess"},
                        "probability": 0.2,
                    },
                    {
                        "seq": 3,
                        "op": "create",
                        "kind": "individual",
                        "fields": {"class_ids": [house["place"]], "title": "Cellar"},
                        "probability": 0.9,
                    },
                    {
                        "seq": 4,
                        "op": "update",
                        "kind": "individual",
                        "target_id": house["attic"],
                        "fields": {"description": "Dusty"},
                        "probability": 0.9,
                    },
                ],
            },
        )
        assert response.status_code == 201
        proposal = response.json()
        assert [o["status"] for o in proposal["operations"]] == [
            "applied",
            "pending",
            "pending",
            "applied",
        ]
        assert proposal["status"] == "open"
        events = ontology.change_repo.get_changes(batch_run_id=proposal["id"], limit=None).events
        assert len(events) == 2

        reverted = client.post(f"/api/proposals/{proposal['id']}/revert").json()
        assert reverted["individuals_deleted"] == 1
        assert ontology.get_individual(house["attic"]).description in (None, "")

    def test_deletes_never_auto_apply(self, client, house, ontology):
        client.put(_url(house["taxonomy"]), json={"auto_apply": [{"kind": "individual"}]})
        proposal = client.post(
            "/api/proposals",
            json={
                "taxonomy_id": house["taxonomy"],
                "title": "Tidy",
                "operations": [
                    {"seq": 1, "op": "delete", "kind": "individual", "target_id": house["attic"]}
                ],
            },
        ).json()
        assert proposal["operations"][0]["status"] == "pending"
        assert ontology.get_individual(house["attic"]) is not None

    def test_a_policy_never_changes_another_taxonomy(self, client, house, ontology):
        other = ontology.create_taxonomy(title="Other")
        other_scheme = ontology.create_scheme(taxonomy_id=other.id, title="Misc")
        thing = ontology.create_class(other_scheme.id, "Thing")
        widget = ontology.create_individual(thing.id, "Widget")
        client.put(
            _url(house["taxonomy"]),
            json={"auto_apply": [{"scope": "editorial"}, {"op": "create"}]},
        )
        response = client.post(
            "/api/proposals",
            json={
                "taxonomy_id": house["taxonomy"],
                "title": "Reach",
                "operations": [
                    {
                        "seq": 1,
                        "op": "update",
                        "kind": "individual",
                        "target_id": widget.id,
                        "fields": {"title": "Gadget"},
                    },
                    {
                        "seq": 2,
                        "op": "create",
                        "kind": "class",
                        "fields": {"concept_scheme_id": other_scheme.id, "title": "Gizmo"},
                    },
                    {"seq": 3, "op": "create", "kind": "taxonomy", "fields": {"title": "Third"}},
                ],
            },
        )
        assert response.status_code == 201
        assert [o["status"] for o in response.json()["operations"]] == ["pending"] * 3
        assert ontology.get_individual(widget.id).title == "Widget"

    def test_a_stored_policy_that_does_not_parse_still_stores_the_proposal(
        self, client, house, session_factory
    ):
        with session_factory() as session:
            session.add(
                ApprovalPolicyRecord(
                    taxonomy_id=house["taxonomy"], rules={"auto_apply": [{"op": "replace"}]}
                )
            )
            session.commit()
        response = client.post(
            "/api/proposals",
            json={
                "taxonomy_id": house["taxonomy"],
                "title": "Chores",
                "operations": [
                    {
                        "seq": 1,
                        "op": "update",
                        "kind": "individual",
                        "target_id": house["attic"],
                        "fields": {"description": "Dusty"},
                    }
                ],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert (body["status"], body["operations"][0]["status"]) == ("open", "pending")
