"""The SourceReader adapters (#1551): PDF, HTML, Markdown and plain text."""

import pytest

from adapters.sources.readers import (
    HtmlReader,
    MarkdownReader,
    PdfTextReader,
    PlainTextReader,
    decode_text,
)
from domain.extraction.exceptions import SourceFailedError
from domain.extraction.sources import SourceHeading
from tests.integration.sources.pdfs import scanned_pdf, text_pdf, with_outline

PAGE = """<html><head><title>Replace a furnace filter | Energy</title></head><body>
<nav><a href="/">Home</a> <a href="/products">Products</a> <a href="/about">About us</a></nav>
<main><article>
<h1>How to replace a furnace filter</h1>
<p>Turn off the <b>furnace</b> before you start. A dirty filter makes the blower work
harder and wastes energy over the winter, so check it every month.</p>
<h2>Find the filter</h2>
<p>The filter sits in a slot between the return duct and the blower compartment.
Check the arrow on its frame for the airflow direction before you pull it out.</p>
<ul><li>16x25x1</li><li>20x25x1</li></ul>
<p>Replace it every three months, or monthly when you have pets in the house.</p>
</article></main>
<footer>Copyright 2026 Energy Star. Privacy policy. Contact us at the number below.</footer>
</body></html>"""


def test_pdf_reads_each_page_with_its_offset_and_outline():
    data = with_outline(
        text_pdf(
            [
                ["Use and care guide", "Read all safety instructions."],
                ["Cleaning", "Unplug the refrigerator before cleaning."],
                [],
            ]
        ),
        [("Safety", 0, 1), ("Cleaning", 1, 1), ("Shelves", 1, 2)],
        title="WRF555SDFZ use and care guide",
    )
    read = PdfTextReader().read(data)

    assert len(read.page_starts) == 3
    assert read.page_starts[0] == 0
    page_two = read.text[read.page_starts[1] : read.page_starts[2]]
    assert "Unplug the refrigerator before cleaning." in page_two
    assert "Read all safety" in read.text[: read.page_starts[1]]
    assert read.title == "WRF555SDFZ use and care guide"
    assert read.headings == [
        SourceHeading(start=0, title="Safety", level=1),
        SourceHeading(start=read.page_starts[1], title="Cleaning", level=1),
        SourceHeading(start=read.page_starts[1], title="Shelves", level=2),
    ]


def test_a_scanned_pdf_has_no_text():
    with pytest.raises(SourceFailedError) as raised:
        PdfTextReader().read(scanned_pdf())
    assert raised.value.failure == "no_text"


def test_a_broken_pdf_is_unsupported():
    with pytest.raises(SourceFailedError) as raised:
        PdfTextReader().read(b"%PDF-1.4 truncated")
    assert raised.value.failure == "unsupported_type"


def test_html_keeps_the_main_text_and_its_headings():
    read = HtmlReader().read(PAGE.encode("utf-8"))

    assert read.title == "How to replace a furnace filter"
    assert read.text.startswith("How to replace a furnace filter\n\nTurn off the furnace")
    assert "- 16x25x1\n- 20x25x1" in read.text
    for chrome in ("Products", "About us", "Privacy policy"):
        assert chrome not in read.text
    assert [(h.title, h.level) for h in read.headings] == [
        ("How to replace a furnace filter", 1),
        ("Find the filter", 2),
    ]
    for heading in read.headings:
        assert read.text[heading.start :].startswith(heading.title)
    assert read.page_starts == [0]


def test_html_with_no_main_text_reads_empty():
    assert HtmlReader().read(b"<html><body></body></html>").text == ""


def test_markdown_headings_skip_fenced_code():
    text = "# Dishwasher\r\n\r\nIntro.\n\n## Filters ##\n```\n# not a heading\n```\n### Rinse aid\n"
    read = MarkdownReader().read(text.encode("utf-8"))

    assert "\r" not in read.text
    assert read.title == "Dishwasher"
    assert [(h.title, h.level) for h in read.headings] == [
        ("Dishwasher", 1),
        ("Filters", 2),
        ("Rinse aid", 3),
    ]
    for heading in read.headings:
        assert read.text[heading.start :].startswith("#")


def test_plain_text_is_one_page():
    read = PlainTextReader().read("﻿Flush the tank.\r\n".encode("utf-8"))
    assert read.text == "Flush the tank.\n"
    assert read.page_starts == [0]
    assert read.headings == []


def test_decode_falls_back_to_windows_1252():
    assert decode_text("café".encode("cp1252")) == "café"
