"""
Unit tests for span resolution functions.

Tests cover exact matching, normalized matching, fuzzy matching, null fallback,
and edge cases (None inputs, empty quote, empty source text).
"""

import pytest

from domain.extraction.span_resolution import (
    find_all_spans,
    resolve_span,
)
from domain.extraction.value_objects import SourceSpan


class TestResolveSpanExactMatch:
    """Tests for exact substring matching in resolve_span."""

    def test_exact_match_single_occurrence(self):
        """Single exact match returns fully-resolved span."""
        quote = "the REST API"
        source_text = "This is the REST API documentation."

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start == 8
        assert span.end == 20

    def test_exact_match_at_start_of_text(self):
        """Exact match at the very beginning of source text."""
        quote = "Starting"
        source_text = "Starting with important information"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start == 0
        assert span.end == 8

    def test_exact_match_at_end_of_text(self):
        """Exact match at the very end of source text."""
        quote = "ending"
        source_text = "The story has a happy ending"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start == 22
        assert span.end == 28

    def test_multiple_occurrences_without_hint(self):
        """Multiple exact matches without hint returns first occurrence."""
        quote = "the"
        source_text = "the quick brown fox jumped over the lazy dog"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start == 0
        assert span.end == 3

    def test_multiple_occurrences_with_hint_closest_to_hint(self):
        """Multiple exact matches with hint returns match closest to hint."""
        quote = "the"
        source_text = "the quick brown fox jumped over the lazy dog"
        # hint_start=33 is closer to "the" at position 32

        span = resolve_span(quote, 33, None, source_text)

        assert span.quote == quote
        assert span.start == 32
        assert span.end == 35

    def test_multiple_occurrences_with_hint_first_is_closer(self):
        """When first occurrence is closer to hint, return it."""
        quote = "fox"
        source_text = "The fox is a fox in the forest"
        # hint_start=5 is closer to first "fox" at position 4

        span = resolve_span(quote, 5, None, source_text)

        assert span.quote == quote
        assert span.start == 4
        assert span.end == 7

    def test_exact_match_not_found(self):
        """No exact match falls through stages and returns null span."""
        quote = "unicorn"
        source_text = "The quick brown fox jumped over the lazy dog"

        span = resolve_span(quote, None, None, source_text)

        # Will continue to stage 2 (normalized), then stage 3, then stage 4 (fallback)
        # "unicorn" won't match anything, so all fields are None to distinguish
        # from fuzzy match found (which preserves quote)
        assert span.quote is None
        assert span.start is None
        assert span.end is None


class TestResolveSpanNormalizedMatch:
    """Tests for normalized (whitespace-collapsed, case-folded) matching."""

    def test_normalized_match_extra_whitespace(self):
        """Extra whitespace in quote matches collapsed form in source."""
        quote = "the  REST  API"  # Double spaces
        source_text = "documentation for the REST API service"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start is not None
        assert span.end is not None
        # Verify the text slice is correct (normalized form)
        assert source_text[span.start:span.end].casefold().split() == quote.casefold().split()

    def test_normalized_match_case_difference(self):
        """Case differences are ignored in normalized matching."""
        quote = "REST API"
        source_text = "Documentation for REST api services"

        span = resolve_span(quote, None, None, source_text)

        # Should match despite case difference
        assert span.quote == quote
        assert span.start is not None
        assert span.end is not None
        # Verify the text slice matches (case-folded comparison)
        assert source_text[span.start:span.end].casefold() == quote.casefold()

    def test_normalized_match_mixed_whitespace(self):
        """Various whitespace characters normalized to single spaces."""
        quote = "foo bar"
        source_text = "The result is foo\t\nbar here"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start is not None
        assert span.end is not None
        # Verify the normalized slice matches (whitespace normalized)
        assert source_text[span.start:span.end].casefold().split() == quote.casefold().split()

    def test_normalized_match_with_hint(self):
        """Normalized match with hint disambiguates multiple matches."""
        quote = "test"
        source_text = "This test is a TEST and another test here"

        span = resolve_span(quote, 28, None, source_text)

        # Should find a match (normalized matching will handle case)
        assert span.quote == quote

    def test_normalized_match_with_leading_whitespace_exact(self):
        """Exact match skips leading whitespace in source text."""
        quote = "Machine Learning"
        source_text = "   Machine Learning is great"

        span = resolve_span(quote, None, None, source_text)

        # Should find the match at position 3, not 0
        assert span.quote == quote
        assert span.start == 3
        assert span.end == 19

    def test_normalized_match_with_leading_whitespace_case_different(self):
        """Normalized match with leading whitespace skips leading spaces."""
        quote = "machine learning"
        source_text = "   Machine Learning is great"

        span = resolve_span(quote, None, None, source_text)

        # Should find via normalized matching at position 3, not 0
        assert span.quote == quote
        assert span.start == 3
        assert span.end == 19


class TestResolveSpanFuzzyMatch:
    """Tests for bounded fuzzy matching with difflib.SequenceMatcher."""

    def test_fuzzy_match_truncated_quote(self):
        """Truncated quote matches via fuzzy matching (>0.80 similarity)."""
        quote = "quick brown"  # Shortened from "The quick brown fox"
        source_text = "Once upon a time, the quick brown fox jumped over the lazy dog"
        hint_start = 30  # Approximate position in source

        span = resolve_span(quote, hint_start, None, source_text)

        # Should fuzzy-match (quote-only, no exact position)
        assert span.quote is not None
        # Either fully resolved with both start and end, or fuzzy-matched with both None
        assert (span.start is not None and span.end is not None) or (
            span.start is None and span.end is None
        )

    def test_fuzzy_match_paraphrased_quote(self):
        """Paraphrased quote with minor differences matches via fuzzy."""
        quote = "quick brownn"  # Very similar to "quick brown" (one extra char)
        source_text = "The quick brown fox is very clever"
        hint_start = 4  # Points near "quick"

        span = resolve_span(quote, hint_start, None, source_text)

        # Should find a fuzzy match with preserved quote, but no position
        assert span.quote == quote
        # Fuzzy matching on a bounded window should find this similar quote
        assert span.start is None and span.end is None

    def test_fuzzy_match_without_hint_fallback_to_null(self):
        """Fuzzy match requires hint_start; without it, fallback returns null span."""
        quote = "somewat similar"
        source_text = "This is somewhat similar text here"

        span = resolve_span(quote, None, None, source_text)

        # No exact match, no normalized match, no hint for fuzzy matching
        # Stage 4 fallback returns fully-null span to distinguish from fuzzy match found
        assert span.quote is None
        assert span.start is None
        assert span.end is None

    def test_fuzzy_match_bounded_window(self):
        """Fuzzy matching respects bounded ±200 character window."""
        # Create a source where fuzzy match is outside ±200 window
        quote = "something"  # Would fuzzy-match if within window
        source_text = "x" * 500 + "somewhat different text" + "y" * 500
        hint_start = 0  # Far from the actual match at ~500

        span = resolve_span(quote, hint_start, None, source_text)

        # Fuzzy match won't find it because hint (0) is >200 chars from match (~500)
        # The search window is [max(0, 0-200), min(len, 0+200)] = [0, 200]
        # but the match is at position 500, well outside the window
        # Falls through to Stage 4 fallback which returns null span
        assert span.quote is None
        assert span.start is None
        assert span.end is None


class TestResolveSpanEdgeCases:
    """Tests for edge cases and error handling."""

    def test_none_quote_returns_null_span(self):
        """None quote parameter returns null span immediately."""
        span = resolve_span(None, 0, None, "any source text")

        assert span.quote is None
        assert span.start is None
        assert span.end is None

    def test_empty_quote_returns_null_span(self):
        """Empty string quote returns null span immediately."""
        span = resolve_span("", 0, None, "any source text")

        assert span.quote is None
        assert span.start is None
        assert span.end is None

    def test_empty_source_text_returns_null_span(self):
        """Empty source_text returns null span immediately."""
        span = resolve_span("some quote", 0, None, "")

        assert span.quote is None
        assert span.start is None
        assert span.end is None

    def test_none_hint_start_exact_match(self):
        """None hint_start is handled gracefully (first match returned)."""
        quote = "apple"
        source_text = "apple pie and apple sauce"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start == 0
        assert span.end == 5

    def test_none_hint_end_ignored(self):
        """hint_end parameter is ignored in current implementation."""
        quote = "test"
        source_text = "This is a test case"

        span = resolve_span(quote, 5, 10, source_text)

        assert span.quote == quote
        assert span.start == 10
        assert span.end == 14

    def test_hint_start_beyond_source_text(self):
        """hint_start beyond source text length is handled."""
        quote = "test"
        source_text = "This is a test"
        hint_start = 1000  # Beyond the text

        span = resolve_span(quote, hint_start, None, source_text)

        # Should still find the match (proximity calculation should handle large distance)
        assert span.quote == quote

    def test_negative_hint_start(self):
        """Negative hint_start is handled gracefully."""
        quote = "test"
        source_text = "This is a test"

        span = resolve_span(quote, -5, None, source_text)

        # Should still find the match
        assert span.quote == quote

    def test_quote_with_special_characters(self):
        """Quote containing special characters matches exactly."""
        quote = "test@example.com"
        source_text = "Contact me at test@example.com for details"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start == 14
        assert span.end == 30

    def test_quote_with_newlines_and_tabs(self):
        """Quote with newlines/tabs normalized and matched."""
        quote = "foo\nbar"
        source_text = "Result: foo\nbar here"

        span = resolve_span(quote, None, None, source_text)

        # Exact match or normalized match should find it
        assert span.quote is not None

    def test_unicode_text(self):
        """Unicode characters are handled correctly."""
        quote = "café"
        source_text = "Welcome to our café"

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start == 15
        assert span.end == 19

    def test_very_long_source_text(self):
        """Long source text is handled efficiently."""
        quote = "needle"
        source_text = "hay " * 10000 + "needle" + " hay" * 10000

        span = resolve_span(quote, None, None, source_text)

        assert span.quote == quote
        assert span.start is not None
        assert span.end is not None


class TestFindAllSpans:
    """Tests for find_all_spans function (schema extraction path)."""

    def test_find_all_spans_single_occurrence(self):
        """Single occurrence returns list with one SourceSpan."""
        term = "apple"
        source_text = "I like apple pie"

        spans = find_all_spans(term, source_text)

        assert len(spans) == 1
        assert spans[0].quote == term
        assert spans[0].start == 7
        assert spans[0].end == 12

    def test_find_all_spans_multiple_occurrences(self):
        """Multiple occurrences returns list with each span."""
        term = "the"
        source_text = "the quick brown fox jumped over the lazy dog"

        spans = find_all_spans(term, source_text)

        assert len(spans) == 2
        assert spans[0].quote == term
        assert spans[0].start == 0
        assert spans[0].end == 3
        assert spans[1].quote == term
        assert spans[1].start == 32
        assert spans[1].end == 35

    def test_find_all_spans_no_occurrences(self):
        """No matches returns empty list."""
        term = "unicorn"
        source_text = "The quick brown fox jumped over the lazy dog"

        spans = find_all_spans(term, source_text)

        assert spans == []

    def test_find_all_spans_normalized_matches(self):
        """Normalized matches found when no exact matches."""
        term = "REST API"
        source_text = "The REST API is great, and the rest api works too"

        spans = find_all_spans(term, source_text)

        # Should find both the exact match and the case-variant match (normalized)
        assert len(spans) == 2
        # Verify each slice matches (case-folded)
        for span in spans:
            assert source_text[span.start:span.end].casefold() == term.casefold()

    def test_find_all_spans_overlapping_matches(self):
        """Overlapping matches are all returned."""
        term = "aa"
        source_text = "aaa"  # Contains "aa" at positions 0-1 and 1-2

        spans = find_all_spans(term, source_text)

        assert len(spans) == 2
        assert spans[0].start == 0
        assert spans[0].end == 2
        assert spans[1].start == 1
        assert spans[1].end == 3

    def test_find_all_spans_empty_term(self):
        """Empty term returns empty list."""
        term = ""
        source_text = "Some text here"

        spans = find_all_spans(term, source_text)

        assert spans == []

    def test_find_all_spans_none_term(self):
        """None term returns empty list."""
        spans = find_all_spans(None, "Some text here")

        assert spans == []

    def test_find_all_spans_empty_source_text(self):
        """Empty source_text returns empty list."""
        spans = find_all_spans("term", "")

        assert spans == []

    def test_find_all_spans_none_source_text(self):
        """None source_text is handled gracefully, returns empty list."""
        spans = find_all_spans("term", None)
        assert spans == []

    def test_find_all_spans_term_equals_source_text(self):
        """Term equal to entire source text."""
        term = "exact match"
        source_text = "exact match"

        spans = find_all_spans(term, source_text)

        assert len(spans) == 1
        assert spans[0].start == 0
        assert spans[0].end == len(term)

    def test_find_all_spans_adjacent_matches(self):
        """Adjacent matches are all returned separately."""
        term = "x"
        source_text = "xxx"

        spans = find_all_spans(term, source_text)

        assert len(spans) == 3
        assert spans[0].start == 0
        assert spans[1].start == 1
        assert spans[2].start == 2

    def test_find_all_spans_case_insensitive_normalized(self):
        """Normalized matching is case-insensitive."""
        term = "test"
        source_text = "Test, TEST, and test"

        spans = find_all_spans(term, source_text)

        # Should find all three occurrences due to normalization
        assert len(spans) == 3
        # Verify each slice matches (case-folded)
        for span in spans:
            assert source_text[span.start:span.end].casefold() == term.casefold()

    def test_find_all_spans_returns_empty_when_no_match(self):
        """find_all_spans returns empty when no match is found (exact or normalized only)."""
        term = "banana"
        source_text = "apples in the orchard, some peaches and pears"

        spans = find_all_spans(term, source_text)

        # "banana" doesn't appear in the text, no matching stages will find it
        assert len(spans) == 0

    def test_find_all_spans_fuzzy_matching_typo(self):
        """find_all_spans does not use fuzzy matching—exact/normalized only."""
        term = "Microservce"  # Typo: missing 'i'
        source_text = "A Microservice is a key architecture pattern for building scalable systems"

        spans = find_all_spans(term, source_text)

        # No fuzzy matching in schema extraction path; typo doesn't match exactly or normalized
        assert len(spans) == 0

    def test_find_all_spans_fuzzy_matching_variant(self):
        """find_all_spans does not use fuzzy matching for spelling variants."""
        term = "organistion"  # Typo/variant
        source_text = "The organization manages multiple service teams"

        spans = find_all_spans(term, source_text)

        # No fuzzy matching; spelling variant doesn't match exactly or normalized
        assert len(spans) == 0

    def test_find_all_spans_unicode(self):
        """Unicode text is handled correctly."""
        term = "café"
        source_text = "Visit our café and enjoy a café latte"

        spans = find_all_spans(term, source_text)

        assert len(spans) == 2

    def test_find_all_spans_special_characters(self):
        """Special characters in term are matched exactly."""
        term = "test@example.com"
        source_text = "Email: test@example.com or contact test@example.com"

        spans = find_all_spans(term, source_text)

        assert len(spans) == 2

    def test_find_all_spans_with_leading_whitespace(self):
        """find_all_spans skips leading whitespace in source text."""
        term = "Machine Learning"
        source_text = "   Machine Learning is great"

        spans = find_all_spans(term, source_text)

        # Should find the match at position 3, not 0
        assert len(spans) == 1
        assert spans[0].quote == term
        assert spans[0].start == 3
        assert spans[0].end == 19


class TestSourceSpanDataclass:
    """Tests for SourceSpan value object."""

    def test_source_span_fully_resolved(self):
        """SourceSpan with all fields populated represents fully-resolved span."""
        span = SourceSpan(quote="test", start=0, end=4)

        assert span.quote == "test"
        assert span.start == 0
        assert span.end == 4

    def test_source_span_quote_only(self):
        """SourceSpan with quote but no start/end represents fuzzy-matched span."""
        span = SourceSpan(quote="test", start=None, end=None)

        assert span.quote == "test"
        assert span.start is None
        assert span.end is None

    def test_source_span_null(self):
        """SourceSpan with all None fields represents unresolved span."""
        span = SourceSpan(quote=None, start=None, end=None)

        assert span.quote is None
        assert span.start is None
        assert span.end is None

    def test_source_span_is_frozen(self):
        """SourceSpan is frozen and immutable."""
        span = SourceSpan(quote="test", start=0, end=4)

        with pytest.raises(Exception):
            span.quote = "changed"

    def test_source_span_equality(self):
        """Two SourceSpans with same values are equal."""
        span1 = SourceSpan(quote="test", start=0, end=4)
        span2 = SourceSpan(quote="test", start=0, end=4)

        assert span1 == span2

    def test_source_span_inequality(self):
        """Two SourceSpans with different values are not equal."""
        span1 = SourceSpan(quote="test", start=0, end=4)
        span2 = SourceSpan(quote="test", start=0, end=5)

        assert span1 != span2

    def test_source_span_hashable(self):
        """SourceSpan is hashable and can be used in sets/dicts."""
        span = SourceSpan(quote="test", start=0, end=4)

        span_set = {span}
        assert span in span_set

    def test_source_span_can_determine_resolution(self):
        """Consumer can check span.start is not None to determine resolution."""
        resolved = SourceSpan(quote="test", start=0, end=4)
        unresolved = SourceSpan(quote=None, start=None, end=None)
        fuzzy = SourceSpan(quote="test", start=None, end=None)

        assert resolved.start is not None  # Fully resolved
        assert unresolved.start is None  # Unresolved
        assert fuzzy.start is None  # Fuzzy-matched

    def test_source_span_validation_start_without_end_invalid(self):
        """SourceSpan rejects start without end (invalid partial state)."""
        with pytest.raises(ValueError, match="Invalid SourceSpan state"):
            SourceSpan(quote="test", start=0, end=None)

    def test_source_span_validation_end_without_start_invalid(self):
        """SourceSpan rejects end without start (invalid partial state)."""
        with pytest.raises(ValueError, match="Invalid SourceSpan state"):
            SourceSpan(quote="test", start=None, end=4)

    def test_source_span_validation_start_greater_than_end_invalid(self):
        """SourceSpan rejects start > end (invalid range)."""
        with pytest.raises(ValueError, match="start must be <= end"):
            SourceSpan(quote="test", start=5, end=2)

    def test_source_span_validation_negative_start_invalid(self):
        """SourceSpan rejects negative start offset."""
        with pytest.raises(ValueError, match="must be non-negative"):
            SourceSpan(quote="test", start=-1, end=4)

    def test_source_span_validation_negative_end_invalid(self):
        """SourceSpan rejects negative end offset."""
        with pytest.raises(ValueError, match="must be non-negative"):
            SourceSpan(quote="test", start=0, end=-1)

    def test_source_span_validation_offsets_without_quote_invalid(self):
        """SourceSpan rejects offsets when quote is None."""
        with pytest.raises(ValueError, match="Invalid SourceSpan state"):
            SourceSpan(quote=None, start=0, end=4)


class TestCasefoldExpansion:
    """Tests for handling casefold expansion (e.g., ß → ss)."""

    def test_normalized_match_with_casefold_expansion(self):
        """Character that expands when case-folded (ß → ss) is handled correctly."""
        quote = "Straße"  # Contains ß which expands to ss when case-folded
        source_text = "The Straße in Berlin is famous"

        span = resolve_span(quote, None, None, source_text)

        # Should match despite the casefold expansion in the normalization process
        assert span.quote == quote
        assert span.start is not None
        assert span.end is not None
        # Verify the matched text
        assert source_text[span.start:span.end].casefold() == quote.casefold()

    def test_find_all_spans_with_casefold_expansion(self):
        """find_all_spans handles casefold expansion correctly."""
        term = "straße"
        source_text = "The Straße and another Straße were both visited"

        spans = find_all_spans(term, source_text)

        # Should find both case-variant occurrences
        assert len(spans) == 2
        for span in spans:
            assert source_text[span.start:span.end].casefold() == term.casefold()

    def test_normalized_match_casefold_expansion_position_mapping(self):
        """Position mapping correctly handles casefold expansion of ß → ss."""
        # Original: "Straße" (6 chars)
        # Normalized: "strasse" (7 chars, ß expanded to ss)
        quote = "aße"  # This is the end of "Straße"
        source_text = "Start with Straße and more"

        span = resolve_span(quote, None, None, source_text)

        # Should map positions correctly despite ß expansion
        assert span.quote == quote
        assert span.start is not None
        assert span.end is not None
        assert source_text[span.start:span.end].casefold() == quote.casefold()


class TestIntegrationScenarios:
    """Integration tests with realistic extraction scenarios."""

    def test_realistic_llm_output_exact_match(self):
        """LLM returns accurate quote and offset."""
        quote = "REST API"
        source_text = "The REST API provides endpoints for data access"
        hint_start = 4

        span = resolve_span(quote, hint_start, None, source_text)

        assert span.quote == quote
        assert span.start == 4
        assert span.end == 12

    def test_realistic_llm_output_with_hallucinated_offset(self):
        """LLM returns accurate quote but wrong offset (healed via normalization)."""
        quote = "REST API"
        source_text = "The REST API provides endpoints for data access"
        hint_start = 50  # Wrong offset, beyond text

        span = resolve_span(quote, hint_start, None, source_text)

        # Should still find via stage 1 or 2
        assert span.quote == quote
        assert span.start == 4
        assert span.end == 12

    def test_realistic_schema_extraction_label_matching(self):
        """Schema extraction finds all instances of a concept label."""
        term = "Organization"
        source_text = "An Organization may have employees. The Organization structure varies."

        spans = find_all_spans(term, source_text)

        assert len(spans) == 2
        assert spans[0].quote == term
        assert spans[1].quote == term

    def test_extraction_with_inconsistent_capitalization(self):
        """Both extraction paths handle capitalization inconsistencies."""
        quote = "Machine Learning"
        source_text = "machine learning is a subset of AI. Machine learning continues to evolve."

        span = resolve_span(quote, 0, None, source_text)

        # Should find via normalized matching
        assert span.quote is not None
