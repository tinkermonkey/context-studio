"""
Route and MCP-tool tests for #1630 over real SQLite: an update gives a long
text field as anchored edits; the edits are stored, applied again to the text
as it is at accept, and an operation whose anchor is gone is stale.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json  # noqa: E402

from adapters.chat.proposal_tools import AmendProposalTool, ProposeChangesTool  # noqa: E402
from domain.versioning.proposals import ProposalSource  # noqa: E402
from tests.integration.routes.test_approval_policy_routes import (  # noqa: E402, F401 - fixtures
    client,
    house,
    ontology,
    session_factory,
)

DESCRIPTION = "Under the roof. Dusty in summer."


def _describe(ontology, house):
    ontology.update_individual(house["attic"], description=DESCRIPTION)


def _edit(house, edits):
    return {
        "seq": 1,
        "op": "update",
        "kind": "individual",
        "target_id": house["attic"],
        "fields": {"description": {"edits": edits}},
    }


def _propose(client, house, *operations):
    body = {
        "taxonomy_id": house["taxonomy"],
        "title": "Attic wording",
        "source": "mcp",
        "operations": list(operations),
    }
    return client.post("/api/proposals", json=body)


def test_post_stores_the_edits_and_the_text_they_make(client, ontology, house):
    _describe(ontology, house)
    edits = [{"replace": "Dusty", "with": "Hot and dusty"}]
    response = _propose(client, house, _edit(house, edits))
    assert response.status_code == 201, response.text
    operation = response.json()["operations"][0]
    assert operation["text_edits"] == {"description": edits}
    assert operation["base"] == {"description": DESCRIPTION}
    assert operation["fields"] == {"description": "Under the roof. Hot and dusty in summer."}

    fetched = client.get(f"/api/proposals/{response.json()['id']}").json()
    assert fetched["operations"][0]["text_edits"] == {"description": edits}


def test_post_refuses_an_anchor_that_is_not_there(client, ontology, house):
    _describe(ontology, house)
    response = _propose(client, house, _edit(house, [{"delete": "In winter."}]))
    assert response.status_code == 422, response.text
    assert "anchor_not_found" in response.text


def test_apply_keeps_a_change_made_since_and_stale_names_a_lost_anchor(client, ontology, house):
    _describe(ontology, house)
    keeps = _propose(client, house, _edit(house, [{"after": "summer.", "insert": " Has a hatch."}]))
    loses = _propose(client, house, _edit(house, [{"replace": "Under the roof.", "with": "Top."}]))
    ontology.update_individual(house["attic"], description="Below the roof. Dusty in summer.")

    stale = client.get(f"/api/proposals/{loses.json()['id']}").json()["operations"][0]
    assert stale["stale"] is True
    fresh = client.get(f"/api/proposals/{keeps.json()['id']}").json()["operations"][0]
    assert fresh["stale"] is False

    applied = client.post(
        f"/api/proposals/{keeps.json()['id']}/apply", json={"operation_ids": [fresh["id"]]}
    )
    assert applied.status_code == 200, applied.text
    assert ontology.get_individual(house["attic"]).description == (
        "Below the roof. Dusty in summer. Has a hatch."
    )
    stored = client.get(f"/api/proposals/{keeps.json()['id']}").json()["operations"][0]
    assert stored["base"] == {"description": "Below the roof. Dusty in summer."}
    assert stored["fields"] == {"description": "Below the roof. Dusty in summer. Has a hatch."}

    # Reverting the applied edit restores the text it was applied to.
    reverted = client.post(f"/api/proposals/{keeps.json()['id']}/revert")
    assert reverted.status_code == 200, reverted.text
    assert ontology.get_individual(house["attic"]).description == (
        "Below the roof. Dusty in summer."
    )


def test_mcp_propose_and_amend_take_edits(client, ontology, house):
    _describe(ontology, house)
    service = client.app.state.proposal_service
    outcome = ProposeChangesTool(service, ProposalSource.MCP).run(
        {
            "taxonomy_id": house["taxonomy"],
            "title": "Attic",
            "operations": [_edit(house, [{"after": "roof.", "insert": " Low ceiling."}])],
        }
    )
    proposal = json.loads(outcome.content)
    assert proposal["stored"] is True, proposal

    # Amending another field keeps the description as its edits, applied to the text now.
    ontology.update_individual(house["attic"], description="Under the roof. Damp.")
    amend = AmendProposalTool(service, ProposalSource.MCP).run(
        {"id": proposal["id"], "replace": [{"seq": 1, "fields": {"title": "Loft"}}]}
    )
    assert json.loads(amend.content).get("stored", True), amend.content
    operation = client.get(f"/api/proposals/{proposal['id']}").json()["operations"][0]
    assert operation["fields"] == {
        "description": "Under the roof. Low ceiling. Damp.",
        "title": "Loft",
    }
    assert operation["text_edits"] == {"description": [{"after": "roof.", "insert": " Low ceiling."}]}
