"""
Integration tests for GET /api/graph/view against a real SQLite repository.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.web.graph_routes import router
from domain.graph.services import GraphAnalysisService
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)

TAX_ID = "00000000-0000-0000-0000-000000000001"
LAYER_A = "00000000-0000-0000-0000-00000000000a"
LAYER_B = "00000000-0000-0000-0000-00000000000b"
CLS_SERVICE = "00000000-0000-0000-0000-000000000c01"
CLS_OPERATION = "00000000-0000-0000-0000-000000000c02"
PROP_ID = "00000000-0000-0000-0000-000000000f01"
IND_A = "00000000-0000-0000-0000-000000000d01"
IND_B = "00000000-0000-0000-0000-000000000d02"
REL_ID = "00000000-0000-0000-0000-000000000e01"


@pytest.fixture
def repository():
    """Real SQLite repository on a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'test.db'}")
        Base.metadata.create_all(engine)
        yield SQLiteOntologyRepository(sessionmaker(bind=engine))
        engine.dispose()


def _client(repository) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.graph_service = GraphAnalysisService(
        repository=repository,
        graph_engine=NetworkXGraphEngine(),
        query_engine=RDFLibQueryEngine(),
    )
    return TestClient(app)


@pytest.fixture
def populated_repository(repository):
    """Two layers, a cross-layer schema edge, and an individual with two classes."""
    repository.save_taxonomy(Taxonomy(id=TAX_ID, identifier="dr_spec", title="DR"))
    repository.save_concept_scheme(
        ConceptScheme(id=LAYER_A, taxonomy_id=TAX_ID, identifier="business", title="Business")
    )
    repository.save_concept_scheme(
        ConceptScheme(id=LAYER_B, taxonomy_id=TAX_ID, identifier="api", title="API")
    )
    repository.save_class(
        Class(
            id=CLS_SERVICE,
            concept_scheme_id=LAYER_A,
            taxonomy_id=TAX_ID,
            identifier="business_service",
            title="Business Service",
        )
    )
    repository.save_class(
        Class(
            id=CLS_OPERATION,
            concept_scheme_id=LAYER_B,
            taxonomy_id=TAX_ID,
            identifier="api_operation",
            title="Operation",
        )
    )
    repository.save_property_definition(
        PropertyDefinition(
            id=PROP_ID,
            identifier="service_realized_by_operation",
            title="realized by",
            domain_class_id=CLS_SERVICE,
            range_class_id=CLS_OPERATION,
        )
    )
    repository.save_individual(
        Individual(id=IND_A, class_ids=[CLS_OPERATION, CLS_SERVICE], title="POST /orders")
    )
    repository.save_individual(Individual(id=IND_B, class_ids=[CLS_SERVICE], title="Checkout"))
    repository.save_relationship(
        Relationship(id=REL_ID, source_id=IND_B, target_id=IND_A, property_definition_id=PROP_ID)
    )
    return repository


class TestGraphViewEndpoint:
    """GET /api/graph/view."""

    def test_returns_layers_nodes_and_typed_edges(self, populated_repository):
        response = _client(populated_repository).get("/api/graph/view")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert [t["identifier"] for t in body["taxonomies"]] == ["dr_spec"]
        assert {layer["id"] for layer in body["layers"]} == {LAYER_A, LAYER_B}

        nodes = {n["id"]: n for n in body["nodes"]}
        assert set(nodes) == {CLS_SERVICE, CLS_OPERATION, IND_A, IND_B}
        assert nodes[CLS_SERVICE]["node_type"] == "class"
        assert nodes[CLS_SERVICE]["concept_scheme_id"] == LAYER_A
        assert nodes[IND_A]["node_type"] == "individual"
        assert nodes[IND_A]["class_ids"] == [CLS_OPERATION, CLS_SERVICE]
        assert nodes[IND_A]["concept_scheme_id"] == LAYER_B

        edge_types = {e["id"]: e["edge_type"] for e in body["edges"]}
        assert edge_types[REL_ID] == "relationship"
        assert edge_types[PROP_ID] == "schema"
        assert edge_types[f"{IND_A}:instance_of:{CLS_OPERATION}"] == "instance_of"
        assert len(edge_types) == 5

        schema_edge = next(e for e in body["edges"] if e["id"] == PROP_ID)
        assert schema_edge["predicate"] == "realized by"
        assert (schema_edge["source"], schema_edge["target"]) == (CLS_SERVICE, CLS_OPERATION)

    def test_empty_database_returns_empty_view(self, repository):
        response = _client(repository).get("/api/graph/view")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"taxonomies": [], "layers": [], "nodes": [], "edges": []}
