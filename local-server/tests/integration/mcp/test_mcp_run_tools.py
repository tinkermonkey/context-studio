"""
Integration tests for the run tools over MCP (#1409): run_refinement starts a
long no-op pipeline run in the background and returns its id at once, the
server keeps answering other calls while it runs, and get_run reports its
progress and the proposal it produced.
"""

import asyncio
import json
import time

import pytest

from adapters.chat.run_tools import build_run_tools
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from domain.pipelines.individual_extraction.bootstrap import register_individual_extraction
from domain.pipelines.requested_via import RequestedVia
from tests.integration.chat.conftest import OPERATION_ID, TAXONOMY_ID
from tests.integration.mcp.test_mcp_server import mcp_client, result_of
from tests.integration.pipelines.test_background_runs import make_executor

LINKS = "\n\nPages in Context Studio:\n"


@pytest.fixture
def run_setup(dr_workspace):
    executor = make_executor(dr_workspace.session_factory)
    # The tool offers the pipelines that have an implementation registered
    register_individual_extraction(executor._implementations, executor._configurations)
    runs = PipelineRepository(dr_workspace.session_factory)
    executor.start()
    yield executor, runs, build_run_tools(executor, runs, dr_workspace.ontology, RequestedVia.MCP)
    executor.stop()


async def call(client, name, arguments):
    result = await result_of(client, "tools/call", {"name": name, "arguments": arguments})
    text = result["content"][0]["text"]
    return result, text


async def get_run(client, run_id):
    _, text = await call(client, "get_run", {"run_id": run_id})
    return json.loads(text.split(LINKS)[0])


async def wait_for_run(client, run_id, condition, timeout=20.0):
    """Poll get_run until condition(run) holds; fail only after a generous deadline."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = await get_run(client, run_id)
        if condition(run):
            return run
        await asyncio.sleep(0.01)
    raise AssertionError(f"run {run_id} never reached the expected state: {run}")


async def test_long_noop_run_started_over_mcp_finishes_in_background(dr_workspace, run_setup):
    _, runs, tools = run_setup
    async with mcp_client(dr_workspace, write_tools=tools) as client:
        result, text = await call(
            client,
            "run_refinement",
            {
                "taxonomy_id": TAXONOMY_ID,
                "pipeline": "no_op",
                "scope": {"scheme": "api"},
                "options": {"items": 200, "item_seconds": 0.01},
            },
        )
        # The call returns the run id before the run has done anything
        assert result["isError"] is False
        started = json.loads(text)
        assert started["status"] == "pending"
        assert started["items_done"] is None
        run_id = started["run_id"]

        # The server keeps answering while the run executes
        midway = await wait_for_run(client, run_id, lambda r: r["items_done"])
        assert midway["status"] == "running"
        assert midway["items_total"] == 200
        assert midway["items_done"] < midway["items_total"]
        entity, _ = await call(client, "get_entity", {"id": OPERATION_ID})
        assert entity["isError"] is False

        finished = await wait_for_run(client, run_id, lambda r: r["status"] != "running")
        assert finished["status"] == "completed"
        assert (finished["items_done"], finished["items_total"]) == (200, 200)
        assert finished["proposal_id"] is None
        echo = runs.get(run_id).output_summary["input_echo"]
        assert echo["taxonomy_id"] == TAXONOMY_ID
        assert echo["scope"] == {"scheme": "api"}


async def test_get_run_links_the_proposal_the_run_produced(dr_workspace, run_setup):
    _, runs, tools = run_setup
    async with mcp_client(dr_workspace, write_tools=tools) as client:
        _, text = await call(
            client, "run_refinement", {"taxonomy_id": TAXONOMY_ID, "pipeline": "no_op"}
        )
        run_id = json.loads(text)["run_id"]
        runs.set_proposal_id(run_id, "11111111-2222-3333-4444-555555555555")

        _, text = await call(client, "get_run", {"run_id": run_id})

        payload, links = text.split(LINKS)
        assert json.loads(payload)["proposal_id"] == "11111111-2222-3333-4444-555555555555"
        assert "11111111-2222-3333-4444-555555555555" in links


async def test_get_run_says_why_a_finished_run_proposed_nothing(dr_workspace, run_setup):
    _, runs, tools = run_setup
    async with mcp_client(dr_workspace, write_tools=tools) as client:
        _, text = await call(
            client, "run_refinement", {"taxonomy_id": TAXONOMY_ID, "pipeline": "no_op"}
        )
        run_id = json.loads(text)["run_id"]
        finished = await wait_for_run(client, run_id, lambda r: r["status"] == "completed")
        assert (finished["no_proposal_reason"], finished["skipped_by_reason"]) == (None, {})
        reason = "None of the 3 candidates made an operation (missing_class 3)."
        runs.update_summaries(
            run_id=run_id,
            output_summary={
                "proposal_id": None,
                "no_proposal_reason": reason,
                "skipped_by_reason": {"missing_class": 3},
            },
        )

        result, text = await call(client, "get_run", {"run_id": run_id})

        payload = json.loads(text)
        assert payload["proposal_id"] is None
        assert payload["no_proposal_reason"] == reason
        assert payload["skipped_by_reason"] == {"missing_class": 3}
        tools_list = await result_of(client, "tools/list", {})
        [get_run_tool] = [t for t in tools_list["tools"] if t["name"] == "get_run"]
        assert "no_proposal_reason" in get_run_tool["description"]


async def test_run_tools_report_bad_arguments_as_errors(dr_workspace, run_setup):
    _, _, tools = run_setup
    async with mcp_client(dr_workspace, write_tools=tools) as client:
        for arguments, message in (
            ({"taxonomy_id": "missing", "pipeline": "no_op"}, "No taxonomy found"),
            ({"taxonomy_id": TAXONOMY_ID, "pipeline": "nope"}, "'nope' is not one of"),
            ({"taxonomy_id": TAXONOMY_ID, "pipeline": "no_op", "options": [1]}, "object"),
            (
                {
                    "taxonomy_id": TAXONOMY_ID,
                    "pipeline": "no_op",
                    "options": {"configuration_ref": "missing"},
                },
                "'missing' is not a configuration of the 'default' implementation of no_op",
            ),
        ):
            result, text = await call(client, "run_refinement", arguments)
            assert result["isError"] is True
            assert message in text

        result, text = await call(client, "get_run", {"run_id": "no-such-run"})
        assert result["isError"] is True
        assert "No pipeline run found" in text


@pytest.mark.parametrize("requested_via", [RequestedVia.MCP, RequestedVia.CHAT])
def test_run_refinement_records_who_asked_over_any_option(dr_workspace, requested_via):
    """A caller can't claim another entry point through options (#1516)."""
    runs = PipelineRepository(dr_workspace.session_factory)
    executor = make_executor(dr_workspace.session_factory)
    tools = build_run_tools(executor, runs, dr_workspace.ontology, requested_via)
    run_refinement = next(t for t in tools if t.spec.name == "run_refinement")

    outcome = run_refinement.run(
        {"taxonomy_id": TAXONOMY_ID, "pipeline": "no_op", "options": {"requested_via": "mcp-x"}}
    )

    # The executor isn't started, so the run is still pending with its input
    run, input_data = runs.claim_next_pending()
    assert run.id == json.loads(outcome.content)["run_id"]
    assert input_data["requested_via"] == requested_via.value


async def test_run_refinement_refuses_individual_extraction_and_still_runs_others(
    dr_workspace, run_setup
):
    """Clients extract a document with add_source and extract_source instead (#1451)."""
    _, runs, tools = run_setup
    async with mcp_client(dr_workspace, write_tools=tools) as client:
        result, text = await call(
            client,
            "run_refinement",
            {
                "taxonomy_id": TAXONOMY_ID,
                "pipeline": "individual_extraction",
                "options": {"text": "Admin Health realizes Health Monitoring."},
            },
        )
        assert result["isError"] is True
        assert "can't start individual_extraction" in text
        assert "extract_source" in text
        assert runs.list() == []  # no run was started

        _, text = await call(
            client, "run_refinement", {"taxonomy_id": TAXONOMY_ID, "pipeline": "no_op"}
        )
        run_id = json.loads(text)["run_id"]
        finished = await wait_for_run(client, run_id, lambda r: r["status"] == "completed")
        assert finished["pipeline"] == "no_op"
