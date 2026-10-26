"""
Integration tests: moving a concept scheme to another taxonomy is stored, carries
the scheme's classes along, and survives a restart.

File-backed SQLite so a "restart" is a new engine and repository on the same file.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "local.db"


def _open(db_path):
    """Open the workspace database as the app does at startup."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine, SQLiteOntologyRepository(session_factory=sessionmaker(bind=engine))


@pytest.fixture()
def opened(db_path):
    engine, repo = _open(db_path)
    yield repo
    engine.dispose()


@pytest.fixture()
def service(opened):
    return OntologyService(
        repository=opened,
        embedding_service=FakeEmbeddingService(),
        event_publisher=FakeEventPublisher(),
    )


@pytest.fixture()
def house(service):
    """A House taxonomy with a Places scheme holding two classes and one individual."""
    house = service.create_taxonomy(title="House")
    garden = service.create_taxonomy(title="Garden")
    places = service.create_scheme(taxonomy_id=house.id, title="Places")
    room = service.create_class(concept_scheme_id=places.id, title="Room")
    kitchen = service.create_class(
        concept_scheme_id=places.id, title="Kitchen", parent_class_id=room.id
    )
    service.create_individual(title="Main kitchen", class_ids=[kitchen.id])
    return house, garden, places, [room, kitchen]


def test_move_is_stored_with_the_schemes_classes(service, opened, house):
    """The scheme and every class under it read back in the new taxonomy."""
    house_tax, garden, places, classes = house

    service.update_concept_scheme(places.id, taxonomy_id=garden.id)

    assert opened.get_concept_scheme(places.id).taxonomy_id == garden.id
    assert [opened.get_class(c.id).taxonomy_id for c in classes] == [garden.id, garden.id]
    assert [s.id for s in opened.list_concept_schemes(taxonomy_id=garden.id)] == [places.id]
    assert opened.list_concept_schemes(taxonomy_id=house_tax.id) == []


def test_counts_follow_the_moved_scheme(service, opened, house):
    """Scheme counts for the new taxonomy include the moved classes and individuals."""
    house_tax, garden, places, _ = house

    service.update_concept_scheme(places.id, taxonomy_id=garden.id)

    [counts] = opened.count_by_scheme(garden.id)
    assert (counts.scheme_id, counts.class_count, counts.individual_count) == (places.id, 2, 1)
    assert opened.count_by_scheme(house_tax.id) == []


def test_move_survives_a_restart(service, db_path, house):
    """A fresh engine on the same file sees the moved scheme, classes and counts."""
    _, garden, places, classes = house

    service.update_concept_scheme(places.id, taxonomy_id=garden.id)

    engine, reopened = _open(db_path)
    try:
        assert reopened.get_concept_scheme(places.id).taxonomy_id == garden.id
        assert {reopened.get_class(c.id).taxonomy_id for c in classes} == {garden.id}
        assert [c.class_count for c in reopened.count_by_scheme(garden.id)] == [2]
    finally:
        engine.dispose()


def test_classes_of_other_schemes_stay_put(service, opened, house):
    """Only the moved scheme's classes change taxonomy."""
    house_tax, garden, places, _ = house
    activities = service.create_scheme(taxonomy_id=house_tax.id, title="Activities")
    cooking = service.create_class(concept_scheme_id=activities.id, title="Cooking")

    service.update_concept_scheme(places.id, taxonomy_id=garden.id)

    assert opened.get_class(cooking.id).taxonomy_id == house_tax.id
    assert opened.get_concept_scheme(activities.id).taxonomy_id == house_tax.id
