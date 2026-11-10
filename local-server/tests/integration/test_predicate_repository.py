"""
Integration tests for the predicate catalog in SQLiteOntologyRepository (#1480).

Runs against a file SQLite database built by the production engine factory, so
foreign keys are enforced and sessions don't expire on commit, as in the app.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.models import Predicate as PredicateORM
from adapters.persistence.sqlite.ontology_repo import (
    SQLiteOntologyRepository,
    _extract_constraint_name_from_integrity_error,
)
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Predicate,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.exceptions import DuplicateEntityError, EntityInUseError
from domain.ontology.value_objects import ExternalReference


@pytest.fixture
def session_factory(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def taxonomy(repo):
    return repo.save_taxonomy(Taxonomy(id="tax-a", identifier="tax_a", title="A"))


@pytest.fixture
def other_taxonomy(repo):
    return repo.save_taxonomy(Taxonomy(id="tax-b", identifier="tax_b", title="B"))


def _predicate(predicate_id: str, taxonomy_id: str, identifier: str, **kwargs) -> Predicate:
    return Predicate(id=predicate_id, taxonomy_id=taxonomy_id, identifier=identifier, **kwargs)


def _type(type_id: str, identifier: str, **kwargs) -> PropertyDefinition:
    return PropertyDefinition(id=type_id, identifier=identifier, title=identifier, **kwargs)


def test_save_and_read_a_predicate(repo, taxonomy):
    dr_ref = ExternalReference(
        source="documentation_robotics",
        identifier="navigates-to",
        metadata={"inverse": "navigated-from", "category": "behavioral"},
    )
    saved = repo.save_predicate(
        _predicate(
            "p-1", taxonomy.id, "navigates-to", description="Moves to", external_references=[dr_ref]
        )
    )

    assert saved.version == 1
    assert saved.title == "navigates-to"
    assert saved.created_at is not None and saved.last_modified is not None
    fetched = repo.get_predicate("p-1")
    assert fetched is not None
    assert fetched.description == "Moves to"
    assert fetched.external_references == [dr_ref]
    assert repo.get_predicate_by_identifier(taxonomy.id, "navigates-to").id == "p-1"
    assert repo.get_predicate("missing") is None
    assert repo.get_predicate_by_identifier(taxonomy.id, "missing") is None


def test_list_predicates_is_per_taxonomy_by_identifier(repo, taxonomy, other_taxonomy):
    repo.save_predicate(_predicate("p-2", taxonomy.id, "uses"))
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    repo.save_predicate(_predicate("p-3", other_taxonomy.id, "causes"))

    assert [p.identifier for p in repo.list_predicates(taxonomy.id)] == ["part_of", "uses"]
    assert [p.identifier for p in repo.list_predicates(other_taxonomy.id)] == ["causes"]


def test_update_bumps_version_and_keeps_the_taxonomy(repo, taxonomy, other_taxonomy):
    created = repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    created.description = "Is a component of"
    created.taxonomy_id = other_taxonomy.id

    updated = repo.save_predicate(created)

    assert updated.version == 2
    assert updated.description == "Is a component of"
    assert updated.taxonomy_id == taxonomy.id


def test_identifier_is_unique_within_a_taxonomy(repo, taxonomy):
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))

    with pytest.raises(DuplicateEntityError):
        repo.save_predicate(_predicate("p-2", taxonomy.id, "part_of"))
    assert [p.id for p in repo.list_predicates(taxonomy.id)] == ["p-1"]


def test_the_table_constraint_is_recognised(repo, taxonomy, session_factory):
    """A duplicate that slips past the pre-check fails on the table's unique constraint."""
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    with session_factory() as session:
        session.add(
            PredicateORM(id="p-2", taxonomy_id=taxonomy.id, identifier="part_of", title="part_of")
        )
        with pytest.raises(IntegrityError) as caught:
            session.commit()

    assert (
        _extract_constraint_name_from_integrity_error(caught.value)
        == "uk_predicate_taxonomy_identifier"
    )


def test_same_identifier_in_two_taxonomies(repo, taxonomy, other_taxonomy):
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    repo.save_predicate(_predicate("p-2", other_taxonomy.id, "part_of"))

    assert repo.get_predicate_by_identifier(taxonomy.id, "part_of").id == "p-1"
    assert repo.get_predicate_by_identifier(other_taxonomy.id, "part_of").id == "p-2"


def test_canonical_predicate_reads_through_predicate_id(repo, taxonomy):
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    repo.save_predicate(_predicate("p-2", taxonomy.id, "has_part"))

    created = repo.save_property_definition(
        _type("type-1", "wheel_part_of_car", predicate_id="p-1", canonical_predicate="ignored")
    )
    assert created.predicate_id == "p-1"
    assert created.canonical_predicate == "part_of"

    created.predicate_id = "p-2"
    updated = repo.save_property_definition(created)
    assert updated.canonical_predicate == "has_part"
    assert repo.get_property_definition("type-1").canonical_predicate == "has_part"
    assert repo.list_property_definitions(ids=["type-1"])[0].canonical_predicate == "has_part"

    updated.predicate_id = None
    cleared = repo.save_property_definition(updated)
    assert cleared.predicate_id is None
    assert cleared.canonical_predicate is None


def test_taxonomy_filter_on_property_definitions(repo, taxonomy, other_taxonomy):
    repo.save_predicate(_predicate("p-a", taxonomy.id, "part_of"))
    repo.save_predicate(_predicate("p-b", other_taxonomy.id, "part_of"))
    repo.save_property_definition(_type("type-a1", "a_one", predicate_id="p-a"))
    repo.save_property_definition(_type("type-a2", "a_two", predicate_id="p-a"))
    repo.save_property_definition(_type("type-b", "b_one", predicate_id="p-b"))
    repo.save_property_definition(_type("type-none", "no_predicate"))

    in_a = repo.list_property_definitions(taxonomy_id=taxonomy.id, sort_by="title")
    assert [p.id for p in in_a] == ["type-a1", "type-a2"]
    assert repo.count_property_definitions(taxonomy_id=taxonomy.id) == 2
    assert repo.count_property_definitions(taxonomy_id=other_taxonomy.id) == 1
    assert repo.count_property_definitions(taxonomy_id=other_taxonomy.id, query="a_") == 0
    assert repo.count_property_definitions() == 4


def test_taxonomy_filter_combines_with_domain(repo, taxonomy):
    scheme = repo.save_concept_scheme(
        ConceptScheme(id="scheme-1", taxonomy_id=taxonomy.id, identifier="scheme_one", title="S")
    )
    cls = repo.save_class(
        Class(
            id="class-1",
            concept_scheme_id=scheme.id,
            taxonomy_id=taxonomy.id,
            identifier="car",
            title="Car",
        )
    )
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    repo.save_property_definition(
        _type("type-1", "with_domain", predicate_id="p-1", domain_class_id=cls.id)
    )
    repo.save_property_definition(_type("type-2", "without_domain", predicate_id="p-1"))

    found = repo.list_property_definitions(taxonomy_id=taxonomy.id, domain_class_id=cls.id)
    assert [p.id for p in found] == ["type-1"]


def test_a_used_predicate_cannot_be_deleted(repo, taxonomy, session_factory):
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    repo.save_property_definition(_type("type-1", "wheel_part_of_car", predicate_id="p-1"))

    with session_factory() as session:
        session.delete(session.get(PredicateORM, "p-1"))
        with pytest.raises(Exception, match="FOREIGN KEY"):
            session.commit()

    assert repo.get_predicate("p-1") is not None


def test_deleting_a_taxonomy_deletes_its_unused_predicates(repo, taxonomy):
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))

    assert repo.delete_taxonomy(taxonomy.id) is True
    assert repo.get_predicate("p-1") is None


def test_deleting_a_taxonomy_whose_predicates_are_in_use_is_refused(repo, taxonomy):
    repo.save_predicate(_predicate("p-1", taxonomy.id, "part_of"))
    repo.save_property_definition(_type("type-1", "wheel_part_of_car", predicate_id="p-1"))

    with pytest.raises(EntityInUseError):
        repo.delete_taxonomy(taxonomy.id)
    assert repo.get_taxonomy(taxonomy.id) is not None
    assert repo.get_predicate("p-1") is not None


def test_taxonomy_predicate_and_type_in_one_transaction_scope(tmp_path):
    """Each repository call flushes in order, so the FK cycle needs no special handling."""
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'scoped.db'}")
    Base.metadata.create_all(engine)
    shared = SharedSessionFactory(sessionmaker(bind=engine))
    repo = SQLiteOntologyRepository(shared)
    try:
        with SqliteTransactionScope(shared).atomic():
            repo.save_taxonomy(Taxonomy(id="tax-a", identifier="tax_a", title="A"))
            repo.save_predicate(_predicate("p-1", "tax-a", "part_of"))
            saved = repo.save_property_definition(_type("type-1", "a_part", predicate_id="p-1"))
            assert saved.canonical_predicate == "part_of"
        assert repo.get_property_definition("type-1").canonical_predicate == "part_of"
    finally:
        engine.dispose()
