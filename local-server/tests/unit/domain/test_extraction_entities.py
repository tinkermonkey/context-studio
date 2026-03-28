"""
Unit tests for extraction domain entities.

Tests cover entity construction, field initialization, and dataclass behavior
for ExtractedEntity and ExtractionResult.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime, timezone

from domain.extraction.entities import ExtractedEntity, ExtractionResult
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

    def test_extracted_entity_source_layers(self):
        """ExtractedEntity supports all source layer values."""
        for layer in [0, 1, 2, 3]:
            entity = ExtractedEntity(label="Test", source_layer=layer)
            assert entity.source_layer == layer

    def test_extracted_entity_confidence_range(self):
        """ExtractedEntity can store confidence values."""
        for confidence in [0.0, 0.5, 0.95, 1.0]:
            entity = ExtractedEntity(label="Test", confidence=confidence)
            assert entity.confidence == confidence


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

    def test_extraction_result_duration(self):
        """ExtractionResult tracks total duration."""
        result = ExtractionResult(text="Test", total_duration_ms=523)
        assert result.total_duration_ms == 523

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
