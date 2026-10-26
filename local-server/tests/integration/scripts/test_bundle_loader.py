"""
Integration tests for the bundle loader (#1338): a small House-shaped bundle
loaded into a fresh SQLite workspace through the import service the CLI uses.
Covers what lands, change events, idempotent reloads, updates, carried
metadata, the identifier guards and the stale report.
"""

import copy
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base, ChangeEvent
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from scripts.bundle_loader import BundleError, load_bundle, read_bundle
from scripts.import_bundle import build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService

BUNDLE = {
    "format": "context-studio-bundle",
    "version": 0,
    "source": "house",
    "taxonomy": {
        "identifier": "house",
        "title": "House",
        "description": "Household tasks filed by place and activity.",
        "vision": "# House\n\nThe graph is memory and vocabulary.",
    },
    "schemes": [
        {"identifier": "house_kinds", "title": "Kinds", "description": "Node kinds."},
    ],
    "classes": [
        {
            "identifier": "house_room",
            "scheme": "house_kinds",
            "parent": "house_place",
            "title": "Room",
            "description": "A room inside a floor.",
        },
        {
            "identifier": "house_place",
            "scheme": "house_kinds",
            "title": "Place",
            "description": "A room or area where tasks happen.",
        },
        {
            "identifier": "house_activity",
            "scheme": "house_kinds",
            "title": "Activity",
            "description": "A type of work, general to specific.",
            "attributes": [
                {
                    "identifier": "house_estimate_minutes",
                    "title": "Estimate (minutes)",
                    "datatype": "integer",
                }
            ],
        },
    ],
    "properties": [
        {
            "identifier": "house_activity_is_a_activity",
            "title": "activity is a activity",
            "description": "General to specific.",
            "predicate": "is_a",
            "domain": "house_activity",
            "range": "house_activity",
            "constraints": {"hierarchy": True, "acyclic": True},
        }
    ],
    "individuals": [
        {
            "id": "cleaning",
            "classes": ["house_activity"],
            "title": "Cleaning",
            "description": "Making a space clean.",
            "data": {"aliases": ["clean", "cleanup"]},
        },
        {
            "id": "vacuuming",
            "classes": ["house_activity"],
            "title": "Vacuuming",
            "description": "Cleaning floors with a vacuum.",
            "data": {"aliases": ["hoover"], "estimate_minutes": 20},
        },
    ],
    "relationships": [
        {"source": "vacuuming", "property": "house_activity_is_a_activity", "target": "cleaning"}
    ],
}


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture()
def service(session_factory):
    return build_import_service(session_factory, FakeEmbeddingService())


def _bundle(**changes):
    bundle = copy.deepcopy(BUNDLE)
    bundle.update(changes)
    return bundle


def test_bundle_lands_as_taxonomy_schemes_classes_properties_and_individuals(service, repo):
    summary = load_bundle(service, repo, _bundle())

    taxonomy = repo.get_by_identifier("house")
    assert taxonomy.description == "Household tasks filed by place and activity."
    assert taxonomy.vision.startswith("# House")
    room = repo.get_by_identifier("house_room")
    assert room.parent_class_id == repo.get_by_identifier("house_place").id
    prop = repo.get_property_definition_by_identifier("house_activity_is_a_activity")
    assert prop.canonical_predicate == "is_a"
    [house_ref] = [r for r in prop.external_references if r.source == "house"]
    assert dict(house_ref.metadata) == {"hierarchy": True, "acyclic": True}
    activity = repo.get_by_identifier("house_activity")
    individuals = {i.title: i for i in repo.list_individuals(class_id=activity.id, limit=None)}
    [vacuum_ref] = individuals["Vacuuming"].external_references
    assert vacuum_ref.identifier == "vacuuming"
    assert dict(vacuum_ref.metadata) == {"aliases": ["hoover"], "estimate_minutes": 20}
    assert repo.list_relationships(
        source_id=individuals["Vacuuming"].id,
        target_id=individuals["Cleaning"].id,
        property_id=prop.id,
        limit=None,
    )
    assert summary.kind("class").created == 3
    assert summary.kind("attribute").created == 1
    assert summary.kind("relationship").created == 1
    assert summary.stale == []


def test_load_records_change_events(service, repo, session_factory):
    load_bundle(service, repo, _bundle())

    with session_factory() as session:
        types = {e.entity_type for e in session.query(ChangeEvent).all()}
    assert {"taxonomy", "concept_scheme", "class", "property_definition", "individual"} <= types
    assert "relationship" in types


def test_reloading_the_same_bundle_changes_nothing(service, repo, session_factory):
    load_bundle(service, repo, _bundle())
    with session_factory() as session:
        events_before = session.query(ChangeEvent).count()

    summary = load_bundle(service, repo, _bundle())

    assert summary.changed == 0
    with session_factory() as session:
        assert session.query(ChangeEvent).count() == events_before


def test_reload_applies_changes(service, repo):
    load_bundle(service, repo, _bundle())
    changed = _bundle()
    changed["taxonomy"]["vision"] = "# House\n\nRevised."
    changed["classes"][0]["parent"] = None
    changed["individuals"][1]["data"] = {"aliases": ["hoover", "vacuum"]}

    summary = load_bundle(service, repo, changed)

    assert repo.get_by_identifier("house").vision == "# House\n\nRevised."
    assert repo.get_by_identifier("house_room").parent_class_id is None
    activity = repo.get_by_identifier("house_activity")
    vacuum = next(
        i for i in repo.list_individuals(class_id=activity.id, limit=None) if i.title == "Vacuuming"
    )
    assert dict(vacuum.external_references[0].metadata) == {"aliases": ["hoover", "vacuum"]}
    assert summary.kind("taxonomy").updated == 1
    assert summary.kind("class").updated == 1
    assert summary.kind("individual").updated == 1


def test_entities_dropped_from_the_bundle_are_reported_not_deleted(service, repo):
    load_bundle(service, repo, _bundle())
    smaller = _bundle(relationships=[])
    smaller["individuals"] = smaller["individuals"][:1]

    summary = load_bundle(service, repo, smaller)

    assert summary.stale == ["Individual 'Vacuuming' (vacuuming)"]
    activity = repo.get_by_identifier("house_activity")
    assert len(repo.list_individuals(class_id=activity.id, limit=None)) == 2


def test_identifier_owned_by_another_taxonomy_is_refused(service, repo):
    other = service.create_taxonomy(title="Other", identifier="other")
    service.create_scheme(taxonomy_id=other.id, title="Kinds", identifier="house_kinds")

    with pytest.raises(BundleError, match="house_kinds"):
        load_bundle(service, repo, _bundle())


def test_relationship_with_attributes_is_rejected(service, repo):
    bundle = _bundle()
    bundle["relationships"][0]["quantity"] = 2

    with pytest.raises(BundleError, match="attributes"):
        load_bundle(service, repo, bundle)


def test_class_hierarchy_cycle_is_rejected(service, repo):
    bundle = _bundle()
    bundle["classes"][1]["parent"] = "house_room"

    with pytest.raises(BundleError, match="cycle"):
        load_bundle(service, repo, bundle)


def test_read_bundle_checks_the_header(tmp_path):
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({"format": "something-else", "version": 0}))

    with pytest.raises(BundleError, match="not a context-studio-bundle v0"):
        read_bundle(path)
