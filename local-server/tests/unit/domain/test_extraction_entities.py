"""
Unit tests for extraction domain entities.

Tests cover entity construction, field initialization, and dataclass behavior
for ExtractedEntity, ExtractionResult, and ProcessingMetrics, including validation of invariants.
"""

from datetime import datetime, timezone

import pytest

from domain.extraction.entities import (
    ExtractedEntity,
    ExtractionResult,
    ProcessingMetrics,
)
from domain.extraction.value_objects import ExtractionLayerResult


class TestExtractedEntity:
    """Tests for ExtractedEntity dataclass."""

    def test_construct_with_all_fields(self):
        """Create an ExtractedEntity with all fields."""
        entity = ExtractedEntity(
            id="entity-123",
            label="Apple Inc.",
            entity_type="ORGANIZATION",
            source_layer=1,
            confidence=0.95,
            uri="https://example.com/apple",
            description="Technology company",
            properties={"founded": "1976", "headquarters": "California"},
        )

        assert entity.id == "entity-123"
        assert entity.label == "Apple Inc."
        assert entity.entity_type == "ORGANIZATION"
        assert entity.source_layer == 1
        assert entity.confidence == 0.95
        assert entity.uri == "https://example.com/apple"
        assert entity.description == "Technology company"
        assert entity.properties == {"founded": "1976", "headquarters": "California"}

    def test_construct_with_minimal_fields(self):
        """Create an ExtractedEntity with minimal fields."""
        entity = ExtractedEntity()

        # Should have default values
        assert entity.id is not None  # Has a generated UUID
        assert entity.label == ""
        assert entity.entity_type == ""
        assert entity.source_layer == 0
        assert entity.confidence == 0.0
        assert entity.uri is None
        assert entity.description is None
        assert entity.properties == {}

    def test_extracted_entity_id_is_unique(self):
        """Each ExtractedEntity gets a unique ID when not specified."""
        entity1 = ExtractedEntity(label="Entity1", source_layer=0)
        entity2 = ExtractedEntity(label="Entity2", source_layer=1)

        assert entity1.id != entity2.id

    def test_extracted_entity_with_empty_properties(self):
        """ExtractedEntity can have empty properties dict."""
        entity = ExtractedEntity(label="Test", properties={})
        assert entity.properties == {}

    def test_extracted_entity_mutable_properties(self):
        """ExtractedEntity properties can be modified."""
        entity = ExtractedEntity(label="Test")
        entity.properties["key"] = "value"
        assert entity.properties["key"] == "value"

    def test_extracted_entity_mutable_properties_isolation(self):
        """ExtractedEntity properties dict doesn't share state across instances."""
        entity1 = ExtractedEntity(label="Entity1")
        entity2 = ExtractedEntity(label="Entity2")

        entity1.properties["key"] = "value1"
        assert "key" not in entity2.properties
        assert entity2.properties == {}

    def test_extracted_entity_invalid_source_layer_negative(self):
        """ExtractedEntity raises ValueError if source_layer is negative."""
        with pytest.raises(ValueError, match="source_layer must be 0-3"):
            ExtractedEntity(label="Test", source_layer=-1)

    def test_extracted_entity_invalid_source_layer_too_high(self):
        """ExtractedEntity raises ValueError if source_layer is > 3."""
        with pytest.raises(ValueError, match="source_layer must be 0-3"):
            ExtractedEntity(label="Test", source_layer=4)

    def test_extracted_entity_invalid_source_layer_boundary(self):
        """ExtractedEntity raises ValueError if source_layer is 5."""
        with pytest.raises(ValueError, match="source_layer must be 0-3"):
            ExtractedEntity(label="Test", source_layer=5)

    def test_extracted_entity_invalid_confidence_negative(self):
        """ExtractedEntity raises ValueError if confidence is negative."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ExtractedEntity(label="Test", confidence=-0.1)

    def test_extracted_entity_invalid_confidence_too_high(self):
        """ExtractedEntity raises ValueError if confidence is > 1.0."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ExtractedEntity(label="Test", confidence=1.5)

    def test_extracted_entity_invalid_confidence_just_over(self):
        """ExtractedEntity raises ValueError if confidence is > 1.0."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ExtractedEntity(label="Test", confidence=1.01)

    def test_extracted_entity_valid_boundary_source_layer_zero(self):
        """ExtractedEntity accepts source_layer=0."""
        entity = ExtractedEntity(label="Test", source_layer=0)
        assert entity.source_layer == 0

    def test_extracted_entity_valid_boundary_source_layer_three(self):
        """ExtractedEntity accepts source_layer=3."""
        entity = ExtractedEntity(label="Test", source_layer=3)
        assert entity.source_layer == 3

    def test_extracted_entity_valid_boundary_confidence_zero(self):
        """ExtractedEntity accepts confidence=0.0."""
        entity = ExtractedEntity(label="Test", confidence=0.0)
        assert entity.confidence == 0.0

    def test_extracted_entity_valid_boundary_confidence_one(self):
        """ExtractedEntity accepts confidence=1.0."""
        entity = ExtractedEntity(label="Test", confidence=1.0)
        assert entity.confidence == 1.0


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_construct_with_all_fields(self):
        """Create an ExtractionResult with all fields."""
        now = datetime.now(timezone.utc)
        layers = [
            ExtractionLayerResult(
                layer_number=0,
                layer_name="KG Context",
                entities_found=2,
                duration_ms=100,
                success=True,
            ),
            ExtractionLayerResult(
                layer_number=1,
                layer_name="LLM Extraction",
                entities_found=3,
                duration_ms=150,
                success=True,
            ),
        ]
        entities = [
            ExtractedEntity(label="Apple", source_layer=0),
            ExtractedEntity(label="Microsoft", source_layer=1),
        ]

        result = ExtractionResult(
            id="result-123",
            text="Apple and Microsoft are companies.",
            extracted_entities=entities,
            layers_executed=layers,
            total_duration_ms=250,
            created_at=now,
        )

        assert result.id == "result-123"
        assert result.text == "Apple and Microsoft are companies."
        assert len(result.extracted_entities) == 2
        assert len(result.layers_executed) == 2
        assert result.total_duration_ms == 250
        assert result.created_at == now

    def test_construct_with_minimal_fields(self):
        """Create an ExtractionResult with minimal fields."""
        result = ExtractionResult()

        # Should have default values
        assert result.id is not None  # Has a generated UUID
        assert result.text == ""
        assert result.extracted_entities == []
        assert result.layers_executed == []
        assert result.total_duration_ms == 0
        assert result.created_at is not None  # Has a generated timestamp

    def test_extraction_result_id_is_unique(self):
        """Each ExtractionResult gets a unique ID when not specified."""
        result1 = ExtractionResult(text="Text1")
        result2 = ExtractionResult(text="Text2")

        assert result1.id != result2.id

    def test_extraction_result_created_at_is_unique(self):
        """Each ExtractionResult gets a timestamp when not specified."""
        result1 = ExtractionResult(text="Text1")
        result2 = ExtractionResult(text="Text2")

        # Times may be very close but should be present
        assert result1.created_at is not None
        assert result2.created_at is not None

    def test_extraction_result_with_entities(self):
        """ExtractionResult can store extracted entities."""
        entities = [
            ExtractedEntity(label="Apple", source_layer=1),
            ExtractedEntity(label="Microsoft", source_layer=2),
            ExtractedEntity(label="Google", source_layer=1),
        ]

        result = ExtractionResult(
            text="Tech companies",
            extracted_entities=entities,
        )

        assert len(result.extracted_entities) == 3
        assert result.extracted_entities[0].label == "Apple"

    def test_extraction_result_with_layers(self):
        """ExtractionResult can store layer execution metadata."""
        layers = [
            ExtractionLayerResult(
                layer_number=0,
                layer_name="Layer 0",
                entities_found=2,
                duration_ms=50,
                success=True,
            ),
            ExtractionLayerResult(
                layer_number=1,
                layer_name="Layer 1",
                entities_found=3,
                duration_ms=75,
                success=True,
            ),
            ExtractionLayerResult(
                layer_number=2,
                layer_name="Layer 2",
                entities_found=0,
                duration_ms=10,
                success=False,
                error_message="Layer failed",
            ),
        ]

        result = ExtractionResult(
            text="Test",
            layers_executed=layers,
        )

        assert len(result.layers_executed) == 3
        assert result.layers_executed[2].success is False
        assert result.layers_executed[2].error_message == "Layer failed"

    def test_extraction_result_mutable_lists(self):
        """ExtractionResult entity and layer lists can be modified."""
        result = ExtractionResult()

        entity = ExtractedEntity(label="Test")
        result.extracted_entities.append(entity)
        assert len(result.extracted_entities) == 1

        layer = ExtractionLayerResult(
            layer_number=0,
            layer_name="Test",
            entities_found=1,
            duration_ms=50,
            success=True,
        )
        result.layers_executed.append(layer)
        assert len(result.layers_executed) == 1

    def test_extraction_result_invalid_negative_duration(self):
        """ExtractionResult raises ValueError if total_duration_ms is negative."""
        with pytest.raises(ValueError, match="total_duration_ms must be non-negative"):
            ExtractionResult(text="Test", total_duration_ms=-1)

    def test_extraction_result_invalid_large_negative_duration(self):
        """ExtractionResult raises ValueError if total_duration_ms is very negative."""
        with pytest.raises(ValueError, match="total_duration_ms must be non-negative"):
            ExtractionResult(text="Test", total_duration_ms=-1000)

    def test_extraction_result_valid_boundary_duration_zero(self):
        """ExtractionResult accepts total_duration_ms=0."""
        result = ExtractionResult(text="Test", total_duration_ms=0)
        assert result.total_duration_ms == 0

    def test_extraction_result_valid_positive_duration(self):
        """ExtractionResult accepts positive total_duration_ms."""
        result = ExtractionResult(text="Test", total_duration_ms=1000)
        assert result.total_duration_ms == 1000


class TestExtractionLayerResult:
    """Tests for ExtractionLayerResult value object validation."""

    def test_extraction_layer_result_invalid_negative_layer_number(self):
        """ExtractionLayerResult raises ValueError if layer_number is negative."""
        with pytest.raises(ValueError, match="layer_number must be 0-3"):
            ExtractionLayerResult(
                layer_number=-1,
                layer_name="Test",
                entities_found=0,
                duration_ms=0,
                success=True,
            )

    def test_extraction_layer_result_invalid_too_high_layer_number(self):
        """ExtractionLayerResult raises ValueError if layer_number is > 3."""
        with pytest.raises(ValueError, match="layer_number must be 0-3"):
            ExtractionLayerResult(
                layer_number=4,
                layer_name="Test",
                entities_found=0,
                duration_ms=0,
                success=True,
            )

    def test_extraction_layer_result_invalid_boundary_layer_number(self):
        """ExtractionLayerResult raises ValueError if layer_number is 5."""
        with pytest.raises(ValueError, match="layer_number must be 0-3"):
            ExtractionLayerResult(
                layer_number=5,
                layer_name="Test",
                entities_found=0,
                duration_ms=0,
                success=True,
            )

    def test_extraction_layer_result_valid_boundary_layer_zero(self):
        """ExtractionLayerResult accepts layer_number=0."""
        result = ExtractionLayerResult(
            layer_number=0,
            layer_name="KG Context",
            entities_found=2,
            duration_ms=100,
            success=True,
        )
        assert result.layer_number == 0

    def test_extraction_layer_result_valid_boundary_layer_three(self):
        """ExtractionLayerResult accepts layer_number=3."""
        result = ExtractionLayerResult(
            layer_number=3,
            layer_name="Reference",
            entities_found=1,
            duration_ms=50,
            success=True,
        )
        assert result.layer_number == 3


class TestProcessingMetrics:
    """Tests for ProcessingMetrics dataclass."""

    def test_construct_with_all_fields(self):
        """Create a ProcessingMetrics with all fields."""
        metrics = ProcessingMetrics(
            layer_name="LLM Extraction",
            duration_ms=500,
            tokens_processed=1000,
            entities_found=5,
            relationships_found=3,
            error_count=1,
            skipped_count=2,
        )

        assert metrics.layer_name == "LLM Extraction"
        assert metrics.duration_ms == 500
        assert metrics.tokens_processed == 1000
        assert metrics.entities_found == 5
        assert metrics.relationships_found == 3
        assert metrics.error_count == 1
        assert metrics.skipped_count == 2

    def test_construct_with_minimal_fields(self):
        """Create a ProcessingMetrics with minimal fields."""
        metrics = ProcessingMetrics(
            layer_name="Test Layer",
            duration_ms=100,
        )

        assert metrics.layer_name == "Test Layer"
        assert metrics.duration_ms == 100
        assert metrics.tokens_processed == 0
        assert metrics.entities_found == 0
        assert metrics.relationships_found == 0
        assert metrics.error_count == 0
        assert metrics.skipped_count == 0

    def test_processing_metrics_is_frozen(self):
        """ProcessingMetrics is frozen and immutable."""
        metrics = ProcessingMetrics(
            layer_name="Test",
            duration_ms=100,
        )
        with pytest.raises(Exception):
            metrics.duration_ms = 200

    def test_processing_metrics_invalid_negative_duration(self):
        """ProcessingMetrics raises ValueError if duration_ms is negative."""
        with pytest.raises(ValueError, match="duration_ms must be non-negative"):
            ProcessingMetrics(
                layer_name="Test",
                duration_ms=-1,
            )

    def test_processing_metrics_invalid_negative_tokens(self):
        """ProcessingMetrics raises ValueError if tokens_processed is negative."""
        with pytest.raises(ValueError, match="tokens_processed must be non-negative"):
            ProcessingMetrics(
                layer_name="Test",
                duration_ms=100,
                tokens_processed=-1,
            )

    def test_processing_metrics_invalid_negative_entities(self):
        """ProcessingMetrics raises ValueError if entities_found is negative."""
        with pytest.raises(ValueError, match="entities_found must be non-negative"):
            ProcessingMetrics(
                layer_name="Test",
                duration_ms=100,
                entities_found=-1,
            )

    def test_processing_metrics_invalid_negative_relationships(self):
        """ProcessingMetrics raises ValueError if relationships_found is negative."""
        with pytest.raises(ValueError, match="relationships_found must be non-negative"):
            ProcessingMetrics(
                layer_name="Test",
                duration_ms=100,
                relationships_found=-1,
            )

    def test_processing_metrics_invalid_negative_errors(self):
        """ProcessingMetrics raises ValueError if error_count is negative."""
        with pytest.raises(ValueError, match="error_count must be non-negative"):
            ProcessingMetrics(
                layer_name="Test",
                duration_ms=100,
                error_count=-1,
            )

    def test_processing_metrics_invalid_negative_skipped(self):
        """ProcessingMetrics raises ValueError if skipped_count is negative."""
        with pytest.raises(ValueError, match="skipped_count must be non-negative"):
            ProcessingMetrics(
                layer_name="Test",
                duration_ms=100,
                skipped_count=-1,
            )

    def test_processing_metrics_valid_boundary_zero(self):
        """ProcessingMetrics accepts all zero values."""
        metrics = ProcessingMetrics(
            layer_name="Test",
            duration_ms=0,
            tokens_processed=0,
            entities_found=0,
            relationships_found=0,
            error_count=0,
            skipped_count=0,
        )
        assert metrics.duration_ms == 0
