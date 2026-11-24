"""
Route tests for #1624 over real SQLite and the real revert: a proposer amends
an open proposal in place, withdraws it (what it applied rolled back), and
supersedes it; proposals show their links both ways.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json  # noqa: E402

import pytest  # noqa: E402

from adapters.chat.proposal_tools import AmendProposalTool, WithdrawProposalTool  # noqa: E402
from domain.ontology.exceptions import EntityNotFoundError  # noqa: E402
from domain.versioning.proposals import ProposalSource  # noqa: E402
from tests.integration.routes.test_approval_policy_routes import (  # noqa: E402, F401 - fixtures
    client,
    house,
    ontology,
    session_factory,
)


def _propose(client, house, *operations, **extra):
    body = {
        "taxonomy_id": house["taxonomy"],
        "title": "Attic wording",
        "source": "mcp",
        "operations": list(operations),
        **extra,
    }
    response = client.post("/api/proposals", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _describe(seq, target, text):
    return {
        "seq": seq,
        "op": "update",
        "kind": "individual",
        "target_id": target,
        "fields": {"description": text},
    }


def _create(seq, house, title):
    return {
        "seq": seq,
        "op": "create",
        "kind": "individual",
        "fields": {"class_ids": [house["place"]], "title": title},
    }


class TestAmend:
    def test_a_replacement_keeps_its_id_and_what_it_replaced(self, client, house):
        proposal = _propose(client, house, _describe(1, house["attic"], "Dusty"))
        op_id = proposal["operations"][0]["id"]

        response = client.post(
            f"/api/proposals/{proposal['id']}/amend",
            json={"replace": [_describe(1, house["attic"], "Dusty, under the roof")]},
        )

        assert response.status_code == 200, response.text
        (operation,) = response.json()["operations"]
        assert operation["id"] == op_id
        assert operation["fields"] == {"description": "Dusty, under the roof"}
        assert operation["amended_at"] is not None
        assert [a["fields"] for a in operation["amendments"]] == [{"description": "Dusty"}]
        stored = client.get(f"/api/proposals/{proposal['id']}").json()
        assert stored["operations"][0]["amendments"] == operation["amendments"]

    def test_a_dry_run_changes_nothing(self, client, house):
        proposal = _propose(client, house, _describe(1, house["attic"], "Dusty"))

        preview = client.post(
            f"/api/proposals/{proposal['id']}/amend",
            params={"dry_run": "true"},
            json={"add": [_create(2, house, "Cellar")]},
        ).json()

        assert len(preview["operations"]) == 2
        assert len(client.get(f"/api/proposals/{proposal['id']}").json()["operations"]) == 1

    def test_errors_are_422_by_seq_and_a_closed_proposal_is_409(self, client, house):
        proposal = _propose(client, house, _describe(1, house["attic"], "Dusty"))

        invalid = client.post(f"/api/proposals/{proposal['id']}/amend", json={"remove": [7]}).json()
        client.post(f"/api/proposals/{proposal['id']}/withdraw", json={})
        closed = client.post(f"/api/proposals/{proposal['id']}/amend", json={"remove": [1]})

        assert invalid["detail"]["errors"] == [
            {"seq": 7, "code": "unknown_seq", "message": "The proposal has no seq 7"}
        ]
        assert closed.status_code == 409


class TestWithdraw:
    def test_what_it_applied_is_rolled_back_and_it_ends_withdrawn(self, client, house, ontology):
        proposal = _propose(
            client, house, _create(1, house, "Cellar"), _describe(2, house["attic"], "Dusty")
        )
        create = proposal["operations"][0]
        applied = client.post(
            f"/api/proposals/{proposal['id']}/apply", json={"operation_ids": [create["id"]]}
        ).json()
        cellar = applied["operations"][0]["result_entity_id"]
        assert ontology.get_individual(cellar) is not None

        response = client.post(f"/api/proposals/{proposal['id']}/withdraw", json={})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "withdrawn"
        assert [o["status"] for o in body["operations"]] == ["applied", "withdrawn"]
        with pytest.raises(EntityNotFoundError):  # rolled back
            ontology.get_individual(cellar)
        assert ontology.get_individual(house["attic"]).description in (None, "")

    def test_superseded_by_shows_on_both_proposals(self, client, house):
        old = _propose(client, house, _describe(1, house["attic"], "Dusty"))
        new = _propose(client, house, _describe(1, house["attic"], "Dusty, under the roof"))

        client.post(
            f"/api/proposals/{old['id']}/withdraw",
            json={"superseded_by": new["id"], "note": "reworded"},
        )

        (old_link,) = client.get(f"/api/proposals/{old['id']}").json()["links"]
        (new_link,) = client.get(f"/api/proposals/{new['id']}").json()["links"]
        assert (old_link["kind"], old_link["proposal_id"], old_link["status"]) == (
            "superseded_by",
            new["id"],
            "open",
        )
        assert (new_link["kind"], new_link["proposal_id"], new_link["status"]) == (
            "supersedes",
            old["id"],
            "withdrawn",
        )
        assert old_link["note"] == "reworded"

    def test_propose_with_supersedes_withdraws_and_links_in_one_call(self, client, house):
        old = _propose(client, house, _describe(1, house["attic"], "Dusty"))

        new = _propose(
            client,
            house,
            _describe(1, house["attic"], "Dusty, under the roof"),
            supersedes=[old["id"]],
        )

        assert client.get(f"/api/proposals/{old['id']}").json()["status"] == "withdrawn"
        assert [(link["kind"], link["proposal_id"]) for link in new["links"]] == [
            ("supersedes", old["id"])
        ]
        listed = client.get("/api/proposals", params={"status": "withdrawn"}).json()
        assert [p["id"] for p in listed["items"]] == [old["id"]]


class TestMcpTools:
    """amend_proposal and withdraw_proposal, as an MCP client calls them."""

    def test_a_replace_item_gives_only_what_changes(self, client, house):
        proposal = _propose(client, house, _describe(1, house["attic"], "Dusty"))
        tool = AmendProposalTool(client.app.state.proposal_service, ProposalSource.MCP)

        outcome = tool.run(
            {"id": proposal["id"], "replace": [{"seq": 1, "fields": {"description": "Damp"}}]}
        )

        assert not outcome.is_error, outcome.content
        stored = client.get(f"/api/proposals/{proposal['id']}").json()["operations"][0]
        assert (stored["op"], stored["target_id"]) == ("update", house["attic"])
        assert stored["fields"] == {"description": "Damp"}
        assert stored["amendments"][0]["fields"] == {"description": "Dusty"}

    def test_a_refused_amendment_lists_its_problems(self, client, house):
        proposal = _propose(client, house, _describe(1, house["attic"], "Dusty"))
        tool = AmendProposalTool(client.app.state.proposal_service, ProposalSource.MCP)

        outcome = tool.run({"id": proposal["id"], "remove": [5]})

        payload = json.loads(outcome.content)
        assert payload["amended"] is False
        assert payload["errors"][0]["code"] == "unknown_seq"

    def test_withdraw_with_superseded_by(self, client, house):
        old = _propose(client, house, _describe(1, house["attic"], "Dusty"))
        new = _propose(client, house, _describe(1, house["attic"], "Damp"))
        tool = WithdrawProposalTool(client.app.state.proposal_service, ProposalSource.MCP)

        outcome = tool.run({"id": old["id"], "superseded_by": new["id"]})
        again = tool.run({"id": old["id"]})

        assert json.loads(outcome.content)["status"] == "withdrawn"
        assert again.is_error and "only an open" in again.content
