"""
Integration tests for relationship-type structure (#1482) in SQLiteOntologyRepository.

Against a real SQLite database (foreign keys on):
- a relationship type's min_per_source, max_per_source, max_per_target, hierarchy
  and symmetric are saved and read back, on create and on update
- an edge attribute definition belongs to a relationship type: listed by the
  property_definition_id filter, identifier unique per owner, deleted with its type,
  and reported by find_references
- the ck_attribute_one_owner CHECK refuses a row with no owner or with two
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import AttributeDefinition as AttributeDefinitionORM
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.exceptions import DuplicateEntityError


@pytest.fixture
def session_factory():
    """A fresh in-memory database with the ORM schema (foreign keys enforced)."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


@pytest.fixture
def repo(session_factory):
    """The repository under test."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def house(repo):
    """A taxonomy with a resource class, a kit class and a kit_includes_tool type."""
    repo.save_taxonomy(Taxonomy(id="tax", identifier="tax_house", title="House"))
    repo.save_concept_scheme(
        ConceptScheme(id="scheme", taxonomy_id="tax", identifier="scheme_house", title="House")
    )
    for class_id in ("kit", "tool"):
        repo.save_class(
            Class(
                id=class_id,
                taxonomy_id="tax",
                concept_scheme_id="scheme",
                identifier=f"cls_{class_id}",
                title=class_id.title(),
            )
        )
    includes = repo.save_property_definition(
        PropertyDefinition(
            id="includes",
            identifier="kit_includes_tool",
            title="includes",
            domain_class_id="kit",
            range_class_id="tool",
        )
    )
    return includes


def _edge_attribute(type_id: str, identifier: str, sort_order: int = 0, **kwargs):
    return AttributeDefinition(
        id=str(uuid.uuid4()),
        class_id=None,
        property_definition_id=type_id,
        identifier=identifier,
        title=identifier,
        datatype=kwargs.pop("datatype", "string"),
        sort_order=sort_order,
        **kwargs,
    )


class TestRelationshipTypeStructure:
    def test_defaults_on_a_new_type(self, repo, house):
        saved = repo.get_property_definition(house.id)
        assert (saved.min_per_source, saved.max_per_source, saved.max_per_target) == (0, None, None)
        assert (saved.hierarchy, saved.symmetric) == (False, False)

    def test_create_saves_the_structure(self, repo, house):
        repo.save_property_definition(
            PropertyDefinition(
                id="part-of",
                identifier="tool_part_of_tool",
                title="part of",
                domain_class_id="tool",
                range_class_id="tool",
                min_per_source=1,
                max_per_source=1,
                max_per_target=3,
                hierarchy=True,
                symmetric=False,
            )
        )
        saved = repo.get_property_definition("part-of")
        assert (saved.min_per_source, saved.max_per_source, saved.max_per_target) == (1, 1, 3)
        assert (saved.hierarchy, saved.symmetric) == (True, False)

    def test_update_saves_the_structure(self, repo, house):
        house.min_per_source = 1
        house.max_per_source = 2
        house.max_per_target = 1
        house.symmetric = True
        house.hierarchy = True
        repo.save_property_definition(house)
        saved = repo.get_property_definition(house.id)
        assert (saved.min_per_source, saved.max_per_source, saved.max_per_target) == (1, 2, 1)
        assert (saved.hierarchy, saved.symmetric) == (True, True)
        assert saved.version == 2

        saved.max_per_source = None
        saved.hierarchy = False
        repo.save_property_definition(saved)
        again = repo.get_property_definition(house.id)
        assert again.max_per_source is None
        assert again.hierarchy is False


class TestEdgeAttributes:
    def test_save_and_read_an_edge_attribute(self, repo, house):
        unit = repo.save_attribute_definition(
            _edge_attribute(house.id, "unit", allowed_values=["each", "pair"])
        )
        got = repo.get_attribute_definition(unit.id)
        assert got.class_id is None
        assert got.property_definition_id == house.id
        assert got.allowed_values == ["each", "pair"]

    def test_unknown_relationship_type_is_refused(self, repo, house):
        with pytest.raises(ValueError, match="Relationship type"):
            repo.save_attribute_definition(_edge_attribute("missing", "quantity"))

    def test_filter_by_relationship_type(self, repo, house):
        repo.save_attribute_definition(_edge_attribute(house.id, "unit", sort_order=1))
        repo.save_attribute_definition(_edge_attribute(house.id, "quantity", 0, datatype="number"))
        repo.save_attribute_definition(
            AttributeDefinition(
                id="kit-name", class_id="kit", identifier="name", title="Name", datatype="string"
            )
        )

        edge = repo.list_attribute_definitions(property_definition_id=house.id, limit=None)
        assert [a.identifier for a in edge] == ["quantity", "unit"]
        assert [a.identifier for a in repo.list_attribute_definitions(class_id="kit")] == ["name"]
        assert len(repo.list_attribute_definitions(limit=None)) == 3
        assert repo.count_attribute_definitions(class_id="kit") == 1
        assert repo.count_attribute_definitions() == 3

    def test_identifier_is_unique_per_owner(self, repo, house):
        repo.save_attribute_definition(_edge_attribute(house.id, "quantity"))
        with pytest.raises(DuplicateEntityError, match="property_definition_id"):
            repo.save_attribute_definition(_edge_attribute(house.id, "quantity"))

        # The same identifier on a class, or on another type, is fine
        repo.save_attribute_definition(
            AttributeDefinition(
                id="kit-quantity",
                class_id="kit",
                identifier="quantity",
                title="Quantity",
                datatype="number",
            )
        )
        repo.save_property_definition(
            PropertyDefinition(id="other", identifier="kit_needs_tool", title="needs")
        )
        repo.save_attribute_definition(_edge_attribute("other", "quantity"))
        assert repo.count_attribute_definitions() == 3

    def test_the_unique_constraint_backs_the_check(self, session_factory, repo, house):
        repo.save_attribute_definition(_edge_attribute(house.id, "note"))
        with session_factory() as session:
            session.add(_orm_row(house.id, None, "note"))
            with pytest.raises(IntegrityError, match="property_definition_id"):
                session.commit()

    @pytest.mark.parametrize(
        "class_id, property_definition_id", [(None, None), ("kit", "includes")]
    )
    def test_exactly_one_owner_is_enforced_by_the_database(
        self, session_factory, house, class_id, property_definition_id
    ):
        with session_factory() as session:
            session.add(_orm_row(property_definition_id, class_id, "note"))
            with pytest.raises(IntegrityError, match="ck_attribute_one_owner"):
                session.commit()

    def test_edge_attributes_are_deleted_with_their_type(self, repo, house):
        quantity = repo.save_attribute_definition(_edge_attribute(house.id, "quantity"))
        references = repo.find_references([house.id])
        assert [(r.dependent_id, r.dependent_kind) for r in references] == [
            (quantity.id, "attribute_definition")
        ]

        assert repo.delete_property_definition(house.id) is True
        assert repo.get_attribute_definition(quantity.id) is None


def _orm_row(property_definition_id, class_id, identifier):
    now = datetime.now(timezone.utc)
    return AttributeDefinitionORM(
        id=str(uuid.uuid4()),
        class_id=class_id,
        property_definition_id=property_definition_id,
        identifier=identifier,
        title=identifier,
        datatype="string",
        is_required=False,
        sort_order=0,
        external_references=[],
        status="draft",
        version=1,
        created_at=now,
        last_modified=now,
    )
