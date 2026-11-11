"""SourceFileStore adapter: originals kept in a folder beside the workspace databases (#1551)."""

from __future__ import annotations

from pathlib import Path

from domain.extraction.sources import SourceKind

_SUFFIXES = {
    SourceKind.PDF: ".pdf",
    SourceKind.MARKDOWN: ".md",
    SourceKind.HTML: ".html",
    SourceKind.WEB: ".html",
    SourceKind.TEXT: ".txt",
}


class LocalSourceFileStore:
    """Keeps each source's original as `<root>/<source id><suffix>`."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def save(self, source_id: str, kind: SourceKind, data: bytes) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / f"{source_id}{_SUFFIXES[SourceKind(kind)]}").write_bytes(data)

    def delete(self, source_id: str) -> None:
        for path in self._root.glob(f"{source_id}.*"):
            path.unlink(missing_ok=True)
