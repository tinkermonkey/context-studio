"""
Unit tests for the OWL/SKOS/GraphML import's persistence (#1465): a re-import
keeps a class's or relationship type's derived flag, and new individuals or
relationships of derived types are refused (reported as warnings).
"""

from adapters.interchange.persistence_helpers import persist_incoming_entities
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


def house():
    repo = FakeOntologyRepository()
    service = OntologyService(repo, FakeEmbeddingService(), FakeEventPublisher())
    taxonomy = service.create_taxonomy(title="House", identifier="house")
    scheme = service.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    kit = service.create_class(scheme.id, "Kit", identifier="house_kit", derived=True)
    tool = service.create_class(scheme.id, "Tool", identifier="house_tool")
    includes = service.create_property_definition(
        "house_kit_includes_tool", "includes", derived=True
    )
    hammer = service.create_individual([tool.id], title="Hammer")
    return repo, scheme, kit, tool, includes, hammer


def test_a_reimport_keeps_derived_flags():
    repo, scheme, kit, _, includes, _ = house()
    incoming = {
        kit.id: {
            "type": "class",
            "id": kit.id,
            "concept_scheme_id": scheme.id,
            "identifier": "house_kit",
            "title": "Kit",
        },
        includes.id: {
            "type": "property_definition",
            "id": includes.id,
            "identifier": "house_kit_includes_tool",
            "title": "includes",
        },
    }
    warnings: list[str] = []

    persist_incoming_entities(incoming, {}, repo, warnings)

    assert warnings == []
    assert repo.get_class(kit.id).derived is True
    assert repo.get_property_definition(includes.id).derived is True


def test_new_members_of_derived_types_are_refused():
    repo, _, kit, tool, includes, hammer = house()
    incoming = {
        "ind-new": {
            "type": "individual",
            "id": "ind-new",
            "title": "Starter kit",
            "class_ids": [kit.id],
        },
        "rel-new": {
            "type": "relationship",
            "id": "rel-new",
            "source_id": hammer.id,
            "target_id": hammer.id,
            "property_definition_id": includes.id,
        },
        "ind-ok": {"type": "individual", "id": "ind-ok", "title": "Saw", "class_ids": [tool.id]},
    }
    warnings: list[str] = []

    affected = persist_incoming_entities(incoming, {}, repo, warnings)

    assert affected == ["ind-ok"]
    assert len(warnings) == 2
    assert all("derived" in w for w in warnings)
    assert repo.get_individual("ind-new") is None
    assert repo.get_relationship("rel-new") is None
