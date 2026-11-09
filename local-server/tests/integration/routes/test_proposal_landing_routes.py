"""
Route tests for mirrored taxonomies and the landed state of proposals (#1463)
over real SQLite: the taxonomy's mirrored flag, the source revision a
proposal is drafted against, marking it landed, the unlanded filter, and the
revert a landing refuses.
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
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.web.ontology_routes import router as ontology_router
from adapters.web.proposals_routes import router as proposals_router
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import SourceRevision
from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.proposal_service import ProposalService
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

DR_REPO = "git@github.com:tinkermonkey/documentation_robotics.git"
IMPORTED = {"repo": DR_REPO, "commit": "aaa111", "spec_version": "0.10.0"}
DRAFTED = {"repo": IMPORTED["repo"], "commit": "bbb222", "spec_version": "0.10.0"}
LANDED = {"repo": IMPORTED["repo"], "commit": "ccc333", "spec_version": "0.10.1"}


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def ontology(session_factory):
    change_repo = SQLiteChangeRepository(session_factory=session_factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    service = OntologyService(
        SQLiteOntologyRepository(session_factory=session_factory), FakeEmbeddingService(), publisher
    )
    service.change_repo = change_repo
    return service


@pytest.fixture()
def policies(session_factory):
    return SQLiteApprovalPolicyRepository(session_factory)


@pytest.fixture()
def client(session_factory, ontology, policies):
    repo = ontology._repository
    app = FastAPI()
    app.include_router(proposals_router)
    app.include_router(ontology_router)
    app.state.ontology_service = ontology
    app.state.proposal_service = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        repo,
        RevertService(change_repo=ontology.change_repo, ontology_repo=repo),
        approval_policies=policies,
    )
    return TestClient(app)


@pytest.fixture()
def spec(ontology, policies):
    """A mirrored taxonomy imported at IMPORTED, whose policy would apply editorial changes."""
    taxonomy = ontology.create_taxonomy(title="DR spec")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="API")
    cls = ontology.create_class(scheme.id, "Operation", identifier="operation")
    ontology.set_taxonomy_mirrored(taxonomy.id, True)
    ontology.set_taxonomy_source_revision(taxonomy.id, SourceRevision.from_dict(IMPORTED))
    policies.save(ApprovalPolicy.from_rules(taxonomy.id, {"auto_apply": [{"scope": "editorial"}]}))
    return {"taxonomy": taxonomy.id, "class": cls.id}


def _propose(client, spec, title="API operation", **extra):
    body = {
        "taxonomy_id": spec["taxonomy"],
        "title": f"Rename to {title}",
        "source": "mcp",
        "operations": [
            {
                "seq": 1,
                "op": "update",
                "kind": "class",
                "target_id": spec["class"],
                "fields": {"title": title},
            }
        ],
        **extra,
    }
    response = client.post("/api/proposals", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _decide(client, spec, **extra):
    proposal = _propose(client, spec, **extra)
    ids = [o["id"] for o in proposal["operations"]]
    response = client.post(f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": ids})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "done"
    return response.json()


class TestMirroredTaxonomy:
    def test_the_taxonomy_shows_and_sets_its_mirrored_flag(self, client, spec):
        taxonomy = client.get(f"/api/taxonomies/{spec['taxonomy']}").json()
        assert taxonomy["mirrored"] is True
        assert taxonomy["source_revision"] == IMPORTED

        response = client.put(f"/api/taxonomies/{spec['taxonomy']}", json={"mirrored": False})

        assert response.status_code == 200, response.text
        assert response.json()["mirrored"] is False
        assert client.get(f"/api/taxonomies/{spec['taxonomy']}").json()["mirrored"] is False

    def test_nothing_auto_applies(self, client, spec, ontology):
        proposal = _propose(client, spec)
        assert [o["status"] for o in proposal["operations"]] == ["pending"]
        assert ontology.get_class(spec["class"]).title == "Operation"

    def test_unmirrored_its_policy_applies_again(self, client, spec, ontology):
        client.put(f"/api/taxonomies/{spec['taxonomy']}", json={"mirrored": False})
        proposal = _propose(client, spec)
        assert [o["status"] for o in proposal["operations"]] == ["applied"]


class TestSourceRevision:
    def test_a_proposal_keeps_the_revision_it_was_drafted_against(self, client, spec):
        proposal = _propose(client, spec, source_revision=DRAFTED)
        assert proposal["source_revision"] == DRAFTED
        assert client.get(f"/api/proposals/{proposal['id']}").json()["source_revision"] == DRAFTED

    def test_without_one_it_keeps_the_taxonomys_imported_revision(self, client, spec):
        assert _propose(client, spec)["source_revision"] == IMPORTED

    def test_an_empty_or_unknown_revision_is_422(self, client, spec):
        for revision in ({}, {"sha": "abc"}):
            body = {
                "taxonomy_id": spec["taxonomy"],
                "title": "Bad",
                "operations": [
                    {
                        "seq": 1,
                        "op": "update",
                        "kind": "class",
                        "target_id": spec["class"],
                        "fields": {"title": "X"},
                    }
                ],
                "source_revision": revision,
            }
            assert client.post("/api/proposals", json=body).status_code == 422


class TestLanding:
    def test_mark_landed_then_clear(self, client, spec):
        proposal = _decide(client, spec)
        assert proposal["landed"] is None

        response = client.put(f"/api/proposals/{proposal['id']}/landed", json=LANDED)

        assert response.status_code == 200, response.text
        landed = response.json()["landed"]
        assert {k: landed[k] for k in LANDED} == LANDED
        assert landed["landed_at"]
        again = client.put(f"/api/proposals/{proposal['id']}/landed", json=LANDED).json()
        assert again["landed"] == landed

        cleared = client.delete(f"/api/proposals/{proposal['id']}/landed")
        assert cleared.status_code == 200
        assert cleared.json()["landed"] is None

    def test_an_open_proposal_is_409(self, client, spec):
        proposal = _propose(client, spec)
        response = client.put(f"/api/proposals/{proposal['id']}/landed", json=LANDED)
        assert response.status_code == 409
        assert "only a done proposal" in response.json()["detail"]

    def test_a_commit_is_required(self, client, spec):
        proposal = _decide(client, spec)
        response = client.put(
            f"/api/proposals/{proposal['id']}/landed", json={"spec_version": "0.10.1"}
        )
        assert response.status_code == 422

    def test_a_missing_proposal_is_404(self, client):
        assert client.put("/api/proposals/nope/landed", json=LANDED).status_code == 404

    def test_the_unlanded_filter(self, client, spec):
        landed = _decide(client, spec)
        client.put(f"/api/proposals/{landed['id']}/landed", json=LANDED)
        unlanded = _decide(client, spec, title="Endpoint")
        _propose(client, spec, title="Still open")

        listed = client.get(
            "/api/proposals",
            params={"taxonomy_id": spec["taxonomy"], "status": "done", "landed": "false"},
        ).json()

        assert [p["id"] for p in listed["items"]] == [unlanded["id"]]
        assert listed["total"] == 1
        only_landed = client.get(
            "/api/proposals", params={"taxonomy_id": spec["taxonomy"], "landed": "true"}
        ).json()
        assert [p["id"] for p in only_landed["items"]] == [landed["id"]]

    def test_a_landed_proposal_cant_be_reverted_here(self, client, spec, ontology):
        proposal = _decide(client, spec)
        client.put(f"/api/proposals/{proposal['id']}/landed", json=LANDED)

        response = client.post(f"/api/proposals/{proposal['id']}/revert")

        assert response.status_code == 409
        assert "propose the reversal" in response.json()["detail"]["message"]
        assert response.json()["detail"]["blocking"] == []
        assert ontology.get_class(spec["class"]).title == "API operation"

    def test_an_unlanded_one_can_be_reverted(self, client, spec, ontology):
        proposal = _decide(client, spec)
        response = client.post(f"/api/proposals/{proposal['id']}/revert")
        assert response.status_code == 200, response.text
        assert ontology.get_class(spec["class"]).title == "Operation"
        # A reverted proposal can't land.
        assert client.put(f"/api/proposals/{proposal['id']}/landed", json=LANDED).status_code == 409
