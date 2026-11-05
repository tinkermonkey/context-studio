"""
Integration tests (#1413): the chat and MCP tools show what REST shows.

get_proposal is compared with GET /api/proposals/{id} for the same proposal
over real SQLite: every value REST returns (nulls and empty lists or objects
aside, which the tools leave out) comes back from the tool unchanged. A dry
run through propose_changes or POST /api/proposals?dry_run=true stores
nothing and gives the same verdict. get_entity carries the REST fields of
each kind and fetches relationships and attribute definitions.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.chat.proposal_tools import build_proposal_tools
from adapters.chat.tools import build_chat_tools
from adapters.web.proposals_routes import router
from domain.ontology.value_objects import DataPropertyValue
from domain.versioning.approval_policy import ApprovalPolicy, AutoApplyRule
from domain.versioning.proposals import ChangeScope, ProposalSource
from tests.integration.chat.conftest import (
    ADMIN_HEALTH_ID,
    HEALTH_MONITORING_ID,
    OPERATION_ID,
    REALIZES_ID,
    RELATIONSHIP_ID,
    SERVICE_CLASS_ID,
    TAXONOMY_ID,
)


@pytest.fixture
def client(proposals):
    app = FastAPI()
    app.include_router(router)
    app.state.proposal_service = proposals.service
    return TestClient(app)


@pytest.fixture
def proposal_tools(proposals):
    return {t.spec.name: t for t in build_proposal_tools(proposals.service, ProposalSource.MCP)}


@pytest.fixture
def read_tools(dr_workspace):
    return {t.spec.name: t for t in build_chat_tools(dr_workspace.ontology, dr_workspace.graph)}


async def call(tools, name, **args):
    outcome = await tools[name].execute(args)
    assert not outcome.is_error, outcome.content
    return json.loads(outcome.content)


def compact(value):
    """REST JSON as the tools give it: no nulls, empty lists or empty objects."""
    if isinstance(value, dict):
        kept = {k: compact(v) for k, v in value.items()}
        return {k: v for k, v in kept.items() if v is not None and v != [] and v != {}}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def operations():
    """A reworded class, and an in-use relationship type replaced by a new one."""
    return [
        {
            "seq": 1,
            "op": "update",
            "kind": "class",
            "target_id": OPERATION_ID,
            "fields": {"description": "One endpoint and method of an API"},
            "rationale": "The vision asks for curated definitions",
            "evidence": [{"quote": "An operation is an endpoint", "url": "https://dr.example"}],
            "probability": 0.9,
        },
        {
            "seq": 2,
            "op": "create",
            "kind": "property",
            "ref": "serves",
            "fields": {
                "identifier": "operation_serves_service",
                "title": "api.operation serves business.service",
                "domain_class_id": OPERATION_ID,
                "range_class_id": SERVICE_CLASS_ID,
            },
        },
        {
            "seq": 3,
            "op": "delete",
            "kind": "property",
            "target_id": REALIZES_ID,
            "replacement": "$serves",
        },
    ]


def body(**extra):
    return {
        "taxonomy_id": TAXONOMY_ID,
        "title": "Rework realizes",
        "rationale": "Serves says it better",
        "source": "mcp",
        "source_detail": "claude-code",
        "operations": operations(),
        **extra,
    }


async def test_get_proposal_matches_rest(client, proposal_tools, proposals):
    response = client.post("/api/proposals", json=body())
    assert response.status_code == 201, response.text
    proposal_id = response.json()["id"]
    update = response.json()["operations"][0]["id"]
    proposals.service.apply(proposal_id, [update])

    rest = compact(client.get(f"/api/proposals/{proposal_id}").json())
    tool = await call(proposal_tools, "get_proposal", id=proposal_id)

    for key, value in rest.items():
        assert tool[key] == value, key
    # What #1413 found missing is all there
    assert tool["source_detail"] == "claude-code"
    applied, create, delete = tool["operations"]
    assert applied["status"] == "applied" and applied["result_entity_id"] == OPERATION_ID
    assert applied["base"] == {"description": "An API operation (endpoint + method)"}
    assert applied["probability"] == 0.9 and applied["evidence"]
    assert create["ref"] == "serves"
    assert delete["proposed_replacement_id"] == "$serves"
    (edge,) = delete["blockers"]["edges"]
    assert edge["relationship_id"] == RELATIONSHIP_ID
    assert (edge["source"]["id"], edge["target"]["id"]) == (ADMIN_HEALTH_ID, HEALTH_MONITORING_ID)
    assert delete["blockers"]["move_unavailable_reason"]  # the replacement isn't created yet
    check = delete["replacement_check"]
    assert check["pair"] == "same"
    assert check["deleted_domain"] == {"id": OPERATION_ID, "title": "Operation"}
    assert check["range"]["id"] == SERVICE_CLASS_ID


async def test_propose_changes_shows_the_blockers_rest_shows(client, proposal_tools):
    result = await call(
        proposal_tools,
        "propose_changes",
        taxonomy_id=TAXONOMY_ID,
        title="Rework realizes",
        operations=operations(),
    )

    rest = compact(client.get(f"/api/proposals/{result['id']}").json())
    delete = result["operations"][2]
    assert delete["blockers"] == rest["operations"][2]["blockers"]
    assert delete["replacement_check"] == rest["operations"][2]["replacement_check"]


async def test_dry_runs_store_nothing_and_agree(client, proposal_tools, proposals):
    proposals.policies.save(
        ApprovalPolicy(TAXONOMY_ID, auto_apply=(AutoApplyRule(scope=ChangeScope.EDITORIAL),))
    )

    response = client.post("/api/proposals", params={"dry_run": "true"}, json=body())
    tool = await call(
        proposal_tools,
        "propose_changes",
        taxonomy_id=TAXONOMY_ID,
        title="Rework realizes",
        operations=operations(),
        dry_run=True,
    )

    assert response.status_code == 200, response.text
    rest = response.json()
    assert rest["dry_run"] is True
    assert [o["auto_apply"] for o in rest["operations"]] == [True, False, False]
    assert [o["status"] for o in rest["operations"]] == ["pending"] * 3
    assert rest["operations"][2]["blockers"]["edges"]
    assert rest["operations"][2]["replacement_check"]["pair"] == "same"
    assert (tool["stored"], tool["dry_run"]) == (False, True)
    assert [o["auto_apply"] for o in tool["operations"]] == [True, False, False]
    assert tool["operations"][2]["blockers"] == compact(rest["operations"][2]["blockers"])
    assert proposals.service.count_proposals() == 0
    assert client.get("/api/proposals").json()["total"] == 0


def test_a_stored_proposal_is_not_a_dry_run(client):
    response = client.post("/api/proposals", json=body())

    assert response.status_code == 201
    assert response.json()["dry_run"] is False
    assert all(o["auto_apply"] is None for o in response.json()["operations"])


async def test_an_invalid_dry_run_is_a_422(client):
    response = client.post(
        "/api/proposals",
        params={"dry_run": "true"},
        json=body(operations=[{"seq": 1, "op": "delete", "kind": "class", "target_id": "nope"}]),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["seq"] == 1


class TestGetEntity:
    async def test_every_kind_has_the_rest_metadata(self, read_tools):
        for entity_id in (TAXONOMY_ID, OPERATION_ID, ADMIN_HEALTH_ID, REALIZES_ID):
            result = await call(read_tools, "get_entity", id=entity_id)

            for key in ("created_at", "last_modified", "version", "status"):
                assert key in result, (entity_id, key)
            assert "color" not in result and "embedding" not in result

    async def test_class_fields(self, read_tools, dr_workspace):
        operation = dr_workspace.repository.get_class(OPERATION_ID)
        operation.data_properties = [DataPropertyValue("layer", "api", "xsd:string")]
        dr_workspace.repository.save_class(operation)

        result = await call(read_tools, "get_entity", id=OPERATION_ID)

        assert result["structural_property_id"] is None
        assert result["external_references"] == [] and result["lexical_senses"] == []
        (value,) = result["data_properties"]
        assert value == {"property_identifier": "layer", "value": "api", "datatype": "xsd:string"}

    async def test_property_fields(self, read_tools):
        result = await call(read_tools, "get_entity", id=REALIZES_ID)

        assert result["domain_class_id"] == OPERATION_ID
        assert {"canonical_predicate", "is_relevant", "lexical_senses"} <= result.keys()

    async def test_a_relationship(self, read_tools):
        outcome = await read_tools["get_entity"].execute({"id": RELATIONSHIP_ID})
        result = json.loads(outcome.content)

        assert result["kind"] == "relationship"
        assert result["property_definition_id"] == REALIZES_ID
        assert [r["id"] for r in result["source"]] == [ADMIN_HEALTH_ID]
        assert [r["id"] for r in result["type"]] == [REALIZES_ID]
        assert [r["id"] for r in result["target"]] == [HEALTH_MONITORING_ID]
        assert {e.id for e in outcome.entities} == {
            ADMIN_HEALTH_ID,
            REALIZES_ID,
            HEALTH_MONITORING_ID,
        }
        assert outcome.summary == (
            "Admin Health api.operation realizes business.service Health Monitoring"
            " (relationship)"
        )

    async def test_an_attribute_definition(self, read_tools, dr_workspace):
        attribute = dr_workspace.ontology.create_attribute_definition(
            OPERATION_ID, "http_method", "HTTP method", "string", allowed_values=["GET", "POST"]
        )

        outcome = await read_tools["get_entity"].execute({"id": attribute.id})
        result = json.loads(outcome.content)

        assert result["kind"] == "attribute"
        assert result["class_id"] == OPERATION_ID
        assert (result["datatype"], result["allowed_values"]) == ("string", ["GET", "POST"])
        assert result["class"] == [{"id": OPERATION_ID, "kind": "class", "title": "Operation"}]
        assert {e.id for e in outcome.entities} == {OPERATION_ID}
        class_result = await call(read_tools, "get_entity", id=OPERATION_ID)
        assert class_result["counts"]["attributes"] == 1
