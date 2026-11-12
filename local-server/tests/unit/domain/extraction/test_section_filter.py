"""Unit tests for skipping boilerplate and other-language sections (section_filter.py)."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from domain.extraction.chunking import Heading, chunk_text
from domain.extraction.section_filter import (
    CONTACT,
    LEGAL,
    OTHER_LANGUAGE,
    SAFETY,
    WARRANTY,
    skip_note,
    skip_summary,
    skipped_by_reason,
    skipped_sections,
)

# An install sheet laid out like the Moen one in #1575: English steps with a
# magnet warning, the steps again in French, then the warranty in English and
# French and the contact and copyright lines. Pages are separated by a blank line.
ENGLISH_STEPS = """Magnetix Handheld Shower Dock
INSTALLATION INSTRUCTIONS
Tools recommended: pencil, drill, 1/4" bit, painter's tape
1. Place painter's tape on the wall where the dock will be mounted and mark the holes with a pencil.
2. Drill the holes with the 1/4" bit and insert the wall anchors (C) into the holes.
3. Attach the mounting bracket (B) to the wall with the screws (D) and tighten them by hand.
4. Peel the film from the adhesive disk (A) and press the hand shower dock (E) onto the bracket."""

MAGNET_WARNING = """WARNING
This product contains magnets. Magnets may interfere with pacemakers and implantable medical
devices. Keep the hand shower at least 6 inches away from a pacemaker."""

FRENCH_STEPS = """INSTRUCTIONS D'INSTALLATION
Outils recommandés : crayon, perceuse, ruban de peintre
1. Placez le ruban sur le mur où le support sera installé et marquez les trous avec un crayon.
2. Percez les trous et insérez les ancrages muraux (C) dans les trous du mur.
3. Fixez le support de montage (B) au mur avec les vis (D) et serrez-les à la main."""

ENGLISH_WARRANTY = """LIMITED LIFETIME WARRANTY
Moen warrants to the original consumer purchaser that this product will be free from defects
in material and workmanship for as long as the original consumer purchaser owns it. Moen will
not be liable for incidental or consequential damages. Proof of purchase is required. This
warranty gives you specific legal rights."""

FRENCH_WARRANTY = """Garantie à vie limitée de Moen
Moen garantit au consommateur original que ce produit sera exempt de défauts de matériau et
de fabrication aussi longtemps que le consommateur en est propriétaire. Une preuve d'achat est
requise pour toute réclamation."""

CONTACT_LINES = """Customer Service
Questions? Call 1-800-BUY-MOEN, Monday to Friday, or visit www.moen.com"""

LEGAL_LINES = "© 2024 Moen Incorporated. All rights reserved. Moen is a registered trademark."


def _pages(*pages: str) -> tuple[str, list[int]]:
    """The pages as one text, a blank line between pages, with each page's start."""
    text = ""
    starts: list[int] = []
    for page in pages:
        if starts:
            text += "\n\n"
        starts.append(len(text))
        text += page
    return text, starts


def _sheet() -> tuple[str, list[int]]:
    return _pages(
        ENGLISH_STEPS + "\n" + MAGNET_WARNING,
        FRENCH_STEPS,
        "\n".join([ENGLISH_WARRANTY, FRENCH_WARRANTY]),
        "\n\n".join([CONTACT_LINES, LEGAL_LINES]),
    )


def _kept_text(text: str, starts: list[int], skipped) -> str:
    chunks = chunk_text(text, page_starts=starts, skip=[(s.start, s.end) for s in skipped])
    return "\n".join(text[c.start : c.end] for c in chunks)


class TestSkippedSections:
    def test_install_sheet_keeps_the_english_steps_only(self):
        text, starts = _sheet()

        skipped = skipped_sections(text, page_starts=starts)
        kept = _kept_text(text, starts, skipped)

        assert kept == ENGLISH_STEPS
        assert [s.reason for s in skipped] == [
            SAFETY,
            OTHER_LANGUAGE,
            WARRANTY,
            OTHER_LANGUAGE,
            CONTACT,
            LEGAL,
        ]

    def test_junk_from_the_issue_is_not_read(self):
        text, starts = _sheet()

        kept = _kept_text(text, starts, skipped_sections(text, page_starts=starts)).lower()

        for junk in (
            "pacemaker",
            "original consumer purchaser",
            "consommateur",
            "preuve d'achat",
            "réclamation",
            "garantie à vie limitée de moen",
        ):
            assert junk not in kept
        # The instructions' own pencil and wall stay
        assert "pencil" in kept and "wall" in kept

    def test_sections_report_pages_reason_and_preview(self):
        text, starts = _sheet()

        section = skipped_sections(text, page_starts=starts)[1].to_json(text, starts)

        assert section["reason"] == OTHER_LANGUAGE
        assert (section["page_first"], section["page_last"]) == (2, 2)
        assert section["preview"].startswith("INSTRUCTIONS D'INSTALLATION Outils")
        assert text[section["start"] : section["end"]] == FRENCH_STEPS

    def test_neighbouring_sections_with_one_reason_merge(self):
        text, starts = _pages(ENGLISH_STEPS, FRENCH_STEPS, FRENCH_WARRANTY)

        skipped = skipped_sections(text, page_starts=starts)

        assert [s.reason for s in skipped] == [OTHER_LANGUAGE]
        assert (skipped[0].start, skipped[0].end) == (starts[1], len(text))

    def test_plain_english_text_skips_nothing(self):
        text = ENGLISH_STEPS + "\n\nSAFETY GLASSES\nWear safety glasses while you drill the holes."

        assert skipped_sections(text) == []

    def test_a_caution_inside_the_steps_does_not_drop_them(self):
        text = ENGLISH_STEPS.replace(
            "2. Drill", "Caution: do not drill into pipes or wires behind the wall.\n2. Drill"
        )

        assert skipped_sections(text) == []

    def test_short_lines_inside_a_skipped_copy_go_with_it(self):
        text = FRENCH_STEPS + "\n\n2\n\n" + FRENCH_STEPS

        skipped = skipped_sections(text)

        assert [(s.start, s.end, s.reason) for s in skipped] == [(0, len(text), OTHER_LANGUAGE)]

    def test_source_heading_names_the_topic(self):
        body = (
            "This product is covered for as long as you own it, except for damage caused"
            " by misuse. Keep your receipt."
        )
        text = ENGLISH_STEPS + "\n" + body
        heading = Heading(start=len(ENGLISH_STEPS) + 1, title="Warranty")

        skipped = skipped_sections(text, headings=[Heading(0, "Install"), heading])

        assert [(s.start, s.reason) for s in skipped] == [(heading.start, WARRANTY)]

    def test_only_the_selected_pages_are_looked_at(self):
        text, starts = _sheet()

        skipped = skipped_sections(text, page_starts=starts, pages="1-2")

        assert [s.reason for s in skipped] == [SAFETY, OTHER_LANGUAGE]
        assert all(s.end <= starts[2] for s in skipped)

    def test_empty_text_skips_nothing(self):
        assert skipped_sections("") == []


class TestSkipReporting:
    def test_counts_and_note(self):
        text, starts = _sheet()
        skipped = skipped_sections(text, page_starts=starts)

        assert skipped_by_reason(skipped) == {
            OTHER_LANGUAGE: 2,
            SAFETY: 1,
            WARRANTY: 1,
            CONTACT: 1,
            LEGAL: 1,
        }
        assert skip_note(skipped).startswith(
            "Skipped 6 sections as boilerplate or another language (other_language 2,"
        )
        assert "skip_boilerplate to false" in skip_note(skipped)
        summary = skip_summary(skipped, text, starts)
        assert len(summary["skipped_sections"]) == 6
        assert summary["skipped_sections_by_reason"][OTHER_LANGUAGE] == 2


class TestChunkTextSkip:
    def test_no_chunk_overlaps_a_skipped_span(self):
        text = "First part here. " * 20 + "Skip this middle. " * 10 + "Last part here. " * 20
        middle = (text.index("Skip"), text.index("Last"))

        chunks = chunk_text(text, max_chars=200, skip=[middle])

        assert chunks
        assert all(c.end <= middle[0] or c.start >= middle[1] for c in chunks)
        assert "Skip" not in "".join(text[c.start : c.end] for c in chunks)

    def test_without_skip_everything_is_chunked(self):
        text, starts = _sheet()

        chunks = chunk_text(text, page_starts=starts)

        assert "".join(text[c.start : c.end] for c in chunks).count("Moen garantit") == 1
