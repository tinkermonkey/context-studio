"""
Sources: the files, web pages and pasted text that extraction reads (#1551).

A source keeps its text, extracted once, with the character offset where each
page and each heading starts, so a candidate can point back to the passage it
came from: `{source_id, page, start, end, quote}`. Pages are numbered from 1;
`page_starts[0]` is where page 1 starts and is always 0.

Reading a format is behind the SourceReader port (one adapter per format) and
fetching a web page behind PageFetcher. A source that can't be read is still
stored, as failed, with the reason.

Removing a source marks it removed rather than deleting it, so provenance rows
that name it keep pointing at a source (with its title and text).
"""

from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Mapping, Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4

from domain.extraction.exceptions import SourceFailedError, SourceNotReadyError
from domain.ontology.datasets import resolve_dataset_id
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.ports import OntologyRepository

if TYPE_CHECKING:
    # The port module imports the types below
    from domain.extraction.ports import (
        PageFetcher,
        SourceFileStore,
        SourceReader,
        SourceRepository,
    )

logger = logging.getLogger(__name__)

DEFAULT_MAX_BYTES = 50 * 1024 * 1024


class SourceKind(str, Enum):
    """What a source is: an uploaded file's format, a fetched web page, or text."""

    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    WEB = "web"


class SourceStatus(str, Enum):
    """Where a source is: being fetched, readable, or not."""

    FETCHING = "fetching"
    READY = "ready"
    FAILED = "failed"


class SourceFailure(str, Enum):
    """Why a source failed."""

    TOO_LARGE = "too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    NO_TEXT = "no_text"
    FETCH_FAILED = "fetch_failed"


_SUFFIX_KINDS = {
    ".pdf": SourceKind.PDF,
    ".md": SourceKind.MARKDOWN,
    ".markdown": SourceKind.MARKDOWN,
    ".html": SourceKind.HTML,
    ".htm": SourceKind.HTML,
    ".txt": SourceKind.TEXT,
    ".text": SourceKind.TEXT,
}

_CONTENT_TYPE_KINDS = {
    "application/pdf": SourceKind.PDF,
    "text/markdown": SourceKind.MARKDOWN,
    "text/x-markdown": SourceKind.MARKDOWN,
    "text/html": SourceKind.HTML,
    "application/xhtml+xml": SourceKind.HTML,
    "application/x-pdf": SourceKind.PDF,
    "text/plain": SourceKind.TEXT,
}

# Content types servers send for files whose real type the name says better
# (Markdown is often served as text/plain).
_GENERIC_TYPES = {"", "application/octet-stream", "application/x-pdf", "text/plain"}

PDF_MAGIC = b"%PDF-"


def _media_type(content_type: Optional[str]) -> str:
    """'text/html; charset=utf-8' -> 'text/html'."""
    return (content_type or "").split(";")[0].strip().lower()


def _suffix_kind(name: Optional[str]) -> Optional[SourceKind]:
    return _SUFFIX_KINDS.get(PurePosixPath(name or "").suffix.lower())


def file_kind(
    file_name: Optional[str], content_type: Optional[str], data: bytes = b""
) -> Optional[SourceKind]:
    """
    An uploaded file's kind: a PDF by its first bytes, else by its extension,
    else its content type (browsers often send Markdown as
    application/octet-stream). None when unsupported.
    """
    if data.startswith(PDF_MAGIC):
        return SourceKind.PDF
    return _suffix_kind(file_name) or _CONTENT_TYPE_KINDS.get(_media_type(content_type))


def fetched_kind(
    url: str,
    content_type: Optional[str],
    data: bytes = b"",
    file_name: Optional[str] = None,
) -> Optional[SourceKind]:
    """
    A fetched page's kind. A PDF by its first bytes; else the content type the
    server sent, except that for a generic type (octet-stream, text/plain) the
    name wins when its extension is known: the Content-Disposition file name,
    else the URL's path. An HTML page is `web`; a PDF or text file behind a URL
    keeps its format. None when unsupported.
    """
    if data.startswith(PDF_MAGIC):
        return SourceKind.PDF
    media = _media_type(content_type)
    named = _suffix_kind(file_name) or _suffix_kind(urlparse(url).path)
    if media in _GENERIC_TYPES:
        kind = named or _CONTENT_TYPE_KINDS.get(media)
    else:
        kind = _CONTENT_TYPE_KINDS.get(media) or named
    return SourceKind.WEB if kind is SourceKind.HTML else kind


def fetched_file_name(page: FetchedPage) -> Optional[str]:
    """
    A fetched file's name: the Content-Disposition file name, else the last
    segment of the URL's path ("ins10668b.pdf"); None when there is neither.
    """
    name = (page.file_name or "").strip() or PurePosixPath(unquote(urlparse(page.url).path)).name
    return name.strip() or None


def check_url(url: str) -> str:
    """
    The URL to fetch, trimmed.

    Raises:
        ValueError: If it is not an absolute http or https URL
    """
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Only http and https URLs can be fetched, not {url!r}")
    return url


@dataclass(frozen=True)
class SourceHeading:
    """
    A heading in a source's text.

    Attributes:
        start: Character offset in the source text where the heading starts
        title: The heading's text
        level: 1 for a top-level heading, 2 below it, and so on
    """

    start: int
    title: str
    level: int


@dataclass(frozen=True)
class SourceText:
    """
    What a SourceReader reads from a file: the text with its page and heading offsets.

    Attributes:
        text: The extracted text
        page_starts: The offset where each page starts; [0] for a single page
        headings: Headings in text order
        title: The title the file gives itself, if any (PDF metadata, HTML title,
            a Markdown file's first top-level heading)
    """

    text: str
    page_starts: list[int] = field(default_factory=lambda: [0])
    headings: list[SourceHeading] = field(default_factory=list)
    title: Optional[str] = None


@dataclass(frozen=True)
class FetchedPage:
    """
    What a PageFetcher fetched.

    Attributes:
        data: The response body
        content_type: The Content-Type header, if any
        url: The URL fetched, after redirects
        file_name: The file name a Content-Disposition header gave, if any
    """

    data: bytes
    content_type: Optional[str]
    url: str
    file_name: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Source:
    """
    A file, web page or text extraction reads, in a taxonomy's dataset.

    Attributes:
        id: UUID
        taxonomy_id: The taxonomy whose schema extraction from it uses
        dataset_id: The dataset its data goes into
        kind: pdf, markdown, html, text or web
        title: Display name
        origin: The URL or file name it came from; None for pasted text
        content_type: The media type it was read as
        bytes: Size of the original
        pages: Number of pages (1 for anything but a PDF)
        chars: Length of `text`
        text: The extracted text ("" until ready)
        page_starts: Offset in `text` where each page starts; [0] for one page
        headings: Headings with their offsets, in text order
        status: fetching, ready or failed
        failure: Why it failed, when it did
        failure_detail: A sentence saying more about the failure
        created_at, updated_at: Timestamps (UTC)
        removed_at: When it was removed; a removed source stays for provenance
    """

    taxonomy_id: str
    dataset_id: str
    kind: SourceKind
    title: str
    id: str = field(default_factory=lambda: str(uuid4()))
    origin: Optional[str] = None
    content_type: Optional[str] = None
    bytes: int = 0
    pages: int = 0
    chars: int = 0
    text: str = ""
    page_starts: list[int] = field(default_factory=list)
    headings: list[SourceHeading] = field(default_factory=list)
    status: SourceStatus = SourceStatus.READY
    failure: Optional[SourceFailure] = None
    failure_detail: Optional[str] = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    removed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.kind = SourceKind(self.kind)
        self.status = SourceStatus(self.status)
        if self.failure is not None:
            self.failure = SourceFailure(self.failure)

    def page_range(self, page: int) -> tuple[int, int]:
        """
        The [start, end) offsets of a page (numbered from 1) in `text`.

        Raises:
            ValueError: If the source has no such page
        """
        if not 1 <= page <= self.pages:
            raise ValueError(f"page must be 1 to {self.pages}, not {page}")
        end = self.page_starts[page] if page < self.pages else self.chars
        return self.page_starts[page - 1], end

    def page_at(self, offset: int) -> int:
        """The page (numbered from 1) that a character offset in `text` falls on."""
        return max(1, bisect.bisect_right(self.page_starts, offset))


class SourceService:
    """Adds, reads and removes sources."""

    def __init__(
        self,
        sources: "SourceRepository",
        ontology_repo: OntologyRepository,
        readers: Mapping[SourceKind, "SourceReader"],
        fetcher: "PageFetcher",
        files: "SourceFileStore",
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._sources = sources
        self._ontology = ontology_repo
        self._readers = readers
        self._fetcher = fetcher
        self._files = files
        self._max_bytes = max_bytes

    @property
    def max_bytes(self) -> int:
        """The largest original a source may have."""
        return self._max_bytes

    def add_file(
        self,
        taxonomy_id: str,
        file_name: str,
        data: bytes,
        content_type: Optional[str] = None,
        dataset: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Source:
        """
        Store an uploaded file and read its text. A file that can't be read is
        stored as a failed source saying why.

        Args:
            taxonomy_id: The taxonomy
            file_name: The uploaded file's name
            data: Its bytes (callers may stop reading past max_bytes)
            content_type: The media type the upload declared
            dataset: The dataset (identifier or id); else the taxonomy's only one
            title: A title; else the file's own, else its name

        Raises:
            EntityNotFoundError: If the taxonomy or the named dataset doesn't exist
            DatasetRequiredError: If none is named and the taxonomy has several
            DatasetMismatchError: If the named dataset is another taxonomy's
        """
        kind = file_kind(file_name, content_type, data)
        source = Source(
            taxonomy_id=taxonomy_id,
            dataset_id=self._dataset_id(taxonomy_id, dataset),
            # An unsupported file is stored as a failed text source saying why
            kind=kind or SourceKind.TEXT,
            title=(title or "").strip() or PurePosixPath(file_name).stem or file_name,
            origin=file_name,
            content_type=_media_type(content_type) or None,
            bytes=len(data),
        )
        if kind is None:
            return self._sources.save(
                _failed(source, SourceFailure.UNSUPPORTED_TYPE, _unsupported(content_type))
            )
        read = self._read(source, data, has_title=bool((title or "").strip()))
        self._keep_original(read, data)
        return self._sources.save(read)

    def add_text(
        self, taxonomy_id: str, title: str, text: str, dataset: Optional[str] = None
    ) -> Source:
        """
        Store pasted text as a single-page source.

        Raises:
            ValueError: If the title or the text is blank
            EntityNotFoundError, DatasetRequiredError, DatasetMismatchError: As add_file
        """
        if not title.strip():
            raise ValueError("A text source needs a title")
        if not text.strip():
            raise ValueError("A text source needs some text")
        data = text.encode("utf-8")
        source = Source(
            taxonomy_id=taxonomy_id,
            dataset_id=self._dataset_id(taxonomy_id, dataset),
            kind=SourceKind.TEXT,
            title=title.strip(),
            content_type="text/plain",
            bytes=len(data),
        )
        return self._sources.save(self._read(source, data, has_title=True))

    def add_url(
        self, taxonomy_id: str, url: str, dataset: Optional[str] = None, title: Optional[str] = None
    ) -> Source:
        """
        Record a web page to fetch, with status `fetching`; `fetch` reads it.

        Raises:
            ValueError: If the URL is not http or https
            EntityNotFoundError, DatasetRequiredError, DatasetMismatchError: As add_file
        """
        url = check_url(url)
        return self._sources.save(
            Source(
                taxonomy_id=taxonomy_id,
                dataset_id=self._dataset_id(taxonomy_id, dataset),
                kind=SourceKind.WEB,
                title=(title or "").strip() or url,
                origin=url,
                status=SourceStatus.FETCHING,
            )
        )

    def fetch(self, source_id: str) -> Source:
        """
        Fetch a `fetching` source's page (one page, no links followed) and read
        it: ready, or failed saying why.

        Raises:
            EntityNotFoundError: If the source doesn't exist
        """
        source = self.get(source_id)
        if source.status is not SourceStatus.FETCHING or source.removed_at is not None:
            return source
        try:
            return self._fetch(source)
        except Exception as exc:  # noqa: BLE001 - it runs in the background: never stay fetching
            logger.exception("Fetching source %s failed", source.id)
            return self._save_unless_removed(
                _failed(source, SourceFailure.FETCH_FAILED, f"{type(exc).__name__}: {exc}")
            )

    def _fetch(self, source: Source) -> Source:
        has_title = source.title != source.origin
        try:
            page = self._fetcher.fetch(str(source.origin), self._max_bytes)
        except SourceFailedError as exc:
            return self._save_unless_removed(_failed(source, exc.failure, exc.detail))
        kind = fetched_kind(page.url, page.content_type, page.data, page.file_name)
        source = replace(
            source,
            content_type=_media_type(page.content_type) or None,
            bytes=len(page.data),
            kind=kind or SourceKind.WEB,
        )
        if kind is None:
            return self._save_unless_removed(
                _failed(source, SourceFailure.UNSUPPORTED_TYPE, _unsupported(page.content_type))
            )
        if not has_title and kind is not SourceKind.WEB:
            # A file behind a URL: its own title (read below) wins, else its file name
            source = replace(source, title=fetched_file_name(page) or source.title)
        return self._save_unless_removed(
            self._read(source, page.data, has_title=has_title), original=page.data
        )

    def _save_unless_removed(self, source: Source, original: Optional[bytes] = None) -> Source:
        """
        Save a fetch's result, and keep its original, unless the source was
        removed while it was being fetched: then it stays removed.
        """
        current = self.get(source.id)
        if current.removed_at is not None:
            return current
        if original is not None:
            self._keep_original(source, original)
        return self._sources.save(source)

    def fail_interrupted_fetches(self) -> int:
        """
        Fail every source still `fetching` (the app stopped mid-fetch); run at
        startup. Returns how many.
        """
        interrupted = self._sources.list_sources(status=SourceStatus.FETCHING)
        for listed in interrupted:
            self._sources.save(
                _failed(
                    self.get(listed.id),
                    SourceFailure.FETCH_FAILED,
                    "The app stopped while fetching",
                )
            )
        return len(interrupted)

    def get(self, source_id: str) -> Source:
        """
        A source, removed or not.

        Raises:
            EntityNotFoundError: If there is none
        """
        source = self._sources.get(source_id)
        if source is None:
            raise EntityNotFoundError("Source", source_id)
        return source

    def list_sources(
        self,
        taxonomy_id: str,
        dataset: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> tuple[list[Source], int]:
        """
        A page of a taxonomy's sources (in one dataset, identifier or id, when
        named), newest first, without removed ones and without their text
        (`get` has it); and how many there are in all.

        Raises:
            EntityNotFoundError: If the taxonomy or the named dataset doesn't exist
        """
        self._check_taxonomy(taxonomy_id)
        dataset_id = self._named_dataset_id(taxonomy_id, dataset) if dataset else None
        page = self._sources.list_sources(
            taxonomy_id=taxonomy_id, dataset_id=dataset_id, limit=limit, offset=offset
        )
        total = self._sources.count_sources(taxonomy_id=taxonomy_id, dataset_id=dataset_id)
        return page, total

    def text(self, source_id: str, page: Optional[int] = None) -> tuple[Source, int, int]:
        """
        A source with the [start, end) offsets of one page, or of all its text.

        Raises:
            EntityNotFoundError: If the source doesn't exist
            SourceNotReadyError: If it is fetching or failed
            ValueError: If it has no such page
        """
        source = self.get(source_id)
        if source.status is not SourceStatus.READY:
            raise SourceNotReadyError(source.id, source.status.value)
        if page is None:
            return source, 0, source.chars
        start, end = source.page_range(page)
        return source, start, end

    def remove(self, source_id: str) -> Source:
        """
        Remove a source: it leaves lists and its original file is deleted, but
        its record stays, so the provenance of entities applied from it still
        names it.

        Raises:
            EntityNotFoundError: If it doesn't exist or is already removed
        """
        source = self.get(source_id)
        if source.removed_at is not None:
            raise EntityNotFoundError("Source", source_id)
        self._files.delete(source.id)
        now = _now()
        return self._sources.save(replace(source, removed_at=now, updated_at=now))

    def _keep_original(self, source: Source, data: bytes) -> None:
        """Keep the original of a file or page that was read (not one too large)."""
        if source.failure is not SourceFailure.TOO_LARGE:
            self._files.save(source.id, source.kind, data)

    def _read(self, source: Source, data: bytes, has_title: bool) -> Source:
        """The source with its text read, or failed: too large, or unreadable."""
        if len(data) > self._max_bytes:
            return _failed(
                source,
                SourceFailure.TOO_LARGE,
                f"Larger than the {self._max_bytes // (1024 * 1024)} MB limit",
            )
        try:
            read = self._readers[source.kind].read(data)
        except SourceFailedError as exc:
            return _failed(source, exc.failure, exc.detail)
        except Exception as exc:  # noqa: BLE001 - a reader's crash fails the source, not the app
            return _failed(
                source,
                SourceFailure.UNSUPPORTED_TYPE,
                f"Could not read it as {source.kind.value} ({type(exc).__name__}: {exc})",
            )
        if not read.text.strip():
            return _failed(source, SourceFailure.NO_TEXT, "No text could be read from it")
        return replace(
            source,
            title=source.title if has_title else (read.title or "").strip() or source.title,
            text=read.text,
            chars=len(read.text),
            pages=len(read.page_starts),
            page_starts=list(read.page_starts),
            headings=list(read.headings),
            status=SourceStatus.READY,
            failure=None,
            failure_detail=None,
            updated_at=_now(),
        )

    def _check_taxonomy(self, taxonomy_id: str) -> None:
        if self._ontology.get_taxonomy(taxonomy_id) is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

    def _named_dataset_id(self, taxonomy_id: str, dataset: str) -> str:
        """A dataset of the taxonomy named by identifier or id."""
        for candidate in self._ontology.list_datasets(taxonomy_id=taxonomy_id):
            if dataset in (candidate.id, candidate.identifier):
                return candidate.id
        raise EntityNotFoundError("Dataset", dataset)

    def _dataset_id(self, taxonomy_id: str, dataset: Optional[str]) -> str:
        """The dataset a new source goes into, resolved like other dataset-scoped writes."""
        self._check_taxonomy(taxonomy_id)
        if dataset and self._ontology.get_dataset(dataset) is None:
            dataset = self._named_dataset_id(taxonomy_id, dataset)
        return resolve_dataset_id(self._ontology, taxonomy_id, dataset or None)


def _unsupported(content_type: Optional[str]) -> str:
    named = _media_type(content_type) or "unknown"
    return f"Not a PDF, Markdown, HTML or text file (type {named})"


def _failed(source: Source, failure: SourceFailure | str, detail: Optional[str]) -> Source:
    return replace(
        source,
        status=SourceStatus.FAILED,
        failure=SourceFailure(failure),
        failure_detail=detail,
        text="",
        chars=0,
        pages=0,
        page_starts=[],
        headings=[],
        updated_at=_now(),
    )
