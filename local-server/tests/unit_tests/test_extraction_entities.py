"""
Unit tests for extraction domain entities.

Tests validate invariant enforcement, enum usage, immutability of
extracted entities, layer results, and extraction results.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.extraction.entities import ExtractedEntity, ExtractionLayerResult, ExtractionResult
from domain.extraction.enums import EntityType, LayerName


class TestEntityType:
    """Tests for EntityType enum."""

    def test_entity_type_values(self):
        """Test that EntityType has all expected values."""
        assert EntityType.PERSON.value == "person"
        assert EntityType.ORGANIZATION.value == "organization"
        assert EntityType.LOCATION.value == "location"
        assert EntityType.CONCEPT.value == "concept"
        assert EntityType.UNKNOWN.value == "unknown"

    def test_entity_type_from_string(self):
        """Test creating EntityType from string value."""
        assert EntityType("person") == EntityType.PERSON
        assert EntityType("organization") == EntityType.ORGANIZATION


class TestLayerName:
    """Tests for LayerName enum."""

    def test_layer_name_values(self):
        """Test that LayerName has all expected values."""
        assert LayerName.KG.value == "kg"
        assert LayerName.NLP.value == "nlp"
        assert LayerName.LLM.value == "llm"
        assert LayerName.WEB.value == "web"


class TestExtractedEntity:
    """Tests for ExtractedEntity entity."""

    def test_valid_extracted_entity(self):
        """Test creating a valid extracted entity."""
        entity = ExtractedEntity(
            text="John Doe",
            entity_type=EntityType.PERSON,
            confidence=0.95,
            start_pos=0,
            end_pos=8,
            suggested_class_id="person-123"
        )
        assert entity.text == "John Doe"
        assert entity.entity_type == EntityType.PERSON
        assert entity.confidence == 0.95

    def test_extracted_entity_confidence_validation(self):
        """Test that confidence must be between 0.0 and 1.0."""
        # Valid: 0.0
        entity = ExtractedEntity(
            text="Test",
            entity_type=EntityType.CONCEPT,
            confidence=0.0,
            start_pos=0,
            end_pos=4
        )
        assert entity.confidence == 0.0

        # Valid: 1.0
        entity = ExtractedEntity(
            text="Test",
            entity_type=EntityType.CONCEPT,
            confidence=1.0,
            start_pos=0,
            end_pos=4
        )
        assert entity.confidence == 1.0

        # Invalid: > 1.0
        with pytest.raises(ValueError, match="confidence must be a number between 0.0 and 1.0"):
            ExtractedEntity(
                text="Test",
                entity_type=EntityType.CONCEPT,
                confidence=1.5,
                start_pos=0,
                end_pos=4
            )

        # Invalid: < 0.0
        with pytest.raises(ValueError, match="confidence must be a number between 0.0 and 1.0"):
            ExtractedEntity(
                text="Test",
                entity_type=EntityType.CONCEPT,
                confidence=-0.1,
                start_pos=0,
                end_pos=4
            )

        # Invalid: bool (even though bool is subclass of int)
        with pytest.raises(ValueError, match="confidence must be a number between 0.0 and 1.0"):
            ExtractedEntity(
                text="Test",
                entity_type=EntityType.CONCEPT,
                confidence=True,
                start_pos=0,
                end_pos=4
            )

    def test_extracted_entity_position_validation(self):
        """Test that positions must be valid."""
        # Invalid: end_pos <= start_pos
        with pytest.raises(ValueError, match="end_pos must be greater than start_pos"):
            ExtractedEntity(
                text="Test",
                entity_type=EntityType.CONCEPT,
                confidence=0.9,
                start_pos=5,
                end_pos=3
            )

        # Invalid: end_pos == start_pos
        with pytest.raises(ValueError, match="end_pos must be greater than start_pos"):
            ExtractedEntity(
                text="Test",
                entity_type=EntityType.CONCEPT,
                confidence=0.9,
                start_pos=5,
                end_pos=5
            )

        # Invalid: negative start_pos
        with pytest.raises(ValueError, match="start_pos must be a non-negative integer"):
            ExtractedEntity(
                text="Test",
                entity_type=EntityType.CONCEPT,
                confidence=0.9,
                start_pos=-1,
                end_pos=4
            )

    def test_extracted_entity_invalid_text(self):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="text must be a non-empty string"):
            ExtractedEntity(
                text="",
                entity_type=EntityType.PERSON,
                confidence=0.9,
                start_pos=0,
                end_pos=4
            )

    def test_extracted_entity_invalid_entity_type(self):
        """Test that non-enum entity_type raises TypeError."""
        with pytest.raises(TypeError, match="entity_type must be an EntityType enum"):
            ExtractedEntity(
                text="Test",
                entity_type="person",  # String instead of enum
                confidence=0.9,
                start_pos=0,
                end_pos=4
            )

    def test_extracted_entity_invalid_suggested_class_id(self):
        """Test that non-string suggested_class_id raises TypeError."""
        with pytest.raises(TypeError, match="suggested_class_id must be None or a string"):
            ExtractedEntity(
                text="Test",
                entity_type=EntityType.PERSON,
                confidence=0.9,
                start_pos=0,
                end_pos=4,
                suggested_class_id=123
            )


class TestExtractionLayerResult:
    """Tests for ExtractionLayerResult entity."""

    def test_valid_extraction_layer_result(self):
        """Test creating a valid extraction layer result."""
        entity = ExtractedEntity(
            text="John Doe",
            entity_type=EntityType.PERSON,
            confidence=0.95,
            start_pos=0,
            end_pos=8
        )
        result = ExtractionLayerResult(
            layer_name=LayerName.NLP,
            entities=(entity,),
            relationships=({"rel_1": {"type": "knows", "target": "Jane"}},)
        )
        assert result.layer_name == LayerName.NLP
        assert len(result.entities) == 1
        assert result.entities[0].text == "John Doe"

    def test_extraction_layer_result_empty_entities(self):
        """Test extraction layer result with no entities."""
        result = ExtractionLayerResult(
            layer_name=LayerName.KG,
            entities=(),
            relationships=()
        )
        assert result.entities == ()
        assert len(result.relationships) == 0

    def test_extraction_layer_result_entities_immutable(self):
        """Test that entities tuple is immutable."""
        entity = ExtractedEntity(
            text="Test",
            entity_type=EntityType.CONCEPT,
            confidence=0.9,
            start_pos=0,
            end_pos=4
        )
        result = ExtractionLayerResult(
            layer_name=LayerName.LLM,
            entities=(entity,),
            relationships=()
        )
        with pytest.raises((TypeError, AttributeError)):
            result.entities[0] = None

    def test_extraction_layer_result_relationships_immutable(self):
        """Test that relationships tuple is immutable."""
        result = ExtractionLayerResult(
            layer_name=LayerName.WEB,
            entities=(),
            relationships=({"rel_1": {"type": "similar"}},)
        )
        with pytest.raises((TypeError, AttributeError)):
            result.relationships[0] = {"rel_2": {"type": "related"}}

    def test_extraction_layer_result_invalid_layer_name(self):
        """Test that non-enum layer_name raises TypeError."""
        with pytest.raises(TypeError, match="layer_name must be a LayerName enum"):
            ExtractionLayerResult(
                layer_name="nlp",  # String instead of enum
                entities=(),
                relationships=()
            )

    def test_extraction_layer_result_invalid_entities(self):
        """Test that non-tuple entities raises TypeError."""
        with pytest.raises(TypeError, match="entities must be a tuple"):
            ExtractionLayerResult(
                layer_name=LayerName.NLP,
                entities=[],  # List instead of tuple
                relationships=()
            )

    def test_extraction_layer_result_invalid_entity_element(self):
        """Test that non-ExtractedEntity elements raise TypeError."""
        with pytest.raises(TypeError, match="All entities must be ExtractedEntity instances"):
            ExtractionLayerResult(
                layer_name=LayerName.NLP,
                entities=({"text": "invalid"},),  # Dict instead of ExtractedEntity
                relationships=()
            )

    def test_extraction_layer_result_invalid_relationships(self):
        """Test that non-tuple relationships raises TypeError."""
        with pytest.raises(TypeError, match="relationships must be a tuple of dicts"):
            ExtractionLayerResult(
                layer_name=LayerName.NLP,
                entities=(),
                relationships={"rel": {}}  # Dict instead of tuple
            )


class TestExtractionResult:
    """Tests for ExtractionResult entity."""

    def test_valid_extraction_result(self):
        """Test creating a valid extraction result."""
        entity = ExtractedEntity(
            text="John",
            entity_type=EntityType.PERSON,
            confidence=0.9,
            start_pos=0,
            end_pos=4
        )
        layer = ExtractionLayerResult(
            layer_name=LayerName.NLP,
            entities=(entity,),
            relationships=()
        )
        result = ExtractionResult(
            source_text="John works at Acme.",
            layers=(layer,),
            execution_id="exec-123"
        )
        assert result.source_text == "John works at Acme."
        assert len(result.layers) == 1
        assert result.execution_id == "exec-123"

    def test_extraction_result_empty_layers(self):
        """Test extraction result with no layers."""
        result = ExtractionResult(
            source_text="Some text",
            layers=(),
            execution_id=None
        )
        assert result.layers == ()

    def test_extraction_result_layers_immutable(self):
        """Test that layers tuple is immutable."""
        layer = ExtractionLayerResult(
            layer_name=LayerName.KG,
            entities=(),
            relationships=()
        )
        result = ExtractionResult(
            source_text="Text",
            layers=(layer,),
            execution_id=None
        )
        with pytest.raises((TypeError, AttributeError)):
            result.layers[0] = None

    def test_extraction_result_invalid_source_text(self):
        """Test that empty source_text raises ValueError."""
        with pytest.raises(ValueError, match="source_text must be a non-empty string"):
            ExtractionResult(
                source_text="",
                layers=(),
                execution_id=None
            )

    def test_extraction_result_invalid_layers(self):
        """Test that non-tuple layers raises TypeError."""
        with pytest.raises(TypeError, match="layers must be a tuple"):
            ExtractionResult(
                source_text="Text",
                layers=[],  # List instead of tuple
                execution_id=None
            )

    def test_extraction_result_invalid_layer_element(self):
        """Test that non-ExtractionLayerResult elements raise TypeError."""
        with pytest.raises(TypeError, match="All layers must be ExtractionLayerResult instances"):
            ExtractionResult(
                source_text="Text",
                layers=({"layer_name": "nlp"},),  # Dict instead of ExtractionLayerResult
                execution_id=None
            )

    def test_extraction_result_invalid_execution_id(self):
        """Test that non-string execution_id raises TypeError."""
        with pytest.raises(TypeError, match="execution_id must be None or a string"):
            ExtractionResult(
                source_text="Text",
                layers=(),
                execution_id=123
            )
