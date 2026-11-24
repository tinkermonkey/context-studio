"""
Route tests (#1615): comparing two pipelines' proposals for the same source,
over real SQLite.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
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
from adapters.web.proposal_comparison_routes import router as comparison_router
from adapters.web.proposals_routes import router as proposals_router
from domain.ontology.services import OntologyService
from domain.pipelines.proposal_comparison import ProposalComparisonService
from domain.pipelines.source_proposals import SUPERSEDED_REASON
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationDraft
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationType as T
from domain.versioning.proposals import ProposalSource
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

SOURCE = "src-1"


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        change_repo = SQLiteChangeRepository(session_factory=session_factory)
        publisher = InProcessEventPublisher()
        wire_change_recorder(publisher, change_repo)
        ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
        service = ProposalService(
            SQLiteChangeProposalRepository(session_factory),
            ontology,
            repo,
            RevertService(change_repo=change_repo, ontology_repo=repo),
        )
        app = FastAPI()
        app.include_router(proposals_router)
        app.include_router(comparison_router)
        app.state.proposal_service = service
        app.state.proposal_comparison_service = ProposalComparisonService(service, repo)
        app.state.ontology = ontology
        yield TestClient(app)
        engine.dispose()


@pytest.fixture()
def house(client):
    ontology = client.app.state.ontology
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room")
    hall = ontology.create_class(vocab.id, "Hall", parent_class_id=room.id)
    den = ontology.create_individual(room.id, "Den")
    return {"taxonomy": taxonomy.id, "room": room.id, "hall": hall.id, "den": den.id}


def extraction(client, house, rows, implementation):
    """rows: (title, class key, near matches)"""
    drafts = [
        OperationDraft(
            n,
            T.CREATE,
            K.INDIVIDUAL,
            fields={"title": title, "class_ids": [house[cls]]},
            evidence=[{"source_id": SOURCE, "page": 1, "start": n, "end": n + 3, "quote": "abc"}],
            alternatives=list(alternatives),
        )
        for n, (title, cls, alternatives) in enumerate(rows, start=1)
    ]
    return client.app.state.proposal_service.propose(
        house["taxonomy"],
        implementation,
        drafts,
        ProposalSource.PIPELINE,
        client_metadata={
            "source_id": SOURCE,
            "pipeline": "individual_extraction",
            "origin": {
                "pipeline_type": "individual_extraction",
                "implementation_id": implementation,
                "configuration_ref": "c",
                "configuration_version": 1,
                "digest": "0123456789ab",
            },
        },
    )


@pytest.fixture()
def pair(client, house):
    near = {"kind": "existing", "entity_id": house["den"], "similarity": 0.8}
    a = extraction(
        client,
        house,
        [("Study", "room", ()), ("Hall", "room", ()), ("Pantry", "room", [near])],
        "single_call",
    )
    b = extraction(
        client, house, [("Study", "room", ()), ("Hall", "hall", ()), ("Larder", "room", ())], "x"
    )
    return a, b


def url(a, b, tail=""):
    return f"/api/proposals/{a.id}/compare/{b.id}{tail}"


def test_compare_pairs_the_two_proposals(client, house, pair):
    a, b = pair

    response = client.get(url(a, b))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["a"]["origin"]["implementation_id"] == "single_call"
    assert (body["taxonomy_id"], body["source_id"]) == (house["taxonomy"], SOURCE)
    assert [(p["group"], p["state"]) for p in body["pairs"]] == [
        ("same_class", "open"),
        ("class_differs", "open"),
        ("only_a", "open"),
        ("only_b", "open"),
    ]
    assert body["counts"] == {
        "same_class": 1,
        "class_differs": 1,
        "only_a": 1,
        "only_b": 1,
        "open": 4,
    }
    assert body["sample"] == {"size": 1, "checked": 0, "changed": 0}
    assert body["pairs"][0]["in_sample"] is True
    differs = body["pairs"][1]
    assert differs["a"]["classes"] == [{"id": house["room"], "title": "Room"}]
    assert differs["b"]["classes"] == [{"id": house["hall"], "title": "Hall"}]
    only_a = body["pairs"][2]
    assert only_a["b"] is None
    assert only_a["a"]["alternatives"][0]["title"] == "Den"
    assert only_a["a"]["lacks_passage"] is False


def test_unknown_proposal_is_404(client, pair):
    a, _ = pair
    assert client.get(f"/api/proposals/{a.id}/compare/nope").status_code == 404


def test_a_proposal_with_itself_is_422_not_comparable(client, pair):
    a, _ = pair

    response = client.get(url(a, a))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "not_comparable"


def test_decide_lands_once_and_both_decisions_record_it(client, house, pair):
    a, b = pair
    differs = client.get(url(a, b)).json()["pairs"][1]

    response = client.post(
        url(a, b, "/decide"),
        json={
            "a_operation_id": differs["a"]["operation_id"],
            "b_operation_id": differs["b"]["operation_id"],
            "verdict": "b_class",
            "review_ms": 2000,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "landed" and body["failure_reason"] is None
    assert body["pair"]["state"] == "decided"
    assert body["pair"]["a"]["status"] == "rejected"
    assert body["pair"]["a"]["reason_code"] == "duplicate"
    assert body["pair"]["a"]["comparison"]["verdict"] == "class_changed"
    assert body["pair"]["b"]["comparison"]["verdict"] == "kept"
    gold = f"/api/taxonomies/{house['taxonomy']}/gold"
    decisions = client.get(gold).json()["items"]
    assert sorted(d["comparison"]["verdict"] for d in decisions) == ["class_changed", "kept"]
    exported = [json.loads(line) for line in client.get(f"{gold}/export").text.splitlines()]
    assert [d["comparison"] for d in exported] == [d["comparison"] for d in decisions]


@pytest.mark.parametrize(
    "body",
    [
        {"verdict": "keep"},
        {"verdict": "maybe"},
        {"verdict": "keep", "reason_code": "other"},
        {"verdict": "a_class"},
    ],
)
def test_a_malformed_decision_is_422(client, pair, body):
    a, b = pair
    study = client.get(url(a, b)).json()["pairs"][0]
    if body["verdict"] != "keep" or "reason_code" in body:
        body = {**body, "a_operation_id": study["a"]["operation_id"]}

    response = client.post(url(a, b, "/decide"), json=body)

    assert response.status_code == 422
    assert client.get(url(a, b)).json()["counts"]["open"] == 4


def test_a_decided_copy_is_409(client, pair):
    a, b = pair
    study = client.get(url(a, b)).json()["pairs"][0]
    client.app.state.proposal_service.reject(b.id, [study["b"]["operation_id"]])

    response = client.post(
        url(a, b, "/decide"),
        json={
            "a_operation_id": study["a"]["operation_id"],
            "b_operation_id": study["b"]["operation_id"],
            "verdict": "keep",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "already_decided"


def test_accept_rest_waits_for_the_sample_then_lands_once(client, house):
    rows = [(f"Room {n}", "room", ()) for n in range(1, 13)]
    a = extraction(client, house, rows, "single_call")
    b = extraction(client, house, rows, "x")

    too_small = client.post(url(a, b, "/accept-rest"), json={"sample_size": 2})
    assert too_small.status_code == 422
    assert too_small.json()["detail"]["code"] == "sample_too_small"
    unchecked = client.post(url(a, b, "/accept-rest"), json={})
    assert unchecked.status_code == 409
    assert unchecked.json()["detail"]["code"] == "sample_unchecked"

    comparison = client.get(url(a, b)).json()
    for p in [p for p in comparison["pairs"] if p["in_sample"]]:
        decided = client.post(
            url(a, b, "/decide"),
            json={
                "a_operation_id": p["a"]["operation_id"],
                "b_operation_id": p["b"]["operation_id"],
                "verdict": "keep",
            },
        )
        assert decided.status_code == 200, decided.text

    accepted = client.post(url(a, b, "/accept-rest"), json={})
    again = client.post(url(a, b, "/accept-rest"), json={})

    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {
        "landed": 2,
        "failed": [],
        "skipped": [],
        "sample": {"size": 10, "checked": 10, "changed": 0},
    }
    assert again.json()["landed"] == 0
    after = client.get(url(a, b)).json()
    assert after["counts"]["open"] == 0
    bulk = [p["a"]["comparison"]["bulk"] for p in after["pairs"] if not p["in_sample"]]
    assert bulk == [{"sample_size": 10, "sample_changed": 0}] * 2


def test_one_copy_of_an_open_pair_is_422(client, pair):
    a, b = pair
    study = client.get(url(a, b)).json()["pairs"][0]

    response = client.post(
        url(a, b, "/decide"),
        json={"a_operation_id": study["a"]["operation_id"], "verdict": "keep"},
    )

    assert response.status_code == 422
    assert "Name both copies" in response.json()["detail"]["message"]


def test_a_superseded_proposal_is_422_not_comparable(client, pair):
    a, b = pair
    client.app.state.proposal_service.reject(
        a.id, [a.operations[0].id], note=SUPERSEDED_REASON.format("newer"), decided_by=None
    )

    response = client.get(url(a, b))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "not_comparable"
    assert "compare the newer one" in response.json()["detail"]["message"]
