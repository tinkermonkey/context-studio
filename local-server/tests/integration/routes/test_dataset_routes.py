"""
Integration tests (#1486): datasets in the REST API. Two datasets over one
schema: each lists, counts and graphs only its own data, and the datasets
endpoints list (with sizes), create and delete (with what was removed).
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from adapters.web.graph_routes import router as graph_router
from adapters.web.ontology_routes import router as ontology_router
from domain.graph.services import GraphAnalysisService
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher


@pytest.fixture()
def parts():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        shared = SharedSessionFactory(sessionmaker(bind=engine))
        repo = SQLiteOntologyRepository(shared)
        service = OntologyService(
            repo,
            FakeEmbeddingService(),
            FakeEventPublisher(),
            transaction_scope=SqliteTransactionScope(shared),
        )
        app = FastAPI()
        app.include_router(ontology_router)
        app.include_router(graph_router)
        app.state.ontology_service = service
        app.state.graph_service = GraphAnalysisService(
            repository=repo, graph_engine=NetworkXGraphEngine(), query_engine=RDFLibQueryEngine()
        )
        yield service, TestClient(app)
        engine.dispose()


@pytest.fixture()
def model(parts):
    service, client = parts
    taxonomy = service.create_taxonomy(title="Documentation Robotics")
    scheme = service.create_scheme(taxonomy.id, title="Application")
    component = service.create_class(scheme.id, "Component")
    uses = service.create_property_definition("uses", "uses", domain_class_id=component.id)
    ids = {}
    for identifier in ("alpha", "beta"):
        dataset = client.post(
            "/api/datasets",
            json={"taxonomy_id": taxonomy.id, "identifier": identifier, "title": identifier},
        ).json()
        gateway = client.post(
            "/api/individuals",
            json={"class_ids": [component.id], "title": "Gateway", "dataset_id": dataset["id"]},
        ).json()
        router_ = service.create_individual(component.id, "Router", dataset_id=dataset["id"])
        service.create_relationship(gateway["id"], router_.id, uses.id)
        ids[identifier] = {"dataset": dataset["id"], "gateway": gateway["id"]}
    return {"taxonomy": taxonomy, "scheme": scheme, "component": component, **ids}


def test_datasets_are_listed_per_taxonomy_with_their_size(parts, model):
    _, client = parts

    listed = client.get("/api/datasets", params={"taxonomy_id": model["taxonomy"].id}).json()

    assert [(d["identifier"], d["individual_count"], d["relationship_count"]) for d in listed] == [
        ("alpha", 2, 1),
        ("beta", 2, 1),
    ]
    assert listed[0]["yields_to_schema"] is False


def test_a_duplicate_identifier_is_refused(parts, model):
    _, client = parts

    response = client.post(
        "/api/datasets",
        json={"taxonomy_id": model["taxonomy"].id, "identifier": "alpha", "title": "Again"},
    )

    assert response.status_code == 409


def test_individuals_relationships_and_counts_take_a_dataset(parts, model):
    _, client = parts
    alpha = model["alpha"]["dataset"]

    individuals = client.get("/api/individuals", params={"dataset_id": alpha}).json()
    assert individuals["total"] == 2
    assert {i["dataset_id"] for i in individuals["items"]} == {alpha}
    assert client.get("/api/individuals").json()["total"] == 4
    assert client.get("/api/relationships", params={"dataset_id": alpha}).json()["total"] == 1
    [scheme_counts] = client.get(
        f"/api/taxonomies/{model['taxonomy'].id}/scheme-counts", params={"dataset_id": alpha}
    ).json()
    assert scheme_counts["individual_count"] == 2
    [class_counts] = client.get(
        f"/api/schemes/{model['scheme'].id}/class-counts", params={"dataset_id": alpha}
    ).json()
    assert (class_counts["individual_count"], class_counts["relationship_count"]) == (2, 1)


def test_creating_an_individual_needs_a_dataset_once_there_are_several(parts, model):
    _, client = parts

    response = client.post(
        "/api/individuals", json={"class_ids": [model["component"].id], "title": "Cache"}
    )

    assert response.status_code == 422
    assert "alpha, beta" in response.json()["detail"]


def test_the_graph_view_and_sparql_show_one_dataset(parts, model):
    _, client = parts
    alpha, beta = model["alpha"], model["beta"]

    view = client.get("/api/graph/view", params={"dataset_id": alpha["dataset"]}).json()
    node_ids = {n["id"] for n in view["nodes"]}
    assert alpha["gateway"] in node_ids
    assert beta["gateway"] not in node_ids
    assert model["component"].id in node_ids  # the schema is shared
    assert sum(1 for e in view["edges"] if e["edge_type"] == "relationship") == 1
    everything = client.get("/api/graph/view").json()
    assert sum(1 for e in everything["edges"] if e["edge_type"] == "relationship") == 2

    query = "SELECT ?s WHERE { ?s ?p ?o }"
    scoped = client.post("/api/graph/sparql", json={"query": query, "dataset_id": beta["dataset"]})
    whole = client.post("/api/graph/sparql", json={"query": query})
    assert scoped.status_code == 200
    assert scoped.json()["triple_count"] < whole.json()["triple_count"]


def test_deleting_a_dataset_removes_its_data_and_says_what(parts, model):
    _, client = parts

    response = client.delete(f"/api/datasets/{model['beta']['dataset']}")

    assert response.status_code == 200
    assert response.json()["individual_count"] == 2
    assert response.json()["relationship_count"] == 1
    assert client.get("/api/individuals").json()["total"] == 2
    assert client.delete(f"/api/datasets/{model['beta']['dataset']}").status_code == 404
