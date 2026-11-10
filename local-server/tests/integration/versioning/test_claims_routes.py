"""Integration tests for the claims routes (#1518) over real SQLite."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.web.claims_routes import router
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.versioning.claims import ClaimService, ClaimTriage

T = "tax-1"


@pytest.fixture()
def service():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        ontology = SQLiteOntologyRepository(session_factory=factory)
        ontology.save_taxonomy(Taxonomy(id=T, identifier="dr", title="DR"))
        ontology.save_concept_scheme(ConceptScheme(id="s1", taxonomy_id=T, title="API"))
        ontology.save_class(
            Class(id="c1", taxonomy_id=T, concept_scheme_id="s1", title="Operation")
        )
        yield ClaimService(SQLiteClaimRepository(factory), ontology)
        engine.dispose()


@pytest.fixture()
def client(service):
    app = FastAPI()
    app.include_router(router)
    app.state.claim_service = service
    return TestClient(app)


def body(*keys, **extra):
    return {
        "claims": [
            {
                "key": key,
                "text": f"Claim {key}",
                "note_ref": key.split("#")[0],
                "note_source": "reviewer",
                **extra,
            }
            for key in keys
        ]
    }


def test_submit_list_get_and_export(client):
    response = client.post(
        f"/api/taxonomies/{T}/claims", json=body("n1#1", "n1#2", affected_ids=["c1", "x.y"])
    )
    assert response.status_code == 200, response.text
    stored = response.json()
    assert [c["key"] for c in stored] == ["n1#1", "n1#2"]
    assert stored[0]["affected_ids"] == ["c1"]
    assert stored[0]["unresolved_refs"] == ["x.y"]
    assert stored[0]["triage"] is None

    listed = client.get(f"/api/taxonomies/{T}/claims", params={"limit": 1}).json()
    assert listed["total"] == 2
    assert [c["key"] for c in listed["items"]] == ["n1#1"]

    one = client.get(f"/api/claims/{stored[1]['id']}").json()
    assert one["key"] == "n1#2"

    export = client.get(f"/api/taxonomies/{T}/claims/export")
    assert export.headers["content-type"].startswith("application/x-ndjson")
    lines = [json.loads(line) for line in export.text.splitlines()]
    assert [c["key"] for c in lines] == ["n1#1", "n1#2"]


def test_filters(client, service):
    stored = client.post(f"/api/taxonomies/{T}/claims", json=body("n1#1", "n2#1")).json()
    service.save_triage(stored[0]["id"], ClaimTriage(validity="real_defect", model="clef"))

    def keys(**params):
        return [
            c["key"]
            for c in client.get(f"/api/taxonomies/{T}/claims", params=params).json()["items"]
        ]

    assert keys(triaged="true") == ["n1#1"]
    assert keys(triaged="false") == ["n2#1"]
    assert keys(validity="real_defect") == ["n1#1"]
    assert keys(note_ref="n2") == ["n2#1"]
    assert client.get(f"/api/taxonomies/{T}/claims", params={"validity": "nope"}).status_code == 422


def test_verdict_set_and_clear(client):
    claim_id = client.post(f"/api/taxonomies/{T}/claims", json=body("n1#1")).json()[0]["id"]

    judged = client.put(
        f"/api/claims/{claim_id}/verdict",
        json={"validity": "works_as_designed", "severity": 0, "rationale": "Intended"},
    )
    assert judged.status_code == 200, judged.text
    verdict = judged.json()["verdict"]
    assert verdict["validity"] == "works_as_designed"
    assert verdict["adjudicated_by"] == "user"
    assert verdict["adjudicated_at"]
    assert (
        client.get(f"/api/taxonomies/{T}/claims", params={"has_verdict": "true"}).json()["total"]
        == 1
    )

    cleared = client.delete(f"/api/claims/{claim_id}/verdict")
    assert cleared.json()["verdict"] is None


def test_errors(client):
    assert client.get("/api/taxonomies/nope/claims").status_code == 404
    assert client.post("/api/taxonomies/nope/claims", json=body("n1#1")).status_code == 404
    assert client.get("/api/claims/nope").status_code == 404
    assert (
        client.put("/api/claims/nope/verdict", json={"validity": "real_defect"}).status_code == 404
    )
    assert client.post(f"/api/taxonomies/{T}/claims", json={"claims": []}).status_code == 422
    repeated = client.post(f"/api/taxonomies/{T}/claims", json=body("n1#1", "n1#1"))
    assert repeated.status_code == 422
    assert "n1#1" in repeated.json()["detail"]
    unknown_subject = client.post(f"/api/taxonomies/{T}/claims", json=body("n1#1", subject_id="x"))
    assert unknown_subject.status_code == 404
    bad_score = client.post(f"/api/taxonomies/{T}/claims", json=body("n1#1")).json()[0]["id"]
    assert (
        client.put(
            f"/api/claims/{bad_score}/verdict", json={"validity": "real_defect", "severity": 5}
        ).status_code
        == 422
    )
