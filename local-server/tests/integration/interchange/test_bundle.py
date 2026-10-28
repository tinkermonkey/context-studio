"""
Integration tests for bundle load (#1338) and export (#1362) against a fresh
SQLite workspace, through the import service the CLI uses. Covers what lands,
change events, idempotent reloads, updates, carried metadata, the identifier
guards, the stale report, and load -> export -> load round trips for the real
House bundle and for a taxonomy authored in Context Studio.
"""

import copy
import json
import os
import sys
from pathlib import Path
from types import MappingProxyType

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite import models
from adapters.persistence.sqlite.models import Base, ChangeEvent
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.interchange.bundle import BundleError, BundleExporter, load_bundle
from domain.ontology.value_objects import ExternalReference
from scripts.import_bundle import build_import_service, read_bundle
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

    assert summary.stale == [
        "Individual 'Vacuuming' (vacuuming)",
        "Relationship 'Vacuuming' house_activity_is_a_activity 'Cleaning'",
    ]
    activity = repo.get_by_identifier("house_activity")
    assert len(repo.list_individuals(class_id=activity.id, limit=None)) == 2


def test_identifier_owned_by_another_taxonomy_is_refused(service, repo):
    other = service.create_taxonomy(title="Other", identifier="other")
    service.create_scheme(taxonomy_id=other.id, title="Kinds", identifier="house_kinds")

    with pytest.raises(BundleError, match="house_kinds"):
        load_bundle(service, repo, _bundle())


def test_relationship_with_unknown_keys_is_rejected(service, repo):
    bundle = _bundle()
    bundle["relationships"][0]["quantity"] = 2

    with pytest.raises(BundleError, match=r"unknown keys \['quantity'\]; edge values go in"):
        load_bundle(service, repo, bundle)


def test_relationship_attributes_the_property_does_not_list_are_refused(service, repo):
    bundle = _bundle()
    bundle["relationships"][0]["attributes"] = {"quantity": 2}

    with pytest.raises(BundleError, match=r"carries attributes \['quantity'\].*allowed: none"):
        load_bundle(service, repo, bundle)
    assert repo.get_by_identifier("house") is None  # refused before anything was written


def test_relationship_attributes_must_be_scalars(service, repo):
    bundle = _kit_bundle()
    bundle["relationships"][-1]["attributes"] = {"quantity": {"value": 2}}

    with pytest.raises(BundleError, match="string, number, boolean or null"):
        load_bundle(service, repo, bundle)


def _kit_bundle():
    """The test bundle plus resources and a kit: hanging a picture requires hooks and a level."""
    bundle = _bundle()
    bundle["classes"].append(
        {
            "identifier": "house_resource",
            "scheme": "house_kinds",
            "title": "Resource",
            "description": "A kind of thing you use.",
        }
    )
    bundle["properties"].append(
        {
            "identifier": "house_activity_requires_resource",
            "title": "activity requires resource",
            "description": "What an activity needs.",
            "predicate": "requires",
            "domain": "house_activity",
            "range": "house_resource",
            "constraints": {"edge_properties": ["quantity", "unit", "optional"]},
        }
    )
    bundle["individuals"] += [
        {"id": "hang", "classes": ["house_activity"], "title": "Hang a picture"},
        {
            "id": "hooks",
            "classes": ["house_resource"],
            "title": "Picture hooks",
            "description": "Small hooks.",
            "data": {},
        },
        {
            "id": "level",
            "classes": ["house_resource"],
            "title": "Level",
            "description": "A spirit level.",
            "data": {},
        },
    ]
    requires = "house_activity_requires_resource"
    bundle["relationships"] += [
        {
            "source": "hang",
            "property": requires,
            "target": "hooks",
            "attributes": {"quantity": 2, "unit": "each"},
        },
        {
            "source": "hang",
            "property": requires,
            "target": "level",
            "attributes": {"optional": True},
        },
    ]
    return bundle


def _kit(repo):
    """The kit's relationships' attributes by target title."""
    hang = next(
        i
        for i in repo.list_individuals(
            class_id=repo.get_by_identifier("house_activity").id, limit=None
        )
        if i.title == "Hang a picture"
    )
    return {
        repo.get_individual(rel.target_id).title: rel.attributes
        for rel in repo.list_relationships(source_id=hang.id, limit=None)
    }


def test_relationship_attributes_load_reload_and_update(service, repo, session_factory):
    summary = load_bundle(service, repo, _kit_bundle())
    assert summary.kind("relationship").created == 3
    assert _kit(repo) == {
        "Picture hooks": {"quantity": 2, "unit": "each"},
        "Level": {"optional": True},
    }

    before = _written(session_factory)
    assert load_bundle(service, repo, _kit_bundle()).changed == 0
    assert _written(session_factory) == before

    changed = _kit_bundle()
    changed["relationships"][1]["attributes"] = {"quantity": 3, "unit": "each"}
    del changed["relationships"][2]["attributes"]
    summary = load_bundle(service, repo, changed)

    assert summary.kind("relationship").updated == 2
    assert _kit(repo) == {"Picture hooks": {"quantity": 3, "unit": "each"}, "Level": {}}
    with session_factory() as session:
        updates = (
            session.query(ChangeEvent)
            .filter(ChangeEvent.entity_type == "relationship", ChangeEvent.operation == "update")
            .all()
        )
    assert sorted(e.previous_state["attributes"].get("quantity", 0) for e in updates) == [0, 2]


def test_relationship_attributes_are_exported_and_round_trip(service, repo, session_factory):
    load_bundle(service, repo, _kit_bundle())

    exported = _assert_round_trip_writes_nothing(
        service, repo, session_factory, _taxonomy_id(repo, "house")
    )

    kit = [r for r in exported["relationships"] if r["source"] == "hang"]
    assert kit == [
        {
            "source": "hang",
            "property": "house_activity_requires_resource",
            "target": "hooks",
            "attributes": {"quantity": 2, "unit": "each"},
        },
        {
            "source": "hang",
            "property": "house_activity_requires_resource",
            "target": "level",
            "attributes": {"optional": True},
        },
    ]
    assert "attributes" not in next(r for r in exported["relationships"] if r["source"] != "hang")


def test_class_hierarchy_cycle_is_rejected(service, repo):
    bundle = _bundle()
    bundle["classes"][1]["parent"] = "house_room"

    with pytest.raises(BundleError, match="cycle"):
        load_bundle(service, repo, bundle)


def test_read_bundle_checks_the_header(tmp_path):
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({"format": "something-else", "version": 0}))

    with pytest.raises(BundleError, match="Not a context-studio-bundle v0"):
        read_bundle(path)


def test_dropping_an_attributes_enum_and_description_applies_once(service, repo):
    bundle = _bundle()
    bundle["classes"][2]["attributes"][0].update(
        {"description": "Typical minutes.", "allowed_values": ["5", "10"]}
    )
    load_bundle(service, repo, bundle)

    first = load_bundle(service, repo, _bundle())
    second = load_bundle(service, repo, _bundle())

    activity = repo.get_by_identifier("house_activity")
    [attribute] = service.list_attribute_definitions(class_id=activity.id, limit=None)
    assert not attribute.allowed_values
    assert not attribute.description
    assert first.kind("attribute").updated == 1
    assert second.changed == 0


def test_class_moves_to_another_scheme_and_parent(service, repo):
    load_bundle(service, repo, _bundle())
    moved = _bundle()
    moved["schemes"].append({"identifier": "house_spaces", "title": "Spaces"})
    moved["classes"][1]["scheme"] = "house_spaces"  # Place
    moved["classes"][0]["scheme"] = "house_spaces"  # Room, still under Place

    summary = load_bundle(service, repo, moved)

    spaces = repo.get_by_identifier("house_spaces")
    place = repo.get_by_identifier("house_place")
    room = repo.get_by_identifier("house_room")
    assert place.concept_scheme_id == spaces.id
    assert room.concept_scheme_id == spaces.id
    assert room.parent_class_id == place.id
    assert summary.kind("class").updated == 2
    assert load_bundle(service, repo, moved).changed == 0


def test_dropped_relationships_and_attributes_are_reported(service, repo):
    load_bundle(service, repo, _bundle())
    smaller = _bundle(relationships=[])
    smaller["classes"][2]["attributes"] = []

    summary = load_bundle(service, repo, smaller)

    assert "Relationship 'Vacuuming' house_activity_is_a_activity 'Cleaning'" in summary.stale
    assert (
        "AttributeDefinition 'Estimate (minutes)' (house_estimate_minutes) on 'Activity'"
        in summary.stale
    )


def test_hand_made_class_is_matched_without_writes(service, repo, session_factory):
    """A class made by hand is matched on its identifier; nothing about it is rewritten."""
    taxonomy = service.create_taxonomy(
        title="House",
        identifier="house",
        description=BUNDLE["taxonomy"]["description"],
        vision=BUNDLE["taxonomy"]["vision"],
    )
    scheme = service.create_scheme(
        taxonomy_id=taxonomy.id, title="Kinds", identifier="house_kinds", description="Node kinds."
    )
    place = service.create_class(
        concept_scheme_id=scheme.id,
        title="Place",
        description="A room or area where tasks happen.",
        identifier="house_place",
    )
    with session_factory() as session:
        before = session.query(ChangeEvent).filter(ChangeEvent.entity_id == place.id).count()

    summary = load_bundle(service, repo, _bundle())

    assert repo.get_by_identifier("house_place").external_references == []
    assert summary.kind("class").unchanged == 1
    with session_factory() as session:
        after = session.query(ChangeEvent).filter(ChangeEvent.entity_id == place.id).count()
    assert after == before


def test_unrelated_relationship_type_is_refused(service, repo):
    service.create_property_definition(
        identifier="house_activity_is_a_activity", title="Someone else's is_a"
    )

    with pytest.raises(BundleError, match="does not lie within this taxonomy"):
        load_bundle(service, repo, _bundle())


def test_relationship_type_reaching_another_taxonomy_is_refused_not_retargeted(service, repo):
    """A type with one end here and one elsewhere is not this bundle's to rewrite."""
    load_bundle(service, repo, _bundle())
    other = service.create_taxonomy(title="Other", identifier="other")
    scheme = service.create_scheme(taxonomy_id=other.id, title="Kinds", identifier="other_kinds")
    site = service.create_class(concept_scheme_id=scheme.id, title="Site", identifier="other_site")
    activity = repo.get_by_identifier("house_activity")
    service.create_property_definition(
        identifier="house_done_at",
        title="done at (a Site)",
        domain_class_id=activity.id,
        range_class_id=site.id,
    )
    bundle = _bundle()
    bundle["properties"].append(
        {
            "identifier": "house_done_at",
            "title": "done at",
            "domain": "house_activity",
            "range": "house_place",
        }
    )

    with pytest.raises(BundleError, match="house_done_at"):
        load_bundle(service, repo, bundle)
    prop = repo.get_property_definition_by_identifier("house_done_at")
    assert (prop.title, prop.range_class_id) == ("done at (a Site)", site.id)


# ---------------------------------------------------------------- round trips

# A snapshot of the House repo's ontology/house.bundle.json (tinkermonkey/house#32).
HOUSE_BUNDLE = Path(__file__).parent.parent / "fixtures" / "bundles" / "house.bundle.json"


def _written(session_factory) -> dict[str, int]:
    """Row counts of everything a load can write."""
    with session_factory() as session:
        return {
            model.__name__: session.query(model).count()
            for model in (
                models.OntologyEntity,
                models.IndividualClass,
                models.Relationship,
                models.PropertyDefinition,
                models.AttributeDefinition,
                ChangeEvent,
            )
        }


def _taxonomy_id(repo, identifier):
    return repo.get_by_identifier(identifier).id


def _normalized(bundle):
    """A bundle with list order and absent-vs-empty optional class keys made irrelevant."""
    result = copy.deepcopy(bundle)
    for kind, key in (
        ("schemes", "identifier"),
        ("classes", "identifier"),
        ("properties", "identifier"),
        ("individuals", "id"),
    ):
        result[kind] = sorted(result[kind], key=lambda entry: entry[key])
    for cls in result["classes"]:
        cls.setdefault("parent", None)
        cls.setdefault("attributes", [])
    result["relationships"] = sorted(
        result["relationships"], key=lambda r: (r["source"], r["property"], r["target"])
    )
    return result


def _assert_round_trip_writes_nothing(service, repo, session_factory, taxonomy_id):
    exported = BundleExporter(repo).export(taxonomy_id)
    before = _written(session_factory)

    summary = load_bundle(service, repo, exported)

    assert summary.changed == 0, summary.counts
    assert summary.stale == []
    assert _written(session_factory) == before
    assert BundleExporter(repo).export(taxonomy_id) == exported
    return exported


def test_house_bundle_round_trip_writes_nothing(service, repo, session_factory):
    house = read_bundle(HOUSE_BUNDLE)
    load_bundle(service, repo, house)

    exported = _assert_round_trip_writes_nothing(
        service, repo, session_factory, _taxonomy_id(repo, "house")
    )

    assert _normalized(exported) == _normalized(house)


def house_with_kits():
    """
    The real House bundle plus kits as House emits them: resources, and `requires`
    edges from starter activities carrying quantity, unit and optional.
    """
    house = read_bundle(HOUSE_BUNDLE)
    house["individuals"] += [
        {
            "id": "kit_hooks",
            "classes": ["house_resource_supply"],
            "title": "Picture hooks",
            "description": "Small hooks.",
            "data": {},
        },
        {
            "id": "kit_hammer",
            "classes": ["house_resource_tool"],
            "title": "Hammer",
            "description": "A claw hammer.",
            "data": {},
        },
        {
            "id": "kit_level",
            "classes": ["house_resource_tool"],
            "title": "Level",
            "description": "A spirit level.",
            "data": {},
        },
    ]
    requires = "house_activity_requires_resource"
    house["relationships"] += [
        {
            "source": "starter_hang_a_picture",
            "property": requires,
            "target": "kit_hooks",
            "attributes": {"quantity": 2, "unit": "each", "optional": False},
        },
        {
            "source": "starter_hang_a_picture",
            "property": requires,
            "target": "kit_hammer",
            "attributes": {"quantity": 1, "unit": "each"},
        },
        {
            "source": "starter_hang_a_shelf",
            "property": requires,
            "target": "kit_level",
            "attributes": {"optional": True},
        },
    ]
    return house


def test_house_bundle_with_kits_round_trip_writes_nothing(service, repo, session_factory):
    house = house_with_kits()
    load_bundle(service, repo, house)

    exported = _assert_round_trip_writes_nothing(
        service, repo, session_factory, _taxonomy_id(repo, "house")
    )

    assert _normalized(exported) == _normalized(house)


def test_reference_identifier_that_differs_from_the_key_is_kept(service, repo, session_factory):
    """The DR importer keys references by spec id, not by the entity identifier."""
    load_bundle(service, repo, _bundle())
    prop = repo.get_property_definition_by_identifier("house_activity_is_a_activity")
    spec_reference = ExternalReference(
        source="house",
        identifier="house.activity.is-a.activity",
        uri="https://example.test/is-a",
        metadata=MappingProxyType({"hierarchy": True, "acyclic": True}),
    )
    service.update_property_definition(prop.id, external_references=[spec_reference])

    exported = _assert_round_trip_writes_nothing(
        service, repo, session_factory, _taxonomy_id(repo, "house")
    )
    [spec] = exported["properties"]
    spec["constraints"] = {"hierarchy": True}
    load_bundle(service, repo, exported)

    [reference] = repo.get_property_definition_by_identifier(
        "house_activity_is_a_activity"
    ).external_references
    assert (reference.identifier, reference.uri) == (spec_reference.identifier, spec_reference.uri)
    assert dict(reference.metadata) == {"hierarchy": True}


@pytest.fixture()
def authored(service):
    """A taxonomy built in Context Studio: no bundle source references anywhere."""
    taxonomy = service.create_taxonomy(
        title="Garden", identifier="garden", description="Beds and plants."
    )
    scheme = service.create_scheme(
        taxonomy_id=taxonomy.id, title="Kinds", identifier="garden_kinds"
    )
    bed = service.create_class(concept_scheme_id=scheme.id, title="Bed", identifier="garden_bed")
    raised = service.create_class(
        concept_scheme_id=scheme.id,
        title="Raised bed",
        identifier="garden_raised_bed",
        parent_class_id=bed.id,
    )
    plant = service.create_class(
        concept_scheme_id=scheme.id, title="Plant", identifier="garden_plant"
    )
    # Left at the default sort_order 0, as the UI creates them.
    for identifier, title in (("garden_sun", "Sun"), ("garden_soil", "Soil")):
        service.create_attribute_definition(
            class_id=bed.id, identifier=identifier, title=title, datatype="string"
        )
    grows_in = service.create_property_definition(
        identifier="garden_grows_in",
        title="grows in",
        canonical_predicate="grows_in",
        domain_class_id=plant.id,
        range_class_id=bed.id,
    )
    north = service.create_individual([raised.id], title="North bed")
    tomato = service.create_individual([plant.id], title="Tomato", description="Cherry.")
    service.create_relationship(tomato.id, north.id, grows_in.id)
    return {"taxonomy": taxonomy, "tomato": tomato, "north": north}


def test_authored_taxonomy_round_trip_writes_nothing(service, repo, session_factory, authored):
    tomato, north = authored["tomato"], authored["north"]

    exported = _assert_round_trip_writes_nothing(
        service, repo, session_factory, authored["taxonomy"].id
    )

    assert exported["source"] == "garden"
    assert {i["id"] for i in exported["individuals"]} == {tomato.id, north.id}
    assert exported["relationships"] == [
        {"source": tomato.id, "property": "garden_grows_in", "target": north.id}
    ]
    assert repo.get_individual(tomato.id).external_references == []


def test_retitling_tied_attributes_settles_in_one_load(service, repo, authored):
    """Sun and Soil both sit at sort_order 0; renaming Sun would flip the tie-break."""
    taxonomy_id = authored["taxonomy"].id
    bundle = BundleExporter(repo).export(taxonomy_id)
    [bed] = [c for c in bundle["classes"] if c["identifier"] == "garden_bed"]
    assert [a["identifier"] for a in bed["attributes"]] == ["garden_soil", "garden_sun"]
    bed["attributes"][1]["title"] = "Aspect"

    first = load_bundle(service, repo, bundle)
    second = load_bundle(service, repo, bundle)

    assert first.kind("attribute").updated >= 1
    assert second.changed == 0
    [bed] = [
        c
        for c in BundleExporter(repo).export(taxonomy_id)["classes"]
        if c["identifier"] == "garden_bed"
    ]
    assert [a["identifier"] for a in bed["attributes"]] == ["garden_soil", "garden_sun"]


def test_authored_bundle_reproduces_in_another_workspace(repo, authored):
    exported = BundleExporter(repo).export(authored["taxonomy"].id)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    other_factory = sessionmaker(bind=engine)
    other_repo = SQLiteOntologyRepository(other_factory)

    load_bundle(build_import_service(other_factory, FakeEmbeddingService()), other_repo, exported)

    assert BundleExporter(other_repo).export(_taxonomy_id(other_repo, "garden")) == exported
    engine.dispose()


def test_individual_added_in_context_studio_round_trips_without_duplicates(
    service, repo, session_factory
):
    load_bundle(service, repo, _bundle())
    activity = repo.get_by_identifier("house_activity")
    mopping = service.create_individual([activity.id], title="Mopping")

    exported = _assert_round_trip_writes_nothing(
        service, repo, session_factory, _taxonomy_id(repo, "house")
    )

    assert mopping.id in {i["id"] for i in exported["individuals"]}
    titles = [i.title for i in repo.list_individuals(class_id=activity.id, limit=None)]
    assert titles.count("Mopping") == 1


def test_mixed_loaded_and_authored_entities_round_trip_writes_nothing(
    service, repo, session_factory
):
    """House as loaded, plus a class, attribute, type, individuals and links made here."""
    load_bundle(service, repo, read_bundle(HOUSE_BUNDLE))
    place = repo.get_by_identifier("house_place")
    activity = repo.get_by_identifier("house_activity")
    shed = service.create_class(
        concept_scheme_id=place.concept_scheme_id,
        title="Shed",
        identifier="house_place_shed",
        parent_class_id=place.id,
    )
    service.create_attribute_definition(
        class_id=place.id, identifier="house_floor_area", title="Floor area", datatype="integer"
    )
    stored_in = service.create_property_definition(
        identifier="house_activity_stored_in_shed",
        title="activity gear stored in shed",
        domain_class_id=activity.id,
        range_class_id=shed.id,
    )
    garden_shed = service.create_individual([shed.id], title="Garden shed")
    edging = service.create_individual([activity.id], title="Edging the lawn")
    vacuuming = next(
        i for i in repo.list_individuals(class_id=activity.id, limit=None) if i.title == "Vacuuming"
    )
    service.create_relationship(edging.id, garden_shed.id, stored_in.id)
    service.create_relationship(vacuuming.id, garden_shed.id, stored_in.id)
    is_a = repo.get_property_definition_by_identifier("house_activity_is_a_activity")
    cleaning = next(
        i for i in repo.list_individuals(class_id=activity.id, limit=None) if i.title == "Cleaning"
    )
    service.create_relationship(edging.id, cleaning.id, is_a.id)

    exported = _assert_round_trip_writes_nothing(
        service, repo, session_factory, _taxonomy_id(repo, "house")
    )

    assert {"house_place_shed"} <= {c["identifier"] for c in exported["classes"]}
    assert {
        (edging.id, "house_activity_stored_in_shed", garden_shed.id),
        (edging.id, "house_activity_is_a_activity", "starter_cleaning"),
        ("starter_vacuuming", "house_activity_stored_in_shed", garden_shed.id),
    } <= {(r["source"], r["property"], r["target"]) for r in exported["relationships"]}
    assert repo.get_property_definition(stored_in.id).external_references == []


def test_uuid_id_does_not_match_an_individual_in_another_taxonomy(service, repo):
    load_bundle(service, repo, _bundle())
    other = service.create_taxonomy(title="Other", identifier="other")
    scheme = service.create_scheme(taxonomy_id=other.id, title="Kinds", identifier="other_kinds")
    thing = service.create_class(concept_scheme_id=scheme.id, title="Thing", identifier="o_thing")
    outsider = service.create_individual([thing.id], title="Outsider")
    bundle = _bundle()
    bundle["individuals"].append(
        {"id": outsider.id, "classes": ["house_activity"], "title": "Insider", "data": {}}
    )

    summary = load_bundle(service, repo, bundle)

    assert summary.kind("individual").created == 1
    after = repo.get_individual(outsider.id)
    assert (after.title, after.class_ids, after.external_references) == (
        "Outsider",
        [thing.id],
        [],
    )
    activity = repo.get_by_identifier("house_activity")
    [insider] = [
        i for i in repo.list_individuals(class_id=activity.id, limit=None) if i.title == "Insider"
    ]
    assert [(r.source, r.identifier) for r in insider.external_references] == [
        ("house", outsider.id)
    ]


def test_data_for_a_context_studio_individual_is_carried_on_reload(service, repo):
    load_bundle(service, repo, _bundle())
    activity = repo.get_by_identifier("house_activity")
    mopping = service.create_individual([activity.id], title="Mopping")
    bundle = BundleExporter(repo).export(_taxonomy_id(repo, "house"))
    next(i for i in bundle["individuals"] if i["id"] == mopping.id)["data"] = {"aliases": ["mop"]}

    summary = load_bundle(service, repo, bundle)

    [reference] = repo.get_individual(mopping.id).external_references
    assert (reference.source, reference.identifier) == ("house", mopping.id)
    assert dict(reference.metadata) == {"aliases": ["mop"]}
    assert summary.kind("individual").updated == 1


def test_export_refuses_a_class_without_an_identifier(service, repo, authored):
    scheme = repo.get_by_identifier("garden_kinds")
    service.create_class(concept_scheme_id=scheme.id, title="Path")

    with pytest.raises(BundleError, match="Class 'Path'"):
        BundleExporter(repo).export(authored["taxonomy"].id)
