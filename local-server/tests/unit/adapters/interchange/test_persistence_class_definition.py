"""
The OWL/SKOS/GraphML import's persistence (#1513): a re-import of a class keeps
its operational definition unless the format gives one.
"""

from adapters.interchange.persistence_helpers import persist_incoming_entities
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


def world():
    repo = FakeOntologyRepository()
    service = OntologyService(repo, FakeEmbeddingService(), FakeEventPublisher())
    taxonomy = service.create_taxonomy(title="DR", identifier="dr")
    scheme = service.create_scheme(taxonomy_id=taxonomy.id, title="API")
    endpoint = service.create_class(scheme.id, "Endpoint", identifier="api_endpoint")
    operation = service.create_class(
        scheme.id,
        "Operation",
        identifier="api_operation",
        distinguish_from=[{"class_id": endpoint.id, "when": "the path, not the action"}],
        evidence_signals=["an HTTP method on a path"],
        standard_reference="OpenAPI 3.0 Operation Object",
    )
    return repo, scheme, operation


def incoming_class(scheme, cls, **extra):
    return {
        cls.id: {
            "type": "class",
            "id": cls.id,
            "concept_scheme_id": scheme.id,
            "identifier": cls.identifier,
            "title": cls.title,
            **extra,
        }
    }


def test_a_reimport_keeps_the_definition():
    repo, scheme, operation = world()
    warnings: list[str] = []

    persist_incoming_entities(incoming_class(scheme, operation), {}, repo, warnings)

    stored = repo.get_class(operation.id)
    assert warnings == []
    assert stored.distinguish_from == operation.distinguish_from
    assert stored.evidence_signals == ["an HTTP method on a path"]
    assert stored.standard_reference == "OpenAPI 3.0 Operation Object"


def test_a_format_that_gives_the_fields_replaces_them():
    repo, scheme, operation = world()

    persist_incoming_entities(
        incoming_class(scheme, operation, evidence_signals=[], standard_reference="OAS 3.1"),
        {},
        repo,
        [],
    )

    stored = repo.get_class(operation.id)
    assert stored.evidence_signals == []
    assert stored.standard_reference == "OAS 3.1"
    assert stored.distinguish_from == operation.distinguish_from
