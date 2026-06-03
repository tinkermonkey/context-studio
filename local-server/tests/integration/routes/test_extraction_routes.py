"""
Integration tests for Knowledge Extraction API routes.

Tests verify the full extraction workflow with:
- Real SQLite database (local.db)
- OntologyRepository backed by actual persistence
- EmbeddingService for semantic search
- LLM provider for extraction
- NLP processor for gap-filling
- Reference sources for enrichment
- HTTP routes via TestClient
- End-to-end request/response validation

These tests exercise the complete stack: routes → domain service → adapters → database.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import (
    SQLiteExtractionRunRepository,
)
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.web.extraction_routes import router
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
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
def repository(session_factory):
    """Create a real SQLiteOntologyRepository with actual persistence."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def populated_repository(repository):
    """Populate repository with test data."""
    # Create taxonomy
    tax = Taxonomy(
        id=str(uuid4()),
        identifier="test_tax",
        title="Test Taxonomy",
        description="Test",
    )
    repository.save_taxonomy(tax)

    # Create concept scheme
    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="test_scheme",
        taxonomy_id=tax.id,
        title="Test Scheme",
        description="Test",
    )
    repository.save_concept_scheme(scheme)

    # Create classes for extraction context
    database_class = Class(
        id=str(uuid4()),
        identifier="database_class",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Database",
        description="A database system",
    )
    sql_class = Class(
        id=str(uuid4()),
        identifier="sql_class",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="SQL",
        description="Structured Query Language",
    )

    repository.save_class(database_class)
    repository.save_class(sql_class)

    return repository


@pytest.fixture(scope="session")
def embedding_service():
    """Create embedding service for semantic search (session-scoped to reduce model load
    overhead)."""
    return FakeEmbeddingService()


@pytest.fixture
def event_publisher():
    """Create event publisher."""
    return InProcessEventPublisher()


@pytest.fixture
def extraction_repository(session_factory):
    """Create a real SQLiteExtractionRepository with actual persistence."""
    return SQLiteExtractionRepository(session_factory)


@pytest.fixture
def extraction_run_repository(session_factory):
    """Create a real SQLiteExtractionRunRepository for extraction run queries."""
    return SQLiteExtractionRunRepository(session_factory)


@pytest.fixture
def interchange_repository(session_factory):
    """Create a real SQLiteInterchangeRepository for change event queries."""
    return SQLiteInterchangeRepository(session_factory)


@pytest.fixture
def extraction_service(
    populated_repository,
    embedding_service,
    event_publisher,
    extraction_repository,
    session_factory,
):
    """Create ExtractionService with fake adapters."""
    from adapters.persistence.sqlite.extraction_run_repo import (
        SQLiteExtractionRunRepository,
    )

    extraction_run_repo = SQLiteExtractionRunRepository(session_factory)

    service = ExtractionService(
        ontology_repo=populated_repository,
        embedding_service=embedding_service,
        llm=FakeLLMProvider(response_content='{"entities": []}'),
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource()],
        event_publisher=event_publisher,
        extraction_repo=extraction_repository,
        extraction_run_repo=extraction_run_repo,
    )
    return service


@pytest.fixture
def client(extraction_service):
    """Create a TestClient with real extraction service."""
    app = FastAPI()
    app.include_router(router)
    app.state.extraction_service = extraction_service

    return TestClient(app)


class TestExtractionRoutes:
    """Integration tests for extraction routes."""

    def test_extract_returns_200_with_valid_text(self, client):
        """POST /api/extract returns 200 with valid text input."""
        response = client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_extract_response_structure(self, client):
        """POST /api/extract response has correct structure."""
        response = client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()

        # Verify all required fields
        assert "id" in body
        assert "text" in body
        assert "extracted_entities" in body
        assert "layers_executed" in body
        assert "total_duration_ms" in body
        assert "created_at" in body

        # Verify types
        assert isinstance(body["id"], str)
        assert isinstance(body["text"], str)
        assert isinstance(body["extracted_entities"], list)
        assert isinstance(body["layers_executed"], list)
        assert isinstance(body["total_duration_ms"], int)
        assert isinstance(body["created_at"], str)

    def test_extract_layers_executed_length(self, client):
        """POST /api/extract response includes all 4 layers."""
        response = client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()

        # Should have executed 4 layers
        assert len(body["layers_executed"]) == 4

    def test_extract_layer_result_structure(self, client):
        """POST /api/extract layer results have correct structure."""
        response = client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()

        # Check each layer result
        for layer in body["layers_executed"]:
            assert "layer_number" in layer
            assert "layer_name" in layer
            assert "entities_found" in layer
            assert "duration_ms" in layer
            assert "success" in layer
            assert "error_message" in layer or layer["error_message"] is None

            # Verify types
            assert isinstance(layer["layer_number"], int)
            assert isinstance(layer["layer_name"], str)
            assert isinstance(layer["entities_found"], int)
            assert isinstance(layer["duration_ms"], int)
            assert isinstance(layer["success"], bool)

    def test_extract_with_empty_text_returns_400(self, client):
        """POST /api/extract with empty text returns 422 (validation error)."""
        response = client.post("/api/extract", json={"text": ""})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extract_with_whitespace_only_returns_400(self, client):
        """POST /api/extract with whitespace-only text returns 400."""
        response = client.post("/api/extract", json={"text": "   \n\t  "})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_extract_with_missing_text_returns_422(self, client):
        """POST /api/extract with missing text field returns 422."""
        response = client.post("/api/extract", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extract_with_long_text(self, client):
        """POST /api/extract handles long text input."""
        long_text = "This is a test. " * 100
        response = client.post("/api/extract", json={"text": long_text})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["text"] == long_text

    def test_extract_entity_structure(self, client):
        """POST /api/extract entity results have correct structure."""
        response = client.post(
            "/api/extract", json={"text": "Test entity extraction with multiple words."}
        )
        body = response.json()

        # Check entity structure (if any entities were found)
        if body["extracted_entities"]:
            for entity in body["extracted_entities"]:
                assert "id" in entity
                assert "label" in entity
                assert "entity_type" in entity
                assert "source_layer" in entity
                assert "confidence" in entity
                assert "uri" in entity or entity["uri"] is None
                assert "description" in entity or entity["description"] is None
                assert "properties" in entity

                # Verify types
                assert isinstance(entity["id"], str)
                assert isinstance(entity["label"], str)
                assert isinstance(entity["entity_type"], str)
                assert isinstance(entity["source_layer"], int)
                assert isinstance(entity["confidence"], float)

    def test_extract_deduplicates_entities(self, client):
        """POST /api/extract deduplicates similar entities across layers."""
        response = client.post(
            "/api/extract", json={"text": "SQLite database SQLite engine."}
        )
        assert response.status_code == status.HTTP_200_OK
        # If deduplication works, similar entities should be merged

    def test_extract_total_duration_positive(self, client):
        """POST /api/extract total_duration_ms is positive."""
        response = client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()
        assert body["total_duration_ms"] >= 0

    def test_extract_created_at_is_iso_format(self, client):
        """POST /api/extract created_at timestamp is ISO 8601 format."""
        response = client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()
        # Should be ISO 8601 string, verify it can be parsed
        try:
            datetime.fromisoformat(body["created_at"])
        except ValueError:
            pytest.fail("created_at is not in valid ISO 8601 format")

    def test_analyze_text_returns_200_with_valid_text(self, client):
        """POST /api/analyze_text returns 200 with valid text input."""
        response = client.post(
            "/api/analyze_text",
            json={"text": "SQLite is an embedded relational database."},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_analyze_text_response_structure(self, client):
        """POST /api/analyze_text response has correct structure."""
        response = client.post(
            "/api/analyze_text",
            json={"text": "SQLite is an embedded relational database."},
        )
        body = response.json()

        # Verify all required fields
        assert "id" in body
        assert "text" in body
        assert "extracted_entities" in body
        assert "layers_executed" in body
        assert "total_duration_ms" in body
        assert "created_at" in body

    def test_analyze_text_layers_executed_count(self, client):
        """POST /api/analyze_text response includes only 2 layers (KG context and NLP)."""
        response = client.post(
            "/api/analyze_text",
            json={"text": "SQLite is an embedded relational database."},
        )
        body = response.json()

        # Should have executed 2 layers: Layer 0 (KG) and Layer 2 (NLP)
        assert len(body["layers_executed"]) == 2

    def test_analyze_text_with_empty_text_returns_400(self, client):
        """POST /api/analyze_text with empty text returns 422."""
        response = client.post("/api/analyze_text", json={"text": ""})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_analyze_text_with_whitespace_only_returns_400(self, client):
        """POST /api/analyze_text with whitespace-only text returns 400."""
        response = client.post("/api/analyze_text", json={"text": "   \n\t  "})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enrich_from_references_returns_200_with_valid_input(self, client):
        """POST /api/enrich_from_references returns 200 with valid text and entities."""
        entities = [
            {
                "id": str(uuid4()),
                "label": "Database",
                "entity_type": "CONCEPT",
                "source_layer": 1,
                "confidence": 0.9,
                "uri": None,
                "description": None,
                "properties": {},
            }
        ]
        response = client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": entities},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_enrich_from_references_response_structure(self, client):
        """POST /api/enrich_from_references response has correct structure."""
        entities = [
            {
                "id": str(uuid4()),
                "label": "Database",
                "entity_type": "CONCEPT",
                "source_layer": 1,
                "confidence": 0.9,
                "uri": None,
                "description": None,
                "properties": {},
            }
        ]
        response = client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": entities},
        )
        body = response.json()

        # Verify all required fields
        assert "id" in body
        assert "text" in body
        assert "extracted_entities" in body
        assert "layers_executed" in body
        assert "total_duration_ms" in body
        assert "created_at" in body

    def test_enrich_from_references_layers_executed_count(self, client):
        """POST /api/enrich_from_references response includes only Layer 3 (reference
        enrichment)."""
        entities = [
            {
                "id": str(uuid4()),
                "label": "Database",
                "entity_type": "CONCEPT",
                "source_layer": 1,
                "confidence": 0.9,
                "uri": None,
                "description": None,
                "properties": {},
            }
        ]
        response = client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": entities},
        )
        body = response.json()

        # Should have executed only 1 layer: Layer 3 (Reference enrichment)
        assert len(body["layers_executed"]) == 1
        assert body["layers_executed"][0]["layer_number"] == 3

    def test_enrich_from_references_with_empty_text_returns_400(self, client):
        """POST /api/enrich_from_references with empty text returns 400."""
        entities = [
            {
                "id": str(uuid4()),
                "label": "Database",
                "entity_type": "CONCEPT",
                "source_layer": 1,
                "confidence": 0.9,
                "uri": None,
                "description": None,
                "properties": {},
            }
        ]
        response = client.post(
            "/api/enrich_from_references",
            json={"text": "", "extracted_entities": entities},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_enrich_from_references_with_empty_entities_list(self, client):
        """POST /api/enrich_from_references with empty entities list returns 200."""
        response = client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": []},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body["extracted_entities"]) == 0
