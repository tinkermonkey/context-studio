"""Integration tests for the claim tools over MCP (#1518), on real SQLite."""

import json

import pytest

from adapters.chat.claim_tools import build_claim_tools
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from domain.versioning.claims import ClaimService
from tests.integration.chat.conftest import OPERATION_ID, TAXONOMY_ID
from tests.integration.mcp.test_mcp_server import mcp_client, result_of


@pytest.fixture
def claim_tools(dr_workspace):
    service = ClaimService(
        SQLiteClaimRepository(dr_workspace.session_factory), dr_workspace.repository
    )
    return build_claim_tools(service)


async def call(client, name, arguments):
    result = await result_of(client, "tools/call", {"name": name, "arguments": arguments})
    return result, result["content"][0]["text"]


async def test_a_client_submits_claims_and_lists_them(dr_workspace, claim_tools):
    async with mcp_client(dr_workspace, write_tools=claim_tools) as client:
        listed = await result_of(client, "tools/list")
        assert {"submit_claims", "list_claims"} <= {t["name"] for t in listed["tools"]}

        result, text = await call(
            client,
            "submit_claims",
            {
                "taxonomy_id": TAXONOMY_ID,
                "claims": [
                    {
                        "key": "api.operation#1",
                        "text": "operation overlaps endpoint",
                        "note_ref": "api.operation",
                        "note_source": "maintainer",
                        "subject_id": OPERATION_ID,
                        "affected_ids": [OPERATION_ID, "api.endpoint"],
                    }
                ],
            },
        )
        assert result["isError"] is False
        stored = json.loads(text)["claims"][0]
        assert stored["affected_ids"] == [OPERATION_ID]
        assert stored["unresolved_refs"] == ["api.endpoint"]

        result, text = await call(
            client, "list_claims", {"taxonomy_id": TAXONOMY_ID, "triaged": False}
        )
        payload = json.loads(text.split("\n\nPages in Context Studio:\n")[0])
        assert payload["total"] == 1
        assert payload["claims"][0]["key"] == "api.operation#1"
        assert payload["claims"][0]["note_source"] == "maintainer"


async def test_bad_claims_are_reported_as_errors(dr_workspace, claim_tools):
    async with mcp_client(dr_workspace, write_tools=claim_tools) as client:
        for arguments, message in (
            ({"taxonomy_id": TAXONOMY_ID, "claims": []}, "non-empty"),
            ({"taxonomy_id": TAXONOMY_ID, "claims": [{"key": "k"}]}, "text"),
            (
                {
                    "taxonomy_id": TAXONOMY_ID,
                    "claims": [{"key": "k", "text": "t", "note_ref": "n", "note_source": "bot"}],
                },
                "'bot' is not one of",
            ),
            (
                {
                    "taxonomy_id": "missing",
                    "claims": [
                        {"key": "k", "text": "t", "note_ref": "n", "note_source": "reviewer"}
                    ],
                },
                "missing",
            ),
        ):
            result, text = await call(client, "submit_claims", arguments)
            assert result["isError"] is True, text
            assert message in text

        result, text = await call(client, "list_claims", {"taxonomy_id": "missing"})
        assert result["isError"] is True
