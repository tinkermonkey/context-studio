"""
Route tests (#1553, part of #1552) over real SQLite wired as in app.py: source
evidence and near-match alternatives pass through the proposal routes, "use
existing" applies through chosen_alternatives, and an individual's and a
relationship's provenance read back from their sources routes.
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
from adapters.persistence.sqlite.entity_source_repo import SQLiteEntitySourceRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from adapters.web.ontology_routes import router as ontology_router
from adapters.web.proposals_routes import router as proposals_router
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import ProposalSource
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

SOURCE = "src-manual"
PASSAGE = {"source_id": SOURCE, "page": 5, "start": 8412, "end": 8447, "quote": "French door"}


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
    app.include_router(ontology_router)
    app.include_router(proposals_router)
    app.state.ontology_service = ontology
    app.state.proposal_service = ProposalService(
        SQLiteChangeProposalRepository(factory),
        ontology,
        repo,
        RevertService(
            change_repo=ontology.change_repo, ontology_repo=repo, transaction_scope=scope
        ),
        transaction_scope=scope,
        entity_sources=SQLiteEntitySourceRepository(factory),
    )
    return TestClient(app)


@pytest.fixture()
def house(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Resources")
    appliance = ontology.create_class(scheme.id, "Appliance")
    business = ontology.create_class(scheme.id, "Business")
    made_by = ontology.create_property_definition(
        "made_by", "made by", domain_class_id=appliance.id, range_class_id=business.id
    )
    fridge = ontology.create_individual(appliance.id, "Kitchen refrigerator")
    whirlpool = ontology.create_individual(business.id, "Whirlpool Corporation")
    return {
        "taxonomy": taxonomy.id,
        "appliance": appliance.id,
        "made_by": made_by.id,
        "fridge": fridge.id,
        "whirlpool": whirlpool.id,
    }


def body(house, alternative=None, evidence=(PASSAGE,)):
    alternative = alternative or {
        "kind": "existing",
        "entity_id": house["fridge"],
        "similarity": 0.93,
    }
    return {
        "taxonomy_id": house["taxonomy"],
        "title": "Extracted",
        "source": "pipeline",
        "operations": [
            {
                "seq": 1,
                "op": "create",
                "kind": "individual",
                "ref": "c1",
                "fields": {"class_ids": [house["appliance"]], "title": "Whirlpool WRF555SDFZ"},
                "evidence": list(evidence),
                "probability": 0.94,
                "alternatives": [alternative],
            },
            {
                "seq": 2,
                "op": "create",
                "kind": "relationship",
                "fields": {
                    "source_id": "$c1",
                    "target_id": house["whirlpool"],
                    "property_definition_id": house["made_by"],
                },
                "evidence": [{**PASSAGE, "start": 0, "end": 20, "page": 1, "quote": "made by"}],
            },
        ],
    }


def test_evidence_and_alternatives_pass_through(client, house):
    response = client.post("/api/proposals", json=body(house))

    assert response.status_code == 201, response.text
    create = response.json()["operations"][0]
    assert create["evidence"] == [PASSAGE]
    assert create["alternatives"] == [
        {
            "kind": "existing",
            "entity_id": house["fridge"],
            "similarity": 0.93,
            "title": "Kitchen refrigerator",
        }
    ]
    assert create["matched"] is False
    fetched = client.get(f"/api/proposals/{response.json()['id']}").json()
    assert fetched["operations"][0]["alternatives"] == create["alternatives"]


def test_a_malformed_passage_is_refused_with_its_seq(client, house):
    response = client.post(
        "/api/proposals", json=body(house, evidence=[{**PASSAGE, "start": 50, "end": 10}])
    )

    assert response.status_code == 422
    [error] = response.json()["detail"]["errors"]
    assert error["seq"] == 1 and "before its start" in error["message"]


@pytest.mark.parametrize("key", ["page", "start", "end"])
def test_an_offset_too_large_to_store_is_refused(client, house, key):
    response = client.post(
        "/api/proposals", json=body(house, evidence=[{**PASSAGE, "end": 10**12, key: 10**20}])
    )

    assert response.status_code == 422
    [error] = response.json()["detail"]["errors"]
    assert (error["seq"], error["code"]) == (1, "invalid")
    assert client.get("/api/proposals").json()["total"] == 0


def test_a_malformed_alternative_is_refused(client, house):
    response = client.post(
        "/api/proposals",
        json=body(house, {"kind": "existing", "entity_id": house["fridge"], "title": "x"}),
    )

    assert response.status_code == 422


def test_use_existing_applies_and_both_sources_routes_read_provenance(client, house):
    proposal = client.post("/api/proposals", json=body(house)).json()
    create, relate = proposal["operations"]

    response = client.post(
        f"/api/proposals/{proposal['id']}/apply",
        json={
            "operation_ids": [create["id"], relate["id"]],
            "chosen_alternatives": {
                create["id"]: {"kind": "existing", "entity_id": house["fridge"]}
            },
        },
    )

    assert response.status_code == 200, response.text
    create, relate = response.json()["operations"]
    assert (create["status"], create["matched"], create["result_entity_id"]) == (
        "applied",
        True,
        house["fridge"],
    )
    relationship = client.get(f"/api/relationships/{relate['result_entity_id']}").json()
    assert relationship["source_id"] == house["fridge"]

    sources = client.get(f"/api/individuals/{house['fridge']}/sources")
    assert sources.status_code == 200
    [row] = sources.json()
    assert {k: row[k] for k in ("source_id", "page", "start", "end", "quote")} == PASSAGE
    assert (row["entity_kind"], row["proposal_id"], row["op_seq"]) == (
        "individual",
        proposal["id"],
        1,
    )
    [edge] = client.get(f"/api/relationships/{relate['result_entity_id']}/sources").json()
    assert (edge["entity_kind"], edge["quote"], edge["op_seq"]) == ("relationship", "made by", 2)

    assert client.post(f"/api/proposals/{proposal['id']}/revert").status_code == 200
    assert client.get(f"/api/individuals/{house['fridge']}/sources").json() == []


def test_an_individual_without_provenance_has_no_sources(client, house):
    response = client.get(f"/api/individuals/{house['whirlpool']}/sources")

    assert (response.status_code, response.json()) == (200, [])


@pytest.mark.parametrize("path", ["individuals", "relationships"])
def test_sources_of_an_unknown_entity_are_404(client, path):
    assert client.get(f"/api/{path}/missing/sources").status_code == 404


def test_an_extraction_operation_without_a_passage_is_flagged(client, house):
    """#1575: an extraction from a source flags each operation that cites no passage in it."""
    service = client.app.state.proposal_service

    def create(seq, title, evidence):
        return OperationDraft(
            seq=seq,
            op="create",
            kind="individual",
            fields={"class_ids": [house["appliance"]], "title": title},
            evidence=evidence,
        )

    extraction = service.propose(
        house["taxonomy"],
        "Extraction: manual",
        [create(1, "Fridge", [PASSAGE]), create(2, "Pacemaker", [{"quote": "pacemaker"}])],
        ProposalSource.PIPELINE,
        client_metadata={"source_id": SOURCE, "pipeline": "individual_extraction"},
    )
    by_hand = client.post("/api/proposals", json=body(house, evidence=()))

    fetched = client.get(f"/api/proposals/{extraction.id}").json()
    assert [o["no_passage"] for o in fetched["operations"]] == [False, True]
    assert [o["no_passage"] for o in by_hand.json()["operations"]] == [False, False]
