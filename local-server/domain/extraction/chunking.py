"""
Split long source text into extraction chunks.

A chunk is a span of the whole text, so offsets found inside a chunk map back
to the whole text by adding the chunk's start. Chunks hold at most
``max_chars`` characters and break, in order of preference, at a heading, at a
page start, at the end of a sentence (or a blank line), and only when a single
sentence is longer than a chunk, at a space.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Sequence

MAX_CHUNK_CHARS = 8000

# A sentence ends at ., ! or ? followed by whitespace, or at a blank line
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n\s*\n")
_WHITESPACE = re.compile(r"\s+")
_PAGE_RANGE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


@dataclass(frozen=True)
class Heading:
    """A heading in the source text: where it starts, its title and its level."""

    start: int
    title: str
    level: int = 1


@dataclass(frozen=True)
class Chunk:
    """
    One chunk of a source text.

    Attributes:
        index: Position among the chunks, from 0
        start: Offset of the chunk's first character in the whole text
        end: Offset just past the chunk's last character
        page_first: Page (from 1) holding the chunk's start; None without page starts
        page_last: Page holding the chunk's last character; None without page starts
        heading: Title of the heading the chunk falls under, if any
    """

    index: int
    start: int
    end: int
    page_first: int | None = None
    page_last: int | None = None
    heading: str | None = None


def page_of(offset: int, page_starts: Sequence[int]) -> int:
    """Return the page (from 1) holding ``offset``, given each page's start offset."""
    return max(1, bisect.bisect_right(page_starts, offset))


def parse_page_range(pages: str) -> list[tuple[int, int]]:
    """
    Parse a page selection such as ``"12-30"``, ``"3"`` or ``"1-3, 7"``.

    Returns:
        (first, last) page pairs, inclusive, numbered from 1

    Raises:
        ValueError: The selection is empty or malformed
    """
    ranges: list[tuple[int, int]] = []
    for part in pages.split(","):
        match = _PAGE_RANGE.match(part)
        if not match:
            raise ValueError(f"Invalid page range: {pages!r}")
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if first < 1 or last < first:
            raise ValueError(f"Invalid page range: {pages!r}")
        ranges.append((first, last))
    return ranges


def chunk_text(
    text: str,
    *,
    max_chars: int = MAX_CHUNK_CHARS,
    page_starts: Sequence[int] | None = None,
    headings: Sequence[Heading] | None = None,
    pages: str | None = None,
) -> list[Chunk]:
    """
    Split ``text`` into chunks of at most ``max_chars`` characters.

    Each chunk is filled to at least half of ``max_chars`` before it breaks at
    a heading or page start, so short sections share a chunk; the rest of the
    text in a chunk-sized window breaks at its last sentence end.

    Args:
        text: The whole source text
        max_chars: Most characters in one chunk
        page_starts: Offset at which each page starts, in page order
        headings: Headings in the text
        pages: Page selection (see parse_page_range); only text on those pages
            is chunked. Needs ``page_starts``.

    Returns:
        The chunks in text order; empty when there is no text to chunk

    Raises:
        ValueError: ``pages`` is malformed, or given without ``page_starts``
    """
    starts = sorted(set(page_starts or []))
    heading_list = sorted(headings or [], key=lambda h: h.start)
    heading_starts = [h.start for h in heading_list]

    chunks: list[Chunk] = []
    for window_start, window_end in _windows(text, starts, pages):
        heading_cuts = [s for s in heading_starts if window_start < s < window_end]
        page_cuts = [s for s in starts if window_start < s < window_end]
        start = _skip_whitespace(text, window_start, window_end)
        while start < window_end:
            if window_end - start <= max_chars:
                cut = window_end
            else:
                cut = _break_point(
                    text, start, start + max_chars, max_chars, heading_cuts, page_cuts
                )
            end = _trim_whitespace(text, start, cut)
            if end > start:
                position = bisect.bisect_right(heading_starts, start) - 1
                chunks.append(
                    Chunk(
                        index=len(chunks),
                        start=start,
                        end=end,
                        page_first=page_of(start, starts) if starts else None,
                        page_last=page_of(end - 1, starts) if starts else None,
                        heading=heading_list[position].title if position >= 0 else None,
                    )
                )
            start = _skip_whitespace(text, cut, window_end)
    return chunks


def _windows(text: str, starts: list[int], pages: str | None) -> list[tuple[int, int]]:
    """The spans of text to chunk: the whole text, or the selected pages."""
    if not pages or not pages.strip():
        return [(0, len(text))]
    if not starts:
        raise ValueError("A page range needs page starts")
    windows: list[tuple[int, int]] = []
    for first, last in parse_page_range(pages):
        if first > len(starts):
            continue
        last = min(last, len(starts))
        end = starts[last] if last < len(starts) else len(text)
        windows.append((starts[first - 1], end))
    return windows


def _break_point(
    text: str,
    start: int,
    limit: int,
    max_chars: int,
    heading_cuts: list[int],
    page_cuts: list[int],
) -> int:
    """Where a chunk starting at ``start`` ends, at or before ``limit``."""
    floor = start + max_chars // 2
    for cuts in (heading_cuts, page_cuts):
        inside = [c for c in cuts if floor <= c <= limit]
        if inside:
            return inside[-1]
    sentence_ends = [m.start() for m in _SENTENCE_BREAK.finditer(text, start, limit)]
    sentence_ends = [e for e in sentence_ends if e > start]
    if sentence_ends:
        return sentence_ends[-1]
    spaces = [m.start() for m in _WHITESPACE.finditer(text, floor, limit)]
    return spaces[-1] if spaces else limit


def _skip_whitespace(text: str, position: int, limit: int) -> int:
    while position < limit and text[position].isspace():
        position += 1
    return position


def _trim_whitespace(text: str, start: int, end: int) -> int:
    while end > start and text[end - 1].isspace():
        end -= 1
    return end
