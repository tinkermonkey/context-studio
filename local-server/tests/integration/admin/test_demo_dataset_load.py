"""
Integration tests for the demo dataset loader.

Exercises the full flow:
    HTTP route -> LoadDemoDataset use case -> CanonDemoDatasetLoader adapter
    -> SQLiteOntologyRepository -> SQLite

Verifies that loading the curated software-architecture canon produces a
non-trivial ontology slice with valid identifier slugs, populated parent_class_id
chains, attached external references, and a stamped source_run_id for provenance.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from adapters.demo import CanonDemoDatasetLoader
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.web.admin_routes import router
from domain.admin.demo_dataset_service import LoadDemoDataset
from tests.utils.canon_assertions import (
    assert_color_present,
    assert_external_references_populated,
    assert_identifier_slugs_populated,
    assert_lexical_senses_distinguish,
    assert_source_run_id_lineage,
    load_canon,
)


CANON_ROOT = Path(__file__).resolve().parents[3] / "datafiles" / "canon"


@pytest.fixture
def ontology_repo():
    """Create a temp-DB-backed SQLiteOntologyRepository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_demo.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        repo = SQLiteOntologyRepository(session_factory)
        yield repo
        engine.dispose()


@pytest.fixture
def load_demo_dataset(ontology_repo):
    """Create a LoadDemoDataset use case wired to the real canon directory."""
    loader = CanonDemoDatasetLoader(canon_root=CANON_ROOT, ontology_repo=ontology_repo)
    return LoadDemoDataset(loader=loader)


@pytest.fixture
def client(load_demo_dataset):
    """Create a TestClient with the demo loader wired in."""
    app = FastAPI()
    app.include_router(router)
    app.state.load_demo_dataset = load_demo_dataset
    return TestClient(app)


class TestListDemoDatasets:
    """Tests for GET /api/v1/admin/demo-datasets."""

    def test_list_demo_datasets_includes_software_architecture(self, client):
        """GET /api/v1/admin/demo-datasets returns the software-architecture entry."""
        response = client.get("/api/v1/admin/demo-datasets")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        names = {entry["name"] for entry in body}
        assert "software-architecture" in names

        software_arch = next(e for e in body if e["name"] == "software-architecture")
        assert software_arch["title"]
        assert software_arch["description"]
        assert software_arch["paper_count"] >= 10
        assert software_arch["taxonomy_count"] >= 1
        assert software_arch["class_count"] >= 20


class TestLoadDemoDataset:
    """Tests for POST /api/v1/admin/demo-datasets/{name}/load."""

    def test_load_software_architecture_creates_canon_ontology(self, client, ontology_repo):
        """Loading the dataset materializes the gold ontology slice."""
        response = client.post("/api/v1/admin/demo-datasets/software-architecture/load")
        assert response.status_code == 201, response.text
        body = response.json()

        # Result counts are populated and non-trivial
        assert body["dataset_name"] == "software-architecture"
        assert body["source_run_id"].startswith("demo:software-architecture:")
        assert body["taxonomies"] == 1
        assert body["concept_schemes"] >= 5
        assert body["classes"] >= 20
        assert body["property_definitions"] >= 5
        assert body["external_references"] >= 1

        # Repo reflects what the route reports
        taxonomies = ontology_repo.list_taxonomies()
        assert len(taxonomies) == 1
        assert taxonomies[0].identifier == "software_architecture"
        assert taxonomies[0].color == "#2b6cb0"

        # The canon-assertion helpers run cleanly on the materialized DB
        assert_identifier_slugs_populated(ontology_repo)
        assert_color_present(ontology_repo, for_node_types=["taxonomy", "concept_scheme"])

        # source_run_id is stamped on a sample class
        rest_class = ontology_repo.get_by_identifier("rest")
        assert rest_class is not None
        assert rest_class.source_run_id == body["source_run_id"]
        # parent_class_id is wired by slug resolution
        assert rest_class.parent_class_id is not None

        # External refs are attached from the paper fixtures
        assert len(rest_class.external_references) >= 2
        sources = {ref.source for ref in rest_class.external_references}
        assert {"dbpedia", "wikidata"} <= sources

        # Canon bundle agreement: every canon class slug is present in the repo
        canon = load_canon(CANON_ROOT / "software_architecture")
        for class_slug in canon.class_identifiers:
            entity = ontology_repo.get_by_identifier(class_slug)
            assert entity is not None, f"Class slug '{class_slug}' missing from repo"

    def test_load_unknown_returns_404(self, client):
        """POST with an unregistered dataset name returns 404."""
        response = client.post("/api/v1/admin/demo-datasets/does-not-exist/load")
        assert response.status_code == 404
        body = response.json()
        assert "does-not-exist" in body["detail"]

    def test_load_twice_returns_409(self, client):
        """POST against an already-loaded workspace returns 409."""
        first = client.post("/api/v1/admin/demo-datasets/software-architecture/load")
        assert first.status_code == 201

        second = client.post("/api/v1/admin/demo-datasets/software-architecture/load")
        assert second.status_code == 409

    def test_source_run_id_lineage_propagates_to_every_persisted_class(
        self, client, ontology_repo
    ):
        """
        Provenance contract: every class in the loaded ontology must carry the
        run's `source_run_id`. Catches regressions where the loader stamps
        only some entities (e.g. forgets the topologically-sorted tail).
        """
        response = client.post("/api/v1/admin/demo-datasets/software-architecture/load")
        assert response.status_code == 201
        run_id = response.json()["source_run_id"]

        # Demand at least 20 classes carry the lineage — well above the canon's
        # ~60-class total, leaving headroom for canon growth.
        assert_source_run_id_lineage(ontology_repo, run_id=run_id, min_count=20)

    def test_external_references_coverage_meets_minimum(self, client, ontology_repo):
        """
        Reference grounding contract: a meaningful fraction of the canon's
        classes must have external_references attached. Catches regressions
        where the loader silently skips ref attachment for a subset of papers
        (e.g. case-sensitivity bug in the slug→paper mapping).
        """
        response = client.post("/api/v1/admin/demo-datasets/software-architecture/load")
        assert response.status_code == 201

        # The canon corpus documents external_refs for ~14 of ~60 classes
        # (~23%). Floor at 0.15 leaves room for canon curation without making
        # the test fragile.
        assert_external_references_populated(ontology_repo, min_coverage=0.15)

    def test_multi_sense_lexical_senses_distinguish_service_term(
        self, client, ontology_repo
    ):
        """
        Multi-sense disambiguation contract: the canon's `service` property
        definition declares 3 distinct lexical_senses (offering / microservice
        / RPC endpoint). The loader must materialize all three.

        Closes the gap surfaced by the canon benchmark's `multi_sense_ratio`
        metric. The PropertyDefinition domain entity carries a `lexical_senses`
        field (mirroring Class), the OntologyEntity unified table persists
        them via its existing `lexical_senses` JSON column, and the canon
        loader passes them through Step 3.
        """
        response = client.post("/api/v1/admin/demo-datasets/software-architecture/load")
        assert response.status_code == 201

        # `service` has 3 distinct senses in canon.json's property_definitions.
        assert_lexical_senses_distinguish(
            ontology_repo, "service", expected_sense_count=3
        )
        # `clock` has 2 distinct senses (logical vs physical).
        assert_lexical_senses_distinguish(
            ontology_repo, "clock", expected_sense_count=2
        )
