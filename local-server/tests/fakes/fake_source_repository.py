"""In-memory fakes for the source ports (#1551)."""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from domain.extraction.exceptions import SourceFailedError
from domain.extraction.sources import (
    FetchedPage,
    Source,
    SourceFailure,
    SourceKind,
    SourceStatus,
    SourceText,
)


class FakeSourceRepository:
    """SourceRepository in a dict; behaves like SQLiteSourceRepository."""

    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}

    def save(self, source: Source) -> Source:
        self.sources[source.id] = replace(source)
        return replace(source)

    def get(self, source_id: str) -> Optional[Source]:
        source = self.sources.get(source_id)
        return replace(source) if source else None

    def list_sources(
        self,
        taxonomy_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        status: Optional[SourceStatus] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Source]:
        found = self._matching(taxonomy_id, dataset_id, status)
        found.sort(key=lambda s: (-s.created_at.timestamp(), s.id))
        end = None if limit is None else offset + limit
        # Like SQLite, a list leaves the text out
        return [replace(s, text="") for s in found[offset:end]]

    def count_sources(
        self,
        taxonomy_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        status: Optional[SourceStatus] = None,
    ) -> int:
        return len(self._matching(taxonomy_id, dataset_id, status))

    def _matching(
        self,
        taxonomy_id: Optional[str],
        dataset_id: Optional[str],
        status: Optional[SourceStatus],
    ) -> list[Source]:
        return [
            s
            for s in self.sources.values()
            if s.removed_at is None
            and (taxonomy_id is None or s.taxonomy_id == taxonomy_id)
            and (dataset_id is None or s.dataset_id == dataset_id)
            and (status is None or s.status == status)
        ]


class FakeSourceReader:
    """Reads bytes as UTF-8; pages split on form feeds; fails as told."""

    def __init__(self, failure: Optional[SourceFailure] = None) -> None:
        self.failure = failure

    def read(self, data: bytes) -> SourceText:
        if self.failure is not None:
            raise SourceFailedError(self.failure.value, "told to fail")
        pages = data.decode("utf-8").split("\f")
        starts, offset = [], 0
        for page in pages:
            starts.append(offset)
            offset += len(page) + 1
        return SourceText(text="\f".join(pages), page_starts=starts, title="Read title")


def fake_readers(**failures: SourceFailure) -> dict[SourceKind, FakeSourceReader]:
    """A fake reader per kind; failures by kind value, e.g. pdf=SourceFailure.NO_TEXT."""
    return {kind: FakeSourceReader(failures.get(kind.value)) for kind in SourceKind}


class FakePageFetcher:
    """Answers each URL with a canned page, or fails."""

    def __init__(self) -> None:
        self.pages: dict[str, FetchedPage] = {}
        self.fetched: list[str] = []
        self.before_answer = None  # called just before a page is returned

    def add(self, url: str, body: bytes, content_type: str = "text/html", file_name=None) -> None:
        self.pages[url] = FetchedPage(
            data=body, content_type=content_type, url=url, file_name=file_name
        )

    def fetch(self, url: str, max_bytes: int) -> FetchedPage:
        self.fetched.append(url)
        if self.before_answer is not None:
            self.before_answer()
        page = self.pages.get(url)
        if page is None:
            raise SourceFailedError(SourceFailure.FETCH_FAILED.value, "HTTP 404")
        if len(page.data) > max_bytes:
            raise SourceFailedError(SourceFailure.TOO_LARGE.value, "too large")
        return page


class FakeSourceFileStore:
    """Keeps originals in a dict."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[SourceKind, bytes]] = {}

    def save(self, source_id: str, kind: SourceKind, data: bytes) -> None:
        self.files[source_id] = (kind, data)

    def delete(self, source_id: str) -> None:
        self.files.pop(source_id, None)
