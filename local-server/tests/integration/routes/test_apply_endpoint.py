"""
Integration tests for POST /api/pipelines/runs/{run_id}/apply endpoint.

Uses a real PipelineRepository (SQLite in-memory) and FakeOntologyRepository
to verify the full apply flow without external dependencies.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.web.pipelines_routes import router
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from domain.pipelines.schema_extraction.apply_service import (
    SchemaExtractionApplyService,
)
from domain.pipelines.schema_node_connection_refinement.apply_service import (
    SchemaConnectionRefinementApplyService,
)
from domain.pipelines.schema_node_definition_refinement.apply_service import (
    SchemaDefinitionRefinementApplyService,
)
from domain.pipelines.schema_node_grounding.apply_service import (
    SchemaGroundingApplyService,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

TAXONOMY_ID = "tx-apply-test"
SCHEME_ID = "cs-apply-test"


@pytest.fixture()
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "local.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        yield SessionLocal


@pytest.fixture()
def pipeline_repo(temp_db):
    return PipelineRepository(session_factory=temp_db)


@pytest.fixture()
def batch_repo(temp_db):
    return BatchRepository(session_factory=temp_db)


@pytest.fixture()
def ontology_repo():
    r = FakeOntologyRepository()
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="test_tax", title="Apply Test Taxonomy"))
    r.save_concept_scheme(
        ConceptScheme(
            id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="test_scheme",
            title="Apply Test Scheme",
        )
    )
    return r


@pytest.fixture()
def ontology_service(ontology_repo):
    return OntologyService(
        repository=ontology_repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=FakeEventPublisher(),
    )


@pytest.fixture()
def client(pipeline_repo, batch_repo, ontology_repo, ontology_service):
    app = FastAPI()
    app.include_router(router)

    app.state.pipeline_run_repo = pipeline_repo
    app.state.batch_repo = batch_repo
    app.state.implementation_registry = MagicMock()
    app.state.config_registry = MagicMock()
    app.state.llm_router = MagicMock()
    app.state.ontology_repo = ontology_repo

    app.state.schema_extraction_apply_svc = SchemaExtractionApplyService(ontology_repo)
    app.state.individual_extraction_apply_svc = IndividualExtractionApplyService(
        ontology_service, ontology_repo
    )
    app.state.schema_grounding_apply_svc = SchemaGroundingApplyService(ontology_repo)
    app.state.schema_definition_apply_svc = SchemaDefinitionRefinementApplyService(ontology_repo)
    app.state.schema_connection_apply_svc = SchemaConnectionRefinementApplyService(ontology_repo)

    return TestClient(app)


def _create_and_complete_schema_run(pipeline_repo, candidates=None, connections=None):
    """Create a completed schema extraction run with the given output."""
    batch_id = str(uuid4())
    run = pipeline_repo.create(
        batch_run_id=batch_id,
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        implementation_id="default",
        configuration_ref="extraction-default",
        configuration_slug="extraction-default",
        configuration_version=1,
    )
    run_id = run.id
    pipeline_repo.update_status(run_id, PipelineRunStatus.COMPLETED)
    pipeline_repo.update_summaries(
        run_id,
        output_summary={
            "candidates": candidates or [],
            "connections": connections or [],
        },
    )
    return run_id


def _create_and_complete_individual_run(pipeline_repo, triples=None):
    """Create a completed individual extraction run."""
    batch_id = str(uuid4())
    run = pipeline_repo.create(
        batch_run_id=batch_id,
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        implementation_id="default",
        configuration_ref="extraction-default",
        configuration_slug="extraction-default",
        configuration_version=1,
        specific_data={"source_text_hash": "abc123"},
    )
    run_id = run.id
    pipeline_repo.update_status(run_id, PipelineRunStatus.COMPLETED)
    pipeline_repo.update_summaries(run_id, output_summary={"triples": triples or []})
    return run_id


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestApplyEndpointHappyPath:
    def test_apply_schema_extraction_returns_200(self, client, pipeline_repo):
        run_id = _create_and_complete_schema_run(pipeline_repo)
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_apply_schema_extraction_creates_classes(self, client, pipeline_repo, ontology_repo):
        run_id = _create_and_complete_schema_run(
            pipeline_repo,
            candidates=[
                {
                    "kind": "class",
                    "label": "Service",
                    "proposed_definition": "A service",
                    "confidence": 0.9,
                },
                {"kind": "class", "label": "Client", "confidence": 0.8},
            ],
        )
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["classes_created"] == 2
        assert body["classes_skipped"] == 0
        assert body["run_id"] == run_id
        assert body["pipeline_type"] == "schema_extraction"

        classes = ontology_repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)
        assert len(classes) == 2
        for cls in classes:
            assert cls.status.value == "draft"
            assert cls.source_run_id == run_id

    def test_apply_individual_extraction_returns_200(self, client, pipeline_repo):
        run_id = _create_and_complete_individual_run(pipeline_repo)
        response = client.post(f"/api/pipelines/runs/{run_id}/apply")
        assert response.status_code == status.HTTP_200_OK

    def test_apply_individual_extraction_populates_recognition_index(
        self, client, pipeline_repo, ontology_repo
    ):
        """The apply route indexes newly created individuals for recognition (#1142)."""
        from tests.fakes.fake_individual_vector_index import FakeIndividualVectorIndex

        class_id = "cls-service"
        ontology_repo.save_class(
            Class(
                id=class_id,
                concept_scheme_id=SCHEME_ID,
                taxonomy_id=TAXONOMY_ID,
                title="Service",
            )
        )
        index = FakeIndividualVectorIndex()
        client.app.state.individual_vector_index = index

        run_id = _create_and_complete_individual_run(
            pipeline_repo,
            triples=[
                {
                    "subject": {
                        "kind": "individual",
                        "label": "Payments API",
                        "class_ids": [class_id],
                    },
                    "predicate": {},
                    "object": {},
                    "confidence": 0.9,
                }
            ],
        )

        response = client.post(f"/api/pipelines/runs/{run_id}/apply")
        assert response.status_code == status.HTTP_200_OK

        # The created individual is now searchable in the recognition index.
        indexed_titles = {title for title, *_ in index._individuals.values()}
        assert "Payments API" in indexed_titles

    def test_apply_individual_extraction_forwards_recognition_threshold(
        self, client, pipeline_repo, ontology_repo, ontology_service
    ):
        """The recognition_threshold query param reaches the recognizer (#1149)."""
        from tests.fakes.fake_individual_recognizer import FakeIndividualRecognizer

        recognizer = FakeIndividualRecognizer()
        client.app.state.individual_extraction_apply_svc = IndividualExtractionApplyService(
            ontology_service, ontology_repo, individual_recognizer=recognizer
        )

        class_id = "cls-service"
        ontology_repo.save_class(
            Class(
                id=class_id,
                concept_scheme_id=SCHEME_ID,
                taxonomy_id=TAXONOMY_ID,
                title="Service",
            )
        )
        run_id = _create_and_complete_individual_run(
            pipeline_repo,
            triples=[
                {
                    "subject": {
                        "kind": "individual",
                        "label": "Payments API",
                        "class_ids": [class_id],
                    },
                    "predicate": {},
                    "object": {},
                    "confidence": 0.9,
                }
            ],
        )

        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"recognition_threshold": 0.6},
        )

        assert response.status_code == status.HTTP_200_OK
        assert recognizer.calls[0]["threshold"] == 0.6


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestApplyIdempotency:
    def test_apply_twice_creates_no_duplicates(self, client, pipeline_repo, ontology_repo):
        run_id = _create_and_complete_schema_run(
            pipeline_repo,
            candidates=[
                {"kind": "class", "label": "Node", "confidence": 0.9},
            ],
        )
        params = {"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID}

        r1 = client.post(f"/api/pipelines/runs/{run_id}/apply", params=params)
        r2 = client.post(f"/api/pipelines/runs/{run_id}/apply", params=params)

        assert r1.status_code == status.HTTP_200_OK
        assert r2.status_code == status.HTTP_200_OK

        b1 = r1.json()
        b2 = r2.json()
        assert b1["classes_created"] == 1
        assert b2["classes_created"] == 0
        assert b2["classes_skipped"] == 1

        classes = ontology_repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)
        assert len(classes) == 1

    def test_apply_with_confidence_threshold(self, client, pipeline_repo, ontology_repo):
        run_id = _create_and_complete_schema_run(
            pipeline_repo,
            candidates=[
                {"kind": "class", "label": "HighConf", "confidence": 0.9},
                {"kind": "class", "label": "LowConf", "confidence": 0.2},
            ],
        )
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={
                "concept_scheme_id": SCHEME_ID,
                "taxonomy_id": TAXONOMY_ID,
                "confidence_threshold": 0.5,
            },
        )
        body = response.json()
        assert body["classes_created"] == 1
        assert body["classes_skipped"] == 1


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestApplyEndpointErrors:
    def test_nonexistent_run_returns_404(self, client):
        response = client.post(
            "/api/pipelines/runs/nonexistent-run-id/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_non_completed_run_returns_422(self, client, pipeline_repo):
        batch_id = str(uuid4())
        run = pipeline_repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="default",
            configuration_ref="extraction-default",
            configuration_slug="extraction-default",
            configuration_version=1,
        )
        run_id = run.id
        # Do NOT complete the run — leave it in PENDING state

        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_schema_extraction_missing_concept_scheme_id_returns_400(self, client, pipeline_repo):
        run_id = _create_and_complete_schema_run(pipeline_repo)
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_schema_extraction_missing_taxonomy_id_returns_400(self, client, pipeline_repo):
        run_id = _create_and_complete_schema_run(pipeline_repo)
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_grounding_missing_node_id_returns_400(self, client, pipeline_repo):
        batch_id = str(uuid4())
        run = pipeline_repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            implementation_id="default",
            configuration_ref="grounding-default",
            configuration_slug="grounding-default",
            configuration_version=1,
        )
        run_id = run.id
        pipeline_repo.update_status(run_id, PipelineRunStatus.COMPLETED)
        pipeline_repo.update_summaries(run_id, output_summary={"groundings": []})

        response = client.post(f"/api/pipelines/runs/{run_id}/apply")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_pipeline_storage_error_returns_500(self, client, pipeline_repo):
        from domain.pipelines.exceptions import PipelineStorageError

        run_id = _create_and_complete_schema_run(pipeline_repo)
        client.app.state.schema_extraction_apply_svc.apply = MagicMock(
            side_effect=PipelineStorageError("Database connection failed")
        )
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_integrity_error_returns_500(self, client, pipeline_repo):
        from sqlalchemy.exc import IntegrityError

        run_id = _create_and_complete_schema_run(pipeline_repo)
        client.app.state.schema_extraction_apply_svc.apply = MagicMock(
            side_effect=IntegrityError("Unique constraint", "", "")
        )
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_operational_error_returns_500(self, client, pipeline_repo):
        from sqlalchemy.exc import OperationalError

        run_id = _create_and_complete_schema_run(pipeline_repo)
        client.app.state.schema_extraction_apply_svc.apply = MagicMock(
            side_effect=OperationalError("Database unavailable", "", "")
        )
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_key_error_returns_400(self, client, pipeline_repo):
        run_id = _create_and_complete_schema_run(pipeline_repo)
        client.app.state.schema_extraction_apply_svc.apply = MagicMock(
            side_effect=KeyError("expected_field")
        )
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert "malformed" in body["detail"].lower()


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


class TestApplyResponseStructure:
    def test_response_includes_all_count_fields(self, client, pipeline_repo):
        run_id = _create_and_complete_schema_run(pipeline_repo)
        response = client.post(
            f"/api/pipelines/runs/{run_id}/apply",
            params={"concept_scheme_id": SCHEME_ID, "taxonomy_id": TAXONOMY_ID},
        )
        body = response.json()
        expected_fields = {
            "run_id",
            "pipeline_type",
            "classes_created",
            "classes_skipped",
            "properties_created",
            "properties_skipped",
            "relationships_created",
            "relationships_skipped",
            "individuals_created",
            "individuals_skipped",
        }
        assert expected_fields.issubset(set(body.keys()))
