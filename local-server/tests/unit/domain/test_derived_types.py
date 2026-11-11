"""
Unit tests for derived classes and relationship types (#1465): the client
computes their individuals and relationships, so none is created directly, the
flag is recorded in change events (so revert restores it), and extraction never
offers them as targets.
"""

from unittest.mock import Mock

import pytest

from domain.extraction.services import ExtractionService
from domain.ontology.events import ClassUpdated, PropertyDefinitionUpdated
from domain.ontology.exceptions import DerivedTypeError
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


@pytest.fixture
def publisher():
    return FakeEventPublisher()


@pytest.fixture
def service(publisher):
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), publisher)


@pytest.fixture
def house(service):
    """House's kits: a derived class and a derived relationship type."""
    taxonomy = service.create_taxonomy(title="House", identifier="house")
    scheme = service.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    kit = service.create_class(scheme.id, "Kit", identifier="house_kit", derived=True)
    tool = service.create_class(scheme.id, "Tool", identifier="house_tool")
    includes = service.create_property_definition(
        "house_kit_includes_tool",
        "includes",
        domain_class_id=kit.id,
        range_class_id=tool.id,
        derived=True,
    )
    uses = service.create_property_definition(
        "house_tool_pairs_with_tool", "pairs with", domain_class_id=tool.id, range_class_id=tool.id
    )
    return {"taxonomy": taxonomy, "kit": kit, "tool": tool, "includes": includes, "uses": uses}


def test_creates_keep_the_flag(service, house):
    assert service.get_class(house["kit"].id).derived is True
    assert service.get_class(house["tool"].id).derived is False
    assert service.get_property_definition(house["includes"].id).derived is True


def test_an_individual_of_a_derived_class_is_refused(service, house):
    with pytest.raises(DerivedTypeError, match="'Kit' is derived"):
        service.create_individual([house["tool"].id, house["kit"].id], title="Starter kit")

    hammer = service.create_individual([house["tool"].id], title="Hammer")
    with pytest.raises(DerivedTypeError, match="'Kit' is derived"):
        service.add_class_to_individual(hammer.id, house["kit"].id)


def test_a_relationship_of_a_derived_type_is_refused(service, house):
    hammer = service.create_individual([house["tool"].id], title="Hammer")
    nails = service.create_individual([house["tool"].id], title="Nails")

    with pytest.raises(DerivedTypeError, match="'house_kit_includes_tool' is derived"):
        service.create_relationship(hammer.id, nails.id, house["includes"].id)
    assert service.create_relationship(hammer.id, nails.id, house["uses"].id) is not None


def test_updates_record_the_flag_for_revert(service, house, publisher):
    service.update_class(house["kit"].id, derived=False)
    service.update_property_definition(house["uses"].id, derived=True)

    [class_event] = publisher.get_events_of_type(ClassUpdated)
    assert class_event.changed_fields == ("derived",)
    assert (class_event.old_values, class_event.new_values) == (
        {"derived": True},
        {"derived": False},
    )
    [property_event] = [
        e
        for e in publisher.get_events_of_type(PropertyDefinitionUpdated)
        if e.property_id == house["uses"].id
    ]
    assert property_event.changed_fields == ("derived",)
    assert property_event.new_values == {"derived": True}
    # Unchanged (None) leaves it as it is.
    assert service.update_class(house["kit"].id, title="Kits").derived is False


def test_extraction_never_offers_derived_types(service, house):
    extraction = ExtractionService(
        ontology_repo=service._repository,
        embedding_service=FakeEmbeddingService(),
        llm=Mock(),
        nlp=Mock(),
        reference_sources=[],
        event_publisher=FakeEventPublisher(),
        extraction_repo=Mock(),
        extraction_run_repo=Mock(),
    )
    taxonomy = house["taxonomy"]

    catalog = extraction._ontology_class_catalog(taxonomy)
    vocabulary = extraction._ontology_predicate_vocabulary(taxonomy)

    assert [title for _, title in catalog] == ["Tool"]
    assert "includes" not in vocabulary and "pairs with" in vocabulary
    _, by_id = extraction._class_index(taxonomy)
    index = extraction._property_definition_index(taxonomy.id, by_id)
    assert "includes" not in index and "pairs with" in index
