"""
Integration tests for POST /api/pipelines/runs/{run_id}/recognition-preview endpoint.

Uses a real PipelineRepository and ExtractionService with FakeRecognizer to verify
the full recognition preview flow without external dependencies.
"""

import hashlib
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
from domain.extraction.ports import RecognitionMatch
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_individual_recognizer import FakeIndividualRecognizer
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

TAXONOMY_ID = "tx-preview-test"
SCHEME_ID = "cs-preview-test"
CLASS_ID = "cls-person"


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
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="test_tax", title="Preview Test Taxonomy"))
    r.save_concept_scheme(
        ConceptScheme(
            id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="test_scheme",
            title="Preview Test Scheme",
        )
    )
    r.save_class(
        Class(
            id=CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="cls_person",
            title="Person",
        )
    )
    return r


@pytest.fixture()
def recognizer():
    return FakeIndividualRecognizer()


@pytest.fixture()
def extraction_service(ontology_repo, recognizer):
    return ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=FakeEmbeddingService(),
        llm=MagicMock(),
        nlp=MagicMock(),
        reference_sources=[],
        event_publisher=FakeEventPublisher(),
        extraction_repo=MagicMock(),
        extraction_run_repo=MagicMock(),
        individual_recognizer=recognizer,
    )


@pytest.fixture()
def client(pipeline_repo, batch_repo, ontology_repo, extraction_service):
    app = FastAPI()
    app.include_router(router)

    app.state.pipeline_run_repo = pipeline_repo
    app.state.batch_repo = batch_repo
    app.state.extraction_service = extraction_service

    return TestClient(app)


def _create_and_complete_individual_run(pipeline_repo, triples=None):
    """Create a completed individual extraction run."""
    batch_id = str(uuid4())
    text_hash = hashlib.sha256(b"test text").hexdigest()
    run = pipeline_repo.create(
        batch_run_id=batch_id,
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        implementation_id="default",
        configuration_ref="extraction-default",
        configuration_slug="extraction-default",
        configuration_version=1,
        specific_data={
            "source_text_hash": text_hash,
            "source_document_uri": None,
        },
    )
    run_id = run.id
    pipeline_repo.update_status(run_id, PipelineRunStatus.COMPLETED)
    pipeline_repo.update_summaries(
        run_id,
        output_summary={"triples": triples or []},
    )
    return run_id


def _make_triple(subject_label, class_ids=None):
    """Helper to build a typing triple for individual extraction."""
    return {
        "subject": {
            "kind": "individual",
            "id": "",
            "label": subject_label,
            "class_ids": class_ids or [CLASS_ID],
        },
        "predicate": {"label": "is_a"},
        "object": {"kind": "class", "id": CLASS_ID, "label": "Person"},
        "confidence": 0.9,
    }


def _make_triple_with_singular_class_id(subject_label):
    """Helper to build a typing triple with singular class_id (format from _make_typing_triple())."""
    return {
        "subject": {
            "kind": "individual",
            "id": "",
            "label": subject_label,
            "class_id": CLASS_ID,
        },
        "predicate": {"label": "is_a"},
        "object": {"kind": "class", "id": CLASS_ID, "label": "Person"},
        "confidence": 0.9,
    }


def test_recognition_preview_returns_404_for_nonexistent_run(client):
    """404 returned for a nonexistent run ID."""
    response = client.post("/api/pipelines/runs/nonexistent-run-id/recognition-preview")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_recognition_preview_returns_422_for_incomplete_run(client, pipeline_repo):
    """422 returned when run is not completed."""
    batch_id = str(uuid4())
    text_hash = hashlib.sha256(b"test text").hexdigest()
    run = pipeline_repo.create(
        batch_run_id=batch_id,
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        implementation_id="default",
        configuration_ref="extraction-default",
        configuration_slug="extraction-default",
        configuration_version=1,
        specific_data={
            "source_text_hash": text_hash,
            "source_document_uri": None,
        },
    )
    response = client.post(f"/api/pipelines/runs/{run.id}/recognition-preview")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_recognition_preview_empty_run(client, pipeline_repo):
    """Empty result returned for a run with no triples."""
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=[])
    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 0
    assert data["matched_count"] == 0
    assert data["unmatched_count"] == 0
    assert data["skipped_count"] == 0
    assert len(data["hits"]) == 0


def test_recognition_preview_single_mention_no_match(client, pipeline_repo, recognizer):
    """Recognition preview reports new mention when no match found."""
    triple = _make_triple("Alice")
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=[triple])

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 1
    assert data["matched_count"] == 0
    assert data["unmatched_count"] == 1
    assert data["skipped_count"] == 0
    assert len(data["hits"]) == 1

    hit = data["hits"][0]
    assert hit["mention_label"] == "Alice"
    assert hit["will_match_existing"] is False
    assert hit["resolved_individual_id"] is None
    assert hit["resolved_individual_title"] is None


def test_recognition_preview_single_mention_with_match(client, pipeline_repo, recognizer):
    """Recognition preview reports match when existing individual found."""
    existing_id = str(uuid4())
    recognizer.add_match(
        label="Alice",
        match=RecognitionMatch(
            individual_id=existing_id,
            title="Alice (Person)",
            score=1.0,
            method="exact",
        ),
    )

    triple = _make_triple("Alice")
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=[triple])

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 1
    assert data["matched_count"] == 1
    assert data["unmatched_count"] == 0
    assert data["skipped_count"] == 0

    hit = data["hits"][0]
    assert hit["mention_label"] == "Alice"
    assert hit["will_match_existing"] is True
    assert hit["resolved_individual_id"] == existing_id
    assert hit["resolved_individual_title"] == "Alice (Person)"
    assert hit["match_method"] == "exact"
    assert hit["match_score"] == 1.0


def test_recognition_preview_multiple_mentions(client, pipeline_repo, recognizer):
    """Recognition preview deduplicates mentions and reports on each."""
    alice_id = str(uuid4())
    recognizer.add_match(
        label="Alice",
        match=RecognitionMatch(
            individual_id=alice_id,
            title="Alice (Person)",
            score=1.0,
            method="exact",
        ),
    )

    triples = [
        _make_triple("Alice"),
        _make_triple("Alice"),  # Duplicate — should be deduped
        _make_triple("Bob"),  # New mention
    ]
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=triples)

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 2
    assert data["matched_count"] == 1
    assert data["unmatched_count"] == 1
    assert data["skipped_count"] == 0

    hit_labels = {hit["mention_label"] for hit in data["hits"]}
    assert hit_labels == {"Alice", "Bob"}


def test_recognition_preview_no_writes_to_ontology(
    client, pipeline_repo, ontology_repo, recognizer
):
    """Recognition preview produces zero writes to ontology."""
    alice_id = str(uuid4())
    recognizer.add_match(
        label="Alice",
        match=RecognitionMatch(
            individual_id=alice_id,
            title="Alice (Person)",
            score=1.0,
            method="exact",
        ),
    )

    triples = [_make_triple("Alice"), _make_triple("Bob")]
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=triples)

    # Check ontology state before preview
    individuals_before = len(ontology_repo.list_individuals(limit=None))

    # Call preview
    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK

    # Check ontology state after preview — should be unchanged
    individuals_after = len(ontology_repo.list_individuals(limit=None))
    assert individuals_before == individuals_after


def test_recognition_preview_empty_result_for_non_individual_pipeline(client, pipeline_repo):
    """Empty result returned for non-individual pipeline types (FR3.6/FR3.7)."""
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
        output_summary={"triples": [_make_triple("SomeClass")]},
    )

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 0
    assert data["matched_count"] == 0
    assert data["unmatched_count"] == 0
    assert data["skipped_count"] == 0
    assert len(data["hits"]) == 0


def test_recognition_preview_filters_by_confidence_threshold(client, pipeline_repo, recognizer):
    """Mentions below confidence_threshold are skipped."""
    triples = [
        _make_triple("Alice"),  # confidence 0.9
        {
            "subject": {
                "kind": "individual",
                "id": "",
                "label": "Bob",
                "class_ids": [CLASS_ID],
            },
            "predicate": {"label": "is_a"},
            "object": {"kind": "class", "id": CLASS_ID, "label": "Person"},
            "confidence": 0.3,
        },
    ]
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=triples)

    response = client.post(
        f"/api/pipelines/runs/{run_id}/recognition-preview",
        json={"confidence_threshold": 0.5},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 1
    assert data["matched_count"] == 0
    assert data["unmatched_count"] == 1
    assert data["skipped_count"] == 1
    assert data["hits"][0]["mention_label"] == "Alice"


def test_recognition_preview_with_recognition_threshold(client, pipeline_repo, recognizer):
    """recognition_threshold parameter is accepted."""
    alice_id = str(uuid4())
    recognizer.add_match(
        label="Alice",
        match=RecognitionMatch(
            individual_id=alice_id,
            title="Alice (Person)",
            score=0.8,
            method="vector",
        ),
    )

    triple = _make_triple("Alice")
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=[triple])

    response = client.post(
        f"/api/pipelines/runs/{run_id}/recognition-preview",
        json={"recognition_threshold": 0.90},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 1


def test_recognition_preview_returns_empty_result_for_unsupported_pipeline_type(client, pipeline_repo):
    """200 with empty results returned for unsupported pipeline types."""
    batch_id = str(uuid4())
    run = pipeline_repo.create(
        batch_run_id=batch_id,
        pipeline_type=PipelineType.NO_OP,
        implementation_id="default",
        configuration_ref="noop-default",
        configuration_slug="noop-default",
        configuration_version=1,
    )
    run_id = run.id
    pipeline_repo.update_status(run_id, PipelineRunStatus.COMPLETED)
    pipeline_repo.update_summaries(
        run_id,
        output_summary={"triples": []},
    )

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 0
    assert data["matched_count"] == 0
    assert data["unmatched_count"] == 0
    assert data["skipped_count"] == 0
    assert len(data["hits"]) == 0


def test_recognition_preview_handles_null_confidence(client, pipeline_repo, recognizer):
    """Null confidence values default to 0.0 and are skipped."""
    triple_with_null_confidence = {
        "subject": {
            "kind": "individual",
            "id": "",
            "label": "Charlie",
            "class_ids": [CLASS_ID],
        },
        "predicate": {"label": "is_a"},
        "object": {"kind": "class", "id": CLASS_ID, "label": "Person"},
        "confidence": None,
    }
    run_id = _create_and_complete_individual_run(
        pipeline_repo, triples=[triple_with_null_confidence]
    )

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 0
    assert data["skipped_count"] == 1


def test_recognition_preview_handles_singular_class_id(client, pipeline_repo, recognizer):
    """Triples with singular class_id (from _make_typing_triple) are recognized correctly."""
    existing_id = str(uuid4())
    recognizer.add_match(
        label="Eve",
        match=RecognitionMatch(
            individual_id=existing_id,
            title="Eve (Person)",
            score=1.0,
            method="exact",
        ),
    )

    triple = _make_triple_with_singular_class_id("Eve")
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=[triple])

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 1
    assert data["matched_count"] == 1
    assert data["unmatched_count"] == 0
    hit = data["hits"][0]
    assert hit["mention_label"] == "Eve"
    assert hit["will_match_existing"] is True
    assert hit["resolved_individual_id"] == existing_id
    assert hit["candidate_class_ids"] == [CLASS_ID]


def test_recognition_preview_includes_candidate_class_ids(client, pipeline_repo, recognizer):
    """candidate_class_ids field is included in recognition preview hits."""
    triple = _make_triple("Diana", class_ids=[CLASS_ID])
    run_id = _create_and_complete_individual_run(pipeline_repo, triples=[triple])

    response = client.post(f"/api/pipelines/runs/{run_id}/recognition-preview")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_mentions"] == 1
    hit = data["hits"][0]
    assert "candidate_class_ids" in hit
    assert hit["candidate_class_ids"] == [CLASS_ID]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
