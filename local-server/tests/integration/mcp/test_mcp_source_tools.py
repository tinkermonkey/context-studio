# ruff: noqa: F811 - tests take the fixtures imported below by name
"""
Integration tests for the source tools over MCP (#1451): a client adds a source
by text, path or URL, lists and reads it, and extracts it into a proposal that
waits in Context Studio's review queue.

Real SQLite, the real readers, the background run executor and the real
orchestrators, with a fake extraction port, a fake LLM and a fake page fetcher
(no model or network calls).
"""

import asyncio
import json
import os
import time
from types import SimpleNamespace

import pytest

from adapters.chat import source_tools
from adapters.chat.proposal_tools import build_proposal_tools
from adapters.chat.run_tools import build_run_tools
from adapters.chat.source_tools import build_source_tools
from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.source_repo import SQLiteSourceRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from adapters.sources.file_store import LocalSourceFileStore
from adapters.sources.readers import source_readers
from domain.extraction.exceptions import SourceNotReadyError
from domain.extraction.sources import SourceService
from domain.graph.services import GraphAnalysisService
from domain.ontology.exceptions import DatasetRequiredError, EntityNotFoundError
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.individual_extraction.bootstrap import register_individual_extraction
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.requested_via import RequestedVia
from domain.pipelines.schema_extraction.bootstrap import register_schema_extraction
from domain.pipelines.source_extraction import SourceExtractionService
from domain.versioning.proposals import ProposalSource
from tests.fakes.fake_source_repository import FakePageFetcher
from tests.integration.mcp.test_mcp_server import mcp_client, result_of
from tests.integration.sources.pdfs import text_pdf
from tests.integration.sources.test_source_extraction import (  # noqa: F401 - fixtures
    PAGE_1,
    PAGE_2,
    FakeExtraction,
    factory,
    house,
    parts,
)
from tests.unit.domain.pipelines.test_schema_extraction_orchestrator import _MockLLM

LINKS = "\n\nPages in Context Studio:\n"
TEXT = "The WRF555SDFZ is a Microservice.\n\nThe WRF555SDFZ is made by Acme."
MAX_BYTES = 20_000


@pytest.fixture()
def roots(tmp_path):
    """An allowed folder with a Markdown file, and a folder outside it."""
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (allowed / "notes.md").write_text("# Fridge notes\n\n" + TEXT)
    (outside / "secret.md").write_text("# Secret\n\nNot for clients.")
    return SimpleNamespace(allowed=allowed, outside=outside)


@pytest.fixture()
def setup(tmp_path, factory, parts, house, roots):
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_individual_extraction(implementations, configurations)
    register_schema_extraction(implementations, configurations)
    runs = PipelineRepository(factory)
    executor = BackgroundRunExecutor(
        runs=runs,
        batches=BatchRepository(factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=_MockLLM(),
        app_state=SimpleNamespace(
            extraction_service=FakeExtraction(house),
            ontology_repo=parts.repo,
            proposal_service=parts.proposals,
        ),
        poll_seconds=0.05,
    )
    fetcher = FakePageFetcher()
    sources_repo = SQLiteSourceRepository(factory)
    sources = SourceService(
        sources=sources_repo,
        ontology_repo=parts.repo,
        readers=source_readers(),
        fetcher=fetcher,
        files=LocalSourceFileStore(tmp_path / "sources"),
        max_bytes=MAX_BYTES,
    )
    extraction = SourceExtractionService(
        sources=sources_repo,
        ontology_repo=parts.repo,
        configurations=configurations,
        submitter=executor,
        runs=runs,
        proposals=parts.proposals_repo,
    )
    workspace = SimpleNamespace(
        ontology=parts.ontology,
        repository=parts.repo,
        graph=GraphAnalysisService(
            repository=parts.repo,
            graph_engine=NetworkXGraphEngine(),
            query_engine=RDFLibQueryEngine(),
        ),
    )

    def tools(allowed_roots=(str(roots.allowed),)):
        return [
            *build_source_tools(sources, extraction, allowed_roots),
            *build_run_tools(executor, runs, parts.ontology, RequestedVia.MCP),
            *build_proposal_tools(parts.proposals, ProposalSource.MCP),
        ]

    yield SimpleNamespace(
        workspace=workspace,
        tools=tools,
        executor=executor,
        runs=runs,
        fetcher=fetcher,
        sources=sources,
        extraction=extraction,
    )
    executor.stop()


async def call(client, name, arguments):
    """A tool call's isError flag and its JSON payload (page links stripped)."""
    result = await result_of(client, "tools/call", {"name": name, "arguments": arguments})
    text = result["content"][0]["text"]
    try:
        payload = json.loads(text.split(LINKS)[0])
    except json.JSONDecodeError:  # the MCP server's own input validation answers in prose
        payload = {"error": text}
    return result["isError"], payload, text


async def wait_for(client, name, arguments, condition, timeout=20.0):
    """Poll a tool until condition(payload) holds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, payload, _ = await call(client, name, arguments)
        if condition(payload):
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError(f"{name} never reached the expected state: {payload}")


def add_text(house, **extra):
    return {
        "taxonomy_id": house["taxonomy"],
        "dataset": "home",
        "title": "Fridge",
        "text": TEXT,
        **extra,
    }


async def test_the_tools_are_listed_with_their_schemas(setup):
    async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
        result = await result_of(client, "tools/list")

    by_name = {t["name"]: t for t in result["tools"]}
    for name in ("add_source", "list_sources", "get_source", "extract_source"):
        assert name in by_name
    assert "allowed_roots" in by_name["add_source"]["description"]
    assert "review queue" in by_name["extract_source"]["description"]
    assert by_name["list_proposals"]["inputSchema"]["properties"]["source"]["enum"]


class TestAddSource:
    async def test_text_is_read_at_once(self, setup, house):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, source, _ = await call(client, "add_source", add_text(house))

        assert is_error is False
        assert source["status"] == "ready"
        assert (source["kind"], source["title"], source["pages"]) == ("text", "Fridge", 1)
        assert source["chars"] == len(TEXT)
        assert source["dataset_id"] == house["home"]
        assert source["last_extraction"] is None
        assert "text" not in source and "page_starts" not in source

    async def test_a_file_inside_an_allowed_root_is_read(self, setup, house, roots):
        path = roots.allowed / "notes.md"
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, source, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "path": str(path)},
            )

        assert source["status"] == "ready"
        assert source["kind"] == "markdown"
        assert source["title"] == "Fridge notes"
        assert source["origin"] == str(path.resolve())

    async def test_a_pdf_file_keeps_its_pages(self, setup, house, roots):
        path = roots.allowed / "guide.pdf"
        path.write_bytes(text_pdf([PAGE_1, PAGE_2]))
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, source, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "path": str(path)},
            )

        assert (source["kind"], source["status"], source["pages"]) == ("pdf", "ready", 2)

    async def test_a_file_too_large_is_stored_as_failed(self, setup, house, roots):
        path = roots.allowed / "huge.txt"
        path.write_text("x" * (MAX_BYTES + 5000))
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, source, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "path": str(path)},
            )

        assert (source["status"], source["failure"]) == ("failed", "too_large")
        assert source["bytes"] == MAX_BYTES + 1  # read no further than one byte past

    @pytest.mark.parametrize(
        "make_path, message",
        [
            (lambda r: r.outside / "secret.md", "is not inside a folder clients may read from"),
            (lambda r: r.allowed / ".." / "outside" / "secret.md", "is not inside a folder"),
            (lambda r: r.allowed / "missing.md", "is not a regular file"),
            (lambda r: r.allowed, "is not a regular file"),
            (lambda r: "allowed/notes.md", "Give an absolute path"),
        ],
    )
    async def test_paths_outside_the_roots_are_refused(
        self, setup, house, roots, make_path, message
    ):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, payload, _ = await call(
                client,
                "add_source",
                {
                    "taxonomy_id": house["taxonomy"],
                    "dataset": "home",
                    "path": str(make_path(roots)),
                },
            )
            _, listed, _ = await call(client, "list_sources", {"taxonomy_id": house["taxonomy"]})

        assert is_error is True
        assert message in payload["error"]
        assert listed["total"] == 0

    async def test_a_symlink_out_of_a_root_is_refused(self, setup, house, roots):
        link = roots.allowed / "link.md"
        link.symlink_to(roots.outside / "secret.md")
        linked_dir = roots.allowed / "elsewhere"
        linked_dir.symlink_to(roots.outside, target_is_directory=True)
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            for path in (link, linked_dir / "secret.md"):
                is_error, payload, _ = await call(
                    client,
                    "add_source",
                    {"taxonomy_id": house["taxonomy"], "dataset": "home", "path": str(path)},
                )
                assert is_error is True
                assert "is not inside a folder clients may read from" in payload["error"]

    async def test_a_symlink_that_stays_inside_a_root_is_read(self, setup, house, roots):
        link = roots.allowed / "alias.md"
        link.symlink_to(roots.allowed / "notes.md")
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, source, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "path": str(link)},
            )

        assert is_error is False
        assert source["origin"] == str((roots.allowed / "notes.md").resolve())

    async def test_no_allowed_roots_refuses_every_path(self, setup, house, roots):
        async with mcp_client(setup.workspace, write_tools=setup.tools(allowed_roots=())) as client:
            is_error, payload, _ = await call(
                client,
                "add_source",
                {
                    "taxonomy_id": house["taxonomy"],
                    "dataset": "home",
                    "path": str(roots.allowed / "notes.md"),
                },
            )

        assert is_error is True
        assert "turned off" in payload["error"]
        assert "sources.allowed_roots" in payload["error"]

    @pytest.mark.parametrize("root", ["", ".", "relative/folder"])
    async def test_a_relative_root_never_means_the_working_directory(self, setup, house, root):
        async with mcp_client(setup.workspace, write_tools=setup.tools((root,))) as client:
            is_error, payload, _ = await call(
                client,
                "add_source",
                {
                    "taxonomy_id": house["taxonomy"],
                    "dataset": "home",
                    "path": os.path.abspath("config.py"),
                },
            )

        assert is_error is True
        assert "must list absolute folders" in payload["error"]

    async def add_path(self, setup, house, path):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, payload, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "path": str(path)},
            )
            _, listed, _ = await call(client, "list_sources", {"taxonomy_id": house["taxonomy"]})
        assert listed["total"] == 0  # nothing stored
        return is_error, payload

    async def test_a_file_swapped_for_a_symlink_after_the_check_is_refused(
        self, setup, house, roots, monkeypatch
    ):
        checked = source_tools.readable_path

        def check_then_swap(raw, allowed_roots):
            resolved = checked(raw, allowed_roots)
            resolved.unlink()
            resolved.symlink_to(roots.outside / "secret.md")
            return resolved

        monkeypatch.setattr(source_tools, "readable_path", check_then_swap)

        is_error, payload = await self.add_path(setup, house, roots.allowed / "notes.md")

        assert is_error is True
        assert "could not be opened" in payload["error"]

    async def test_a_folder_swapped_for_a_symlink_after_the_check_is_refused(
        self, setup, house, roots, monkeypatch
    ):
        """The last component is a regular file, but the folder above it now points out."""
        inner = roots.allowed / "inner"
        inner.mkdir()
        (inner / "secret.md").write_text("# Inside\n\nFine to read.")
        checked = source_tools.readable_path

        def check_then_swap(raw, allowed_roots):
            resolved = checked(raw, allowed_roots)
            (inner / "secret.md").unlink()
            inner.rmdir()
            inner.symlink_to(roots.outside, target_is_directory=True)
            return resolved

        monkeypatch.setattr(source_tools, "readable_path", check_then_swap)

        is_error, payload = await self.add_path(setup, house, inner / "secret.md")

        assert is_error is True
        assert "is not inside a folder clients may read from" in payload["error"]

    async def test_a_fifo_is_refused_without_blocking(self, setup, house, roots):
        fifo = roots.allowed / "pipe.md"
        os.mkfifo(fifo)

        is_error, payload = await asyncio.wait_for(self.add_path(setup, house, fifo), timeout=10)

        assert is_error is True
        assert "is not a regular file" in payload["error"]

    async def test_a_hard_link_to_an_outside_file_is_refused(self, setup, house, roots):
        link = roots.allowed / "hard.md"
        os.link(roots.outside / "secret.md", link)

        is_error, payload = await self.add_path(setup, house, link)

        assert is_error is True
        assert "has other hard links" in payload["error"]

    async def test_a_title_is_capped(self, setup, house):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, payload, _ = await call(
                client, "add_source", add_text(house, title="t" * 501)
            )
            ok, _, _ = await call(client, "add_source", add_text(house, title="t" * 500))

        assert is_error is True
        # The MCP server checks the schema's maxLength; the tool checks it again
        assert "is too long" in payload["error"] or "500" in payload["error"]
        assert ok is False
        add_source = build_source_tools(setup.sources, setup.extraction, ())[0]
        outcome = add_source._run_safely(add_text(house, title="t" * 501))
        assert outcome.is_error is True
        assert "at most 500 characters" in json.loads(outcome.content)["error"]

    async def test_a_url_is_fetched_after_the_call_returns(self, setup, house):
        url = "https://example.com/fridge"
        page = f"<html><head><title>Fridge page</title></head><body><p>{TEXT}</p></body></html>"
        setup.fetcher.add(url, page.encode())
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, added, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "url": url},
            )
            assert is_error is False
            assert (added["kind"], added["origin"]) == ("web", url)
            assert added["status"] in ("fetching", "ready")

            ready = await wait_for(
                client,
                "get_source",
                {"source_id": added["id"]},
                lambda s: s["status"] != "fetching",
            )

        assert ready["status"] == "ready"
        assert ready["title"] == "Fridge page"
        assert "WRF555SDFZ" in setup.sources.get(added["id"]).text
        assert setup.fetcher.fetched == [url]

    async def test_a_url_that_cannot_be_fetched_fails(self, setup, house):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, added, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "url": "https://x.test/404"},
            )
            failed = await wait_for(
                client,
                "get_source",
                {"source_id": added["id"]},
                lambda s: s["status"] != "fetching",
            )

        assert (failed["status"], failed["failure"]) == ("failed", "fetch_failed")
        assert "404" in failed["failure_detail"]

    @pytest.mark.parametrize(
        "arguments, message",
        [
            ({}, "exactly one of 'path', 'url' or 'text'"),
            ({"text": TEXT, "url": "https://example.com"}, "exactly one of"),
            ({"text": TEXT}, "A text source needs a title"),
            ({"url": "ftp://example.com/x"}, "Only http and https URLs"),
            ({"text": TEXT, "title": "T", "dataset": "garage"}, "Dataset"),
        ],
    )
    async def test_bad_arguments_are_errors(self, setup, house, arguments, message):
        arguments = {"taxonomy_id": house["taxonomy"], "dataset": "home", **arguments}
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, payload, _ = await call(client, "add_source", arguments)

        assert is_error is True
        assert message in payload["error"]

    async def test_a_missing_taxonomy_or_unnamed_dataset_is_an_error(self, setup, house):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            is_error, payload, _ = await call(
                client, "add_source", {"taxonomy_id": "nope", "title": "T", "text": TEXT}
            )
            assert is_error is True
            assert "nope" in payload["error"]

            # House has two datasets, so one must be named
            is_error, payload, _ = await call(
                client, "add_source", {"taxonomy_id": house["taxonomy"], "title": "T", "text": TEXT}
            )
            assert is_error is True
            assert "home" in payload["error"] and "cabin" in payload["error"]


class TestListAndGet:
    async def test_list_pages_newest_first_and_filters_by_dataset(self, setup, house):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            for title in ("First", "Second"):
                await call(client, "add_source", add_text(house, title=title))
            await call(client, "add_source", add_text(house, title="Cabin", dataset="cabin"))

            _, everything, _ = await call(
                client, "list_sources", {"taxonomy_id": house["taxonomy"]}
            )
            _, home, _ = await call(
                client, "list_sources", {"taxonomy_id": house["taxonomy"], "dataset": "home"}
            )
            _, second_page, _ = await call(
                client,
                "list_sources",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "offset": 1},
            )
            is_error, missing, _ = await call(client, "list_sources", {"taxonomy_id": "nope"})

        assert [s["title"] for s in everything["items"]] == ["Cabin", "Second", "First"]
        assert everything["total"] == 3
        assert [s["title"] for s in home["items"]] == ["Second", "First"]
        assert ([s["title"] for s in second_page["items"]], second_page["total"]) == (["First"], 2)
        assert all("text" not in s and "last_extraction" in s for s in everything["items"])
        assert is_error is True and "nope" in missing["error"]

    async def test_get_returns_metadata_and_a_removed_source_still_answers(self, setup, house):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, added, _ = await call(client, "add_source", add_text(house))
            _, got, _ = await call(client, "get_source", {"source_id": added["id"]})
            setup.sources.remove(added["id"])
            _, removed, _ = await call(client, "get_source", {"source_id": added["id"]})
            is_error, missing, _ = await call(client, "get_source", {"source_id": "nope"})

        assert got == added
        assert removed["removed_at"] is not None
        assert is_error is True and "nope" in missing["error"]


class TestExtractSource:
    async def test_extraction_ends_in_a_proposal_for_review(self, setup, parts, house):
        setup.executor.start()
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, source, _ = await call(client, "add_source", add_text(house))

            is_error, started, _ = await call(client, "extract_source", {"source_id": source["id"]})
            assert is_error is False
            [run] = started["runs"]
            assert (run["pipeline"], run["status"]) == ("individual_extraction", "pending")
            assert "get_run" in started["next"] and "get_proposal" in started["next"]
            assert "review queue" in started["next"]

            done = await wait_for(
                client,
                "get_run",
                {"run_id": run["run_id"]},
                lambda r: r["status"] not in ("pending", "running"),
            )
            assert done["status"] == "completed", done["failure_reason"]
            assert done["proposal_id"]

            _, proposal, proposal_text = await call(
                client, "get_proposal", {"id": done["proposal_id"]}
            )
            _, got, got_text = await call(client, "get_source", {"source_id": source["id"]})
            _, listed, _ = await call(
                client, "list_proposals", {"taxonomy_id": house["taxonomy"], "source": "pipeline"}
            )
            _, from_mcp, _ = await call(
                client, "list_proposals", {"taxonomy_id": house["taxonomy"], "source": "mcp"}
            )

        # The source's dataset, as none was named
        assert setup.runs.get(run["run_id"]).input_summary["dataset_id"] == house["home"]

        assert proposal["status"] == "open"
        titles = {o["fields"].get("title") for o in proposal["operations"]}
        assert {"Whirlpool WRF555SDFZ", "Acme"} <= titles
        assert all(o["status"] == "pending" for o in proposal["operations"])
        assert done["proposal_id"] in proposal_text.split(LINKS)[1]

        [last_run] = got["last_extraction"]["runs"]
        assert last_run["proposal_id"] == done["proposal_id"]
        assert last_run["operations"] == len(proposal["operations"])
        assert done["proposal_id"] in got_text.split(LINKS)[1]

        assert [p["id"] for p in listed["items"]] == [done["proposal_id"]]
        assert from_mcp["items"] == []

    async def test_schema_adds_a_schema_run_even_on_a_mirrored_taxonomy(self, setup, parts, house):
        parts.ontology.set_taxonomy_mirrored(house["taxonomy"], True)
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, source, _ = await call(client, "add_source", add_text(house))
            is_error, started, _ = await call(
                client,
                "extract_source",
                {"source_id": source["id"], "schema": True, "dataset": "home"},
            )

        assert is_error is False
        assert [r["pipeline"] for r in started["runs"]] == [
            "individual_extraction",
            "schema_extraction",
        ]
        # The executor isn't started: both runs wait with the caller recorded
        for _ in started["runs"]:
            _, input_data = setup.runs.claim_next_pending()
            assert input_data["requested_via"] == "mcp"

    async def test_errors_are_tool_errors(self, setup, house, roots):
        async with mcp_client(setup.workspace, write_tools=setup.tools()) as client:
            _, ready, _ = await call(client, "add_source", add_text(house))
            empty = roots.allowed / "empty.txt"
            empty.write_text("   ")
            _, failed, _ = await call(
                client,
                "add_source",
                {"taxonomy_id": house["taxonomy"], "dataset": "home", "path": str(empty)},
            )
            assert failed["status"] == "failed"

            for arguments, message in (
                ({"source_id": "nope"}, "nope"),
                ({"source_id": failed["id"]}, "is failed"),
                ({"source_id": ready["id"], "pages": "3"}, "The source has 1 pages"),
                ({"source_id": ready["id"], "pages": "two"}, ""),
                ({"source_id": ready["id"], "dataset": "garage"}, "garage"),
                ({"source_id": ready["id"], "configuration": "nope"}, "'nope' is not"),
                ({"source_id": ready["id"], "schema": "yes"}, "boolean"),
            ):
                is_error, payload, _ = await call(client, "extract_source", arguments)
                assert is_error is True, arguments
                assert message in payload["error"], payload

        assert setup.runs.list() == []


@pytest.mark.parametrize(
    "error, summary",
    [
        (EntityNotFoundError("Source", "s1"), "extract_source: not found"),
        (SourceNotReadyError("s1", "fetching"), "Source not ready"),
        (PipelineInputError("only its client may"), "Extraction not started"),
        (DatasetRequiredError("t1", ["home", "cabin"]), "extract_source: invalid request"),
        (ValueError("bad pages"), "extract_source: invalid request"),
    ],
)
def test_each_service_error_maps_to_a_tool_error(error, summary):
    class Refusing:
        def extract(self, *args, **kwargs):
            raise error

    sources = SimpleNamespace(get=lambda _: SimpleNamespace(dataset_id="d1"))
    extract = build_source_tools(sources, Refusing(), ())[3]

    outcome = extract._run_safely({"source_id": "s1"})

    assert outcome.is_error is True
    assert outcome.summary == summary
    assert str(error) in json.loads(outcome.content)["error"]
