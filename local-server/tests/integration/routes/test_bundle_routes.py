"""
Integration tests for GET /api/v1/interchange/bundles/{taxonomy_id} (#1363):
bundle export over REST against a real SQLite workspace loaded with the House
fixture bundle.
"""

import os
import sys
from pathlib import Path

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.web.interchange_routes import router
from domain.interchange.bundle import BundleExporter, load_bundle
from scripts.import_bundle import build_import_service, read_bundle
from tests.fakes.fake_embedding_service import FakeEmbeddingService

HOUSE_BUNDLE = Path(__file__).parent.parent / "fixtures" / "bundles" / "house.bundle.json"


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture()
def service(session_factory):
    return build_import_service(session_factory, FakeEmbeddingService())


@pytest.fixture()
def house_id(service, repo):
    load_bundle(service, repo, read_bundle(HOUSE_BUNDLE))
    return repo.get_by_identifier("house").id


@pytest.fixture()
def client(repo):
    app = FastAPI()
    app.include_router(router)
    app.state.ontology_repo = repo
    return TestClient(app)


def _url(taxonomy_id):
    return f"/api/v1/interchange/bundles/{taxonomy_id}"


def test_returns_the_taxonomy_as_a_bundle(client, repo, house_id):
    response = client.get(_url(house_id))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    bundle = response.json()
    assert bundle == BundleExporter(repo).export(house_id)
    assert bundle["format"] == "context-studio-bundle"
    assert bundle["source"] == "house"
    assert bundle["taxonomy"]["identifier"] == "house"


def test_exported_bundle_reloads_without_changes(client, service, repo, house_id):
    bundle = client.get(_url(house_id)).json()

    summary = load_bundle(service, repo, bundle)

    assert summary.changed == 0, summary.counts
    assert summary.stale == []


def test_source_is_passed_to_the_exporter(client, repo, house_id):
    response = client.get(_url(house_id), params={"source": "elsewhere"})

    assert response.status_code == 200
    assert response.json() == BundleExporter(repo).export(house_id, "elsewhere")
    assert response.json()["source"] == "elsewhere"


def test_unknown_taxonomy_is_404(client):
    response = client.get(_url("00000000-0000-4000-8000-000000000000"))

    assert response.status_code == 404
    assert "00000000-0000-4000-8000-000000000000" in response.json()["detail"]


def test_id_of_a_non_taxonomy_is_404(client, repo, house_id):
    scheme = repo.get_by_identifier("house_vocabulary")

    response = client.get(_url(scheme.id))

    assert response.status_code == 404


def test_class_without_an_identifier_is_409_with_the_exporter_message(
    client, service, repo, house_id
):
    scheme = repo.get_by_identifier("house_vocabulary")
    service.create_class(concept_scheme_id=scheme.id, title="Attic")

    response = client.get(_url(house_id))

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "no stored identifier" in detail
    assert "Class 'Attic'" in detail
