"""
Span resolution functions for grounding text quotes in source documents.

This module provides pure functions (no infrastructure imports) for resolving text spans
against source text using a multi-stage cascade that handles exact matches, normalized
matches, and fuzzy matching. Used by both individual extraction and schema extraction
pipelines to reliably ground provenance information.
"""

import difflib
import unicodedata

from domain.extraction.value_objects import SourceSpan

# Curly quotes and primes, compared as straight ones
_QUOTES = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "″": '"',
    }
)
# The soft hyphen and the registered, copyright and trademark marks: quotes leave them out
_DROPPED = frozenset("­®©™")
# Hyphens and dashes: PDF text breaks words with them where a quote joins them
_HYPHENS = frozenset("-‐‑‒–—―−")


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
    2. Normalized match: normalize both quote and source_text (whitespace collapsed,
       case-folded, and PDF typography such as curly quotes, ligatures and line-break
       hyphens folded: `_normalize_with_offsets`), then repeat the substring search.
       Derive offsets from the original source.
    3. Bounded fuzzy match: if hint_start is provided, scan a ±200 character window
       around the hint and slide substrings of length len(quote)±20% looking for a
       match above 0.80 similarity (difflib.SequenceMatcher.ratio).
    4. Fallback: return SourceSpan(quote=None, start=None, end=None).

    The function never raises on missing/empty inputs—it degrades gracefully to a
    fully-null span (all fields None). Warning emission is the caller's responsibility.

    Args:
        quote: The text to find, or None. May be verbatim or paraphrased.
        hint_start: Approximate character position of the span start, or None.
        hint_end: Approximate character position of the span end, or None
            (unused in current implementation).
        source_text: The full source document text to search within.

    Returns:
        SourceSpan with fully-resolved (quote, start, end), quote-only (quote present,
        start/end None), or fully-null (all None) based on the cascade result.
        Stage 4 returns fully-null (same as empty input) to distinguish "fuzzy match found"
        (Stage 3, quote-only) from "nothing found" (Stage 4, fully-null).
    """
    if not quote or not source_text:
        return SourceSpan(quote=None, start=None, end=None)

    # Stage 1: Exact substring match
    exact_match_result = _find_exact_match(quote, source_text, hint_start)
    if exact_match_result is not None:
        start, end = exact_match_result
        return SourceSpan(quote=quote, start=start, end=end)

    # Stage 2: Normalized match (whitespace, case and typography folded)
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

    # Stage 4: Fallback — nothing found at all
    # Return null span to distinguish from Stage 3 (fuzzy match found).
    # This allows callers to emit appropriate warnings: "fuzzy match only" vs "no match found".
    return SourceSpan(quote=None, start=None, end=None)


def find_all_spans(
    term: str,
    source_text: str,
) -> list[SourceSpan]:
    """
    Find all occurrences of a term in source text using exact and normalized matching.

    DESIGN DECISION (Architect Guidance): Schema extraction labels are known a priori
    (e.g., ontology class names, relationship types from schema). Per architect guidance,
    these known labels should match exactly or with minor normalization—NOT fuzzy matching.
    Fuzzy matching is reserved for the individual extraction path (resolve_span) where
    the quote may be paraphrased by the LLM and requires bounded fuzzy recovery.

    This function intentionally uses only stages 1-2 of the resolution cascade:
    1. Exact matching: locate term exactly in source_text
    2. Normalized matching: normalize both term and source (`_normalize_with_offsets`)

    Args:
        term: The text to find (a known schema label). Must be non-empty.
        source_text: The source document to search within.

    Returns:
        A list of SourceSpan objects, each representing one occurrence; its quote
        is the source text at [start, end) (e.g. "heating system" for the term
        "Heating System"), never the term.
        Empty list if term is empty, source_text is empty, or no matches found.
    """
    if not term or not source_text:
        return []

    spans: list[SourceSpan] = []

    # Stage 1: Exact substring matches
    exact_matches = _find_all_exact_matches(term, source_text)
    for start, end in exact_matches:
        spans.append(SourceSpan(quote=source_text[start:end], start=start, end=end))

    # Stage 2: Normalized matches (always run to catch case-variant occurrences)
    normalized_matches = _find_all_normalized_matches(term, source_text)
    for start, end in normalized_matches:
        # Avoid duplicates from stage 1 (exact match will also be found in normalized)
        if not any(s.start == start and s.end == end for s in spans):
            spans.append(SourceSpan(quote=source_text[start:end], start=start, end=end))

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
    Find a match by normalized comparison (see `_normalize_with_offsets`).

    If several matches exist, uses hint_start to select the closest one.

    Args:
        quote: The text to find.
        source_text: The text to search within.
        hint_start: If not None, pick the match closest to this position.

    Returns:
        Tuple of (start, end) in the original source_text, or None if not found.
    """
    matches = _find_all_normalized_matches(quote, source_text)
    if not matches:
        return None
    if hint_start is not None:
        return min(matches, key=lambda match: abs(match[0] - hint_start))
    return matches[0]


def _find_all_normalized_matches(term: str, source_text: str) -> list[tuple[int, int]]:
    """
    Find all matches by normalized comparison (see `_normalize_with_offsets`).

    Args:
        term: The text to find.
        source_text: The text to search within.

    Returns:
        List of (start, end) tuples in the original source_text for each match.
    """
    normalized_term, _ = _normalize_with_offsets(term)
    if not normalized_term:
        return []
    normalized_source, offsets = _normalize_with_offsets(source_text)

    matches: list[tuple[int, int]] = []
    pos = normalized_source.find(normalized_term)
    while pos != -1:
        # From the first matched character's offset to just past the last's
        # (every part of a character a fold expanded has that character's offset).
        last = offsets[pos + len(normalized_term) - 1]
        matches.append((offsets[pos], last + 1))
        pos = normalized_source.find(normalized_term, pos + 1)
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
    # Both normalized once (see `_normalize_with_offsets`); candidates are cut from the window
    window, _ = _normalize_with_offsets(source_text[window_start:window_end])
    normalized_quote, _ = _normalize_with_offsets(quote)

    quote_len = len(normalized_quote)
    min_len = max(1, int(quote_len * 0.8))  # 80% of quote length
    max_len = int(quote_len * 1.2)  # 120% of quote length

    # Slide through window
    for candidate_len in range(min_len, max_len + 1):
        for i in range(len(window) - candidate_len + 1):
            candidate = window[i : i + candidate_len]

            ratio = difflib.SequenceMatcher(None, normalized_quote, candidate).ratio()

            if ratio >= 0.80:
                return True

    return False


def _normalize_with_offsets(text: str) -> tuple[str, list[int]]:
    """
    Normalize text for comparison, keeping where each character came from.

    Text read from a PDF differs from what a model quotes back of it in ways
    that change no word, so both sides are normalized alike:

    - case-folded, compatibility forms unfolded (NFKC: the "fi" ligature is "fi")
    - curly quotes and primes as straight ones
    - the soft hyphen and the registered, copyright and trademark marks dropped
    - hyphens and dashes dropped, and a word a hyphen splits at a line break
      joined ("instal-\\nlation" is "installation", as "hand-held" is "handheld")
    - runs of whitespace as one space, none at either end

    Args:
        text: The text to normalize.

    Returns:
        (the normalized text, the offset in text of each of its characters);
        every part of a character a fold expands (ß is "ss") has its offset
    """
    folded: list[tuple[str, int]] = []
    for index, char in enumerate(text):
        if char in _DROPPED:
            continue
        for part in unicodedata.normalize("NFKC", char.translate(_QUOTES)).casefold():
            folded.append((part, index))

    chars: list[str] = []
    offsets: list[int] = []
    space_at: int | None = None
    k = 0
    while k < len(folded):
        char, index = folded[k]
        if char in _HYPHENS:
            after = k + 1
            while after < len(folded) and folded[after][0].isspace():
                after += 1
            line_break = any(folded[m][0] == "\n" for m in range(k + 1, after))
            # At a line break the whitespace goes too: the hyphen split one word
            k = after if line_break else k + 1
            continue
        if char.isspace():
            if space_at is None:
                space_at = index
            k += 1
            continue
        if space_at is not None and chars:
            chars.append(" ")
            offsets.append(space_at)
        space_at = None
        chars.append(char)
        offsets.append(index)
        k += 1
    return "".join(chars), offsets
