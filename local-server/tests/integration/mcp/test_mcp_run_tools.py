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
from tests.integration.chat.conftest import OPERATION_ID, TAXONOMY_ID
from tests.integration.mcp.test_mcp_server import mcp_client, result_of
from tests.integration.pipelines.test_background_runs import make_executor

LINKS = "\n\nPages in Context Studio:\n"


@pytest.fixture
def run_setup(dr_workspace):
    executor = make_executor(dr_workspace.session_factory)
    runs = PipelineRepository(dr_workspace.session_factory)
    executor.start()
    yield executor, runs, build_run_tools(executor, runs, dr_workspace.ontology)
    executor.stop()


async def call(client, name, arguments):
    result = await result_of(client, "tools/call", {"name": name, "arguments": arguments})
    text = result["content"][0]["text"]
    return result, text


async def get_run(client, run_id):
    _, text = await call(client, "get_run", {"run_id": run_id})
    return json.loads(text.split(LINKS)[0])


async def test_long_noop_run_started_over_mcp_finishes_in_background(dr_workspace, run_setup):
    _, runs, tools = run_setup
    async with mcp_client(dr_workspace, write_tools=tools) as client:
        started_at = time.monotonic()
        result, text = await call(
            client,
            "run_refinement",
            {
                "taxonomy_id": TAXONOMY_ID,
                "pipeline": "no_op",
                "scope": {"scheme": "api"},
                "options": {"items": 20, "item_seconds": 0.05},
            },
        )
        # The 1-second run is started, not awaited
        assert time.monotonic() - started_at < 0.8
        assert result["isError"] is False
        started = json.loads(text)
        assert started["status"] == "pending"
        run_id = started["run_id"]

        # The server keeps answering while the run executes
        for _ in range(100):
            midway = await get_run(client, run_id)
            if midway["items_done"]:
                break
            await asyncio.sleep(0.02)
        assert midway["status"] == "running"
        assert 0 < midway["items_done"] < 20
        entity, _ = await call(client, "get_entity", {"id": OPERATION_ID})
        assert entity["isError"] is False

        for _ in range(250):
            finished = await get_run(client, run_id)
            if finished["status"] == "completed":
                break
            await asyncio.sleep(0.02)
        assert finished["status"] == "completed"
        assert (finished["items_done"], finished["items_total"]) == (20, 20)
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
                "Configuration not found",
            ),
        ):
            result, text = await call(client, "run_refinement", arguments)
            assert result["isError"] is True
            assert message in text

        result, text = await call(client, "get_run", {"run_id": "no-such-run"})
        assert result["isError"] is True
        assert "No pipeline run found" in text
