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
    4. Fallback: return SourceSpan(quote=quote, start=None, end=None).

    The function never raises on missing/empty inputs—it degrades gracefully to a
    quote-only span. Warning emission is the caller's responsibility (Phase 2).

    Args:
        quote: The text to find, or None. May be verbatim or paraphrased.
        hint_start: Approximate character position of the span start, or None.
        hint_end: Approximate character position of the span end, or None
            (unused in current implementation).
        source_text: The full source document text to search within.

    Returns:
        SourceSpan with fully-resolved (quote, start, end), quote-only (quote present,
        start/end None), or fully-null (all None) based on the cascade result.
        Note: fully-null only occurs when inputs are empty/None; stages 1-4 preserve
        the quote as a quote-only span even when exact position cannot be resolved.
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

    # Stage 4: Fallback to quote-only span
    # Preserve the original quote even if we couldn't find an exact position;
    # a paraphrased quote is more useful provenance than None
    return SourceSpan(quote=quote, start=None, end=None)


def find_all_spans(
    term: str,
    source_text: str,
) -> list[SourceSpan]:
    """
    Find all occurrences of a term in source text using exact, normalized, and fuzzy matching.

    Used by the schema extraction path where the term is known a priori (e.g., a
    schema label). This function uses the full resolution cascade:
    1. Exact matching: locate term exactly in source_text
    2. Normalized matching: collapse whitespace and case-fold both term and source
    3. Fuzzy matching: find close matches (>0.80 similarity) for variants/typos
       (only if stages 1-2 find no results)

    Returns all matches found, preferring exact/normalized matches. Fuzzy matches
    are used as a fallback only when exact and normalized matching find nothing.

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

    # Stage 2: Normalized matches (always run to catch case-variant occurrences)
    normalized_matches = _find_all_normalized_matches(term, source_text)
    for start, end in normalized_matches:
        # Avoid duplicates from stage 1 (exact match will also be found in normalized)
        if not any(s.start == start and s.end == end for s in spans):
            spans.append(SourceSpan(quote=term, start=start, end=end))

    # Stage 3: Fuzzy matches for variant spellings/typos (quote-only, no exact positions)
    # Only apply fuzzy matching if stages 1-2 found no results
    if not spans:
        fuzzy_matches = _find_fuzzy_match_in_text(term, source_text)
        spans.extend(fuzzy_matches)

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


def _find_all_exact_matches(term: str, source_text: str) -> list[tuple[int, int]]:
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
    whitespace, and case-folds both quote and source_text. If multiple matches
    exist, uses hint_start to select the closest one.

    Args:
        quote: The text to find.
        source_text: The text to search within.
        hint_start: If not None, pick the match closest to this position.

    Returns:
        Tuple of (start, end) in the original source_text, or None if not found.
    """
    normalized_quote = _normalize_text(quote)
    normalized_source = _normalize_text(source_text)

    # Find all normalized matches
    occurrences: list[int] = []
    pos = 0
    while True:
        pos = normalized_source.find(normalized_quote, pos)
        if pos == -1:
            break
        occurrences.append(pos)
        pos += 1

    if not occurrences:
        return None

    # Pick the best match (first or closest to hint)
    if len(occurrences) == 1:
        best_normalized_pos = occurrences[0]
    else:
        # Multiple occurrences: pick first, or closest to hint if provided
        if hint_start is not None:
            # Map each normalized position back to original and pick closest to hint
            candidates = []
            for norm_pos in occurrences:
                orig_pos = _map_normalized_to_original(normalized_source, source_text, norm_pos)
                if orig_pos is not None:
                    candidates.append((norm_pos, orig_pos))

            if candidates:
                best_normalized_pos, _ = min(candidates, key=lambda c: abs(c[1] - hint_start))
            else:
                best_normalized_pos = occurrences[0]
        else:
            # No hint: return the first occurrence
            best_normalized_pos = occurrences[0]

    # Map the normalized position back to the original text
    original_start = _map_normalized_to_original(
        normalized_source, source_text, best_normalized_pos
    )
    original_end = _map_normalized_to_original(
        normalized_source, source_text, best_normalized_pos + len(normalized_quote)
    )

    if original_start is not None and original_end is not None:
        return (original_start, original_end)

    return None


def _find_all_normalized_matches(term: str, source_text: str) -> list[tuple[int, int]]:
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


def _find_fuzzy_match(quote: str, source_text: str, hint_start: int) -> bool:
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

            ratio = difflib.SequenceMatcher(None, normalized_quote, normalized_candidate).ratio()

            if ratio >= 0.80:
                return True

    return False


def _find_fuzzy_match_in_text(term: str, source_text: str) -> list[SourceSpan]:
    """
    Find a fuzzy match in source text as a quote-only span.

    Fuzzy matching is a fallback when exact and normalized matching find nothing.
    It returns at most one quote-only span (no exact position) because position
    mapping from normalized text back to original text is unreliable when comparing
    normalized substrings of varying lengths.

    To avoid O(n*k) SequenceMatcher overhead on very large texts, this function
    short-circuits when source_text exceeds 100,000 characters. Fuzzy matching for
    such texts is deferred as the probability of finding a meaningful variant match
    diminishes with text size.

    Args:
        term: The text to match (approximately).
        source_text: The text to search within. Very large texts (>100k chars)
            are skipped for performance.

    Returns:
        List with a single quote-only SourceSpan if fuzzy match found, empty otherwise.
    """
    if len(source_text) > 100_000:
        # Skip fuzzy matching for very large texts to avoid O(n*k) cost
        return []

    term_len = len(term)
    min_len = max(1, int(term_len * 0.8))  # 80% of term length
    max_len = int(term_len * 1.2)  # 120% of term length

    normalized_term = _normalize_text(term)

    # Slide through entire text looking for fuzzy matches
    for candidate_len in range(min_len, max_len + 1):
        for i in range(len(source_text) - candidate_len + 1):
            candidate = source_text[i : i + candidate_len]
            normalized_candidate = _normalize_text(candidate)

            ratio = difflib.SequenceMatcher(None, normalized_term, normalized_candidate).ratio()

            if ratio >= 0.80:
                # Found a fuzzy match; return as quote-only (no exact position)
                # Position mapping is unreliable when working with normalized substrings
                return [SourceSpan(quote=term, start=None, end=None)]

    return []


def _normalize_text(text: str) -> str:
    """
    Normalize text by collapsing whitespace and case-folding.

    Replaces runs of whitespace with single spaces, strips leading/trailing
    whitespace, and case-folds using Unicode case folding rules.

    Args:
        text: The text to normalize.

    Returns:
        Normalized text.
    """
    # Collapse runs of whitespace to single spaces
    normalized = " ".join(text.split())
    # Case-fold using Unicode case folding rules
    return normalized.casefold()


def _map_normalized_to_original(
    normalized_text: str, original_text: str, normalized_pos: int
) -> int | None:
    """
    Map a position in normalized text back to the original text.

    Correctly handles casefold expansion where a single original character
    (e.g., 'ß') may become multiple characters in normalized text (e.g., 'ss').

    Args:
        normalized_text: The normalized (whitespace-collapsed, case-folded) text.
        original_text: The original text.
        normalized_pos: A position in normalized_text.

    Returns:
        The corresponding position in original_text, or None if mapping fails.
    """
    normalized_idx = 0
    original_idx = 0

    while original_idx < len(original_text) and normalized_idx < normalized_pos:
        if original_text[original_idx].isspace():
            # Skip all consecutive whitespace in original
            while original_idx < len(original_text) and original_text[original_idx].isspace():
                original_idx += 1
            # In normalized, this becomes a single space
            if normalized_idx < len(normalized_text) and normalized_text[normalized_idx].isspace():
                normalized_idx += 1
        else:
            # Non-whitespace character may expand when case-folded
            char = original_text[original_idx]
            folded = char.casefold()
            folded_len = len(folded)

            # If normalized_pos falls within this character's expansion
            if normalized_idx + folded_len > normalized_pos:
                # If normalized_pos is exactly at the start of the expansion,
                # return the position before this character
                if normalized_idx == normalized_pos:
                    return original_idx
                else:
                    # Otherwise, return the position after this character
                    return original_idx + 1

            normalized_idx += folded_len
            original_idx += 1

    # If we've reached the exact position
    if normalized_idx == normalized_pos:
        return original_idx

    return None
