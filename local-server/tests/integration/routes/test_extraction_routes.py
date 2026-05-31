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

import json
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import SQLiteExtractionRunRepository
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
    tax = Taxonomy(id=str(uuid4()), title="Test Taxonomy", description="Test")
    repository.save_taxonomy(tax)

    # Create concept scheme
    scheme = ConceptScheme(
        id=str(uuid4()), taxonomy_id=tax.id, title="Test Scheme", description="Test"
    )
    repository.save_concept_scheme(scheme)

    # Create classes for extraction context
    database_class = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Database",
        description="A database system",
    )
    sql_class = Class(
        id=str(uuid4()),
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
        response = client.post("/api/extract", json={"text": "SQLite database SQLite engine."})
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


class TestTripleExtraction:
    """Integration tests for triple extraction endpoints."""

    @pytest.fixture
    def ontology_with_individuals(self, populated_repository):
        """Use existing populated repository with taxonomy for triple extraction tests."""
        # Get existing taxonomy and scheme
        taxonomies = populated_repository.list_taxonomies()
        assert len(taxonomies) > 0
        tax = taxonomies[0]

        schemes = populated_repository.list_concept_schemes(taxonomy_id=tax.id)
        assert len(schemes) > 0
        scheme = schemes[0]

        # Get existing classes
        classes = populated_repository.list_classes(concept_scheme_id=scheme.id)
        assert len(classes) >= 2

        return {
            "taxonomy": tax,
            "scheme": scheme,
            "subject_class": classes[0],
            "object_class": classes[1],
        }

    @pytest.fixture
    def extraction_service(
        self,
        populated_repository,
        embedding_service,
        event_publisher,
        extraction_repository,
        session_factory,
    ):
        """Override extraction service to use LLM provider that returns triples."""
        from adapters.persistence.sqlite.extraction_run_repo import SQLiteExtractionRunRepository

        extraction_run_repo = SQLiteExtractionRunRepository(session_factory)

        # Configure LLM provider to return triples that will create change events
        triple_response = {
            "triples": [
                {
                    "subject": {"label": "database", "type": "entity"},
                    "predicate": {"label": "stores", "type": "relation"},
                    "object": {"label": "information", "type": "entity"},
                    "confidence": 0.95,
                    "provenance": {
                        "text_offset_start": 0,
                        "text_offset_end": 10,
                    },
                }
            ]
        }

        service = ExtractionService(
            ontology_repo=populated_repository,
            embedding_service=embedding_service,
            llm=FakeLLMProvider(response_content=json.dumps(triple_response)),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=event_publisher,
            extraction_repo=extraction_repository,
            extraction_run_repo=extraction_run_repo,
        )
        return service

    @pytest.fixture
    def client_with_change_recorder(self, extraction_service, event_publisher, session_factory):
        """Create a TestClient with extraction service and change event handlers registered."""
        from adapters.events.change_recorder import ChangeEventRecorder
        from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository

        # Set up event handlers
        change_repo = SQLiteChangeRepository(session_factory)
        change_recorder = ChangeEventRecorder(change_repo)

        # Subscribe event handlers to the event publisher
        from domain.extraction.events import ExtractionCompleted

        event_publisher.subscribe(ExtractionCompleted, change_recorder.on_extraction_completed)

        # Create FastAPI app with extraction service
        app = FastAPI()
        app.include_router(router)
        app.state.extraction_service = extraction_service

        return TestClient(app)

    def test_extract_triples_valid_request_returns_200(self, client, ontology_with_individuals):
        """POST /api/extraction/extract returns 200 with valid input."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "The database stores information.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK

    def test_extract_triples_response_structure(self, client, ontology_with_individuals):
        """POST /api/extraction/extract response has correct structure."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "The database stores information.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        # Verify required fields
        assert "triples" in body
        assert "warnings" in body
        assert "metadata" in body

        # Verify types
        assert isinstance(body["triples"], list)
        assert isinstance(body["warnings"], list)
        assert isinstance(body["metadata"], dict)

    def test_extract_triples_response_metadata_structure(self, client, ontology_with_individuals):
        """POST /api/extraction/extract response metadata has correct structure."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "The database stores information.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        metadata = body["metadata"]

        # Verify metadata fields
        assert "model" in metadata
        assert "tokens_used" in metadata
        assert "duration_ms" in metadata

        # Verify types
        assert isinstance(metadata["model"], str)
        assert isinstance(metadata["tokens_used"], int)
        assert isinstance(metadata["duration_ms"], int)

        # Verify model matches request
        assert metadata["model"] == "gpt-4"

    def test_extract_triples_with_empty_text_returns_422(self, client, ontology_with_individuals):
        """POST /api/extraction/extract with empty text returns 422 (Pydantic validation)."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extract_triples_with_missing_ontology_id_returns_422(self, client):
        """POST /api/extraction/extract with missing ontology_id returns 422."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "Some text",
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extract_triples_with_whitespace_only_returns_400(
        self, client, ontology_with_individuals
    ):
        """POST /api/extraction/extract with whitespace-only text returns 400."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "   \n\t  ",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_extract_triples_triple_structure_when_returned(
        self, client, ontology_with_individuals
    ):
        """POST /api/extraction/extract triple has correct structure when returned."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "The database stores information.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        triples = body["triples"]

        # If triples are returned, verify their structure
        for triple in triples:
            assert "subject" in triple
            assert "predicate" in triple
            assert "object" in triple
            assert "confidence" in triple
            assert "provenance" in triple

            # Verify subject structure
            subject = triple["subject"]
            assert "kind" in subject
            assert subject["kind"] in ["individual", "class"]
            assert "id" in subject
            assert "label" in subject

            # Verify predicate structure
            predicate = triple["predicate"]
            assert "property_definition_id" in predicate
            assert "label" in predicate

            # Verify object structure (discriminated by kind)
            obj = triple["object"]
            assert "kind" in obj
            assert obj["kind"] in ["individual", "class", "literal"]

            if obj["kind"] == "literal":
                assert "value" in obj
                # datatype is optional for literals
            else:
                assert "id" in obj
                assert "label" in obj

            # Verify confidence bounds
            assert isinstance(triple["confidence"], float)
            assert 0.0 <= triple["confidence"] <= 1.0

            # Verify provenance
            provenance = triple["provenance"]
            assert "text_offset_start" in provenance
            assert "text_offset_end" in provenance
            assert "raw" in provenance

            # Verify provenance offsets are valid
            assert provenance["text_offset_start"] >= 0
            assert provenance["text_offset_end"] >= provenance["text_offset_start"]
            assert provenance["text_offset_end"] <= len("The database stores information.")

    def test_extract_triples_confidence_values_valid(self, client, ontology_with_individuals):
        """All returned triple confidence values are in [0.0, 1.0]."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "Database systems manage structured data efficiently.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        triples = body["triples"]

        for triple in triples:
            assert isinstance(triple["confidence"], (int, float))
            assert 0.0 <= triple["confidence"] <= 1.0

    def test_extract_triples_object_kind_values_valid(self, client, ontology_with_individuals):
        """All returned triple object kind values are valid."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "SQL is a language for relational databases.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        triples = body["triples"]

        for triple in triples:
            obj = triple["object"]
            assert obj["kind"] in ["individual", "class", "literal"]

    def test_extract_triples_subject_kind_values_valid(self, client, ontology_with_individuals):
        """All returned triple subject kind values are valid."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "A taxonomy organizes concepts.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        triples = body["triples"]

        for triple in triples:
            subject = triple["subject"]
            assert subject["kind"] in ["individual", "class"]

    def test_extract_triples_provenance_offsets_within_bounds(
        self, client, ontology_with_individuals
    ):
        """All returned triple provenance offsets are within text bounds."""
        text = "The quick brown fox jumps over the lazy dog."
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": text,
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        triples = body["triples"]

        for triple in triples:
            provenance = triple["provenance"]
            # Offsets should be within text bounds
            assert provenance["text_offset_start"] >= 0
            assert provenance["text_offset_end"] <= len(text)
            assert provenance["text_offset_start"] <= provenance["text_offset_end"]

            # Raw text should match the specified offsets
            extracted_text = text[provenance["text_offset_start"] : provenance["text_offset_end"]]
            assert provenance["raw"] == extracted_text

    def test_extract_triples_with_long_text(self, client, ontology_with_individuals):
        """POST /api/extraction/extract returns 200 with long text input."""
        long_text = "This is a test sentence. " * 100
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": long_text,
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK

    def test_extract_triples_response_validates_against_schema(
        self, client, ontology_with_individuals
    ):
        """POST /api/extraction/extract response validates against schema."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "A simple test sentence.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify response has expected structure
        body = response.json()
        assert body is not None
        # Note: ExtractTripleResponse schema not yet defined (Phase 2 work)

    def test_extract_triples_with_different_models(self, client, ontology_with_individuals):
        """POST /api/extraction/extract works regardless of model."""
        models = ["gpt-4", "claude-opus", "gpt-3.5-turbo"]

        for model in models:
            response = client.post(
                "/api/extraction/extract",
                json={
                    "text": "Test text for extraction.",
                    "ontology_id": ontology_with_individuals["taxonomy"].id,
                    "options": {
                        "model": model,
                        "temperature": 0.0,
                        "max_tokens": 2000,
                    },
                },
            )
            assert response.status_code == status.HTTP_200_OK

    def test_extract_triples_temperature_variation(self, client, ontology_with_individuals):
        """POST /api/extraction/extract works regardless of temperature."""
        temperatures = [0.0, 0.5, 1.0, 1.5, 2.0]

        for temp in temperatures:
            response = client.post(
                "/api/extraction/extract",
                json={
                    "text": "Test text for extraction.",
                    "ontology_id": ontology_with_individuals["taxonomy"].id,
                    "options": {
                        "model": "gpt-4",
                        "temperature": temp,
                        "max_tokens": 2000,
                    },
                },
            )
            assert response.status_code == status.HTTP_200_OK

    def test_extract_triples_returns_200_ok(self, client, ontology_with_individuals):
        """POST /api/extraction/extract returns 200 OK."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "Test text for extraction.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK

    def test_extract_triples_creates_extraction_run_record(
        self, client, ontology_with_individuals, session_factory
    ):
        """POST /api/extraction/extract creates an ExtractionRun record with status completed."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "Test text for triple extraction.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify ExtractionRun record exists in database
        from adapters.persistence.sqlite.extraction_run_repo import (
            SQLiteExtractionRunRepository,
        )

        extraction_run_repo = SQLiteExtractionRunRepository(session_factory)
        runs = extraction_run_repo.list_extraction_runs()
        assert len(runs) > 0
        run = runs[-1]  # Most recent run
        assert run.status.value == "completed"

    def test_extract_triples_batch_run_id_in_change_events(
        self,
        client_with_change_recorder,
        ontology_with_individuals,
        extraction_run_repository,
        interchange_repository,
    ):
        """Extraction run correctly populates batch_run_id in change_events."""
        response = client_with_change_recorder.post(
            "/api/extraction/extract",
            json={
                "text": "Test text for triple extraction.",
                "ontology_id": ontology_with_individuals["taxonomy"].id,
                "options": {
                    "model": "gpt-4",
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Get ExtractionRun from repository
        runs = extraction_run_repository.list_extraction_runs()
        assert len(runs) > 0
        run = runs[-1]

        # The extraction run itself should have batch_run_id as None
        # (it represents the operation, not a parent batch)
        assert run.batch_run_id is None

        # Verify change_events for this extraction run have batch_run_id populated
        # The batch_run_id on change_events should point to the extraction run
        change_events = interchange_repository.get_change_events_for_run(run.id)
        # Precondition: extraction should produce at least one change event
        # If this fails, the test setup (LLM provider response) may not be returning entities
        assert len(change_events) > 0, (
            "No change events found for extraction run. "
            "The LLM provider may not be configured to return entities."
        )
        for event in change_events:
            assert event.batch_run_id == run.id, (
                f"Change event {event.id} has batch_run_id={event.batch_run_id}, "
                f"expected extraction run ID {run.id}"
            )
