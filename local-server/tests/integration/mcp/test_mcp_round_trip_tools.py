"""
Integration tests (#1451): a client does the whole DR round trip over MCP.

submit_reflection_plan proposes a `dr-reflection-plan/1` plan as the import
script does (an invalid one stores nothing); once a reviewer applies it,
get_spec_changes returns the `cs-dr-spec-changes/1` document the export script
writes and get_decisions what GET /api/proposals/{id}/decisions serves, paging
when too large for one result.

Built on the pinned DR spec snapshot and the reflection-plan fixtures of
`tests/integration/scripts/test_dr_reflection_plan.py`, on real SQLite.
"""

import dataclasses
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.chat import interchange_tools
from adapters.chat.interchange_tools import SPEC_CHANGE_LISTS, build_interchange_tools
from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.interchange.dr_reflection_plan import import_reflection_plan, read_plan
from adapters.interchange.dr_spec_changes import spec_changes_for
from adapters.web.proposals_routes import router as proposals_router
from domain.graph.services import GraphAnalysisService
from domain.versioning.gold import DecisionFilter, by_operation
from domain.versioning.proposals import ProposalSource
from tests.integration.mcp.test_mcp_run_tools import LINKS, call
from tests.integration.mcp.test_mcp_server import mcp_client
from tests.integration.scripts import test_dr_reflection_plan as plan_tests
from tests.integration.scripts.test_dr_reflection_plan import PLAN_FILE, apply_all, plan_for

# The pinned-spec database fixtures, shared with the reflection-plan tests.
spec_db = plan_tests.spec_db
parts = plan_tests.parts

# The operation fields a proposal keeps from its plan, compared tool vs script.
_COMPARED = (
    "seq",
    "op",
    "kind",
    "target_id",
    "ref",
    "fields",
    "replacement",
    "rationale",
    "evidence",
    "probability",
    "scope",
    "status",
    "base",
)


def workspace(parts):
    ontology, repo, _ = parts
    graph = GraphAnalysisService(
        repository=repo, graph_engine=NetworkXGraphEngine(), query_engine=RDFLibQueryEngine()
    )
    return SimpleNamespace(ontology=ontology, repository=repo, graph=graph)


def tools(parts, source=ProposalSource.MCP):
    _, repo, proposals = parts
    return build_interchange_tools(proposals, repo, source)


def taxonomy_id(parts):
    return parts[1].get_by_identifier("dr_spec").id


def body(text):
    return json.loads(text.split(LINKS)[0])


def operations(proposal):
    return [
        {k: v for k, v in dataclasses.asdict(o).items() if k in _COMPARED}
        for o in proposal.operations
    ]


async def pages(client, name, proposal_id):
    """Every page of a paged result, following each truncated note's offset."""
    found, offset = [], 0
    while True:
        result, text = await call(client, name, {"proposal_id": proposal_id, "offset": offset})
        assert result["isError"] is False, text
        assert len(text.split(LINKS)[0]) <= interchange_tools.MAX_PROPOSAL_CHARS
        page = body(text)
        found.append(page)
        if "truncated" not in page:
            return found
        offset = int(page["truncated"].rsplit("pass offset ", 1)[1].split()[0])


def merged(found, lists):
    """The pages joined back into one document: each list's entries appended in order."""
    whole = {k: v for k, v in found[0].items() if k not in {"offset", "total", "truncated"}}
    for key in lists:
        whole[key] = [entry for page in found for entry in page[key]]
    return whole


# ------------------------------------------------------------- submit_reflection_plan


async def test_a_submitted_plan_becomes_the_proposal_the_script_makes(parts):
    _, repo, proposals = parts
    plan = plan_for(1, 13, 14, 28)
    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        result, text = await call(
            client, "submit_reflection_plan", {"taxonomy_id": taxonomy_id(parts), "plan": plan}
        )

    assert result["isError"] is False, text
    stored = body(text)
    assert stored["stored"] is True and stored["counts"]["pending"] == 4
    assert stored["id"] in text.split(LINKS)[1]  # the review page link
    submitted = proposals.get(stored["id"])
    scripted = import_reflection_plan(plan_for(1, 13, 14, 28), proposals, repo)

    assert submitted.source is ProposalSource.MCP  # the client submitted it
    assert scripted.source is ProposalSource.PIPELINE
    for name in ("taxonomy_id", "title", "rationale", "source_detail", "source_revision"):
        assert getattr(submitted, name) == getattr(scripted, name), name
    assert operations(submitted) == operations(scripted)


async def test_the_taxonomy_may_be_named_by_identifier_as_a_plan_names_it(parts):
    _, _, proposals = parts
    plan = plan_for(14)
    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        result, text = await call(
            client, "submit_reflection_plan", {"taxonomy_id": plan["taxonomy_id"], "plan": plan}
        )
    assert result["isError"] is False, text
    assert proposals.get(body(text)["id"]).taxonomy_id == taxonomy_id(parts)


async def test_an_invalid_plan_stores_nothing_and_lists_every_problem(parts):
    _, _, proposals = parts
    unresolved = plan_for(1, 14)
    unresolved["operations"][0]["target_id"] = "api.nothing.serves.api.nowhere"
    unresolved["operations"][1]["fields"]["source_spec_node_id"] = "api.nowhere"
    too_long = plan_for(14)
    too_long["title"] = "x" * 501
    wrong_format = {**plan_for(14), "format": "dr-reflection-plan/0"}

    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        found = {}
        for label, plan in (
            ("unresolved", unresolved),
            ("too_long", too_long),
            ("wrong_format", wrong_format),
        ):
            result, text = await call(
                client, "submit_reflection_plan", {"taxonomy_id": taxonomy_id(parts), "plan": plan}
            )
            assert result["isError"] is False  # an answer to act on, as propose_changes gives
            found[label] = body(text)

    assert proposals.count_proposals() == 0
    assert all(f["stored"] is False and f["id"] is None for f in found.values())
    problems = found["unresolved"]["problems"]
    assert len(problems) == 2
    assert problems[0].startswith("seq 1 (delete api.nothing.serves.api.nowhere)")
    assert "api.nowhere" in problems[1]
    assert found["too_long"]["problems"] == [
        {"code": "too_long", "message": "title is 501 characters; at most 500"}
    ]
    assert "dr-reflection-plan/0" in found["wrong_format"]["problems"][0]
    assert "submit_reflection_plan again" in found["unresolved"]["next"]


async def test_a_dry_run_stores_nothing(parts):
    _, _, proposals = parts
    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        result, text = await call(
            client,
            "submit_reflection_plan",
            {"taxonomy_id": taxonomy_id(parts), "plan": plan_for(1, 13, 14, 28), "dry_run": True},
        )

    assert result["isError"] is False, text
    checked = body(text)
    assert checked["stored"] is False and checked["dry_run"] is True
    assert [o["seq"] for o in checked["operations"]] == [1, 13, 14, 28]
    assert "submit_reflection_plan again without dry_run" in checked["next"]
    assert proposals.count_proposals() == 0


async def test_a_plan_is_only_for_the_dr_spec_taxonomy(parts):
    ontology, _, proposals = parts
    other = ontology.create_taxonomy(title="House", identifier="house")
    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        for arguments, message in (
            ({"taxonomy_id": other.id, "plan": plan_for(14)}, "is not it"),
            ({"taxonomy_id": "missing", "plan": plan_for(14)}, "No taxonomy found"),
            ({"taxonomy_id": taxonomy_id(parts), "plan": [plan_for(14)]}, "not of type"),
        ):
            result, text = await call(client, "submit_reflection_plan", arguments)
            assert result["isError"] is True
            assert message in text
    assert proposals.count_proposals() == 0


def test_only_a_mirrored_taxonomys_client_submits_plans_to_it(parts):
    ontology, _, proposals = parts
    ontology.set_taxonomy_mirrored(taxonomy_id(parts), True)
    chat = next(t for t in tools(parts, ProposalSource.CHAT) if t.name == "submit_reflection_plan")

    outcome = chat.run({"taxonomy_id": taxonomy_id(parts), "plan": plan_for(14)})

    assert outcome.is_error is True
    assert "mirrors an external source" in outcome.content
    assert proposals.count_proposals() == 0


# ------------------------------------------------------- get_spec_changes, get_decisions


async def test_an_applied_plan_comes_back_as_the_scripts_and_rests_output(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(1, 13, 14, 28), proposals, repo)
    applied = apply_all(proposals, proposal)
    app = FastAPI()
    app.include_router(proposals_router)
    app.state.proposal_service = proposals
    rest = TestClient(app).get(f"/api/proposals/{proposal.id}/decisions")
    assert rest.status_code == 200
    # As scripts/export_dr_spec_changes.py reads the decisions and builds the document
    recorded = by_operation(
        proposals.list_decisions(DecisionFilter(proposal_id=proposal.id, include_superseded=True))
    )
    exported = spec_changes_for(applied, repo, recorded)

    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        _, spec_text = await call(client, "get_spec_changes", {"proposal_id": proposal.id})
        _, decisions_text = await call(client, "get_decisions", {"proposal_id": proposal.id})

    assert body(spec_text) == json.loads(json.dumps(exported))
    assert len(exported["changes"]) == 4
    assert body(decisions_text) == {"proposal_id": proposal.id, "decisions": rest.json()}
    assert {d["status"] for d in rest.json()} == {"applied"}
    assert proposal.id in spec_text.split(LINKS)[1]


async def test_a_large_document_pages_without_cutting_an_entry(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(read_plan(PLAN_FILE), proposals, repo)
    applied = apply_all(proposals, proposal)
    exported = json.loads(
        json.dumps(spec_changes_for(applied, repo, proposals.decisions_of(proposal.id)))
    )
    assert len(json.dumps(exported)) > interchange_tools.MAX_PROPOSAL_CHARS

    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        found = await pages(client, "get_spec_changes", proposal.id)

    assert len(found) > 1
    assert found[0]["total"] == sum(len(exported[k]) for k in SPEC_CHANGE_LISTS)
    assert merged(found, SPEC_CHANGE_LISTS) == exported


async def test_decisions_page_too(parts, monkeypatch):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(1, 13, 14, 28), proposals, repo)
    monkeypatch.setattr(interchange_tools, "MAX_PROPOSAL_CHARS", 400)

    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        found = await pages(client, "get_decisions", proposal.id)

    assert len(found) > 1
    whole = merged(found, ["decisions"])
    assert [d["seq"] for d in whole["decisions"]] == [1, 13, 14, 28]
    assert {d["status"] for d in whole["decisions"]} == {"pending"}


async def test_reverted_or_unknown_proposals_are_errors(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(14), proposals, repo)
    apply_all(proposals, proposal)
    proposals.revert(proposal.id)

    async with mcp_client(workspace(parts), write_tools=tools(parts)) as client:
        for name in ("get_spec_changes", "get_decisions"):
            result, text = await call(client, name, {"proposal_id": proposal.id})
            assert result["isError"] is True and "was reverted" in text
            result, text = await call(client, name, {"proposal_id": "no-such-proposal"})
            assert result["isError"] is True and "No proposal found" in text
