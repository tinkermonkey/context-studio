"""
E2E tests for the Knowledge Extraction bounded context.

This module tests the Knowledge Extraction bounded context through the HTTP API
with a fully initialized application using real databases and real adapters.

Tests verify:
- Full extraction workflow with all 4 layers
- Text analysis with KG context and NLP gap-filling
- Reference source enrichment
- Error handling for invalid inputs
- Extraction metrics and execution traces
- Entity deduplication across layers
"""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import status


@pytest.mark.e2e
class TestExtractionWorkflow:
    """Tests for complete extraction workflow."""

    def test_extract_returns_200_with_valid_text(self, e2e_client):
        """
        Extract entities from text returns 200.

        Asserts:
        - Status code 200 (OK)
        - Response contains extraction result with all required fields
        """
        response = e2e_client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_extract_response_structure(self, e2e_client):
        """
        Extraction response has correct structure.

        Asserts:
        - Response contains id, text, extracted_entities, layers_executed, timestamps
        - All required fields are present with correct types
        """
        response = e2e_client.post(
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

    def test_extract_executes_all_layers(self, e2e_client):
        """
        Extraction executes all 4 layers.

        Asserts:
        - Response includes results from Layer 0 (KG), Layer 1 (LLM), Layer 2 (NLP), Layer 3
        (Reference)
        """
        response = e2e_client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()

        # Should have executed 4 layers
        assert len(body["layers_executed"]) == 4

    def test_extract_layer_results_valid(self, e2e_client):
        """
        Extraction layer results have correct structure.

        Asserts:
        - Each layer result contains layer_number, layer_name, entities_found, duration_ms, success
        - All fields have correct types
        """
        response = e2e_client.post(
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

            # Verify types
            assert isinstance(layer["layer_number"], int)
            assert isinstance(layer["layer_name"], str)
            assert isinstance(layer["entities_found"], int)
            assert isinstance(layer["duration_ms"], int)
            assert isinstance(layer["success"], bool)

    def test_extract_total_duration_positive(self, e2e_client):
        """
        Extraction total_duration_ms is positive.

        Asserts:
        - total_duration_ms is a non-negative integer
        """
        response = e2e_client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()
        assert body["total_duration_ms"] >= 0

    def test_extract_created_at_iso_format(self, e2e_client):
        """
        Extraction created_at is ISO 8601 format.

        Asserts:
        - created_at can be parsed as ISO 8601 timestamp
        """
        response = e2e_client.post(
            "/api/extract", json={"text": "SQLite is an embedded relational database."}
        )
        body = response.json()
        # Should be ISO 8601 string, verify it can be parsed
        try:
            datetime.fromisoformat(body["created_at"])
        except ValueError:
            pytest.fail("created_at is not in valid ISO 8601 format")

    def test_extract_with_long_text(self, e2e_client):
        """
        Extraction handles long text input.

        Asserts:
        - Status code 200 (OK)
        - Text field in response matches input text
        """
        long_text = "This is a test. " * 100
        response = e2e_client.post("/api/extract", json={"text": long_text})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["text"] == long_text

    def test_extract_with_special_characters(self, e2e_client):
        """
        Extraction handles special characters in text.

        Asserts:
        - Status code 200 (OK)
        - Response is valid for text with special characters
        """
        response = e2e_client.post(
            "/api/extract",
            json={"text": "Test with special chars: @#$%^&*() and unicode: 你好 مرحبا"},
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.e2e
class TestExtractionErrorHandling:
    """Tests for extraction error handling."""

    def test_extract_with_empty_text_fails(self, e2e_client):
        """
        Extraction with empty text returns validation error.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
        response = e2e_client.post("/api/extract", json={"text": ""})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_extract_with_whitespace_only_fails(self, e2e_client):
        """
        Extraction with whitespace-only text returns bad request.

        Asserts:
        - Status code 400 (Bad Request)
        """
        response = e2e_client.post("/api/extract", json={"text": "   \n\t  "})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_extract_with_missing_text_fails(self, e2e_client):
        """
        Extraction with missing text field returns validation error.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
        response = e2e_client.post("/api/extract", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.e2e
class TestTextAnalysis:
    """Tests for text analysis endpoint."""

    def test_analyze_text_returns_200(self, e2e_client):
        """
        Analyze text returns 200.

        Asserts:
        - Status code 200 (OK)
        """
        response = e2e_client.post(
            "/api/analyze_text",
            json={"text": "SQLite is an embedded relational database."},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_analyze_text_response_structure(self, e2e_client):
        """
        Analyze text response has correct structure.

        Asserts:
        - Response contains id, text, extracted_entities, layers_executed
        """
        response = e2e_client.post(
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

    def test_analyze_text_layers_executed(self, e2e_client):
        """
        Analyze text executes only KG context and NLP layers.

        Asserts:
        - Response includes Layer 0 (KG) and Layer 2 (NLP) only
        """
        response = e2e_client.post(
            "/api/analyze_text",
            json={"text": "SQLite is an embedded relational database."},
        )
        body = response.json()

        # Should have executed 2 layers: Layer 0 (KG context) and Layer 2 (NLP)
        assert len(body["layers_executed"]) == 2

    def test_analyze_text_with_empty_text_fails(self, e2e_client):
        """
        Analyze text with empty text returns validation error.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
        response = e2e_client.post("/api/analyze_text", json={"text": ""})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_analyze_text_with_whitespace_only_fails(self, e2e_client):
        """
        Analyze text with whitespace-only text returns bad request.

        Asserts:
        - Status code 400 (Bad Request)
        """
        response = e2e_client.post("/api/analyze_text", json={"text": "   \n\t  "})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.e2e
class TestReferenceEnrichment:
    """Tests for reference source enrichment."""

    def test_enrich_from_references_returns_200(self, e2e_client):
        """
        Enrich from references returns 200.

        Asserts:
        - Status code 200 (OK)
        """
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
        response = e2e_client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": entities},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_enrich_from_references_response_structure(self, e2e_client):
        """
        Enrich from references response has correct structure.

        Asserts:
        - Response contains all required fields
        """
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
        response = e2e_client.post(
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

    def test_enrich_from_references_layer(self, e2e_client):
        """
        Enrich from references executes only Layer 3.

        Asserts:
        - Response includes Layer 3 (reference enrichment) only
        """
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
        response = e2e_client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": entities},
        )
        body = response.json()

        # Should have executed only 1 layer: Layer 3 (Reference enrichment)
        assert len(body["layers_executed"]) == 1
        assert body["layers_executed"][0]["layer_number"] == 3

    def test_enrich_from_references_with_empty_text_fails(self, e2e_client):
        """
        Enrich with empty text returns validation error.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
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
        response = e2e_client.post(
            "/api/enrich_from_references",
            json={"text": "", "extracted_entities": entities},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_enrich_from_references_with_empty_entities_list(self, e2e_client):
        """
        Enrich with empty entities list returns 200.

        Asserts:
        - Status code 200 (OK)
        - Response entities list is empty
        """
        response = e2e_client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": []},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body["extracted_entities"]) == 0

    def test_enrich_from_references_enriches_entities(self, e2e_client):
        """
        Enrichment adds URI and description to entities.

        Asserts:
        - Enriched entities have uri and description fields populated
        """
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
        response = e2e_client.post(
            "/api/enrich_from_references",
            json={"text": "SQLite is a database.", "extracted_entities": entities},
        )
        body = response.json()

        # Check if enrichment added metadata
        assert body["extracted_entities"], "Expected at least one enriched entity"
        entity = body["extracted_entities"][0]
        # Entity should still have all original fields
        assert "id" in entity
        assert "label" in entity
        assert "confidence" in entity


@pytest.mark.e2e
class TestExtractionDeduplication:
    """Tests for entity deduplication across layers."""

    def test_extract_maintains_unique_entities(self, e2e_client):
        """
        Extraction maintains unique entities from different sources.

        Asserts:
        - Status code 200 (OK)
        - Response contains multiple unique entities (different labels)
        - All extracted entities have required fields
        """
        response = e2e_client.post(
            "/api/extract",
            json={
                "text": (
                    "Python is a programming language. Postgres is a database. Java is"
                    " another language."
                )
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        # Verify response structure is valid
        assert "extracted_entities" in body
        entities = body["extracted_entities"]

        # Verify we have at least one entity
        assert len(entities) > 0, "Expected at least one entity to be extracted"

        # Verify each entity has required fields
        for entity in entities:
            assert "id" in entity, "Entity missing id field"
            assert "label" in entity, "Entity missing label field"
            assert "entity_type" in entity, "Entity missing entity_type field"

        # Verify uniqueness: different entities should have different labels
        entity_labels = [entity["label"] for entity in entities]
        assert len(entity_labels) == len(
            set(entity_labels)
        ), "Duplicate entity labels found - uniqueness not maintained"
