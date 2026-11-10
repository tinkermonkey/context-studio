"""
Unit tests (#1487): chat and MCP tools over datasets. `list_datasets` lists
them; a read of a class's data uses the taxonomy's only dataset, takes
`dataset` when there are several, and refuses an ambiguous call with the list.
"""

import json

import pytest

from adapters.chat.tools import (
    EntityResolver,
    GetEntityTool,
    ListChildrenTool,
    ListDatasetsTool,
)
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def model(ontology):
    taxonomy = ontology.create_taxonomy(title="Architecture")
    component = ontology.create_class(
        ontology.create_scheme(taxonomy.id, title="App").id, "Component", identifier="component"
    )
    alpha = ontology.create_dataset(taxonomy.id, "alpha", "Platform Alpha")
    beta = ontology.create_dataset(taxonomy.id, "beta", "Platform Beta")
    ontology.create_individual(component.id, "Gateway", dataset_id=alpha.id)
    ontology.create_individual(component.id, "Gateway", dataset_id=beta.id)
    ontology.create_individual(component.id, "Cache", dataset_id=beta.id)
    return {"taxonomy": taxonomy, "component": component, "alpha": alpha, "beta": beta}


def _run(tool_cls, ontology, **args):
    outcome = tool_cls(ontology, EntityResolver(ontology)).run(args)
    return outcome, json.loads(outcome.content)


def test_list_datasets_gives_each_with_its_size(ontology, model):
    _, payload = _run(ListDatasetsTool, ontology, taxonomy_id=model["taxonomy"].id)

    assert [(d["identifier"], d["individuals"]) for d in payload["datasets"]] == [
        ("alpha", 1),
        ("beta", 2),
    ]


def test_an_ambiguous_read_is_refused_with_the_dataset_list(ontology, model):
    outcome = ListChildrenTool(ontology, EntityResolver(ontology))._run_safely(
        {"id": model["component"].id}
    )

    assert outcome.is_error
    assert "alpha (Platform Alpha), beta (Platform Beta)" in json.loads(outcome.content)["error"]


def test_a_read_takes_a_dataset_identifier(ontology, model):
    _, payload = _run(ListChildrenTool, ontology, id=model["component"].id, dataset="beta")

    assert sorted(i["title"] for i in payload["items"]) == ["Cache", "Gateway"]
    assert payload["total"] == 2


def test_a_single_dataset_is_implied(ontology):
    taxonomy = ontology.create_taxonomy(title="Solo")
    cls = ontology.create_class(ontology.create_scheme(taxonomy.id, title="S").id, "Thing")
    ontology.create_individual(cls.id, "Widget")

    _, payload = _run(ListChildrenTool, ontology, id=cls.id)

    assert [i["title"] for i in payload["items"]] == ["Widget"]


def test_get_entity_shows_an_individuals_dataset_and_a_class_per_dataset(ontology, model):
    [gateway] = ontology.list_individuals(query="Gateway", dataset_id=model["beta"].id)

    _, individual = _run(GetEntityTool, ontology, id=gateway.id)
    _, cls = _run(GetEntityTool, ontology, id=model["component"].id)

    assert individual["dataset"]["identifier"] == "beta"
    assert cls["individuals_by_dataset"] == {"alpha": 1, "beta": 2}
