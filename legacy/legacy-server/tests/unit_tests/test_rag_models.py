"""
Unit tests for RAG pipeline Pydantic models.

Tests request/response models for RAG entity extraction pipeline.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from uuid import UUID

import pytest
from pydantic import ValidationError
from rag.models import (
    ExtractedEntity,
    LayerMetrics,
    ProcessingMetrics,
    RAGExtractionRequest,
    RAGExtractionResponse,
)


class TestRAGExtractionRequest:
    """Tests for RAGExtractionRequest model."""

    def test_basic_request(self):
        """Test creating a basic RAG extraction request."""
        request = RAGExtractionRequest(text="This is a test sentence.")
        assert request.text == "This is a test sentence."
        assert request.enable_trace is False  # Default per architect requirement

    def test_request_with_trace_enabled(self):
        """Test creating request with trace enabled."""
        request = RAGExtractionRequest(text="Test", enable_trace=True)
        assert request.enable_trace is True

    def test_request_empty_text_validation(self):
        """Test that empty text is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RAGExtractionRequest(text="")
        assert "String should have at least 1 character" in str(exc_info.value)

    def test_request_whitespace_only_validation(self):
        """Test that whitespace-only text is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RAGExtractionRequest(text="   ")
        assert "Text cannot be empty or whitespace only" in str(exc_info.value)

    def test_request_missing_text(self):
        """Test that text field is required."""
        with pytest.raises(ValidationError) as exc_info:
            RAGExtractionRequest()
        assert "Field required" in str(exc_info.value)

    def test_request_with_newlines(self):
        """Test request with multi-line text."""
        text = "First sentence.\nSecond sentence.\nThird sentence."
        request = RAGExtractionRequest(text=text)
        assert request.text == text


class TestExtractedEntity:
    """Tests for ExtractedEntity model."""

    def test_basic_entity(self):
        """Test creating a basic extracted entity."""
        entity = ExtractedEntity(
            text="John Doe",
            type="PERSON",
            confidence=0.95,
            source_layer="nlp",
            sentence_index=0,
        )
        assert entity.text == "John Doe"
        assert entity.type == "PERSON"
        assert entity.confidence == 0.95
        assert entity.source_layer == "nlp"
        assert entity.sentence_index == 0
        assert entity.metadata == {}

    def test_entity_with_metadata(self):
        """Test entity with metadata."""
        metadata = {
            "kb_id": "Q12345",
            "relations": ["works_at", "lives_in"],
            "context": "additional context",
        }
        entity = ExtractedEntity(
            text="OpenAI",
            type="ORG",
            confidence=0.88,
            source_layer="kg",
            sentence_index=1,
            metadata=metadata,
        )
        assert entity.metadata == metadata
        assert entity.metadata["kb_id"] == "Q12345"

    def test_entity_confidence_validation(self):
        """Test confidence score validation (0.0 to 1.0)."""
        # Valid confidence values
        valid_confidences = [0.0, 0.5, 0.9, 1.0]
        for conf in valid_confidences:
            entity = ExtractedEntity(
                text="Test",
                type="TEST",
                confidence=conf,
                source_layer="nlp",
                sentence_index=0,
            )
            assert entity.confidence == conf

        # Invalid confidence values
        invalid_confidences = [-0.1, -1.0, 1.1, 2.0]
        for conf in invalid_confidences:
            with pytest.raises(ValidationError):
                ExtractedEntity(
                    text="Test",
                    type="TEST",
                    confidence=conf,
                    source_layer="nlp",
                    sentence_index=0,
                )

    def test_entity_source_layer_validation(self):
        """Test source_layer validation (must be kg, nlp, llm, or web)."""
        # Valid source layers
        valid_layers = ["kg", "nlp", "llm", "web"]
        for layer in valid_layers:
            entity = ExtractedEntity(
                text="Test",
                type="TEST",
                confidence=0.8,
                source_layer=layer,
                sentence_index=0,
            )
            assert entity.source_layer == layer

        # Invalid source layers
        invalid_layers = ["unknown", "api", "database", ""]
        for layer in invalid_layers:
            with pytest.raises(ValidationError) as exc_info:
                ExtractedEntity(
                    text="Test",
                    type="TEST",
                    confidence=0.8,
                    source_layer=layer,
                    sentence_index=0,
                )
            error_message = str(exc_info.value)
            assert (
                "source_layer must be one of" in error_message
                or "Value error" in error_message
            )

    def test_entity_sentence_index_validation(self):
        """Test sentence_index validation (must be >= 0)."""
        # Valid indices
        valid_indices = [0, 1, 5, 100]
        for idx in valid_indices:
            entity = ExtractedEntity(
                text="Test",
                type="TEST",
                confidence=0.8,
                source_layer="nlp",
                sentence_index=idx,
            )
            assert entity.sentence_index == idx

        # Invalid indices
        invalid_indices = [-1, -10]
        for idx in invalid_indices:
            with pytest.raises(ValidationError):
                ExtractedEntity(
                    text="Test",
                    type="TEST",
                    confidence=0.8,
                    source_layer="nlp",
                    sentence_index=idx,
                )

    def test_entity_empty_text_validation(self):
        """Test that empty text is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractedEntity(
                text="",
                type="TEST",
                confidence=0.8,
                source_layer="nlp",
                sentence_index=0,
            )
        assert "String should have at least 1 character" in str(exc_info.value)


class TestLayerMetrics:
    """Tests for LayerMetrics model."""

    def test_basic_layer_metrics(self):
        """Test creating basic layer metrics."""
        metrics = LayerMetrics(execution_time_ms=123.45, entities_found=10)
        assert metrics.execution_time_ms == 123.45
        assert metrics.entities_found == 10
        assert metrics.entities_deduplicated == 0  # Default

    def test_layer_metrics_with_deduplication(self):
        """Test layer metrics with deduplication count."""
        metrics = LayerMetrics(
            execution_time_ms=200.0, entities_found=15, entities_deduplicated=3
        )
        assert metrics.entities_deduplicated == 3

    def test_layer_metrics_validation(self):
        """Test field validation for layer metrics."""
        # Negative execution time should fail
        with pytest.raises(ValidationError):
            LayerMetrics(execution_time_ms=-10.0, entities_found=5)

        # Negative entities_found should fail
        with pytest.raises(ValidationError):
            LayerMetrics(execution_time_ms=100.0, entities_found=-1)

        # Negative entities_deduplicated should fail
        with pytest.raises(ValidationError):
            LayerMetrics(
                execution_time_ms=100.0, entities_found=5, entities_deduplicated=-1
            )


class TestProcessingMetrics:
    """Tests for ProcessingMetrics model."""

    def test_basic_processing_metrics(self):
        """Test creating comprehensive processing metrics."""
        kg_metrics = LayerMetrics(execution_time_ms=50.0, entities_found=5)
        nlp_metrics = LayerMetrics(execution_time_ms=100.0, entities_found=8)
        llm_metrics = LayerMetrics(execution_time_ms=200.0, entities_found=3)
        web_metrics = LayerMetrics(execution_time_ms=150.0, entities_found=2)

        metrics = ProcessingMetrics(
            kg_layer=kg_metrics,
            nlp_layer=nlp_metrics,
            llm_layer=llm_metrics,
            web_layer=web_metrics,
            total_execution_time_ms=500.0,
            total_entities=15,
            total_sentences=3,
        )

        assert metrics.kg_layer.entities_found == 5
        assert metrics.nlp_layer.entities_found == 8
        assert metrics.llm_layer.entities_found == 3
        assert metrics.web_layer.entities_found == 2
        assert metrics.total_execution_time_ms == 500.0
        assert metrics.total_entities == 15
        assert metrics.total_sentences == 3

    def test_processing_metrics_validation(self):
        """Test validation for processing metrics."""
        kg_metrics = LayerMetrics(execution_time_ms=50.0, entities_found=5)
        nlp_metrics = LayerMetrics(execution_time_ms=100.0, entities_found=8)
        llm_metrics = LayerMetrics(execution_time_ms=200.0, entities_found=3)
        web_metrics = LayerMetrics(execution_time_ms=150.0, entities_found=2)

        # Negative total_execution_time_ms should fail
        with pytest.raises(ValidationError):
            ProcessingMetrics(
                kg_layer=kg_metrics,
                nlp_layer=nlp_metrics,
                llm_layer=llm_metrics,
                web_layer=web_metrics,
                total_execution_time_ms=-500.0,
                total_entities=15,
                total_sentences=3,
            )

        # Negative total_entities should fail
        with pytest.raises(ValidationError):
            ProcessingMetrics(
                kg_layer=kg_metrics,
                nlp_layer=nlp_metrics,
                llm_layer=llm_metrics,
                web_layer=web_metrics,
                total_execution_time_ms=500.0,
                total_entities=-15,
                total_sentences=3,
            )

        # Negative total_sentences should fail
        with pytest.raises(ValidationError):
            ProcessingMetrics(
                kg_layer=kg_metrics,
                nlp_layer=nlp_metrics,
                llm_layer=llm_metrics,
                web_layer=web_metrics,
                total_execution_time_ms=500.0,
                total_entities=15,
                total_sentences=-3,
            )


class TestRAGExtractionResponse:
    """Tests for RAGExtractionResponse model."""

    def test_basic_response(self):
        """Test creating a basic RAG extraction response."""
        kg_metrics = LayerMetrics(execution_time_ms=50.0, entities_found=5)
        nlp_metrics = LayerMetrics(execution_time_ms=100.0, entities_found=8)
        llm_metrics = LayerMetrics(execution_time_ms=200.0, entities_found=3)
        web_metrics = LayerMetrics(execution_time_ms=150.0, entities_found=2)

        metrics = ProcessingMetrics(
            kg_layer=kg_metrics,
            nlp_layer=nlp_metrics,
            llm_layer=llm_metrics,
            web_layer=web_metrics,
            total_execution_time_ms=500.0,
            total_entities=15,
            total_sentences=3,
        )

        response = RAGExtractionResponse(metrics=metrics)

        assert response.entities == []  # Default empty list
        assert response.trace_available is False  # Default
        assert isinstance(response.request_id, str)
        # Verify request_id is a valid UUID
        UUID(response.request_id)

    def test_response_with_entities(self):
        """Test response with extracted entities."""
        entity1 = ExtractedEntity(
            text="Alice",
            type="PERSON",
            confidence=0.95,
            source_layer="nlp",
            sentence_index=0,
        )
        entity2 = ExtractedEntity(
            text="OpenAI",
            type="ORG",
            confidence=0.88,
            source_layer="kg",
            sentence_index=1,
        )

        kg_metrics = LayerMetrics(execution_time_ms=50.0, entities_found=2)
        nlp_metrics = LayerMetrics(execution_time_ms=100.0, entities_found=2)
        llm_metrics = LayerMetrics(execution_time_ms=200.0, entities_found=0)
        web_metrics = LayerMetrics(execution_time_ms=150.0, entities_found=0)

        metrics = ProcessingMetrics(
            kg_layer=kg_metrics,
            nlp_layer=nlp_metrics,
            llm_layer=llm_metrics,
            web_layer=web_metrics,
            total_execution_time_ms=500.0,
            total_entities=2,
            total_sentences=2,
        )

        response = RAGExtractionResponse(
            entities=[entity1, entity2], metrics=metrics, trace_available=True
        )

        assert len(response.entities) == 2
        assert response.entities[0].text == "Alice"
        assert response.entities[1].text == "OpenAI"
        assert response.trace_available is True

    def test_response_request_id_validation(self):
        """Test that request_id must be a valid UUID."""
        kg_metrics = LayerMetrics(execution_time_ms=50.0, entities_found=0)
        nlp_metrics = LayerMetrics(execution_time_ms=100.0, entities_found=0)
        llm_metrics = LayerMetrics(execution_time_ms=200.0, entities_found=0)
        web_metrics = LayerMetrics(execution_time_ms=150.0, entities_found=0)

        metrics = ProcessingMetrics(
            kg_layer=kg_metrics,
            nlp_layer=nlp_metrics,
            llm_layer=llm_metrics,
            web_layer=web_metrics,
            total_execution_time_ms=500.0,
            total_entities=0,
            total_sentences=1,
        )

        # Invalid UUID should fail
        with pytest.raises(ValidationError) as exc_info:
            RAGExtractionResponse(request_id="not-a-uuid", metrics=metrics)
        error_message = str(exc_info.value)
        assert (
            "request_id must be a valid UUID string" in error_message
            or "Value error" in error_message
        )

        # Valid UUID should work
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        response = RAGExtractionResponse(request_id=valid_uuid, metrics=metrics)
        assert response.request_id == valid_uuid

    def test_response_auto_generated_request_id(self):
        """Test that request_id is auto-generated if not provided."""
        kg_metrics = LayerMetrics(execution_time_ms=50.0, entities_found=0)
        nlp_metrics = LayerMetrics(execution_time_ms=100.0, entities_found=0)
        llm_metrics = LayerMetrics(execution_time_ms=200.0, entities_found=0)
        web_metrics = LayerMetrics(execution_time_ms=150.0, entities_found=0)

        metrics = ProcessingMetrics(
            kg_layer=kg_metrics,
            nlp_layer=nlp_metrics,
            llm_layer=llm_metrics,
            web_layer=web_metrics,
            total_execution_time_ms=500.0,
            total_entities=0,
            total_sentences=1,
        )

        response1 = RAGExtractionResponse(metrics=metrics)
        response2 = RAGExtractionResponse(metrics=metrics)

        # Each response should have a unique ID
        assert response1.request_id != response2.request_id

        # Both should be valid UUIDs
        UUID(response1.request_id)
        UUID(response2.request_id)


class TestModelDocstrings:
    """Tests for model documentation."""

    def test_all_models_have_docstrings(self):
        """Test that all models have docstrings."""
        models = [
            RAGExtractionRequest,
            RAGExtractionResponse,
            ExtractedEntity,
            LayerMetrics,
            ProcessingMetrics,
        ]

        for model in models:
            assert model.__doc__ is not None, f"{model.__name__} has no docstring"
            assert (
                len(model.__doc__.strip()) > 0
            ), f"{model.__name__} has empty docstring"

    def test_all_fields_have_descriptions(self):
        """Test that all fields have descriptions."""
        models = [
            RAGExtractionRequest,
            ExtractedEntity,
            LayerMetrics,
            ProcessingMetrics,
            RAGExtractionResponse,
        ]

        for model in models:
            for field_name, field_info in model.model_fields.items():
                assert (
                    field_info.description is not None
                ), f"{model.__name__}.{field_name} has no description"
                assert (
                    len(field_info.description) > 0
                ), f"{model.__name__}.{field_name} has empty description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
