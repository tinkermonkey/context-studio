"""Unit tests for pipelines route helper functions."""


from adapters.web.pipelines_routes import _normalize_provenance
from adapters.web.schemas.extraction import SourceSpanSchema


class TestNormalizeProvenance:
    """Tests for _normalize_provenance helper function."""

    def test_normalize_empty_provenance(self):
        """Empty provenance data returns empty list."""
        assert _normalize_provenance(None) == []
        assert _normalize_provenance([]) == []
        assert _normalize_provenance("") == []

    def test_normalize_post_span_format(self):
        """Post-span format (quote/start/end) is normalized correctly."""
        provenance_data = [
            {"quote": "example text", "start": 10, "end": 22},
            {"quote": "another", "start": 50, "end": 57},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 2
        assert result[0].quote == "example text"
        assert result[0].start == 10
        assert result[0].end == 22
        assert result[1].quote == "another"
        assert result[1].start == 50
        assert result[1].end == 57

    def test_normalize_pre_span_format(self):
        """Pre-span format (text_offset_start/text_offset_end/raw) is normalized correctly."""
        provenance_data = [
            {"text_offset_start": 5, "text_offset_end": 15, "raw": "example"},
            {"text_offset_start": 20, "text_offset_end": 25, "raw": "text"},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 2
        assert result[0].quote == "example"
        assert result[0].start == 5
        assert result[0].end == 15
        assert result[1].quote == "text"
        assert result[1].start == 20
        assert result[1].end == 25

    def test_normalize_start_zero_not_dropped(self):
        """start=0 is not silently dropped due to falsy check (critical bug fix)."""
        provenance_data = [
            {"quote": "first word", "start": 0, "end": 10},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert result[0].start == 0  # Must preserve 0, not drop to None
        assert result[0].end == 10

    def test_normalize_end_zero_not_dropped(self):
        """end=0 is not silently dropped due to falsy check (critical bug fix)."""
        provenance_data = [
            {"quote": "text", "start": 0, "end": 0},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert result[0].start == 0
        assert result[0].end == 0  # Must preserve 0, not drop to None

    def test_normalize_pre_span_start_zero_not_dropped(self):
        """Pre-span format with start=0 is not silently dropped (critical bug fix)."""
        provenance_data = [
            {"text_offset_start": 0, "text_offset_end": 5, "raw": "start"},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert result[0].start == 0  # Must preserve 0 from text_offset_start
        assert result[0].quote == "start"

    def test_normalize_empty_string_quote_preserved(self):
        """Empty string quotes are preserved, not treated as missing."""
        provenance_data = [
            {"quote": "", "start": 10, "end": 10},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert result[0].quote == ""  # Empty string should be preserved

    def test_normalize_mixed_formats_fallback(self):
        """Fallback works correctly when post-span keys are missing."""
        provenance_data = [
            # Only raw/pre-span keys present
            {"raw": "fallback text", "text_offset_start": 15, "text_offset_end": 28},
            # Only post-span keys present
            {"quote": "post span", "start": 30, "end": 39},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 2
        assert result[0].quote == "fallback text"
        assert result[0].start == 15
        assert result[0].end == 28
        assert result[1].quote == "post span"
        assert result[1].start == 30
        assert result[1].end == 39

    def test_normalize_string_provenance(self):
        """String provenance data is wrapped in a single SourceSpanSchema."""
        result = _normalize_provenance("simple provenance text")

        assert len(result) == 1
        assert result[0].quote == "simple provenance text"
        assert result[0].start is None
        assert result[0].end is None

    def test_normalize_list_with_non_dict_items(self):
        """Non-dict items in list are skipped."""
        provenance_data = [
            {"quote": "valid", "start": 10, "end": 15},
            "string item",  # This will be skipped
            None,  # This will be skipped
            {"quote": "another valid", "start": 20, "end": 33},
        ]

        result = _normalize_provenance(provenance_data)

        # Only dict items are processed
        assert len(result) == 2
        assert result[0].quote == "valid"
        assert result[1].quote == "another valid"

    def test_normalize_returns_source_span_schema_objects(self):
        """Result contains SourceSpanSchema objects."""
        provenance_data = [{"quote": "text", "start": 0, "end": 4}]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert isinstance(result[0], SourceSpanSchema)

    def test_normalize_dict_provenance_single(self):
        """Dict-format provenance (single dict, not in a list) is normalized correctly."""
        provenance_data = {"quote": "example text", "start": 10, "end": 22}

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert result[0].quote == "example text"
        assert result[0].start == 10
        assert result[0].end == 22

    def test_normalize_dict_provenance_with_raw_key(self):
        """Dict-format provenance with raw key (old format) is normalized correctly."""
        provenance_data = {"raw": "old format text", "text_offset_start": 5, "text_offset_end": 20}

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert result[0].quote == "old format text"
        assert result[0].start == 5
        assert result[0].end == 20

    def test_normalize_negative_start_skipped(self):
        """Spans with negative start offset are skipped with warning."""
        provenance_data = [
            {"quote": "valid", "start": 10, "end": 15},
            {"quote": "invalid negative start", "start": -1, "end": 20},
            {"quote": "another valid", "start": 30, "end": 43},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 2
        assert result[0].quote == "valid"
        assert result[0].start == 10
        assert result[1].quote == "another valid"
        assert result[1].start == 30

    def test_normalize_negative_end_skipped(self):
        """Spans with negative end offset are skipped with warning."""
        provenance_data = [
            {"quote": "valid", "start": 0, "end": 5},
            {"quote": "invalid negative end", "start": 10, "end": -1},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 1
        assert result[0].quote == "valid"
        assert result[0].start == 0
        assert result[0].end == 5

    def test_normalize_dict_with_negative_offsets_skipped(self):
        """Dict-format provenance with negative offsets is skipped."""
        provenance_data = {"quote": "invalid", "start": -5, "end": 10}

        result = _normalize_provenance(provenance_data)

        assert len(result) == 0

    def test_normalize_pre_span_negative_offsets_skipped(self):
        """Pre-span format with negative offsets is skipped."""
        provenance_data = [
            {"raw": "text1", "text_offset_start": 5, "text_offset_end": 10},
            {"raw": "invalid", "text_offset_start": -1, "text_offset_end": 5},
            {"raw": "text2", "text_offset_start": 20, "text_offset_end": 25},
        ]

        result = _normalize_provenance(provenance_data)

        assert len(result) == 2
        assert result[0].quote == "text1"
        assert result[1].quote == "text2"
