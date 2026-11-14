"""
Source tools for a client's own session, MCP only (#1451): add a source (a
local file, a web page or pasted text), list and read sources, and extract one
into proposals. They wrap the services the REST routes in
`adapters/web/sources_routes.py` use.

- `add_source`: a file by `path`, read only inside a folder listed in
  config.json `sources.allowed_roots`; a `url`, fetched after the call returns
  (the source comes back `fetching`; poll `get_source`); or `text`.
- `list_sources`, `get_source`: sources without their text, each with its
  last extraction.
- `extract_source`: starts background runs that each end in one change
  proposal; follow them with `get_run`, then `get_proposal`.

Decisions are a person's, in Context Studio's review queue; these tools only
add sources and start extractions.
"""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path
from typing import Any, Optional, Sequence

try:
    import fcntl
except ImportError:  # Windows: a descriptor's path can't be confirmed, so paths are refused
    fcntl = None  # type: ignore[assignment]

from adapters.chat.proposal_tools import DEFAULT_LIMIT, PROPOSAL_KIND, _capped
from adapters.chat.tools import (
    ToolArgumentError,
    ToolBase,
    dumps,
    error_outcome,
    int_arg,
    optional_str,
    required_str,
)
from adapters.web.schemas.sources import SourceResponse
from domain.chat.value_objects import EntityRef, ToolOutcome
from domain.extraction.exceptions import SourceNotReadyError
from domain.extraction.sources import Source, SourceService, SourceStatus
from domain.ontology.exceptions import (
    DatasetMismatchError,
    DatasetRequiredError,
    EntityNotFoundError,
)
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionOrchestrator
from domain.pipelines.requested_via import RequestedVia
from domain.pipelines.source_extraction import LastExtraction, SourceExtractionService

# The configuration extract_source runs with when none is named
DEFAULT_CONFIGURATION = IndividualExtractionOrchestrator.SOURCE_CONFIGURATION

_REVIEW = (
    "A person decides each operation in Context Studio's review queue; these tools never decide."
)
_FORMATS = "PDF (its text layer; scanned PDFs have none), Markdown, HTML or plain text"
# As the REST routes cap it
MAX_TITLE_CHARS = 500
# What a source result leaves out: get_source is for following status, not reading.
_OMITTED = {"page_starts", "headings"}


def source_payload(source: Source, last: Optional[LastExtraction]) -> dict[str, Any]:
    """A source as the tools report it: the REST shape, without its text and offsets."""
    return SourceResponse.from_domain(source, last).model_dump(mode="json", exclude=_OMITTED)


def _proposal_refs(last: Optional[LastExtraction]) -> list[EntityRef]:
    """Links to the proposals a source's last extraction produced."""
    if last is None:
        return []
    return [
        EntityRef(id=run.proposal_id, kind=PROPOSAL_KIND, title="Proposal from extraction")
        for run in last.runs
        if run.proposal_id
    ]


class PathRefusedError(ValueError):
    """A path a client may not add a source from."""


def _roots(allowed_roots: Sequence[str]) -> list[Path]:
    """
    The allowed roots, resolved.

    Raises:
        PathRefusedError: If there are none, or one is not absolute (config.py
            refuses those too: a relative root would mean the server's folder)
    """
    if not allowed_roots:
        raise PathRefusedError(
            "Adding a source by path is turned off. To allow it, list the folders"
            " clients may read from (absolute paths) in config.json"
            " sources.allowed_roots and restart Context Studio; or pass the file's"
            " contents as text, or its url."
        )
    roots = [Path(root.strip()).expanduser() for root in allowed_roots]
    if not all(root.is_absolute() and str(root).strip() for root in roots):
        raise PathRefusedError("config.json sources.allowed_roots must list absolute folders")
    return [root.resolve() for root in roots]


def _refuse_outside(raw: str, path: Path, roots: Sequence[Path]) -> None:
    if not any(path.is_relative_to(root) for root in roots):
        raise PathRefusedError(
            f"{raw!r} is not inside a folder clients may read from"
            f" ({', '.join(str(r) for r in roots)}; config.json sources.allowed_roots)"
        )


def readable_path(raw: str, allowed_roots: Sequence[str]) -> Path:
    """
    The path, resolved (symlinks followed), when it is inside one of the
    allowed roots. `read_allowed_file` checks the file it actually opens again.

    Raises:
        PathRefusedError: If no roots are configured, the path is relative, or
            it resolves outside every root
    """
    roots = _roots(allowed_roots)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise PathRefusedError(f"Give an absolute path, not {raw!r}")
    resolved = path.resolve()
    _refuse_outside(raw, resolved, roots)
    return resolved


def _descriptor_path(fd: int) -> Optional[Path]:
    """The path an open descriptor refers to now; None where the platform can't say."""
    if fcntl is not None and hasattr(fcntl, "F_GETPATH"):  # macOS
        named = fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024))
        return Path(os.fsdecode(named.split(b"\0", 1)[0]))
    proc = f"/proc/self/fd/{fd}"  # Linux
    if os.path.islink(proc):
        return Path(os.readlink(proc))
    return None


def read_allowed_file(raw: str, allowed_roots: Sequence[str], max_bytes: int) -> tuple[Path, bytes]:
    """
    Read a file inside the allowed roots: its real path and at most max_bytes
    + 1 bytes (one past, so a file too large is known).

    The checks are made on the descriptor that is read, not the name, so a file
    swapped for a symlink, a FIFO or a link elsewhere after `readable_path`
    can't get in: the last component may not be a symlink, the file must be a
    regular file with no other hard links, and its path once open must still
    be inside a root.

    Raises:
        PathRefusedError: If any check fails or the file can't be read
    """
    resolved = readable_path(raw, allowed_roots)
    roots = _roots(allowed_roots)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise PathRefusedError("This platform can't read a source by path safely")
    try:
        fd = os.open(resolved, os.O_RDONLY | os.O_NONBLOCK | nofollow)
    except FileNotFoundError:
        raise PathRefusedError(f"{raw!r} is not a regular file") from None
    except OSError as exc:  # ELOOP: the last component became a symlink
        raise PathRefusedError(f"{raw!r} could not be opened: {exc.strerror}") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PathRefusedError(f"{raw!r} is not a regular file")
        if info.st_nlink > 1:
            raise PathRefusedError(f"{raw!r} has other hard links, so it can't be read")
        real = _descriptor_path(fd)
        if real is None:
            raise PathRefusedError("This platform can't confirm where an open file is")
        _refuse_outside(raw, real, roots)  # its real path: no names resolved again
        file = os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise
    with file:
        try:
            return real, file.read(max_bytes + 1)
        except OSError as exc:
            raise PathRefusedError(f"{raw!r} could not be read: {exc.strerror}") from None


class _SourceTool(ToolBase):
    """Base for the source tools: domain errors become error outcomes."""

    def __init__(self, sources: SourceService, extraction: SourceExtractionService) -> None:
        self._sources = sources
        self._extraction = extraction

    def _run_safely(self, args: dict[str, Any]) -> ToolOutcome:
        try:
            return super()._run_safely(args)
        except EntityNotFoundError as exc:
            return error_outcome(str(exc), f"{self.name}: not found")
        except PathRefusedError as exc:
            return error_outcome(str(exc), "Path refused")
        except SourceNotReadyError as exc:
            detail = "; poll get_source until it is ready" if exc.status == "fetching" else ""
            return error_outcome(f"{exc}{detail}", "Source not ready")
        except PipelineInputError as exc:
            return error_outcome(str(exc), "Extraction not started")
        except (DatasetRequiredError, DatasetMismatchError, ValueError) as exc:
            return error_outcome(str(exc), f"{self.name}: invalid request")

    def _payload(self, source: Source) -> tuple[dict[str, Any], list[EntityRef]]:
        last = self._extraction.last_extractions([source.id]).get(source.id)
        return source_payload(source, last), _proposal_refs(last)


class AddSourceTool(_SourceTool):
    """Add a file, web page or text to a taxonomy's dataset as a source."""

    name = "add_source"
    description = (
        "Add a source for extraction to a taxonomy's dataset: exactly one of path (a local"
        " file), url (a web page) or text (with a title). A file is "
        + _FORMATS
        + "; it is read only if it is a regular file (no other hard links) whose absolute"
        " path, symlinks followed, is inside a folder listed in Context Studio's"
        " config.json sources.allowed_roots (none are by default), and anything else is"
        " refused. A url is one http or https page (no links"
        " followed, a PDF or text file behind a URL works too): the source comes back with"
        " status fetching and turns ready or failed in the background, so poll get_source"
        " until it does. A file or text is read at once. A source that can't be read is"
        " still stored, status failed, with failure (too_large, unsupported_type, no_text,"
        " fetch_failed) and failure_detail. Returns the source without its text (id, kind,"
        " title, status, pages, chars, ...). Then extract it with extract_source. " + _REVIEW
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "Taxonomy the source is for"},
            "dataset": {
                "type": "string",
                "description": "Dataset (identifier or id); needed only with several",
            },
            "path": {
                "type": "string",
                "description": "Absolute path of a local file under sources.allowed_roots",
            },
            "url": {"type": "string", "description": "An http or https page to fetch"},
            "text": {"type": "string", "description": "Text to add (needs a title)"},
            "title": {
                "type": "string",
                "maxLength": MAX_TITLE_CHARS,
                "description": "Title; for a file or page, defaults to its own title or name",
            },
        },
        "required": ["taxonomy_id"],
    }

    def __init__(
        self,
        sources: SourceService,
        extraction: SourceExtractionService,
        allowed_roots: Sequence[str],
    ) -> None:
        super().__init__(sources, extraction)
        self._allowed_roots = list(allowed_roots)

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = required_str(args, "taxonomy_id")
        dataset = optional_str(args, "dataset")
        title = optional_str(args, "title")
        if title is not None and len(title) > MAX_TITLE_CHARS:
            raise ToolArgumentError(f"'title' must be at most {MAX_TITLE_CHARS} characters")
        given = {k: args.get(k) for k in ("path", "url", "text") if args.get(k) not in (None, "")}
        if len(given) != 1:
            raise ToolArgumentError("pass exactly one of 'path', 'url' or 'text'")
        if "text" in given:
            text = given["text"]
            if not isinstance(text, str):
                raise ToolArgumentError("'text' must be a string")
            source = self._sources.add_text(taxonomy_id, title or "", text, dataset)
        elif "url" in given:
            url = required_str(args, "url")
            source = self._sources.add_url(taxonomy_id, url, dataset, title)
            _fetch_in_background(self._sources, source.id)
        else:
            path, data = read_allowed_file(
                required_str(args, "path"), self._allowed_roots, self._sources.max_bytes
            )
            source = self._sources.add_file(
                taxonomy_id, str(path), data, dataset=dataset, title=title
            )
        payload, _ = self._payload(source)
        return ToolOutcome(content=dumps(payload), summary=_summary(source))


def _fetch_in_background(sources: SourceService, source_id: str) -> None:
    """
    Fetch a web page source off the call, so the tool returns at once. `fetch`
    never leaves it fetching; a fetch the app's exit interrupts is failed at
    the next start.
    """
    threading.Thread(
        target=sources.fetch, args=(source_id,), name=f"fetch-source-{source_id}", daemon=True
    ).start()


def _summary(source: Source) -> str:
    if source.status is SourceStatus.FAILED:
        return f"Source “{source.title}” failed: {source.failure.value if source.failure else ''}"
    return f"Source “{source.title}” {source.status.value}"


class ListSourcesTool(_SourceTool):
    """A page of a taxonomy's sources."""

    name = "list_sources"
    description = (
        "List a taxonomy's sources (one dataset's when named), newest first, without removed"
        " ones and without their text: each with its status, pages, chars and"
        " last_extraction (the runs of its most recent extract_source, with their status,"
        " progress and proposal_id)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "Taxonomy"},
            "dataset": {"type": "string", "description": "Only this dataset (identifier or id)"},
            "offset": {"type": "integer", "minimum": 0, "description": "Sources to skip"},
        },
        "required": ["taxonomy_id"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = required_str(args, "taxonomy_id")
        dataset = optional_str(args, "dataset")
        offset = int_arg(args, "offset", 0, 0, 1_000_000)
        page, total = self._sources.list_sources(taxonomy_id, dataset, DEFAULT_LIMIT, offset)
        last = self._extraction.last_extractions([s.id for s in page]) if page else {}
        payload = {
            "items": [source_payload(s, last.get(s.id)) for s in page],
            "total": total,
            "offset": offset,
        }
        content, items = _capped(
            payload,
            "items",
            lambda kept: f"pass offset {offset + kept} for the rest",
            total=total,
            offset=offset,
        )
        shown = {item["id"] for item in items}
        refs = [r for s in page if s.id in shown for r in _proposal_refs(last.get(s.id))]
        return ToolOutcome(
            content=content,
            summary=f"{len(page)} of {total} sources",
            entities=tuple(refs),
        )


class GetSourceTool(_SourceTool):
    """One source's status and last extraction."""

    name = "get_source"
    description = (
        "Get a source without its text: its status (fetching, ready, failed with failure"
        " and failure_detail), kind, title, pages, chars, and last_extraction (the runs of"
        " its most recent extract_source, with their status, progress and proposal_id)."
        " Poll it after add_source with a url until the status is no longer fetching."
        " A removed source still answers, with removed_at set."
    )
    input_schema = {
        "type": "object",
        "properties": {"source_id": {"type": "string", "description": "Source id"}},
        "required": ["source_id"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        source = self._sources.get(required_str(args, "source_id"))
        payload, refs = self._payload(source)
        return ToolOutcome(content=dumps(payload), summary=_summary(source), entities=tuple(refs))


class ExtractSourceTool(_SourceTool):
    """Start extracting a ready source into proposals."""

    name = "extract_source"
    description = (
        "Extract a ready source into change proposals, in the background, and return the"
        " runs at once: an individual_extraction run that reads the source chunk by chunk"
        " (items_done of items_total are chunks; get_run also gives the stage a run is"
        " in when its implementation reports one) and proposes individuals and their"
        " relationships, each with the passage it came from and any near matches to"
        " existing individuals; with schema true, a schema_extraction run over the same"
        " text too, proposing classes and relationship types. Each run ends in its own"
        " proposal. Poll get_run with each run_id until it has a proposal_id (or failed, or"
        " completed without one: its no_proposal_reason says why), then read the proposal"
        " with get_proposal. " + _REVIEW + " dataset defaults to the"
        " source's; pages selects pages, such as '12-30' or '1-3, 7' (all by default);"
        f" configuration names an individual-extraction configuration ({DEFAULT_CONFIGURATION}"
        " by default). Warranty, safety, legal and contact sections and copies in other"
        " languages are skipped unless skip_boilerplate is false; get_run's"
        " skipped_sections_by_reason counts them. Extracting again supersedes the source's"
        " earlier proposal."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "source_id": {"type": "string", "description": "A ready source"},
            "dataset": {
                "type": "string",
                "description": (
                    "Dataset of the source's taxonomy (identifier or id); the"
                    " source's by default"
                ),
            },
            "configuration": {
                "type": "string",
                "description": f"Individual-extraction configuration ({DEFAULT_CONFIGURATION})",
            },
            "pages": {"type": "string", "description": "Pages, e.g. '12-30' or '1-3, 7'"},
            "schema": {
                "type": "boolean",
                "description": "Also propose schema changes (classes, relationship types)",
            },
            "skip_boilerplate": {
                "type": "boolean",
                "description": (
                    "Skip warranty, safety, legal and contact sections and copies in other"
                    " languages (true by default)"
                ),
            },
        },
        "required": ["source_id"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        source_id = required_str(args, "source_id")
        schema = args.get("schema", False)
        if not isinstance(schema, bool):
            raise ToolArgumentError("'schema' must be true or false")
        skip_boilerplate = args.get("skip_boilerplate", True)
        if not isinstance(skip_boilerplate, bool):
            raise ToolArgumentError("'skip_boilerplate' must be true or false")
        dataset = optional_str(args, "dataset") or self._sources.get(source_id).dataset_id
        runs = self._extraction.extract(
            source_id,
            dataset,
            configuration_ref=optional_str(args, "configuration"),
            pages=optional_str(args, "pages"),
            schema=schema,
            requested_via=RequestedVia.MCP,
            skip_boilerplate=skip_boilerplate,
        )
        payload = {
            "source_id": source_id,
            "runs": [
                {"run_id": run.id, "pipeline": run.pipeline_type.value, "status": run.status.value}
                for run in runs
            ],
            "next": (
                "Poll get_run with each run_id until it has a proposal_id, then read it with"
                " get_proposal. A run that completes with none proposed nothing; its"
                " no_proposal_reason says why. " + _REVIEW
            ),
        }
        return ToolOutcome(
            content=dumps(payload),
            summary=f"Started {', '.join(r.pipeline_type.value for r in runs)}",
        )


def build_source_tools(
    sources: SourceService,
    extraction: SourceExtractionService,
    allowed_roots: Sequence[str],
) -> list[ToolBase]:
    """
    The source tools, MCP only: add, list and get sources, and extract one.

    Args:
        sources: Adds and reads sources
        extraction: Starts extraction runs and reports each source's last one
        allowed_roots: Folders add_source may read a path from (config.json
            sources.allowed_roots); none refuses every path
    """
    return [
        AddSourceTool(sources, extraction, allowed_roots),
        ListSourcesTool(sources, extraction),
        GetSourceTool(sources, extraction),
        ExtractSourceTool(sources, extraction),
    ]
