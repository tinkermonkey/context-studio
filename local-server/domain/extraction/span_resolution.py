"""
Span resolution functions for grounding text quotes in source documents.

This module provides pure functions (no infrastructure imports) for resolving text spans
against source text using a multi-stage cascade that handles exact matches, normalized
matches, and fuzzy matching. Used by both individual extraction and schema extraction
pipelines to reliably ground provenance information.
"""

import difflib
from domain.extraction.value_objects import SourceSpan


def resolve_span(
    quote: str | None,
    hint_start: int | None,
    hint_end: int | None,
    source_text: str,
) -> SourceSpan:
    """
    Resolve a single span using a 4-stage cascade from exact to fuzzy matching.

    Given a quote (which may be verbatim or paraphrased), optional character offsets,
    and source text, attempts to find the exact location in source_text using a cascade:

    1. Exact substring match: locate quote in source_text. If found multiple times,
       use hint_start to pick the occurrence closest to the hint.
    2. Normalized match: collapse whitespace, case-fold both quote and source_text,
       then repeat the substring search. Derive offsets from the original source.
    3. Bounded fuzzy match: if hint_start is provided, scan a ±200 character window
       around the hint and slide substrings of length len(quote)±20% looking for a
       match above 0.80 similarity (difflib.SequenceMatcher.ratio).
    4. Fallback: return SourceSpan(quote=None, start=None, end=None).

    The function never raises on missing/empty inputs—it degrades gracefully to a
    null span. Warning emission is the caller's responsibility (Phase 2).

    Args:
        quote: The text to find, or None. May be verbatim or paraphrased.
        hint_start: Approximate character position of the span start, or None.
        hint_end: Approximate character position of the span end, or None (unused in current implementation).
        source_text: The full source document text to search within.

    Returns:
        SourceSpan with fully-resolved (quote, start, end), quote-only (quote present,
        start/end None), or fully-null (all None) based on the cascade result.
    """
    if not quote or not source_text:
        return SourceSpan(quote=None, start=None, end=None)

    # Stage 1: Exact substring match
    exact_match_result = _find_exact_match(quote, source_text, hint_start)
    if exact_match_result is not None:
        start, end = exact_match_result
        return SourceSpan(quote=quote, start=start, end=end)

    # Stage 2: Normalized match (whitespace-collapsed, case-folded)
    normalized_result = _find_normalized_match(quote, source_text, hint_start)
    if normalized_result is not None:
        start, end = normalized_result
        return SourceSpan(quote=quote, start=start, end=end)

    # Stage 3: Bounded fuzzy match (if we have a hint offset)
    if hint_start is not None:
        fuzzy_result = _find_fuzzy_match(quote, source_text, hint_start)
        if fuzzy_result:
            # Fuzzy match returns quote-only (no exact position)
            return SourceSpan(quote=quote, start=None, end=None)

    # Stage 4: Fallback to null span
    return SourceSpan(quote=None, start=None, end=None)


def find_all_spans(
    term: str,
    source_text: str,
) -> list[SourceSpan]:
    """
    Find all occurrences of a term in source text using exact and normalized matching.

    Used by the schema extraction path where the term is known a priori (e.g., a
    schema label). This function uses only steps 1-2 of the resolution cascade
    (exact and normalized matching), not fuzzy matching, since schema labels should
    match exactly or with minor normalization.

    Args:
        term: The text to find. Must be non-empty.
        source_text: The source document to search within.

    Returns:
        A list of SourceSpan objects, each representing one occurrence.
        Empty list if term is empty, source_text is empty, or no matches found.
    """
    if not term or not source_text:
        return []

    spans: list[SourceSpan] = []

    # Stage 1: Exact substring matches
    exact_matches = _find_all_exact_matches(term, source_text)
    for start, end in exact_matches:
        spans.append(SourceSpan(quote=term, start=start, end=end))

    # If we found exact matches, return them
    if spans:
        return spans

    # Stage 2: Normalized matches (if no exact matches)
    normalized_matches = _find_all_normalized_matches(term, source_text)
    for start, end in normalized_matches:
        spans.append(SourceSpan(quote=term, start=start, end=end))

    return spans


def _find_exact_match(
    quote: str, source_text: str, hint_start: int | None
) -> tuple[int, int] | None:
    """
    Find exact substring match, using hint_start to disambiguate multiple occurrences.

    Args:
        quote: The exact text to find.
        source_text: The text to search within.
        hint_start: If not None, pick the match closest to this position.

    Returns:
        Tuple of (start, end) for the best match, or None if not found.
    """
    pos = 0
    occurrences: list[int] = []

    while True:
        pos = source_text.find(quote, pos)
        if pos == -1:
            break
        occurrences.append(pos)
        pos += 1

    if not occurrences:
        return None

    if len(occurrences) == 1:
        start = occurrences[0]
        return (start, start + len(quote))

    # Multiple occurrences: use hint_start as a proximity tiebreaker
    if hint_start is not None:
        best_match = min(occurrences, key=lambda pos: abs(pos - hint_start))
        return (best_match, best_match + len(quote))

    # No hint: return the first occurrence
    return (occurrences[0], occurrences[0] + len(quote))


def _find_all_exact_matches(
    term: str, source_text: str
) -> list[tuple[int, int]]:
    """
    Find all exact substring matches in source text.

    Args:
        term: The text to find.
        source_text: The text to search within.

    Returns:
        List of (start, end) tuples for each match.
    """
    matches: list[tuple[int, int]] = []
    pos = 0

    while True:
        pos = source_text.find(term, pos)
        if pos == -1:
            break
        matches.append((pos, pos + len(term)))
        pos += 1

    return matches


def _find_normalized_match(
    quote: str, source_text: str, hint_start: int | None
) -> tuple[int, int] | None:
    """
    Find match using whitespace-normalized, case-folded comparison.

    Collapses runs of whitespace to single spaces, strips leading/trailing
    whitespace, and case-folds both quote and source_text.

    Args:
        quote: The text to find.
        source_text: The text to search within.
        hint_start: If not None, pick the match closest to this position.

    Returns:
        Tuple of (start, end) in the original source_text, or None if not found.
    """
    normalized_quote = _normalize_text(quote)
    normalized_source = _normalize_text(source_text)

    # Find match in normalized text
    pos = normalized_source.find(normalized_quote)
    if pos == -1:
        return None

    # Map position back to original source text
    # Count characters (including whitespace) in original source up to the normalized position
    original_pos = 0
    normalized_pos = 0
    normalized_idx = 0

    while normalized_idx < pos and original_pos < len(source_text):
        if source_text[original_pos].isspace():
            if normalized_idx < len(normalized_source) and not normalized_source[
                normalized_idx
            ].isspace():
                # Skipped a space in normalized version
                original_pos += 1
            else:
                original_pos += 1
                normalized_idx += 1
        else:
            original_pos += 1
            normalized_idx += 1

    # Find the end position (length of normalized match mapped back)
    start_pos = original_pos
    chars_remaining = len(quote)  # Approximate, map normalized length
    end_pos = original_pos

    # Scan forward to find where the normalized match ends in the original text
    normalized_chars_matched = 0
    while end_pos < len(source_text) and normalized_chars_matched < len(
        normalized_quote
    ):
        if not source_text[end_pos].isspace():
            normalized_chars_matched += 1
        end_pos += 1

    return (start_pos, end_pos)


def _find_all_normalized_matches(
    term: str, source_text: str
) -> list[tuple[int, int]]:
    """
    Find all matches using whitespace-normalized, case-folded comparison.

    Args:
        term: The text to find.
        source_text: The text to search within.

    Returns:
        List of (start, end) tuples in the original source_text for each match.
    """
    matches: list[tuple[int, int]] = []
    normalized_term = _normalize_text(term)
    normalized_source = _normalize_text(source_text)

    pos = 0
    while True:
        pos = normalized_source.find(normalized_term, pos)
        if pos == -1:
            break

        # Map position back to original source text
        original_start = _map_normalized_to_original(normalized_source, source_text, pos)
        original_end = _map_normalized_to_original(
            normalized_source, source_text, pos + len(normalized_term)
        )

        if original_start is not None and original_end is not None:
            matches.append((original_start, original_end))

        pos += 1

    return matches


def _find_fuzzy_match(
    quote: str, source_text: str, hint_start: int
) -> bool:
    """
    Find a fuzzy match within a bounded window around hint_start.

    Slides a substring of length len(quote)±20% through a ±200 character window
    around hint_start and scores each candidate using difflib.SequenceMatcher.

    Args:
        quote: The text to match (approximately).
        source_text: The text to search within.
        hint_start: The approximate position to search around.

    Returns:
        True if a match above 0.80 similarity is found, False otherwise.
    """
    window_half = 200
    window_start = max(0, hint_start - window_half)
    window_end = min(len(source_text), hint_start + window_half)
    window = source_text[window_start:window_end]

    quote_len = len(quote)
    min_len = max(1, int(quote_len * 0.8))  # 80% of quote length
    max_len = int(quote_len * 1.2)  # 120% of quote length

    normalized_quote = _normalize_text(quote)

    # Slide through window
    for candidate_len in range(min_len, max_len + 1):
        for i in range(len(window) - candidate_len + 1):
            candidate = window[i : i + candidate_len]
            normalized_candidate = _normalize_text(candidate)

            ratio = difflib.SequenceMatcher(
                None, normalized_quote, normalized_candidate
            ).ratio()

            if ratio >= 0.80:
                return True

    return False


def _normalize_text(text: str) -> str:
    """
    Normalize text by collapsing whitespace and case-folding.

    Replaces runs of whitespace with single spaces, strips leading/trailing
    whitespace, and converts to lowercase.

    Args:
        text: The text to normalize.

    Returns:
        Normalized text.
    """
    # Collapse runs of whitespace to single spaces
    normalized = " ".join(text.split())
    # Case-fold to lowercase
    return normalized.lower()


def _map_normalized_to_original(
    normalized_text: str, original_text: str, normalized_pos: int
) -> int | None:
    """
    Map a position in normalized text back to the original text.

    Args:
        normalized_text: The normalized (whitespace-collapsed, lowercased) text.
        original_text: The original text.
        normalized_pos: A position in normalized_text.

    Returns:
        The corresponding position in original_text, or None if mapping fails.
    """
    normalized_idx = 0
    original_idx = 0

    while normalized_idx < normalized_pos and original_idx < len(original_text):
        if original_text[original_idx].isspace():
            # Skip all whitespace in original
            while (
                original_idx < len(original_text)
                and original_text[original_idx].isspace()
            ):
                original_idx += 1
            # Skip one space in normalized (representing all that whitespace)
            if normalized_idx < len(normalized_text) and normalized_text[
                normalized_idx
            ].isspace():
                normalized_idx += 1
        else:
            original_idx += 1
            if normalized_idx < len(normalized_text):
                normalized_idx += 1

    return original_idx if normalized_idx == normalized_pos else None
