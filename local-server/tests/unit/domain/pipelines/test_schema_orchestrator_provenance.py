"""
Unit tests for schema orchestrator provenance serialization.

Tests for:
- _serialize_provenance function in schema extraction orchestrator
- CandidateClass.to_dict() with provenance
- CandidatePropertyDefinition.to_dict() with provenance
- CandidateConnection.to_dict() with provenance
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.extraction.value_objects import SourceSpan
from domain.pipelines.schema_extraction.orchestrator import (
    CandidateClass,
    CandidateConnection,
    CandidatePropertyDefinition,
    _serialize_provenance,
)


class TestSerializeProvenanceFunction:
    """Tests for _serialize_provenance function."""

    def test_serialize_fully_resolved_spans(self):
        """Serialize fully-resolved spans with quote and offsets."""
        spans = [
            SourceSpan(quote="Microservice", start=0, end=12),
            SourceSpan(quote="Architecture", start=20, end=32),
        ]

        result = _serialize_provenance(spans)

        assert len(result) == 2
        assert result[0]["quote"] == "Microservice"
        assert result[0]["start"] == 0
        assert result[0]["end"] == 12
        assert result[1]["quote"] == "Architecture"
        assert result[1]["start"] == 20
        assert result[1]["end"] == 32

    def test_serialize_quote_only_spans(self):
        """Serialize quote-only spans (fuzzy-matched, no offsets)."""
        spans = [
            SourceSpan(quote="Technology", start=None, end=None),
            SourceSpan(quote="System", start=None, end=None),
        ]

        result = _serialize_provenance(spans)

        assert len(result) == 2
        assert result[0]["quote"] == "Technology"
        assert result[0]["start"] is None
        assert result[0]["end"] is None
        assert result[1]["quote"] == "System"
        assert result[1]["start"] is None
        assert result[1]["end"] is None

    def test_serialize_mixed_spans(self):
        """Serialize a mix of fully-resolved and quote-only spans."""
        spans = [
            SourceSpan(quote="Kubernetes", start=0, end=10),  # fully resolved
            SourceSpan(quote="Container", start=None, end=None),  # quote-only
            SourceSpan(quote="Orchestration", start=25, end=38),  # fully resolved
        ]

        result = _serialize_provenance(spans)

        assert len(result) == 3
        # First span: fully resolved
        assert result[0]["quote"] == "Kubernetes"
        assert result[0]["start"] == 0
        assert result[0]["end"] == 10
        # Second span: quote-only
        assert result[1]["quote"] == "Container"
        assert result[1]["start"] is None
        assert result[1]["end"] is None
        # Third span: fully resolved
        assert result[2]["quote"] == "Orchestration"
        assert result[2]["start"] == 25
        assert result[2]["end"] == 38

    def test_exclude_unresolved_spans_without_quote(self):
        """Unresolved spans (all None) are excluded from serialization."""
        spans = [
            SourceSpan(quote="Known", start=0, end=5),
            SourceSpan(quote=None, start=None, end=None),  # unresolved
            SourceSpan(quote="AlsoKnown", start=None, end=None),  # quote-only
        ]

        result = _serialize_provenance(spans)

        # Only spans with a quote are included
        assert len(result) == 2
        assert result[0]["quote"] == "Known"
        assert result[1]["quote"] == "AlsoKnown"

    def test_serialize_empty_list(self):
        """Serialize an empty list of spans."""
        result = _serialize_provenance([])
        assert result == []

    def test_serialized_provenance_uses_correct_keys(self):
        """Verify serialized provenance uses quote/start/end, not legacy keys."""
        spans = [SourceSpan(quote="Test", start=0, end=4)]

        result = _serialize_provenance(spans)
        provenance_dict = result[0]

        # Verify correct keys exist
        assert "quote" in provenance_dict
        assert "start" in provenance_dict
        assert "end" in provenance_dict

        # Verify legacy keys do not exist
        assert "text_offset_start" not in provenance_dict
        assert "text_offset_end" not in provenance_dict
        assert "raw" not in provenance_dict


class TestCandidateClassSerialization:
    """Tests for CandidateClass.to_dict() with provenance."""

    def test_candidate_class_with_fully_resolved_provenance(self):
        """Serialize CandidateClass with fully-resolved provenance."""
        candidate = CandidateClass(
            label="Microservice",
            proposed_definition="A small independent service",
            confidence=0.85,
            provenance=[SourceSpan(quote="Microservice", start=0, end=12)],
        )

        result = candidate.to_dict()

        assert result["kind"] == "class"
        assert result["label"] == "Microservice"
        assert result["proposed_definition"] == "A small independent service"
        assert result["confidence"] == 0.85
        assert len(result["provenance"]) == 1
        assert result["provenance"][0]["quote"] == "Microservice"
        assert result["provenance"][0]["start"] == 0
        assert result["provenance"][0]["end"] == 12

    def test_candidate_class_with_quote_only_provenance(self):
        """Serialize CandidateClass with quote-only (fuzzy-matched) provenance."""
        candidate = CandidateClass(
            label="Architecture",
            proposed_definition="System design pattern",
            confidence=0.75,
            provenance=[SourceSpan(quote="Architecture", start=None, end=None)],
        )

        result = candidate.to_dict()

        assert result["kind"] == "class"
        assert result["label"] == "Architecture"
        assert len(result["provenance"]) == 1
        assert result["provenance"][0]["quote"] == "Architecture"
        assert result["provenance"][0]["start"] is None
        assert result["provenance"][0]["end"] is None

    def test_candidate_class_with_multiple_provenance(self):
        """Serialize CandidateClass with multiple provenance spans."""
        candidate = CandidateClass(
            label="Service",
            proposed_definition="A component providing functionality",
            confidence=0.9,
            provenance=[
                SourceSpan(quote="Service", start=5, end=12),
                SourceSpan(quote="Service", start=45, end=52),  # mentioned twice
            ],
        )

        result = candidate.to_dict()

        assert len(result["provenance"]) == 2
        assert all(p["quote"] == "Service" for p in result["provenance"])

    def test_candidate_class_with_no_provenance(self):
        """Serialize CandidateClass with no provenance."""
        candidate = CandidateClass(
            label="Unknown",
            proposed_definition="Unknown concept",
            confidence=0.5,
            provenance=[],
        )

        result = candidate.to_dict()

        assert result["provenance"] == []


class TestCandidatePropertyDefinitionSerialization:
    """Tests for CandidatePropertyDefinition.to_dict() with provenance."""

    def test_property_definition_with_provenance(self):
        """Serialize CandidatePropertyDefinition with provenance."""
        candidate = CandidatePropertyDefinition(
            label="manages",
            proposed_definition="Controls or oversees",
            proposed_domain="Service",
            proposed_range="Resource",
            confidence=0.8,
            provenance=[SourceSpan(quote="manages", start=20, end=27)],
        )

        result = candidate.to_dict()

        assert result["kind"] == "property_definition"
        assert result["label"] == "manages"
        assert result["proposed_definition"] == "Controls or oversees"
        assert result["proposed_domain"] == "Service"
        assert result["proposed_range"] == "Resource"
        assert result["confidence"] == 0.8
        assert len(result["provenance"]) == 1
        assert result["provenance"][0]["quote"] == "manages"
        assert result["provenance"][0]["start"] == 20
        assert result["provenance"][0]["end"] == 27

    def test_property_definition_with_mixed_provenance(self):
        """Serialize property with both resolved and quote-only provenance."""
        candidate = CandidatePropertyDefinition(
            label="connects",
            proposed_definition="Links or establishes connection",
            confidence=0.7,
            provenance=[
                SourceSpan(quote="connects", start=10, end=18),
                SourceSpan(quote="connects", start=None, end=None),  # also fuzzy-matched
            ],
        )

        result = candidate.to_dict()

        # Both resolved and quote-only spans should be included
        assert len(result["provenance"]) == 2


class TestCandidateConnectionSerialization:
    """Tests for CandidateConnection.to_dict() with provenance."""

    def test_connection_with_provenance(self):
        """Serialize CandidateConnection with provenance."""
        connection = CandidateConnection(
            subject_ref="Microservice",
            predicate="communicates_with",
            object_ref="Database",
            confidence=0.82,
            provenance=[SourceSpan(quote="communicates with", start=30, end=48)],
        )

        result = connection.to_dict()

        assert result["subject_ref"] == "Microservice"
        assert result["predicate"] == "communicates_with"
        assert result["object_ref"] == "Database"
        assert result["confidence"] == 0.82
        assert len(result["provenance"]) == 1
        assert result["provenance"][0]["quote"] == "communicates with"
        assert result["provenance"][0]["start"] == 30
        assert result["provenance"][0]["end"] == 48

    def test_connection_with_quote_only_provenance(self):
        """Serialize CandidateConnection with quote-only provenance."""
        connection = CandidateConnection(
            subject_ref="API",
            predicate="returns",
            object_ref="Response",
            confidence=0.75,
            provenance=[SourceSpan(quote="returns", start=None, end=None)],
        )

        result = connection.to_dict()

        assert len(result["provenance"]) == 1
        assert result["provenance"][0]["quote"] == "returns"
        assert result["provenance"][0]["start"] is None
        assert result["provenance"][0]["end"] is None

    def test_connection_with_no_provenance(self):
        """Serialize CandidateConnection with no provenance."""
        connection = CandidateConnection(
            subject_ref="X",
            predicate="related_to",
            object_ref="Y",
            confidence=0.5,
            provenance=[],
        )

        result = connection.to_dict()

        assert result["provenance"] == []
