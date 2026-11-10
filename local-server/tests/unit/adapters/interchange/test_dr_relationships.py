"""
Unit tests for DR relationship identifiers and the cardinality mapping
(adapters/interchange/dr_relationships.py).
"""

import pytest

from adapters.interchange.dr_relationships import (
    Triple,
    assign_relationship_identifiers,
    dr_cardinality,
    dr_cardinality_fields,
)
from domain.ontology.entities import PropertyDefinition
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

RELATIONSHIP_IDS = [
    "api.operation.delivers.api.response",
    "ux.view.serves.business.businessrole",
    "data-store.view.serves.business.businessrole",  # strips like the one above
    "api.tag.governs.api.ratelimit",  # its stripped form is held by a class
    "api.header.uses.api.schema",
]


@pytest.fixture()
def repo():
    ontology = OntologyService(
        FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher()
    )
    taxonomy = ontology.create_taxonomy(title="Other")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Things")
    ontology.create_class(scheme.id, "Taken", identifier="tag_governs_ratelimit")
    return ontology._repository


@pytest.mark.parametrize("wanted", RELATIONSHIP_IDS)
def test_only_the_wanted_identifier_matches_the_full_assignment(repo, wanted):
    records = [Triple.parse(r).record() for r in RELATIONSHIP_IDS]
    owners = {r: None for r in RELATIONSHIP_IDS}
    full = assign_relationship_identifiers(records, repo, owners)

    assert assign_relationship_identifiers(records, repo, owners, only=[wanted]) == {
        wanted: full[wanted]
    }


def test_the_fixture_covers_taken_and_colliding_forms(repo):
    records = [Triple.parse(r).record() for r in RELATIONSHIP_IDS]
    full = assign_relationship_identifiers(records, repo, {r: None for r in RELATIONSHIP_IDS})

    assert full["api.operation.delivers.api.response"] == "operation_delivers_response"
    assert full["api.tag.governs.api.ratelimit"].startswith("tag_governs_ratelimit_")
    assert full["ux.view.serves.business.businessrole"].startswith("view_serves_businessrole_")


CARDINALITIES = [
    ("many-to-many", {"min_per_source": 0, "max_per_source": None, "max_per_target": None}),
    ("many-to-one", {"min_per_source": 0, "max_per_source": 1, "max_per_target": None}),
    ("one-to-many", {"min_per_source": 0, "max_per_source": None, "max_per_target": 1}),
    ("one-to-one", {"min_per_source": 0, "max_per_source": 1, "max_per_target": 1}),
]


@pytest.mark.parametrize("cardinality, fields", CARDINALITIES)
def test_a_dr_cardinality_maps_to_the_structure_fields_and_back(cardinality, fields):
    assert dr_cardinality_fields(cardinality) == fields
    assert dr_cardinality(fields) == cardinality
    prop = PropertyDefinition(id="p", identifier="p", title="P", **fields)
    assert dr_cardinality(prop) == cardinality


def test_missing_fields_have_their_defaults():
    assert dr_cardinality({}) == "many-to-many"
    assert dr_cardinality({"max_per_target": 1}) == "one-to-many"


@pytest.mark.parametrize(
    "fields",
    [
        {"min_per_source": 1},
        {"min_per_source": 2, "max_per_source": 2},
        {"max_per_source": 3},
        {"max_per_target": 0},
        {"max_per_target": True},  # not the number 1
    ],
)
def test_numbers_dr_cannot_express_have_no_cardinality(fields):
    assert dr_cardinality(fields) is None


def test_an_unknown_cardinality_is_refused():
    with pytest.raises(ValueError, match="not a DR cardinality"):
        dr_cardinality_fields("one-to-several")
