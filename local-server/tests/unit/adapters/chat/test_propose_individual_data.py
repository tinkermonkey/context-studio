"""
Tool tests (#1415): propose_changes sets an individual's attribute values
through the real ProposalService, and reports values that don't fit as
fixable entries.
"""

import json

import pytest

from adapters.chat.proposal_tools import build_proposal_tools
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import DataPropertyValue
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ProposalSource
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        return RevertResult(run_id=run_id, events_reverted=0)


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def service(ontology):
    return ProposalService(
        FakeChangeProposalRepository(), ontology, ontology._repository, StubRevertService()
    )


@pytest.fixture()
def house(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Life")
    resource = ontology.create_class(scheme.id, "Resource", identifier="resource")
    tool = ontology.create_class(scheme.id, "Tool", parent_class_id=resource.id)
    ontology.create_attribute_definition(resource.id, "brand", "Brand", "string")
    ontology.create_attribute_definition(tool.id, "watts", "Watts", "integer")
    drill = ontology.create_individual(tool.id, "Drill")
    ontology.update_individual(
        drill.id, data_properties=[DataPropertyValue("brand", "Bosch", "string")]
    )
    return {"taxonomy": taxonomy.id, "tool": tool.id, "drill": drill.id}


async def propose(service, house, *operations):
    tool = {t.spec.name: t for t in build_proposal_tools(service, ProposalSource.MCP)}
    outcome = await tool["propose_changes"].execute(
        {"taxonomy_id": house["taxonomy"], "title": "Kit", "operations": list(operations)}
    )
    return outcome, json.loads(outcome.content)


def test_the_field_guide_lists_data_properties_for_individuals(service):
    tool = {t.spec.name: t for t in build_proposal_tools(service, ProposalSource.MCP)}
    description = tool["propose_changes"].spec.description
    line = next(row for row in description.splitlines() if row.startswith("- individual:"))
    assert "data_properties" in line.split("; update")[0]
    assert "data_properties" in line.split("; update")[1]


async def test_create_and_update_with_values(service, house, ontology):
    outcome, result = await propose(
        service,
        house,
        {
            "seq": 1,
            "op": "create",
            "kind": "individual",
            "fields": {
                "class_ids": [house["tool"]],
                "title": "Saw",
                "data_properties": {"brand": "Makita", "watts": 1200},
            },
        },
        {
            "seq": 2,
            "op": "update",
            "kind": "individual",
            "target_id": house["drill"],
            "fields": {"data_properties": {"watts": 700}},
        },
    )

    assert outcome.is_error is False
    assert result["stored"] is True
    assert [(o["seq"], o["status"], o["scope"]) for o in result["operations"]] == [
        (1, "pending", "additive"),
        (2, "pending", "additive"),
    ]
    proposal = service.get(result["id"])
    applied = service.apply(proposal.id, [o.id for o in proposal.operations])
    saw = ontology.get_individual(applied.operations[0].result_entity_id)
    assert {v.property_identifier: v.value for v in saw.data_properties} == {
        "brand": "Makita",
        "watts": 1200,
    }
    drill = ontology.get_individual(house["drill"])
    assert {v.property_identifier: v.value for v in drill.data_properties} == {
        "brand": "Bosch",
        "watts": 700,
    }


async def test_values_that_dont_fit_are_fixable_entries(service, house):
    outcome, result = await propose(
        service,
        house,
        {
            "seq": 1,
            "op": "create",
            "kind": "individual",
            "fields": {
                "class_ids": [house["tool"]],
                "title": "Saw",
                "data_properties": {"colour": "red"},
            },
        },
        {
            "seq": 2,
            "op": "update",
            "kind": "individual",
            "target_id": house["drill"],
            "fields": {"data_properties": {"watts": "lots"}},
        },
    )

    assert outcome.is_error is False
    assert result["stored"] is False
    assert result["operations"] == [
        {
            "seq": 1,
            "status": "invalid",
            "code": "invalid",
            "message": (
                "data_properties 'colour' is not an attribute of the individual's"
                " classes (theirs and inherited: brand, watts)"
            ),
        },
        {
            "seq": 2,
            "status": "invalid",
            "code": "invalid",
            "message": "data_properties 'watts' is integer, so 'lots' doesn't fit",
        },
    ]
