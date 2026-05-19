"""
Unit tests for extraction domain ports and port value objects.

Tests cover validation and invariants for NLPEntity and ReferenceResult
which are used in port contracts.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.extraction.ports import (
    NLPEntity,
    NLPResult,
    ReferenceRelation,
    ReferenceResult,
)


class TestNLPEntity:
    """Tests for NLPEntity value object."""

    def test_construct_with_all_fields(self):
        """Create an NLPEntity with all fields."""
        entity = NLPEntity(
            text="Apple Inc.",
            label="ORG",
            start=0,
            end=9,
            confidence=0.95,
            linked_uri="https://example.com/apple",
        )

        assert entity.text == "Apple Inc."
        assert entity.label == "ORG"
        assert entity.start == 0
        assert entity.end == 9
        assert entity.confidence == 0.95
        assert entity.linked_uri == "https://example.com/apple"

    def test_construct_with_minimal_fields(self):
        """Create an NLPEntity with minimal fields."""
        entity = NLPEntity(
            text="Test",
            label="PERSON",
            start=5,
            end=9,
            confidence=0.8,
        )

        assert entity.text == "Test"
        assert entity.label == "PERSON"
        assert entity.start == 5
        assert entity.end == 9
        assert entity.confidence == 0.8
        assert entity.linked_uri is None

    def test_nlp_entity_is_frozen(self):
        """NLPEntity is frozen and immutable."""
        entity = NLPEntity(
            text="Test",
            label="PERSON",
            start=0,
            end=4,
            confidence=0.9,
        )

        with pytest.raises(Exception):
            entity.text = "Changed"

    def test_nlp_entity_invalid_confidence_negative(self):
        """NLPEntity raises ValueError if confidence is negative."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            NLPEntity(
                text="Test",
                label="PERSON",
                start=0,
                end=4,
                confidence=-0.1,
            )

    def test_nlp_entity_invalid_confidence_too_high(self):
        """NLPEntity raises ValueError if confidence is > 1.0."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            NLPEntity(
                text="Test",
                label="PERSON",
                start=0,
                end=4,
                confidence=1.1,
            )

    def test_nlp_entity_invalid_confidence_just_over(self):
        """NLPEntity raises ValueError if confidence is slightly > 1.0."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            NLPEntity(
                text="Test",
                label="PERSON",
                start=0,
                end=4,
                confidence=1.01,
            )

    def test_nlp_entity_invalid_span_end_less_than_start(self):
        """NLPEntity raises ValueError if end < start."""
        with pytest.raises(ValueError, match="end must be >= start"):
            NLPEntity(
                text="Test",
                label="PERSON",
                start=10,
                end=5,
                confidence=0.9,
            )

    def test_nlp_entity_invalid_span_end_equals_start(self):
        """NLPEntity allows end == start (zero-length span)."""
        entity = NLPEntity(
            text="",
            label="PERSON",
            start=5,
            end=5,
            confidence=0.9,
        )
        assert entity.start == entity.end

    def test_nlp_entity_valid_boundary_confidence_zero(self):
        """NLPEntity accepts confidence=0.0."""
        entity = NLPEntity(
            text="Test",
            label="PERSON",
            start=0,
            end=4,
            confidence=0.0,
        )
        assert entity.confidence == 0.0

    def test_nlp_entity_valid_boundary_confidence_one(self):
        """NLPEntity accepts confidence=1.0."""
        entity = NLPEntity(
            text="Test",
            label="PERSON",
            start=0,
            end=4,
            confidence=1.0,
        )
        assert entity.confidence == 1.0

    def test_nlp_entity_with_large_span(self):
        """NLPEntity can have large character offsets."""
        entity = NLPEntity(
            text="phrase",
            label="LOCATION",
            start=1000,
            end=1006,
            confidence=0.75,
        )
        assert entity.start == 1000
        assert entity.end == 1006

    def test_nlp_entity_with_special_characters(self):
        """NLPEntity can handle special characters in text."""
        entity = NLPEntity(
            text="Dr. John O'Brien, Ph.D.",
            label="PERSON",
            start=0,
            end=25,
            confidence=0.85,
        )
        assert "O'Brien" in entity.text


class TestNLPResult:
    """Tests for NLPResult value object."""

    def test_nlp_result_construction(self):
        """Create an NLPResult with all components."""
        entities = [
            NLPEntity(text="Apple", label="ORG", start=0, end=5, confidence=0.9),
            NLPEntity(text="Inc.", label="ORG", start=6, end=10, confidence=0.85),
        ]
        tokens = ["Apple", "Inc.", "is", "a", "company"]
        noun_chunks = ["Apple Inc."]

        result = NLPResult(
            tokens=tokens,
            entities=entities,
            noun_chunks=noun_chunks,
            language="en",
        )

        assert len(result.tokens) == 5
        assert len(result.entities) == 2
        assert len(result.noun_chunks) == 1
        assert result.language == "en"

    def test_nlp_result_is_frozen(self):
        """NLPResult is frozen and immutable."""
        result = NLPResult(
            tokens=["test"],
            entities=[],
            noun_chunks=[],
            language="en",
        )

        with pytest.raises(Exception):
            result.language = "es"


class TestReferenceResult:
    """Tests for ReferenceResult value object."""

    def test_construct_with_all_fields(self):
        """Create a ReferenceResult with all fields."""
        result = ReferenceResult(
            uri="https://example.com/apple",
            label="Apple Inc.",
            description="Technology company",
            confidence=0.95,
            source="DBpedia",
        )

        assert result.uri == "https://example.com/apple"
        assert result.label == "Apple Inc."
        assert result.description == "Technology company"
        assert result.confidence == 0.95
        assert result.source == "DBpedia"

    def test_construct_with_minimal_fields(self):
        """Create a ReferenceResult with minimal fields."""
        result = ReferenceResult(
            uri="https://example.com/apple",
            label="Apple",
        )

        assert result.uri == "https://example.com/apple"
        assert result.label == "Apple"
        assert result.description is None
        assert result.confidence == 1.0  # Default
        assert result.source == ""  # Default

    def test_reference_result_is_frozen(self):
        """ReferenceResult is frozen and immutable."""
        result = ReferenceResult(
            uri="https://example.com/apple",
            label="Apple",
        )

        with pytest.raises(Exception):
            result.label = "Changed"

    def test_reference_result_invalid_confidence_negative(self):
        """ReferenceResult raises ValueError if confidence is negative."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ReferenceResult(
                uri="https://example.com/apple",
                label="Apple",
                confidence=-0.1,
            )

    def test_reference_result_invalid_confidence_too_high(self):
        """ReferenceResult raises ValueError if confidence is > 1.0."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ReferenceResult(
                uri="https://example.com/apple",
                label="Apple",
                confidence=1.5,
            )

    def test_reference_result_invalid_confidence_just_over(self):
        """ReferenceResult raises ValueError if confidence is slightly > 1.0."""
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ReferenceResult(
                uri="https://example.com/apple",
                label="Apple",
                confidence=1.01,
            )

    def test_reference_result_valid_boundary_confidence_zero(self):
        """ReferenceResult accepts confidence=0.0."""
        result = ReferenceResult(
            uri="https://example.com/apple",
            label="Apple",
            confidence=0.0,
        )
        assert result.confidence == 0.0

    def test_reference_result_valid_boundary_confidence_one(self):
        """ReferenceResult accepts confidence=1.0."""
        result = ReferenceResult(
            uri="https://example.com/apple",
            label="Apple",
            confidence=1.0,
        )
        assert result.confidence == 1.0

    def test_reference_result_with_description(self):
        """ReferenceResult can have an optional description."""
        result = ReferenceResult(
            uri="https://example.com/apple",
            label="Apple Inc.",
            description="American multinational technology company",
            confidence=0.92,
            source="ConceptNet",
        )

        assert result.description == "American multinational technology company"
        assert result.source == "ConceptNet"

    def test_reference_result_from_different_sources(self):
        """ReferenceResult can come from different reference sources."""
        sources = ["DBpedia", "ConceptNet", "Wikidata", "schema.org"]

        for source in sources:
            result = ReferenceResult(
                uri=f"https://example.com/{source.lower()}/item",
                label="Test",
                source=source,
            )
            assert result.source == source


class TestReferenceRelation:
    """Tests for ReferenceRelation value object."""

    def test_reference_relation_construction(self):
        """Create a ReferenceRelation with required fields."""
        relation = ReferenceRelation(
            subject_uri="https://example.com/apple",
            predicate="narrower",
            object_uri="https://example.com/tech-company",
        )

        assert relation.subject_uri == "https://example.com/apple"
        assert relation.predicate == "narrower"
        assert relation.object_uri == "https://example.com/tech-company"
        assert relation.weight is None
        assert relation.source == ""

    def test_reference_relation_with_weight_and_source(self):
        """Create a ReferenceRelation with optional fields."""
        relation = ReferenceRelation(
            subject_uri="https://example.com/apple",
            predicate="similar_to",
            object_uri="https://example.com/microsoft",
            weight=0.85,
            source="ConceptNet",
        )

        assert relation.weight == 0.85
        assert relation.source == "ConceptNet"

    def test_reference_relation_is_frozen(self):
        """ReferenceRelation is frozen and immutable."""
        relation = ReferenceRelation(
            subject_uri="https://example.com/apple",
            predicate="narrower",
            object_uri="https://example.com/tech",
        )

        with pytest.raises(Exception):
            relation.predicate = "broader"
