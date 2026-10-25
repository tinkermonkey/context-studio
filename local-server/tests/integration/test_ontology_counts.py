"""
Integration tests for the grouped count queries and the domain-class filter
on SQLiteOntologyRepository (scheme counts, class counts, property definitions
by domain), against a real in-memory SQLite database.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher


@pytest.fixture
def repo():
    """A repository over a fresh in-memory database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return SQLiteOntologyRepository(sessionmaker(bind=engine))


@pytest.fixture
def model(repo):
    """Two taxonomies; the first has a populated scheme and an empty one."""
    service = OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=FakeEventPublisher(),
    )
    tax = service.create_taxonomy(title="Architecture")
    app = service.create_scheme(tax.id, title="Application")
    empty = service.create_scheme(tax.id, title="Business")
    component = service.create_class(app.id, title="Component")
    service_cls = service.create_class(app.id, title="Service")
    realizes = service.create_property_definition(
        identifier="realizes",
        title="Realizes",
        domain_class_id=component.id,
        range_class_id=service_cls.id,
    )
    service.create_property_definition(
        identifier="uses", title="Uses", domain_class_id=component.id
    )
    router = service.create_individual(class_ids=[component.id], title="Router")
    gateway = service.create_individual(
        class_ids=[component.id, service_cls.id], title="Gateway"
    )
    api = service.create_individual(class_ids=[service_cls.id], title="API")
    service.create_relationship(router.id, api.id, realizes.id)
    service.create_relationship(gateway.id, api.id, realizes.id)

    # A second taxonomy whose content must not leak into the first's counts.
    other = service.create_taxonomy(title="Other")
    other_scheme = service.create_scheme(other.id, title="Other scheme")
    other_cls = service.create_class(other_scheme.id, title="Other class")
    service.create_individual(class_ids=[other_cls.id], title="Elsewhere")
    service.create_property_definition(
        identifier="other_prop", title="Other prop", domain_class_id=other_cls.id
    )
    return {
        "taxonomy": tax,
        "app": app,
        "empty": empty,
        "component": component,
        "service": service_cls,
    }


class TestCountByScheme:
    def test_counts_every_scheme_in_title_order(self, repo, model):
        counts = repo.count_by_scheme(model["taxonomy"].id)

        assert [c.scheme_id for c in counts] == [model["app"].id, model["empty"].id]
        app, empty = counts
        assert (app.class_count, app.individual_count, app.property_definition_count) == (
            2,
            3,
            2,
        )
        assert (empty.class_count, empty.individual_count, empty.property_definition_count) == (
            0,
            0,
            0,
        )

    def test_unknown_taxonomy_has_no_schemes(self, repo, model):
        assert repo.count_by_scheme("missing") == []


class TestCountByClass:
    def test_counts_every_class_in_title_order(self, repo, model):
        counts = repo.count_by_class(model["app"].id)

        assert [c.class_id for c in counts] == [model["component"].id, model["service"].id]
        component, service_cls = counts
        assert component.individual_count == 2
        assert component.property_definition_count == 2
        assert component.relationship_count == 2
        assert service_cls.individual_count == 2
        assert service_cls.property_definition_count == 0
        assert service_cls.relationship_count == 1

    def test_empty_scheme_has_no_classes(self, repo, model):
        assert repo.count_by_class(model["empty"].id) == []


class TestPropertyDefinitionsByDomain:
    def test_list_and_count_filter_by_domain_class(self, repo, model):
        component_id = model["component"].id

        props = repo.list_property_definitions(domain_class_id=component_id, sort_by="title")

        assert [p.identifier for p in props] == ["realizes", "uses"]
        assert props[0].range_class_id == model["service"].id
        assert repo.count_property_definitions(domain_class_id=component_id) == 2
        assert repo.count_property_definitions(domain_class_id=model["service"].id) == 0
