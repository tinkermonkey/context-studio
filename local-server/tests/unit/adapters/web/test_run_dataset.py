"""
Unit tests (#1487): an individual-extraction run settles its dataset before it
runs: the one named, else the taxonomy's only one; several and none named is a
422 that lists them.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from adapters.web.pipelines_routes import _resolve_run_dataset
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineType
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


@pytest.fixture()
def parts():
    repo = FakeOntologyRepository()
    ontology = OntologyService(repo, FakeEmbeddingService(), FakeEventPublisher())
    taxonomy = ontology.create_taxonomy(title="Architecture")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(ontology_repo=repo)))
    return ontology, taxonomy, request


def test_the_only_dataset_is_used(parts):
    ontology, taxonomy, request = parts
    only = ontology.create_dataset(taxonomy.id, "alpha", "Alpha")
    data = {"ontology_id": taxonomy.id}

    _resolve_run_dataset(request, PipelineType.INDIVIDUAL_EXTRACTION, data)

    assert data["dataset_id"] == only.id


def test_several_datasets_and_none_named_is_a_422_listing_them(parts):
    ontology, taxonomy, request = parts
    ontology.create_dataset(taxonomy.id, "alpha", "Alpha")
    ontology.create_dataset(taxonomy.id, "beta", "Beta")

    with pytest.raises(HTTPException) as raised:
        _resolve_run_dataset(
            request, PipelineType.INDIVIDUAL_EXTRACTION, {"ontology_id": taxonomy.id}
        )

    assert raised.value.status_code == 422
    assert "alpha, beta" in raised.value.detail


def test_an_unknown_dataset_is_a_404_and_other_pipelines_are_untouched(parts):
    _, taxonomy, request = parts

    with pytest.raises(HTTPException) as raised:
        _resolve_run_dataset(
            request,
            PipelineType.INDIVIDUAL_EXTRACTION,
            {"ontology_id": taxonomy.id, "dataset_id": "missing"},
        )
    data = {"ontology_id": taxonomy.id}
    _resolve_run_dataset(request, PipelineType.SCHEMA_EXTRACTION, data)

    assert raised.value.status_code == 404
    assert "dataset_id" not in data


def test_an_unknown_taxonomy_is_left_for_the_run_to_fail_on(parts):
    ontology, _, request = parts

    data = {"ontology_id": "no-such-taxonomy"}
    _resolve_run_dataset(request, PipelineType.INDIVIDUAL_EXTRACTION, data)

    assert "dataset_id" not in data
    assert ontology.list_datasets() == []
