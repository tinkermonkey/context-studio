"""
Integration tests (#1364): a bundle import is a change proposal on real SQLite.
The real House bundle with kits lands as one proposal whose change events carry
its id; a re-import proposes nothing; dropped entities are pending deletes that,
once applied, revert with the rest; and POST /api/v1/interchange/bundles plans,
dry-runs and applies.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import ChangeEvent
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.web.bundle_routes import router
from domain.interchange.bundle import BundleExporter
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
from scripts.import_bundle import build_bundle_importer
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.interchange.test_bundle import _workspace, house_with_kits


@pytest.fixture()
def session_factory(tmp_path):
    factory = _workspace(tmp_path / "local.db")
    yield factory
    factory.kw["bind"].dispose()


@pytest.fixture()
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture()
def importer(session_factory):
    return build_bundle_importer(session_factory, FakeEmbeddingService())


def _events(session_factory, run_id=None):
    with session_factory() as session:
        query = session.query(ChangeEvent)
        if run_id is not None:
            query = query.filter(ChangeEvent.batch_run_id == run_id)
        return query.count()


def _kit(repo):
    """Kit attributes by (activity, resource) title."""
    activity = repo.get_by_identifier("house_activity")
    return {
        (ind.title, repo.get_individual(rel.target_id).title): rel.attributes
        for ind in repo.list_individuals(class_id=activity.id, limit=None)
        for rel in repo.list_relationships(source_id=ind.id, limit=None)
        if rel.attributes
    }


def test_house_with_kits_imports_as_one_proposal_and_round_trips(importer, repo, session_factory):
    house = house_with_kits()

    result = importer.import_bundle(house, apply=True, file_name="house.bundle.json")

    proposal = result.proposal
    assert result.taxonomy_created
    assert proposal.source is ProposalSource.BUNDLE
    assert proposal.status is ProposalStatus.DONE
    assert {o.status for o in proposal.operations} == {OperationStatus.APPLIED}
    assert {o.scope for o in proposal.operations} == {ChangeScope.ADDITIVE}
    assert len(proposal.operations) == len(result.plan.operations) > 100
    assert _events(session_factory, proposal.id) >= len(proposal.operations)
    assert _kit(repo)[("Hang a picture", "Picture hooks")] == {
        "quantity": 2,
        "unit": "each",
        "optional": False,
    }

    # load -> export -> load proposes nothing and writes nothing.
    before = _events(session_factory)
    exported = BundleExporter(repo).export(proposal.taxonomy_id, source="house")
    again = importer.import_bundle(exported, apply=True)
    assert again.proposal is None and again.plan.operations == []
    assert _events(session_factory) == before


def test_dropped_entities_wait_for_review_and_revert_with_the_proposal(importer, repo):
    importer.import_bundle(house_with_kits(), apply=True)
    smaller = house_with_kits()
    smaller["individuals"] = [i for i in smaller["individuals"] if i["id"] != "kit_level"]
    smaller["relationships"] = [r for r in smaller["relationships"] if r["target"] != "kit_level"]
    smaller["relationships"][-1]["attributes"] = {"quantity": 1, "unit": "each", "optional": True}
    level = next(
        i
        for i in repo.list_individuals(
            class_id=repo.get_by_identifier("house_resource_tool").id, limit=None
        )
        if i.title == "Level"
    )

    result = importer.import_bundle(smaller, apply=True)

    ops = {(o.op, o.kind): o for o in result.proposal.operations}
    delete = ops[(OperationType.DELETE, OperationKind.INDIVIDUAL)]
    assert (delete.target_id, delete.status) == (level.id, OperationStatus.PENDING)
    assert ops[(OperationType.UPDATE, OperationKind.RELATIONSHIP)].status is (
        OperationStatus.APPLIED
    )
    assert result.proposal.status is ProposalStatus.OPEN
    assert result.plan.deletes == [
        "Individual 'Level' (kit_level)",
        "Relationship 'Hang a shelf' house_activity_requires_resource 'Level'",
    ]

    proposals = importer._proposals
    pending = [o.id for o in result.proposal.pending]
    assert proposals.apply(result.proposal.id, pending).status is ProposalStatus.DONE
    assert repo.get_individual(level.id) is None
    assert _kit(repo)[("Hang a picture", "Hammer")] == {
        "quantity": 1,
        "unit": "each",
        "optional": True,
    }

    proposals.revert(result.proposal.id)

    assert repo.get_individual(level.id) is not None
    assert _kit(repo)[("Hang a shelf", "Level")] == {"optional": True}
    assert _kit(repo)[("Hang a picture", "Hammer")] == {"quantity": 1, "unit": "each"}


def test_dry_run_stores_nothing(importer, repo, session_factory):
    importer.import_bundle(house_with_kits(), apply=True)
    changed = house_with_kits()
    changed["taxonomy"]["title"] = "Home"
    before = _events(session_factory)

    result = importer.import_bundle(changed, dry_run=True)

    assert result.dry_run and [o.op for o in result.proposal.operations] == [OperationType.UPDATE]
    assert _events(session_factory) == before
    assert repo.get_by_identifier("house").title == "House"
    assert len(SQLiteChangeProposalRepository(session_factory).list_proposals()) == 1


# ------------------------------------------------------------------- route


@pytest.fixture()
def client(importer):
    app = FastAPI()
    app.include_router(router)
    app.state.bundle_import_service = importer
    app.state.proposal_service = importer._proposals
    return TestClient(app)


def test_route_dry_run_then_apply_then_nothing_to_do(client, repo):
    house = house_with_kits()

    dry = client.post("/api/v1/interchange/bundles", params={"dry_run": True}, json=house)
    assert dry.status_code == 200, dry.text
    body = dry.json()
    assert body["dry_run"] and body["taxonomy_created"] and body["proposal"] is None
    assert body["operation_count"] > 100
    assert repo.get_by_identifier("house") is None

    applied = client.post(
        "/api/v1/interchange/bundles",
        params={"apply": True, "file_name": "house.bundle.json"},
        json=house,
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["proposal"]["status"] == "done"
    assert body["proposal"]["source"] == "bundle"
    assert body["proposal"]["source_detail"] == "bundle:house"
    assert "from house.bundle.json" in body["proposal"]["rationale"]
    assert body["counts"]["relationship"]["created"] == len(house["relationships"])

    again = client.post("/api/v1/interchange/bundles", params={"apply": True}, json=house)
    assert again.json()["proposal"] is None and again.json()["operation_count"] == 0


def test_route_refuses_a_bad_bundle_with_422(client):
    bad = copy.deepcopy(house_with_kits())
    bad["relationships"][-1]["attributes"] = {"brand": "Acme"}

    response = client.post("/api/v1/interchange/bundles", json=bad)

    assert response.status_code == 422
    assert "brand" in response.json()["detail"]
    not_a_bundle = client.post("/api/v1/interchange/bundles", json={"format": "x"})
    assert not_a_bundle.status_code == 422


def test_changes_are_recorded_against_the_proposal(importer, session_factory):
    result = importer.import_bundle(house_with_kits(), apply=True)
    changes = SQLiteChangeRepository(session_factory).get_changes(
        batch_run_id=result.proposal.id, limit=None
    )
    kinds = {e.entity_type for e in changes.events}
    assert {"concept_scheme", "class", "property_definition", "individual", "relationship"} <= kinds


def test_route_maps_a_concurrent_write_to_409(client, importer, monkeypatch):
    """F7: another import creating the same taxonomy meanwhile is a conflict, not a 500."""

    def collide(*args, **kwargs):
        raise IntegrityError("INSERT INTO ontology_entities", {}, Exception("UNIQUE constraint"))

    monkeypatch.setattr(importer, "import_bundle", collide)

    response = client.post("/api/v1/interchange/bundles", json=house_with_kits())

    assert response.status_code == 409
    assert "import again" in response.json()["detail"]
