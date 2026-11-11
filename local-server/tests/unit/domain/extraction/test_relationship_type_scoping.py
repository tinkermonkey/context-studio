"""
Unit tests (#1450): a relationship triple's predicate resolves to a type of
the run's taxonomy only, never another taxonomy's type of the same name; among
the taxonomy's types sharing a predicate, the one whose domain and range fit
the subject's and object's classes wins.
"""

from unittest.mock import Mock

import pytest

from domain.extraction.services import ExtractionService
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


@pytest.fixture
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture
def extraction(ontology):
    return ExtractionService(
        ontology_repo=ontology._repository,
        embedding_service=FakeEmbeddingService(),
        llm=Mock(),
        nlp=Mock(),
        reference_sources=[],
        event_publisher=FakeEventPublisher(),
        extraction_repo=Mock(),
        extraction_run_repo=Mock(),
    )


def _type(ontology, identifier, predicate, domain, range_):
    return ontology.create_property_definition(
        identifier,
        identifier.replace("_", " "),
        canonical_predicate=predicate,
        domain_class_id=domain.id if domain else None,
        range_class_id=range_.id,
        create_missing_predicate=True,
    )


@pytest.fixture
def taxonomies(ontology):
    # DR's types come first, so a first-name-wins index over every taxonomy picks them
    dr = ontology.create_taxonomy(title="DR", identifier="dr")
    dr_scheme = ontology.create_scheme(taxonomy_id=dr.id, title="API")
    document = ontology.create_class(dr_scheme.id, "OpenAPIDocument", identifier="dr_document")
    scheme_cls = ontology.create_class(dr_scheme.id, "SecurityScheme", identifier="dr_scheme")
    dr_requires = _type(
        ontology, "openapidocument_requires_securityscheme", "requires", document, scheme_cls
    )

    house = ontology.create_taxonomy(title="House", identifier="house")
    scheme = ontology.create_scheme(taxonomy_id=house.id, title="Resources")
    task = ontology.create_class(scheme.id, "Task", identifier="house_task")
    resource = ontology.create_class(scheme.id, "Resource", identifier="house_resource")
    item = ontology.create_class(scheme.id, "Item", identifier="house_item")
    place = ontology.create_class(scheme.id, "Place", identifier="house_place")
    requires = _type(ontology, "house_task_requires_resource", "requires", task, resource)
    task_located = _type(ontology, "house_task_located_in_place", "located_in", task, place)
    item_located = _type(ontology, "house_item_located_in_place", "located_in", item, place)
    return {
        "house": house,
        "dr_requires": dr_requires.id,
        "requires": requires.id,
        "task_located": task_located.id,
        "item_located": item_located.id,
    }


def typing(label, class_ref):
    return {
        "subject": {"kind": "individual", "id": "", "label": label, "class_ids": []},
        "predicate": {"property_definition_id": "is_a", "label": "is_a"},
        "object": {"kind": "class", "id": "", "label": class_ref},
        "confidence": 0.9,
    }


def relation(subject, predicate, obj):
    return {
        "subject": {"kind": "individual", "id": "", "label": subject, "class_ids": []},
        "predicate": {"property_definition_id": "", "label": predicate},
        "object": {"kind": "individual", "id": "", "label": obj},
        "confidence": 0.8,
    }


def stamped(extraction, taxonomy, individuals, relationships):
    triples, _ = extraction._type_concept_objects(relationships, individuals, taxonomy)
    return [t["predicate"]["property_definition_id"] for t in triples if t in relationships]


def test_a_predicate_resolves_to_the_runs_taxonomy_only(extraction, taxonomies):
    individuals = [typing("Replace the filter", "house_task"), typing("Filter", "house_resource")]
    relationships = [relation("Replace the filter", "requires", "Filter")]

    assert stamped(extraction, taxonomies["house"], individuals, relationships) == [
        taxonomies["requires"]
    ]


def test_the_type_whose_domain_fits_the_subject_wins(extraction, taxonomies):
    individuals = [
        typing("Water filter", "house_item"),
        typing("Clean the gutters", "Task"),
        typing("Kitchen", "house_place"),
    ]
    relationships = [
        relation("Water filter", "located_in", "Kitchen"),
        relation("Clean the gutters", "located in", "Kitchen"),
    ]

    assert stamped(extraction, taxonomies["house"], individuals, relationships) == [
        taxonomies["item_located"],
        taxonomies["task_located"],
    ]


def test_the_prompt_offers_only_the_taxonomys_predicates(extraction, ontology, taxonomies):
    other = ontology.create_taxonomy(title="Other", identifier="other")
    other_scheme = ontology.create_scheme(taxonomy_id=other.id, title="Things")
    a = ontology.create_class(other_scheme.id, "A", identifier="other_a")
    _type(ontology, "other_a_watches_a", "watches", a, a)

    vocabulary = extraction._ontology_predicate_vocabulary(taxonomies["house"])

    assert sorted(vocabulary) == ["located_in", "requires"]


@pytest.fixture
def hierarchy(ontology):
    """Chore is a Task, which is a Thing; four located_in types from more to less specific."""
    house = ontology.create_taxonomy(title="Chores", identifier="chores")
    scheme = ontology.create_scheme(taxonomy_id=house.id, title="Work")
    thing = ontology.create_class(scheme.id, "Thing", identifier="c_thing")
    task = ontology.create_class(scheme.id, "Task", identifier="c_task", parent_class_id=thing.id)
    chore = ontology.create_class(scheme.id, "Chore", identifier="c_chore", parent_class_id=task.id)
    place = ontology.create_class(scheme.id, "Place", identifier="c_place")
    types = {
        name: _type(ontology, f"c_{name}_located_in_place", "located_in", domain, place)
        for name, domain in (("chore", chore), ("task", task), ("thing", thing), ("open", None))
    }
    by_id = {c.id: c for c in (thing, task, chore, place)}
    return {"types": types, "by_id": by_id, "chore": chore.id, "place": place.id}


@pytest.mark.parametrize(
    "listed, chosen",
    [
        (("task", "chore"), "chore"),  # the class itself beats an ancestor
        (("thing", "task"), "task"),  # a nearer ancestor beats a farther one
        (("open", "thing"), "thing"),  # an ancestor beats an open end
        (("open", "chore", "thing", "task"), "chore"),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_the_most_specific_type_wins_in_any_order(extraction, hierarchy, listed, chosen, reverse):
    types = hierarchy["types"]
    candidates = [types[name] for name in (reversed(listed) if reverse else listed)]

    picked = extraction._pick_property_definition(
        candidates, [hierarchy["chore"]], [hierarchy["place"]], hierarchy["by_id"]
    )

    assert picked.id == types[chosen].id


def test_a_true_tie_keeps_list_order(extraction, hierarchy):
    types = hierarchy["types"]
    candidates = [types["task"], types["chore"]]

    # Unknown classes fit nothing, so neither type is more specific
    picked = extraction._pick_property_definition(candidates, [], [], hierarchy["by_id"])

    assert picked.id == types["task"].id
