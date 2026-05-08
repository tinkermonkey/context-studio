"""
Unit tests for extraction schemas, specifically TripleProvenance cross-field validation.

Tests the TripleProvenance validator to verify that inverted text offsets are rejected.
"""

import sys
import os

# Add local-server root to path for imports
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)

from pydantic import ValidationError
import pytest

from adapters.web.schemas.extraction import TripleProvenance


class TestTripleProvenanceOffsetValidation:
    """Test cross-field validation of text offsets in TripleProvenance."""

    def test_valid_offsets_start_equals_end(self) -> None:
        """Test that offsets where start == end are accepted."""
        provenance = TripleProvenance(
            text_offset_start=0,
            text_offset_end=0,
            raw="x"
        )
        assert provenance.text_offset_start == 0
        assert provenance.text_offset_end == 0

    def test_valid_offsets_start_less_than_end(self) -> None:
        """Test that offsets where start < end are accepted."""
        provenance = TripleProvenance(
            text_offset_start=10,
            text_offset_end=20,
            raw="hello"
        )
        assert provenance.text_offset_start == 10
        assert provenance.text_offset_end == 20

    def test_invalid_offsets_end_less_than_start(self) -> None:
        """Test that inverted offsets (end < start) are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TripleProvenance(
                text_offset_start=100,
                text_offset_end=50,
                raw="text"
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "text_offset_end" in str(errors[0]) or "text_offset_start" in str(errors[0])

    def test_invalid_offsets_zero_and_negative(self) -> None:
        """Test that negative offsets are rejected by field validators."""
        with pytest.raises(ValidationError):
            TripleProvenance(
                text_offset_start=-1,
                text_offset_end=10,
                raw="text"
            )

    def test_invalid_offsets_both_negative(self) -> None:
        """Test that both offsets being negative are rejected."""
        with pytest.raises(ValidationError):
            TripleProvenance(
                text_offset_start=-10,
                text_offset_end=-5,
                raw="text"
            )

    def test_error_message_includes_offset_values(self) -> None:
        """Test that validation error message includes the problematic offset values."""
        with pytest.raises(ValidationError) as exc_info:
            TripleProvenance(
                text_offset_start=100,
                text_offset_end=50,
                raw="text"
            )

        error_str = str(exc_info.value)
        assert "100" in error_str or "50" in error_str

    def test_large_valid_offsets(self) -> None:
        """Test that large valid offsets are accepted."""
        provenance = TripleProvenance(
            text_offset_start=10000,
            text_offset_end=20000,
            raw="x" * 10000
        )
        assert provenance.text_offset_start == 10000
        assert provenance.text_offset_end == 20000

    def test_large_inverted_offsets(self) -> None:
        """Test that large inverted offsets are rejected."""
        with pytest.raises(ValidationError):
            TripleProvenance(
                text_offset_start=20000,
                text_offset_end=10000,
                raw="text"
            )
