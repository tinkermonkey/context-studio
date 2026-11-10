"""
Integration tests for a class's operational definition (#1513) over real SQLite:
it persists, a proposal sets, clears and reverts it, and REST reads and writes it.
"""

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
from adapters.web.dependencies import get_ontology_service
from adapters.web.ontology_routes import router
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationStatus, ProposalSource
from domain.versioning.proposals import OperationType as T
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder


@pytest.fixture()
def world():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        shared = SharedSessionFactory(sessionmaker(bind=engine))
        repo = SQLiteOntologyRepository(session_factory=shared)
        change_repo = SQLiteChangeRepository(session_factory=shared)
        publisher = InProcessEventPublisher()
        wire_change_recorder(publisher, change_repo)
        ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
        proposals = ProposalService(
            SQLiteChangeProposalRepository(shared),
            ontology,
            repo,
            RevertService(
                change_repo=change_repo,
                ontology_repo=repo,
                transaction_scope=SqliteTransactionScope(shared),
            ),
        )
        taxonomy = ontology.create_taxonomy(title="DR", identifier="dr")
        scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="API")
        operation = ontology.create_class(scheme.id, "Operation", identifier="api_operation")
        endpoint = ontology.create_class(scheme.id, "Endpoint", identifier="api_endpoint")
        yield {
            "ontology": ontology,
            "repo": repo,
            "proposals": proposals,
            "taxonomy": taxonomy,
            "scheme": scheme,
            "operation": operation,
            "endpoint": endpoint,
        }
        engine.dispose()


DEFINITION = {
    "evidence_signals": ["an HTTP method on a path", "an operationId"],
    "standard_reference": "OpenAPI 3.0 Operation Object",
}


def test_the_definition_persists(world):
    repo, ontology = world["repo"], world["ontology"]
    distinguish = [{"class_id": world["endpoint"].id, "when": "it is the path, not the action"}]

    ontology.update_class(world["operation"].id, distinguish_from=distinguish, **DEFINITION)

    stored = repo.get_class(world["operation"].id)
    assert stored.distinguish_from == distinguish
    assert stored.evidence_signals == DEFINITION["evidence_signals"]
    assert stored.standard_reference == DEFINITION["standard_reference"]
    # A class without a definition reads back empty
    assert repo.get_class(world["endpoint"].id).distinguish_from == []
    assert repo.get_class(world["endpoint"].id).evidence_signals == []


def test_a_proposal_sets_clears_and_reverts_the_definition(world):
    proposals, repo = world["proposals"], world["repo"]
    operation, endpoint = world["operation"], world["endpoint"]
    distinguish = [{"class_id": endpoint.id, "when": "it is the path, not the action"}]

    setting = proposals.propose(
        world["taxonomy"].id,
        "Operational definition",
        [
            OperationDraft(
                1,
                T.UPDATE,
                K.CLASS,
                operation.id,
                fields={"distinguish_from": distinguish, **DEFINITION},
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.CLASS,
                fields={
                    "concept_scheme_id": world["scheme"].id,
                    "title": "Callback",
                    "distinguish_from": [{"class_id": operation.id, "when": "a client calls it"}],
                    "evidence_signals": ["a webhook URL"],
                },
            ),
        ],
        ProposalSource.MCP,
    )
    applied = proposals.apply(setting.id, [o.id for o in setting.operations])
    assert [o.status for o in applied.operations] == [OperationStatus.APPLIED] * 2, [
        o.reason for o in applied.operations
    ]
    assert repo.get_class(operation.id).distinguish_from == distinguish
    callback = repo.get_class(applied.operations[1].result_entity_id)
    assert callback.evidence_signals == ["a webhook URL"]

    clearing = proposals.propose(
        world["taxonomy"].id,
        "Clear it",
        [
            OperationDraft(
                1,
                T.UPDATE,
                K.CLASS,
                operation.id,
                fields={
                    "distinguish_from": None,
                    "evidence_signals": None,
                    "standard_reference": None,
                },
            )
        ],
        ProposalSource.MCP,
    )
    cleared = proposals.apply(clearing.id, [clearing.operations[0].id])
    assert cleared.operations[0].status is OperationStatus.APPLIED, cleared.operations[0].reason
    after = repo.get_class(operation.id)
    assert (after.distinguish_from, after.evidence_signals, after.standard_reference) == (
        [],
        [],
        None,
    )

    proposals.revert(clearing.id)
    restored = repo.get_class(operation.id)
    assert restored.distinguish_from == distinguish
    assert restored.standard_reference == DEFINITION["standard_reference"]


def test_a_proposal_naming_another_taxonomys_class_fails_that_operation(world):
    ontology, proposals = world["ontology"], world["proposals"]
    house = ontology.create_taxonomy(title="House", identifier="house")
    room = ontology.create_class(
        ontology.create_scheme(taxonomy_id=house.id, title="Rooms").id, "Room"
    )
    proposal = proposals.propose(
        world["taxonomy"].id,
        "Bad",
        [
            OperationDraft(
                1,
                T.UPDATE,
                K.CLASS,
                world["operation"].id,
                fields={"distinguish_from": [{"class_id": room.id, "when": "x"}]},
            )
        ],
        ProposalSource.MCP,
    )
    result = proposals.apply(proposal.id, [proposal.operations[0].id])
    assert result.operations[0].status is OperationStatus.FAILED
    assert "not a class of this taxonomy" in result.operations[0].reason


def test_a_malformed_definition_is_refused_when_proposed(world):
    with pytest.raises(Exception, match="distinguish_from"):
        world["proposals"].propose(
            world["taxonomy"].id,
            "Bad",
            [
                OperationDraft(
                    1,
                    T.UPDATE,
                    K.CLASS,
                    world["operation"].id,
                    fields={"distinguish_from": "the endpoint"},
                )
            ],
            ProposalSource.MCP,
        )


def test_rest_reads_and_writes_the_definition(world):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_ontology_service] = lambda: world["ontology"]
    client = TestClient(app)
    operation, endpoint = world["operation"], world["endpoint"]

    updated = client.put(
        f"/api/classes/{operation.id}",
        json={"distinguish_from": [{"class_id": endpoint.id, "when": "the path"}], **DEFINITION},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["distinguish_from"] == [{"class_id": endpoint.id, "when": "the path"}]
    assert body["evidence_signals"] == DEFINITION["evidence_signals"]
    assert body["standard_reference"] == DEFINITION["standard_reference"]

    # A title-only update leaves the definition alone; empty values clear it
    assert (
        client.put(f"/api/classes/{operation.id}", json={"title": "Op"}).json()[
            "standard_reference"
        ]
        == DEFINITION["standard_reference"]
    )
    cleared = client.put(
        f"/api/classes/{operation.id}",
        json={"distinguish_from": [], "evidence_signals": [], "standard_reference": ""},
    ).json()
    assert (cleared["distinguish_from"], cleared["evidence_signals"]) == ([], [])
    assert cleared["standard_reference"] is None

    created = client.post(
        f"/api/schemes/{world['scheme'].id}/classes",
        json={"title": "Callback", "evidence_signals": ["a webhook URL"]},
    )
    assert created.status_code in (200, 201), created.text
    assert created.json()["evidence_signals"] == ["a webhook URL"]

    bad = client.put(
        f"/api/classes/{operation.id}",
        json={"distinguish_from": [{"class_id": "nope", "when": "x"}]},
    )
    assert bad.status_code == 400, bad.text
