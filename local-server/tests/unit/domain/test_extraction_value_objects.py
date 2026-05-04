"""
Unit tests for extraction domain value objects.

Tests cover immutability, type conversions, and validation for
LayerInput, LayerOutput, and ExtractionLayerResult.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from types import MappingProxyType

from domain.extraction.value_objects import (
    LayerInput,
    LayerOutput,
    ExtractionLayerResult,
)
from domain.extraction.entities import ExtractedEntity


class TestLayerInput:
    """Tests for LayerInput value object."""

    def test_layer_input_with_tuple_entities_and_kg_context(self):
        """Create a LayerInput with tuple of entities and KG context."""
        entity = ExtractedEntity(label="Apple", source_layer=0)
        kg_context_dict = {"entity": "company", "domain": "technology"}

        layer_input = LayerInput(
            text="Apple and Microsoft are tech companies",
            existing_entities=(entity,),
            kg_context=(kg_context_dict,),
        )

        assert layer_input.text == "Apple and Microsoft are tech companies"
        assert isinstance(layer_input.existing_entities, tuple)
        assert len(layer_input.existing_entities) == 1
        assert layer_input.existing_entities[0].label == "Apple"
        assert isinstance(layer_input.kg_context, tuple)
        assert len(layer_input.kg_context) == 1
        assert layer_input.kg_context[0]["entity"] == "company"

    def test_layer_input_with_empty_entities_and_kg_context(self):
        """Create a LayerInput with empty tuple of entities and None KG context."""
        layer_input = LayerInput(
            text="Test text",
            existing_entities=(),
            kg_context=None,
        )

        assert layer_input.text == "Test text"
        assert layer_input.existing_entities == ()
        assert layer_input.kg_context is None

    def test_layer_input_entities_is_tuple_and_immutable(self):
        """LayerInput.existing_entities is a tuple and immutable."""
        entity = ExtractedEntity(label="Test", source_layer=0)
        layer_input = LayerInput(
            text="Test",
            existing_entities=(entity,),
        )

        with pytest.raises(AttributeError):
            layer_input.existing_entities.append(ExtractedEntity(label="Another"))

    def test_layer_input_kg_context_is_tuple_and_immutable(self):
        """LayerInput.kg_context tuple is immutable."""
        kg_context = ({"key": "value"},)
        layer_input = LayerInput(
            text="Test",
            existing_entities=(),
            kg_context=kg_context,
        )

        with pytest.raises(AttributeError):
            layer_input.kg_context.append({"another": "value"})

    def test_layer_input_is_frozen(self):
        """LayerInput is frozen and immutable."""
        layer_input = LayerInput(
            text="Test",
            existing_entities=(),
        )

        with pytest.raises(Exception):
            layer_input.text = "Changed"

    def test_layer_input_with_multiple_entities(self):
        """Create a LayerInput with multiple entities."""
        entities = (
            ExtractedEntity(label="Apple", source_layer=0),
            ExtractedEntity(label="Microsoft", source_layer=1),
            ExtractedEntity(label="Google", source_layer=2),
        )
        layer_input = LayerInput(
            text="Tech companies",
            existing_entities=entities,
        )

        assert len(layer_input.existing_entities) == 3
        assert layer_input.existing_entities[0].label == "Apple"
        assert layer_input.existing_entities[2].label == "Google"

    def test_layer_input_with_multiple_kg_contexts(self):
        """Create a LayerInput with multiple KG context dicts."""
        kg_context = (
            {"type": "organization", "domain": "tech"},
            {"type": "company", "industry": "software"},
        )
        layer_input = LayerInput(
            text="Test",
            existing_entities=(),
            kg_context=kg_context,
        )

        assert len(layer_input.kg_context) == 2
        assert layer_input.kg_context[0]["domain"] == "tech"
        assert layer_input.kg_context[1]["industry"] == "software"


class TestLayerOutput:
    """Tests for LayerOutput value object."""

    def test_layer_output_with_tuple_entities_and_metadata(self):
        """Create a LayerOutput with tuple of entities and immutable metadata."""
        entity = ExtractedEntity(label="Apple", source_layer=1)
        metadata_dict = {"extraction_method": "llm", "model": "gpt-4"}
        metadata = MappingProxyType(metadata_dict)

        layer_output = LayerOutput(
            entities=(entity,),
            metadata=metadata,
        )

        assert isinstance(layer_output.entities, tuple)
        assert len(layer_output.entities) == 1
        assert layer_output.entities[0].label == "Apple"
        assert isinstance(layer_output.metadata, MappingProxyType)
        assert layer_output.metadata["extraction_method"] == "llm"

    def test_layer_output_with_empty_entities_and_none_metadata(self):
        """Create a LayerOutput with empty tuple and None metadata."""
        layer_output = LayerOutput(
            entities=(),
            metadata=None,
        )

        assert layer_output.entities == ()
        assert layer_output.metadata is None

    def test_layer_output_entities_is_tuple_and_immutable(self):
        """LayerOutput.entities is a tuple and immutable."""
        entity = ExtractedEntity(label="Test", source_layer=1)
        layer_output = LayerOutput(
            entities=(entity,),
        )

        with pytest.raises(AttributeError):
            layer_output.entities.append(ExtractedEntity(label="Another"))

    def test_layer_output_metadata_is_immutable(self):
        """LayerOutput.metadata wrapped in MappingProxyType is immutable."""
        metadata_dict = {"key": "value"}
        metadata = MappingProxyType(metadata_dict)
        layer_output = LayerOutput(
            entities=(),
            metadata=metadata,
        )

        with pytest.raises(TypeError):
            layer_output.metadata["new_key"] = "new_value"

    def test_layer_output_is_frozen(self):
        """LayerOutput is frozen and immutable."""
        layer_output = LayerOutput(
            entities=(),
        )

        with pytest.raises(Exception):
            layer_output.entities = (ExtractedEntity(label="Test"),)

    def test_layer_output_with_multiple_entities(self):
        """Create a LayerOutput with multiple entities."""
        entities = (
            ExtractedEntity(label="Apple", source_layer=1),
            ExtractedEntity(label="Microsoft", source_layer=1),
        )
        layer_output = LayerOutput(
            entities=entities,
        )

        assert len(layer_output.entities) == 2
        assert layer_output.entities[1].label == "Microsoft"

    def test_layer_output_metadata_dict_contains_multiple_keys(self):
        """Create a LayerOutput with rich metadata."""
        metadata_dict = {
            "extraction_method": "nlp",
            "language": "en",
            "confidence": 0.95,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        metadata = MappingProxyType(metadata_dict)
        layer_output = LayerOutput(
            entities=(),
            metadata=metadata,
        )

        assert len(layer_output.metadata) == 4
        assert layer_output.metadata["confidence"] == 0.95


class TestExtractionLayerResult:
    """Tests for ExtractionLayerResult frozen value object."""

    def test_extraction_layer_result_is_frozen(self):
        """ExtractionLayerResult is frozen and immutable."""
        result = ExtractionLayerResult(
            layer_number=0,
            layer_name="Test",
            entities_found=5,
            duration_ms=100,
            success=True,
        )

        with pytest.raises(Exception):
            result.layer_name = "Changed"

    def test_extraction_layer_result_with_error_message(self):
        """ExtractionLayerResult can store error message when failed."""
        result = ExtractionLayerResult(
            layer_number=1,
            layer_name="LLM Layer",
            entities_found=0,
            duration_ms=50,
            success=False,
            error_message="API timeout",
        )

        assert result.success is False
        assert result.error_message == "API timeout"
        assert result.entities_found == 0
