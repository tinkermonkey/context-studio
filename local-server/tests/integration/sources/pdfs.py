"""Tiny PDFs built in memory for source tests (#1551)."""

import io
from typing import Optional

from pypdf import PdfReader, PdfWriter


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_pdf(pages: list[list[str]], title: Optional[str] = None) -> bytes:
    """
    A PDF with a text layer: each page a list of lines in Helvetica. An empty
    page list gives a page with no text.
    """
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # the page tree, filled in once the page ids are known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_ids = []
    for lines in pages:
        ops = ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"]
        for line in lines:
            ops += [f"({_escape(line)}) Tj", "T*"]
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content_id = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % content_id
        )
        page_ids.append(len(objects))
    kids = " ".join(f"{i} 0 R" for i in page_ids).encode()
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n%s\nendobj\n" % (number, body))
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1))
    out.write(b"startxref\n%d\n%%%%EOF\n" % xref)  # the marker is %%EOF
    data = out.getvalue()
    if title is None:
        return data
    return with_outline(data, [], title=title)


def with_outline(
    data: bytes, outline: list[tuple[str, int, int]], title: Optional[str] = None
) -> bytes:
    """
    The PDF with outline entries (title, 0-based page, level 1 or 2) and a
    metadata title. A level-2 entry nests under the level-1 entry before it.
    """
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    parent = None
    for entry_title, page, level in outline:
        item = writer.add_outline_item(entry_title, page, parent=parent if level == 2 else None)
        if level == 1:
            parent = item
    if title is not None:
        writer.add_metadata({"/Title": title})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def scanned_pdf(page_count: int = 2) -> bytes:
    """A PDF whose pages have no text layer, like a scan."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
