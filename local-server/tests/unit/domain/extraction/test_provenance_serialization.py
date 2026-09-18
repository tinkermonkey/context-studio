"""
Unit tests for provenance serialization functions.

Tests for:
- _serialize_triple_provenance: converts SourceSpan objects in triples to dicts
- Related provenance serialization and validation
"""

import os
import sys

# Add parent directories to path for imports
_file_path = os.path.abspath(__file__)
_four_levels_up = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(_file_path)
)))
sys.path.append(_four_levels_up)

from domain.extraction.services import _serialize_triple_provenance  # noqa: E402
from domain.extraction.value_objects import SourceSpan  # noqa: E402


class TestSerializeTripleProvenance:
    """Tests for _serialize_triple_provenance function."""

    def test_serialize_fully_resolved_span(self):
        """Serialize a fully-resolved SourceSpan with quote and offsets."""
        triple = {
            "subject": {"label": "Technology", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "System", "kind": "class"},
            "confidence": 0.92,
            "provenance": SourceSpan(quote="Technology System", start=0, end=19),
        }

        result = _serialize_triple_provenance(triple)

        assert result["provenance"]["quote"] == "Technology System"
        assert result["provenance"]["start"] == 0
        assert result["provenance"]["end"] == 19
        assert result["subject"] == triple["subject"]
        assert result["predicate"] == triple["predicate"]
        assert result["object"] == triple["object"]
        assert result["confidence"] == triple["confidence"]

    def test_serialize_quote_only_span(self):
        """Serialize a quote-only SourceSpan (fuzzy-matched, no offsets)."""
        triple = {
            "subject": {"label": "Microservice", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "Architecture", "kind": "class"},
            "confidence": 0.85,
            "provenance": SourceSpan(quote="Microservice", start=None, end=None),
        }

        result = _serialize_triple_provenance(triple)

        # Quote-only spans are preserved with None offsets
        assert result["provenance"]["quote"] == "Microservice"
        assert result["provenance"]["start"] is None
        assert result["provenance"]["end"] is None

    def test_serialize_unresolved_span(self):
        """Serialize an unresolved SourceSpan (all fields None)."""
        triple = {
            "subject": {"label": "Unknown", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "Class", "kind": "class"},
            "confidence": 0.5,
            "provenance": SourceSpan(quote=None, start=None, end=None),
        }

        result = _serialize_triple_provenance(triple)

        # Unresolved spans serialize with all None
        assert result["provenance"]["quote"] is None
        assert result["provenance"]["start"] is None
        assert result["provenance"]["end"] is None

    def test_passthrough_dict_provenance(self):
        """Passthrough provenance that is already a dict."""
        triple = {
            "subject": {"label": "Concept", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "Class", "kind": "class"},
            "confidence": 0.75,
            "provenance": {"quote": "Concept", "start": 5, "end": 12},
        }

        result = _serialize_triple_provenance(triple)

        # Dict provenance is left unchanged
        assert result["provenance"] == {"quote": "Concept", "start": 5, "end": 12}

    def test_passthrough_none_provenance(self):
        """Passthrough triple with no provenance."""
        triple = {
            "subject": {"label": "Entity", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "Class", "kind": "class"},
            "confidence": 0.6,
            "provenance": None,
        }

        result = _serialize_triple_provenance(triple)

        # None provenance is left unchanged
        assert result["provenance"] is None

    def test_passthrough_missing_provenance(self):
        """Passthrough triple without provenance field."""
        triple = {
            "subject": {"label": "Entity", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "Class", "kind": "class"},
            "confidence": 0.6,
        }

        result = _serialize_triple_provenance(triple)

        # Missing provenance field is left unchanged
        assert "provenance" not in result or result.get("provenance") is None

    def test_serialized_provenance_has_correct_keys(self):
        """Verify serialized provenance uses quote/start/end, not legacy keys."""
        triple = {
            "subject": {"label": "Tech", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "System", "kind": "class"},
            "confidence": 0.9,
            "provenance": SourceSpan(quote="Tech System", start=10, end=21),
        }

        result = _serialize_triple_provenance(triple)
        provenance_dict = result["provenance"]

        # Verify correct keys exist
        assert "quote" in provenance_dict
        assert "start" in provenance_dict
        assert "end" in provenance_dict

        # Verify legacy keys do not exist
        assert "text_offset_start" not in provenance_dict
        assert "text_offset_end" not in provenance_dict
        assert "raw" not in provenance_dict

    def test_normalized_match_span(self):
        """Serialize a normalized-match span (offsets but text differs from quote)."""
        # This represents a case where extraction found text with different case/whitespace
        triple = {
            "subject": {"label": "kubernetes", "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": "Orchestrator", "kind": "class"},
            "confidence": 0.88,
            "provenance": SourceSpan(quote="kubernetes", start=25, end=35),
        }

        result = _serialize_triple_provenance(triple)

        assert result["provenance"]["quote"] == "kubernetes"
        assert result["provenance"]["start"] == 25
        assert result["provenance"]["end"] == 35
