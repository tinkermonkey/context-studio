"""Integration tests for provenance validation in candidate endpoints.

Tests verify that:
1. Candidates with invalid provenance (negative offsets) are gracefully skipped
2. The endpoint continues processing other candidates instead of crashing
3. Valid provenance spans are preserved in the response
"""

from adapters.web.pipelines_routes import (
    _map_grounding_candidate,
    _map_refinement_candidate,
    _map_schema_class_candidate,
    _map_triple_candidate,
)
from adapters.web.schemas.pipelines import (
    GroundingCandidate,
    RefinementCandidate,
    SchemaClassCandidate,
    TripleCandidate,
)


class TestProvenanceValidation:
    """Tests for handling invalid provenance in candidate mapping functions."""

    def test_grounding_candidate_with_negative_start_offset(self):
        """Grounding with negative start offset in provenance is skipped."""
        grounding_dict = {
            "uri": "http://dbpedia.org/resource/Test",
            "label": "Test",
            "description": "Test item",
            "source": "DBpedia",
            "confidence": 0.85,
            "provenance": [
                {"quote": "valid span", "start": 10, "end": 20},
                {"quote": "invalid span", "start": -1, "end": 25},
            ],
        }

        result = _map_grounding_candidate(grounding_dict)

        assert isinstance(result, GroundingCandidate)
        assert len(result.provenance) == 1
        assert result.provenance[0].quote == "valid span"
        assert result.provenance[0].start == 10

    def test_grounding_candidate_with_negative_end_offset(self):
        """Grounding with negative end offset in provenance is skipped."""
        grounding_dict = {
            "uri": "http://dbpedia.org/resource/Test",
            "label": "Test",
            "description": "Test item",
            "source": "DBpedia",
            "confidence": 0.85,
            "provenance": [
                {"quote": "first span", "start": 0, "end": 10},
                {"quote": "invalid", "start": 5, "end": -5},
                {"quote": "last span", "start": 30, "end": 39},
            ],
        }

        result = _map_grounding_candidate(grounding_dict)

        assert isinstance(result, GroundingCandidate)
        assert len(result.provenance) == 2
        assert result.provenance[0].quote == "first span"
        assert result.provenance[1].quote == "last span"

    def test_schema_class_candidate_with_negative_provenance_offsets(self):
        """Schema class candidate with negative provenance is skipped."""
        candidate_dict = {
            "kind": "class",
            "label": "Person",
            "proposed_definition": "A human being",
            "confidence": 0.92,
            "provenance": [
                {"quote": "valid", "start": 0, "end": 5},
                {"quote": "invalid", "start": -10, "end": 20},
            ],
        }

        result = _map_schema_class_candidate(candidate_dict)

        assert isinstance(result, SchemaClassCandidate)
        assert len(result.provenance) == 1
        assert result.provenance[0].quote == "valid"

    def test_triple_candidate_with_mixed_provenance_validity(self):
        """Triple candidate skips invalid provenance but keeps valid spans."""
        triple_dict = {
            "subject": {"label": "Alice", "kind": "individual"},
            "predicate": {"label": "knows", "kind": "property"},
            "object": {"label": "Bob", "kind": "individual"},
            "confidence": 0.88,
            "provenance": [
                {"quote": "Alice knows Bob", "start": 0, "end": 14},
                {"quote": "invalid1", "start": -1, "end": 8},
                {"quote": "Alice and Bob are friends", "start": 20, "end": 45},
                {"quote": "invalid2", "start": 50, "end": -5},
            ],
        }

        result = _map_triple_candidate(triple_dict)

        assert isinstance(result, TripleCandidate)
        assert len(result.provenance) == 2
        assert result.provenance[0].quote == "Alice knows Bob"
        assert result.provenance[1].quote == "Alice and Bob are friends"

    def test_refinement_candidate_with_negative_provenance_offsets(self):
        """Refinement candidate with negative provenance is skipped."""
        refinement_dict = {
            "definition": "An improved definition",
            "confidence": 0.87,
            "provenance": [
                {"quote": "valid text", "start": 0, "end": 10},
                {"quote": "invalid", "start": -5, "end": 15},
            ],
        }

        result = _map_refinement_candidate(refinement_dict)

        assert isinstance(result, RefinementCandidate)
        assert len(result.provenance) == 1
        assert result.provenance[0].quote == "valid text"

    def test_all_invalid_provenance_returns_empty_spans(self):
        """Candidate with all invalid provenance returns empty span list."""
        grounding_dict = {
            "uri": "http://dbpedia.org/resource/Test",
            "label": "Test",
            "confidence": 0.80,
            "provenance": [
                {"quote": "invalid1", "start": -1, "end": 5},
                {"quote": "invalid2", "start": 10, "end": -2},
                {"quote": "invalid3", "start": -3, "end": -1},
            ],
        }

        result = _map_grounding_candidate(grounding_dict)

        assert isinstance(result, GroundingCandidate)
        assert len(result.provenance) == 0

    def test_candidate_still_created_when_provenance_invalid(self):
        """Candidate object is still created and returned even with invalid provenance."""
        grounding_dict = {
            "uri": "http://example.org/item",
            "label": "Item",
            "description": "An item",
            "source": "Example",
            "confidence": 0.75,
            "provenance": [{"quote": "bad", "start": -100, "end": -50}],
        }

        result = _map_grounding_candidate(grounding_dict)

        assert isinstance(result, GroundingCandidate)
        assert result.uri == "http://example.org/item"
        assert result.label == "Item"
        assert result.confidence == 0.75
        assert len(result.provenance) == 0

    def test_pre_span_format_negative_offsets_skipped(self):
        """Pre-span format with negative offsets is skipped."""
        grounding_dict = {
            "uri": "http://dbpedia.org/resource/Test",
            "label": "Test",
            "confidence": 0.85,
            "provenance": [
                {
                    "text_offset_start": 0,
                    "text_offset_end": 5,
                    "raw": "valid text",
                },
                {
                    "text_offset_start": -1,
                    "text_offset_end": 10,
                    "raw": "invalid text",
                },
            ],
        }

        result = _map_grounding_candidate(grounding_dict)

        assert isinstance(result, GroundingCandidate)
        assert len(result.provenance) == 1
        assert result.provenance[0].quote == "valid text"


class TestConfidenceEdgeCases:
    """Tests for handling edge cases in confidence values."""

    def test_schema_class_candidate_with_zero_confidence(self):
        """Schema class candidate preserves zero confidence without promoting to 0.5."""
        candidate_dict = {
            "kind": "class",
            "label": "Person",
            "proposed_definition": "A human being",
            "confidence": 0,  # Zero confidence should be preserved, not promoted
            "provenance": [],
        }

        result = _map_schema_class_candidate(candidate_dict)

        assert isinstance(result, SchemaClassCandidate)
        assert result.confidence == 0.0  # Must preserve 0, not promote to 0.5

    def test_schema_class_candidate_with_zero_float_confidence(self):
        """Schema class candidate preserves 0.0 float confidence without promoting to 0.5."""
        candidate_dict = {
            "kind": "class",
            "label": "Person",
            "proposed_definition": "A human being",
            "confidence": 0.0,  # Zero float confidence should be preserved
            "provenance": [],
        }

        result = _map_schema_class_candidate(candidate_dict)

        assert isinstance(result, SchemaClassCandidate)
        assert result.confidence == 0.0  # Must preserve 0.0, not promote to 0.5

    def test_triple_candidate_with_zero_confidence(self):
        """Triple candidate preserves zero confidence without promoting to 0.5."""
        triple_dict = {
            "subject": {"label": "Alice", "kind": "individual"},
            "predicate": {"label": "knows", "kind": "property"},
            "object": {"label": "Bob", "kind": "individual"},
            "confidence": 0,  # Zero confidence should be preserved
            "provenance": [],
        }

        result = _map_triple_candidate(triple_dict)

        assert isinstance(result, TripleCandidate)
        assert result.confidence == 0.0  # Must preserve 0, not promote to 0.5

    def test_triple_candidate_with_zero_float_confidence(self):
        """Triple candidate preserves 0.0 float confidence without promoting to 0.5."""
        triple_dict = {
            "subject": {"label": "Alice", "kind": "individual"},
            "predicate": {"label": "knows", "kind": "property"},
            "object": {"label": "Bob", "kind": "individual"},
            "confidence": 0.0,  # Zero float confidence should be preserved
            "provenance": [],
        }

        result = _map_triple_candidate(triple_dict)

        assert isinstance(result, TripleCandidate)
        assert result.confidence == 0.0  # Must preserve 0.0, not promote to 0.5
