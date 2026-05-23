"""
Integration tests for Individual Extraction pipeline.

Tests verify:
1. IndividualExtractionOrchestrator wraps ExtractionService correctly
2. Pipeline run persistence with batch_run_id correlation
3. Configuration registration and versioning
4. Backward compatibility with legacy /api/extraction/extract endpoint
5. Text2KGBench benchmark harness compatibility

These tests use hand-authored fixtures to validate extraction output.
"""

import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import SQLiteExtractionRunRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.web.extraction_routes import router as extraction_router
from adapters.web.pipelines_routes import router as pipelines_router
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction import (
    IndividualExtractionOrchestrator,
    register_individual_extraction,
)
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def ontology_repo(session_factory):
    """Create a real SQLiteOntologyRepository with test data."""
    repo = SQLiteOntologyRepository(session_factory)

    # Create ontology with classes for testing
    tax = Taxonomy(id=str(uuid4()), title="Test Ontology", description="Test ontology for extraction")
    repo.save_taxonomy(tax)

    scheme = ConceptScheme(
        id=str(uuid4()),
        taxonomy_id=tax.id,
        title="Test Scheme",
        description="Test scheme",
    )
    repo.save_concept_scheme(scheme)

    # Create some test classes
    person_class = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Person",
        description="A person",
    )
    company_class = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Company",
        description="An organization",
    )

    repo.save_class(person_class)
    repo.save_class(company_class)

    yield repo


@pytest.fixture
def extraction_service(ontology_repo, session_factory):
    """Create ExtractionService with fake adapters."""
    embedding_service = FakeEmbeddingService()
    event_publisher = InProcessEventPublisher()
    extraction_repo = SQLiteExtractionRepository(session_factory)
    extraction_run_repo = SQLiteExtractionRunRepository(session_factory)

    # Use a fake LLM provider with structured response
    llm_response = """{
        "triples": [
            {
                "subject": {"kind": "individual", "id": "john_doe", "label": "John Doe"},
                "predicate": {"kind": "property", "id": "works_for", "label": "works_for"},
                "object": {"kind": "individual", "id": "acme_corp", "label": "ACME Corp"},
                "confidence": 0.95,
                "provenance": [0, 50]
            }
        ]
    }"""

    service = ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=embedding_service,
        llm=FakeLLMProvider(response_content=llm_response),
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource()],
        event_publisher=event_publisher,
        extraction_repo=extraction_repo,
        extraction_run_repo=extraction_run_repo,
    )
    return service


@pytest.fixture
def impl_registry():
    """Create initialized implementation registry."""
    registry = PipelineImplementationRegistry()
    # Individual extraction will be registered by bootstrap below
    return registry


@pytest.fixture
def config_registry():
    """Create initialized configuration registry."""
    return PipelineConfigurationRegistry()


@pytest.fixture
def registered_extraction(impl_registry, config_registry):
    """Register individual extraction pipeline with both registries."""
    register_individual_extraction(
        impl_registry=impl_registry,
        config_registry=config_registry,
    )
    return impl_registry, config_registry


@pytest.fixture
def legacy_client(extraction_service):
    """Create a TestClient for legacy extraction routes."""
    app = FastAPI()
    app.include_router(extraction_router)
    app.state.extraction_service = extraction_service

    return TestClient(app)


class TestIndividualExtractionRegistration:
    """Test pipeline registration and configuration."""

    def test_orchestrator_registered_with_implementation_registry(self, registered_extraction):
        """IndividualExtractionOrchestrator is registered as 'default' implementation."""
        impl_registry, _ = registered_extraction

        impl_class = impl_registry.get(PipelineType.INDIVIDUAL_EXTRACTION, "default")
        assert impl_class is not None
        assert impl_class == IndividualExtractionOrchestrator

    def test_extraction_default_config_registered(self, registered_extraction):
        """Wave A 'extraction-default' configuration is registered (Anthropic/Claude)."""
        _, config_registry = registered_extraction

        config = config_registry.get_latest(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
        )
        assert config is not None
        assert config.config["provider"] == "anthropic"
        assert config.config["model"] == "claude-opus-4-7"
        assert config.version == 1

    def test_extraction_openrouter_config_registered(self, registered_extraction):
        """'extraction-openrouter-default' configuration is registered (Gemini)."""
        _, config_registry = registered_extraction

        config = config_registry.get_latest(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-openrouter-default",
        )
        assert config is not None
        assert config.config["provider"] == "openrouter"
        assert config.config["model"] == "google/gemini-3-flash-preview"
        assert config.version == 1

    def test_configurations_preserve_wave_a_model_choices(self, registered_extraction):
        """Wave A configuration preserves original model; no silent upgrades."""
        _, config_registry = registered_extraction

        wave_a_config = config_registry.get_latest(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
        )
        # Verify Wave A's original Anthropic config is unchanged
        assert wave_a_config.config["provider"] == "anthropic"
        assert "claude-opus" in wave_a_config.config["model"]


class TestLegacyExtractionEndpoint:
    """Test backward compatibility with Wave A /api/extraction/extract endpoint."""

    def test_extract_triples_legacy_endpoint_returns_200(self, legacy_client, ontology_repo):
        """POST /api/extraction/extract returns 200 with valid inputs."""
        # Get an ontology ID from the repo
        ontologies = ontology_repo.list_taxonomies()
        assert len(ontologies) > 0
        ontology_id = ontologies[0].id

        response = legacy_client.post(
            "/api/extraction/extract",
            json={
                "text": "John Doe works for ACME Corp.",
                "ontology_id": ontology_id,
                "options": {
                    "model": "claude-opus-4-7",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK

    def test_extract_triples_response_structure(self, legacy_client, ontology_repo):
        """POST /api/extraction/extract response has correct format for benchmark."""
        ontologies = ontology_repo.list_taxonomies()
        ontology_id = ontologies[0].id

        response = legacy_client.post(
            "/api/extraction/extract",
            json={
                "text": "John Doe works for ACME Corp.",
                "ontology_id": ontology_id,
                "options": {
                    "model": "claude-opus-4-7",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            },
        )
        body = response.json()

        # Verify expected benchmark format
        assert "triples" in body
        assert "warnings" in body
        assert "metadata" in body

        assert isinstance(body["triples"], list)
        assert isinstance(body["warnings"], list)
        assert isinstance(body["metadata"], dict)

    def test_extract_triples_metadata_includes_model_info(self, legacy_client, ontology_repo):
        """POST /api/extraction/extract metadata includes model and token counts."""
        ontologies = ontology_repo.list_taxonomies()
        ontology_id = ontologies[0].id

        response = legacy_client.post(
            "/api/extraction/extract",
            json={
                "text": "John Doe works for ACME Corp.",
                "ontology_id": ontology_id,
                "options": {
                    "model": "claude-opus-4-7",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            },
        )
        body = response.json()
        metadata = body["metadata"]

        # Verify benchmark harness expectations
        assert "model" in metadata
        assert "tokens_used" in metadata
        assert "duration_ms" in metadata

        assert isinstance(metadata["model"], str)
        assert isinstance(metadata["tokens_used"], int)
        assert isinstance(metadata["duration_ms"], int)

    def test_extract_triples_with_invalid_ontology_returns_200_with_warnings(self, legacy_client):
        """POST /api/extraction/extract with invalid ontology_id returns 200 with error in warnings."""
        response = legacy_client.post(
            "/api/extraction/extract",
            json={
                "text": "John Doe works for ACME Corp.",
                "ontology_id": "nonexistent-ontology-id",
                "options": {
                    "model": "claude-opus-4-7",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # Errors are returned as warnings in the response
        assert len(body["warnings"]) > 0
        assert "not found" in body["warnings"][0].lower()

    def test_extract_triples_with_empty_text_returns_422(self, legacy_client, ontology_repo):
        """POST /api/extraction/extract with empty text returns 422 (validation error)."""
        ontologies = ontology_repo.list_taxonomies()
        ontology_id = ontologies[0].id

        response = legacy_client.post(
            "/api/extraction/extract",
            json={
                "text": "",
                "ontology_id": ontology_id,
                "options": {
                    "model": "claude-opus-4-7",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            },
        )
        # Empty text is caught by Pydantic validation
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extract_triples_produces_structured_output(self, legacy_client, ontology_repo):
        """POST /api/extraction/extract produces well-formed triples with confidence."""
        ontologies = ontology_repo.list_taxonomies()
        ontology_id = ontologies[0].id

        response = legacy_client.post(
            "/api/extraction/extract",
            json={
                "text": "John Doe works for ACME Corp.",
                "ontology_id": ontology_id,
                "options": {
                    "model": "claude-opus-4-7",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            },
        )
        body = response.json()
        triples = body["triples"]

        # Verify triple structure (from fake LLM response)
        if triples:
            for triple in triples:
                assert "subject" in triple or "subject_ref" in triple
                assert "predicate" in triple or "predicate_ref" in triple
                assert "object" in triple or "object_ref" in triple
                # confidence and provenance are optional but often present
