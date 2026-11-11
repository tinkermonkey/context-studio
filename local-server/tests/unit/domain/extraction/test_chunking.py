"""Unit tests for the source text chunker (domain/extraction/chunking.py)."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.extraction.chunking import Heading, chunk_text, page_of, parse_page_range


def _sentences(count: int, length: int = 50, prefix: str = "S") -> str:
    """``count`` sentences of exactly ``length`` characters each, space separated."""
    body = []
    for i in range(count):
        head = f"{prefix}{i} "
        body.append(head + "x" * (length - len(head) - 1) + ".")
    return " ".join(body)


def _assert_covers_sentences(text: str, chunks) -> None:
    """Every chunk starts at a sentence start and ends at a sentence end."""
    for chunk in chunks:
        piece = text[chunk.start : chunk.end]
        assert piece == piece.strip()
        assert piece.endswith(".")
        assert chunk.start == 0 or text[chunk.start - 1] == " "


class TestChunkText:
    def test_tiny_text_is_one_chunk(self):
        chunks = chunk_text("A short note.")
        assert len(chunks) == 1
        chunk = chunks[0]
        assert (chunk.index, chunk.start, chunk.end) == (0, 0, 13)
        assert chunk.page_first is None and chunk.page_last is None
        assert chunk.heading is None

    def test_empty_or_blank_text_has_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   \n  ") == []

    def test_long_text_splits_on_sentence_boundaries_within_the_limit(self):
        text = _sentences(100)  # 100 * 50 + 99 spaces
        chunks = chunk_text(text, max_chars=1000)
        assert len(chunks) > 1
        assert all(c.end - c.start <= 1000 for c in chunks)
        assert [c.index for c in chunks] == list(range(len(chunks)))
        _assert_covers_sentences(text, chunks)
        # Nothing but the separating spaces is left out
        assert sum(c.end - c.start for c in chunks) + len(chunks) - 1 == len(text)

    def test_blank_line_is_a_sentence_boundary(self):
        paragraph = "word " * 150  # 750 characters, no sentence punctuation
        text = paragraph.strip() + "\n\n" + paragraph.strip()
        chunks = chunk_text(text, max_chars=1000)
        assert len(chunks) == 2
        assert chunks[1].start == text.index("\n\n") + 2

    def test_a_sentence_longer_than_a_chunk_breaks_at_a_space(self):
        text = "word " * 500  # 2500 characters, no sentence end
        chunks = chunk_text(text, max_chars=1000)
        assert len(chunks) == 3
        for chunk in chunks:
            assert chunk.end - chunk.start <= 1000
            assert not text[chunk.start : chunk.end].startswith(" ")
            assert text[chunk.start : chunk.end].endswith("word")

    def test_breaks_at_a_heading_before_a_sentence_end(self):
        text = _sentences(30)  # 1529 characters
        heading_at = text.index("S12 ")  # 612, past half of a 1000-char chunk
        chunks = chunk_text(
            text, max_chars=1000, headings=[Heading(start=heading_at, title="Install")]
        )
        assert chunks[0].end == heading_at - 1
        assert chunks[1].start == heading_at
        assert chunks[0].heading is None
        assert chunks[1].heading == "Install"

    def test_short_sections_share_a_chunk(self):
        text = _sentences(30)
        early = text.index("S2 ")  # 102, under half a chunk
        chunks = chunk_text(text, max_chars=1000, headings=[Heading(start=early, title="Intro")])
        # The early heading does not split off a tiny chunk
        assert chunks[0].start == 0
        assert chunks[0].end > early
        assert chunks[1].heading == "Intro"

    def test_breaks_at_a_page_start_when_no_heading_fits(self):
        text = _sentences(30)
        page_two = text.index("S14 ")
        chunks = chunk_text(text, max_chars=1000, page_starts=[0, page_two])
        assert chunks[0].end == page_two - 1
        assert (chunks[0].page_first, chunks[0].page_last) == (1, 1)
        assert (chunks[1].page_first, chunks[1].page_last) == (2, 2)

    def test_heading_wins_over_a_page_start(self):
        text = _sentences(30)
        heading_at = text.index("S11 ")
        page_two = text.index("S15 ")
        chunks = chunk_text(
            text,
            max_chars=1000,
            page_starts=[0, page_two],
            headings=[Heading(start=heading_at, title="Care")],
        )
        assert chunks[1].start == heading_at
        assert (chunks[1].page_first, chunks[1].page_last) == (1, 2)

    def test_page_numbers_span_several_pages(self):
        text = _sentences(10)
        starts = [0, text.index("S3 "), text.index("S6 ")]
        chunks = chunk_text(text, page_starts=starts)
        assert len(chunks) == 1
        assert (chunks[0].page_first, chunks[0].page_last) == (1, 3)

    def test_page_range_selects_only_those_pages(self):
        text = _sentences(10)
        starts = [text.index(f"S{i} ") for i in range(0, 10, 2)]  # 5 pages, 2 sentences each
        chunks = chunk_text(text, page_starts=starts, pages="2-3")
        assert len(chunks) == 1
        assert chunks[0].start == starts[1]
        assert chunks[0].end == starts[3] - 1
        assert (chunks[0].page_first, chunks[0].page_last) == (2, 3)

    def test_page_range_with_several_parts(self):
        text = _sentences(10)
        starts = [text.index(f"S{i} ") for i in range(0, 10, 2)]
        chunks = chunk_text(text, page_starts=starts, pages="1, 5")
        assert [(c.page_first, c.page_last) for c in chunks] == [(1, 1), (5, 5)]
        assert chunks[1].end == len(text)
        assert [c.index for c in chunks] == [0, 1]

    def test_page_range_past_the_last_page_is_empty(self):
        text = _sentences(4)
        assert chunk_text(text, page_starts=[0], pages="3-4") == []

    def test_page_range_needs_page_starts(self):
        with pytest.raises(ValueError):
            chunk_text("Some text.", pages="1-2")

    def test_heading_before_a_selected_page_names_its_chunks(self):
        text = _sentences(10)
        starts = [text.index(f"S{i} ") for i in range(0, 10, 2)]
        chunks = chunk_text(
            text,
            page_starts=starts,
            headings=[Heading(start=0, title="Overview")],
            pages="4",
        )
        assert chunks[0].heading == "Overview"


class TestReviewFixes:
    """Page starts mid-sentence, repeated page starts, page range merging, tiny chunks."""

    def test_page_start_mid_sentence_moves_to_the_sentence_end_before_it(self):
        text = _sentences(30)
        page_two = text.index("S14 ") + 20  # inside sentence 14
        chunks = chunk_text(text, max_chars=1000, page_starts=[0, page_two])
        assert chunks[0].end == text.index("S14 ") - 1
        _assert_covers_sentences(text, chunks)
        assert chunks[1].page_first == 1  # the rest of page one's sentence leads chunk 1

    def test_page_start_mid_word_never_splits_the_word(self):
        text = _sentences(30)
        page_two = text.index("S13 ") + 2  # inside the word "S13"
        chunks = chunk_text(text, max_chars=1000, page_starts=[0, page_two])
        _assert_covers_sentences(text, chunks)
        assert chunks[0].end == text.index("S13 ") - 1

    def test_page_start_without_a_sentence_end_before_it_uses_the_next_one(self):
        text = _sentences(10, length=300)  # sentence ends at 300, 601, 902, ...
        chunks = chunk_text(text, max_chars=1000, page_starts=[0, 550])
        assert chunks[0].end == 601
        _assert_covers_sentences(text, chunks)

    def test_repeated_page_start_keeps_later_page_numbers(self):
        text = "Door one. Shelf two. Drawer three."
        starts = [0, 10, 21, 21]  # page 3 is empty
        assert page_of(21, starts) == 4
        chunks = chunk_text(text, page_starts=starts, pages="4")
        assert [(c.start, c.page_first, c.page_last) for c in chunks] == [(21, 4, 4)]

    def test_decreasing_page_starts_are_refused(self):
        with pytest.raises(ValueError):
            chunk_text("Door one. Shelf two.", page_starts=[0, 12, 5])

    def test_overlapping_page_ranges_merge(self):
        text = _sentences(10)
        starts = [text.index(f"S{i} ") for i in range(0, 10, 2)]
        chunks = chunk_text(text, page_starts=starts, pages="1-3, 2-4")
        assert len(chunks) == 1
        assert (chunks[0].page_first, chunks[0].page_last) == (1, 4)

    def test_page_ranges_come_out_in_page_order(self):
        text = _sentences(10)
        starts = [text.index(f"S{i} ") for i in range(0, 10, 2)]
        chunks = chunk_text(text, page_starts=starts, pages="5, 1")
        assert [c.page_first for c in chunks] == [1, 5]

    def test_too_small_max_chars_is_refused(self):
        with pytest.raises(ValueError):
            chunk_text("Some text.", max_chars=10)


class TestPageHelpers:
    def test_page_of(self):
        starts = [0, 100, 250]
        assert page_of(0, starts) == 1
        assert page_of(99, starts) == 1
        assert page_of(100, starts) == 2
        assert page_of(999, starts) == 3

    def test_page_of_before_the_first_page_start_is_page_one(self):
        assert page_of(5, [10, 20]) == 1

    @pytest.mark.parametrize(
        "pages, expected",
        [
            ("12-30", [(12, 30)]),
            ("3", [(3, 3)]),
            (" 1 - 3 , 7 ", [(1, 3), (7, 7)]),
        ],
    )
    def test_parse_page_range(self, pages, expected):
        assert parse_page_range(pages) == expected

    @pytest.mark.parametrize("pages", ["", "a-b", "5-2", "0-3", "1-", "1,,2"])
    def test_parse_page_range_rejects_malformed(self, pages):
        with pytest.raises(ValueError):
            parse_page_range(pages)
