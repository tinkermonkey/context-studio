"""
SourceReader adapters, one per format (#1551).

- PDF: the text layer, page by page (pypdf); the PDF's outline gives headings.
  A scanned PDF has no text layer; the service fails it with no_text.
- HTML (uploaded files and fetched pages): the main text without menus and
  footers (trafilatura), with its headings.
- Markdown: the file's text as it is, with headings from its `#` lines.
- Plain text: the text as it is.

Pages are separated by a blank line in a PDF's text; everything else is one page.
"""

from __future__ import annotations

import io
import re
from typing import Any, Optional

import trafilatura
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from domain.extraction.exceptions import SourceFailedError
from domain.extraction.sources import SourceFailure, SourceHeading, SourceKind, SourceText
from utils.logger import get_logger

logger = get_logger(__name__)

PAGE_SEPARATOR = "\n\n"
BLOCK_SEPARATOR = "\n\n"

_ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_WHITESPACE = re.compile(r"\s+")


def decode_text(data: bytes) -> str:
    """Bytes as text: UTF-8 (with or without a BOM), else Windows-1252; newlines as \\n."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _squash(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


class PlainTextReader:
    """Plain text: one page, no headings."""

    def read(self, data: bytes) -> SourceText:
        return SourceText(text=decode_text(data))


class MarkdownReader:
    """Markdown as written, with ATX (`#`) headings outside fenced code."""

    def read(self, data: bytes) -> SourceText:
        text = decode_text(data)
        headings = []
        offset = 0
        in_fence = False
        for line in text.split("\n"):
            if _FENCE.match(line):
                in_fence = not in_fence
            elif not in_fence:
                match = _ATX_HEADING.match(line)
                if match:
                    headings.append(
                        SourceHeading(
                            start=offset, title=match.group(2).strip(), level=len(match.group(1))
                        )
                    )
            offset += len(line) + 1
        title = next((h.title for h in headings if h.level == 1), None)
        return SourceText(text=text, headings=headings, title=title)


class HtmlReader:
    """An HTML page's main text, without navigation, footers and comments."""

    def read(self, data: bytes) -> SourceText:
        # A trafilatura Document (body: an lxml element; title) or None
        document: Any = trafilatura.bare_extraction(
            data,
            with_metadata=True,
            include_formatting=True,
            include_comments=False,
            include_links=False,
            include_images=False,
        )
        if document is None or document.body is None:
            return SourceText(text="")
        blocks: list[str] = []
        headings: list[SourceHeading] = []
        offset = 0
        for element in document.body:
            block = self._block_text(element)
            if not block:
                continue
            if blocks:
                offset += len(BLOCK_SEPARATOR)
            if element.tag == "head":
                headings.append(
                    SourceHeading(start=offset, title=block, level=self._level(element))
                )
            blocks.append(block)
            offset += len(block)
        return SourceText(
            text=BLOCK_SEPARATOR.join(blocks),
            headings=headings,
            title=_squash(document.title or "") or None,
        )

    @staticmethod
    def _level(element: Any) -> int:
        """`<head rend="h2">` is level 2; a head with no level is 1."""
        match = re.fullmatch(r"h([1-6])", element.get("rend") or "")
        return int(match.group(1)) if match else 1

    @staticmethod
    def _block_text(element: Any) -> str:
        """A block's text: list items and table rows on their own lines."""
        if element.tag == "list":
            items = [_squash("".join(item.itertext())) for item in element.iter("item")]
            return "\n".join(f"- {item}" for item in items if item)
        if element.tag == "table":
            rows = [
                " | ".join(_squash("".join(cell.itertext())) for cell in row.iter("cell"))
                for row in element.iter("row")
            ]
            return "\n".join(row for row in rows if row.strip(" |"))
        return _squash("".join(element.itertext()))


class PdfTextReader:
    """A PDF's text layer, page by page, with headings from its outline."""

    def read(self, data: bytes) -> SourceText:
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise SourceFailedError(
                    SourceFailure.NO_TEXT.value, "The PDF is encrypted with a password"
                )
            pages = list(reader.pages)
        except SourceFailedError:
            raise
        except (PdfReadError, ValueError, KeyError, TypeError) as exc:
            raise SourceFailedError(
                SourceFailure.UNSUPPORTED_TYPE.value, f"Not a readable PDF ({exc})"
            ) from exc

        text = ""
        page_starts: list[int] = []
        for number, page in enumerate(pages, start=1):
            if page_starts:
                text += PAGE_SEPARATOR
            page_starts.append(len(text))
            text += self._page_text(page, number)
        if not text.strip():
            raise SourceFailedError(
                SourceFailure.NO_TEXT.value,
                "The PDF has no text layer (a scanned PDF needs OCR, which isn't supported yet)",
            )
        return SourceText(
            text=text,
            page_starts=page_starts,
            headings=self._outline_headings(reader, page_starts),
            title=self._title(reader),
        )

    @staticmethod
    def _page_text(page: Any, number: int) -> str:
        try:
            return (page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n")
        except Exception as exc:  # noqa: BLE001 - one unreadable page leaves the rest
            logger.warning("Could not read the text of PDF page %d: %s", number, exc)
            return ""

    @staticmethod
    def _title(reader: PdfReader) -> Optional[str]:
        try:
            return _squash((reader.metadata.title if reader.metadata else None) or "") or None
        except Exception:  # noqa: BLE001 - a malformed info dictionary means no title
            return None

    @staticmethod
    def _outline_headings(reader: PdfReader, page_starts: list[int]) -> list[SourceHeading]:
        """Outline (bookmark) entries as headings at the start of the page they point to."""
        headings: list[SourceHeading] = []

        def walk(items: list, level: int) -> None:
            for item in items:
                if isinstance(item, list):
                    walk(item, level + 1)
                    continue
                page = reader.get_destination_page_number(item)
                title = _squash(str(item.title or ""))
                if title and page is not None and 0 <= page < len(page_starts):
                    headings.append(
                        SourceHeading(start=page_starts[page], title=title, level=level)
                    )

        try:
            walk(reader.outline, 1)
        except Exception as exc:  # noqa: BLE001 - a broken outline means no headings
            logger.warning("Could not read the PDF outline: %s", exc)
            return []
        return sorted(headings, key=lambda h: h.start)


def source_readers() -> dict[SourceKind, Any]:
    """The reader for each source kind; fetched web pages read as HTML."""
    html = HtmlReader()
    return {
        SourceKind.PDF: PdfTextReader(),
        SourceKind.MARKDOWN: MarkdownReader(),
        SourceKind.HTML: html,
        SourceKind.WEB: html,
        SourceKind.TEXT: PlainTextReader(),
    }
