"""
Integration tests (#1483): bundle v1 carries the predicate catalog, each
relationship type's structure (cardinality, hierarchy, symmetric), its typed
edge attributes and derived flags as fields; `constraints` keeps only the
client's leftover metadata. v0 still imports.
"""

import copy

import pytest

from domain.interchange.bundle import BundleError, BundleExporter, plan_bundle
from tests.integration.interchange.test_bundle import (  # noqa: F401 - fixtures
    BUNDLE,
    HOUSE_BUNDLE,
    _kit_bundle,
    authored,
    _assert_round_trip_writes_nothing,
    _taxonomy_id,
    by_key,
    house_with_kits,
    importer,
    load_bundle,
    read_bundle,
    repo,
    service,
    session_factory,
)


def _house_v1(importer, repo):
    load_bundle(importer, house_with_kits())
    return BundleExporter(repo).export(_taxonomy_id(repo, "house"))


def test_v1_carries_predicates_structure_edge_attributes_and_derived(importer, repo):
    exported = _house_v1(importer, repo)

    assert exported["version"] == 1
    identifiers = [p["identifier"] for p in exported["predicates"]]
    assert identifiers == sorted(identifiers) and "part_of" in identifiers
    assert set(exported["predicates"][0]) >= {"identifier", "title", "description"}
    part_of = by_key(exported["properties"], "identifier", "house_place_part_of_place")
    assert part_of["cardinality"] == {
        "min_per_source": 0,
        "max_per_source": 1,
        "max_per_target": None,
    }
    assert (part_of["hierarchy"], part_of["symmetric"], part_of["derived"]) == (True, False, False)
    for prop in exported["properties"]:
        assert not {"min", "max", "hierarchy", "symmetric", "edge_properties", "derived"} & set(
            prop["constraints"]
        )
    requires = by_key(exported["properties"], "identifier", "house_activity_requires_resource")
    assert [(a["identifier"], a["datatype"]) for a in requires["attributes"]] == [
        ("quantity", "number"),
        ("unit", "string"),
        ("optional", "boolean"),
    ]
    assert all("derived" in c for c in exported["classes"])


def test_a_v1_round_trip_plans_nothing(importer, repo, session_factory):
    exported = _house_v1(importer, repo)
    load_bundle(importer, exported)

    again = _assert_round_trip_writes_nothing(
        importer, repo, session_factory, _taxonomy_id(repo, "house")
    )

    assert again == exported


def test_v1_changes_plan_predicate_structure_and_edge_attribute_operations(importer, repo):
    exported = _house_v1(importer, repo)
    changed = copy.deepcopy(exported)
    changed["predicates"].append(
        {"identifier": "next_to", "title": "next to", "description": "Beside"}
    )
    part_of = by_key(changed["properties"], "identifier", "house_place_part_of_place")
    part_of["cardinality"]["max_per_target"] = 3
    requires = by_key(changed["properties"], "identifier", "house_activity_requires_resource")
    requires["attributes"].append(
        {"identifier": "weight", "title": "Weight", "datatype": "number", "description": None}
    )

    plan = plan_bundle(repo, changed)

    ops = {(o.op.value, o.kind.value): o for o in plan.operations}
    assert ops[("create", "predicate")].fields["identifier"] == "next_to"
    assert ops[("update", "property")].fields == {"max_per_target": 3}
    weight = ops[("create", "attribute")].fields
    assert (weight["identifier"], weight["datatype"]) == ("weight", "number")
    assert weight["property_definition_id"] == repo.get_property_definition_by_identifier(
        "house_activity_requires_resource"
    ).id


def test_a_v0_bundle_with_a_new_predicate_plans_it(importer, repo):
    """v0 has no catalog: its properties' predicate strings build it (#1483)."""
    load_bundle(importer, read_bundle(HOUSE_BUNDLE))
    v0 = read_bundle(HOUSE_BUNDLE)
    v0["properties"][0]["predicate"] = "contained_in"

    plan = plan_bundle(repo, v0)

    created = [o for o in plan.operations if o.kind.value == "predicate"]
    assert [o.fields["identifier"] for o in created] == ["contained_in"]


def _kit_export_with_new_edge(importer, repo, attributes):
    """The kit bundle as v1, with a new resource and a kit edge to it."""
    load_bundle(importer, _kit_bundle())
    exported = BundleExporter(repo).export(_taxonomy_id(repo, "house"))
    exported["individuals"].append(
        {"id": "nails", "classes": ["house_resource"], "title": "Nails", "description": None, "data": {}}
    )
    exported["relationships"].append(
        {
            "source": "hang",
            "property": "house_activity_requires_resource",
            "target": "nails",
            "attributes": attributes,
        }
    )
    return exported


def _edge_attribute(repo, name):
    requires = repo.get_property_definition_by_identifier("house_activity_requires_resource")
    [attribute] = [
        a
        for a in repo.list_attribute_definitions(property_definition_id=requires.id, limit=None)
        if a.identifier == name
    ]
    return attribute


def test_a_new_allowed_value_applies_before_the_relationship_using_it(importer, service, repo):
    load_bundle(importer, _kit_bundle())
    service.update_attribute_definition(_edge_attribute(repo, "unit").id, allowed_values=["each"])
    exported = _kit_export_with_new_edge(importer, repo, {"unit": "box"})
    requires = by_key(exported["properties"], "identifier", "house_activity_requires_resource")
    by_key(requires["attributes"], "identifier", "unit")["allowed_values"] = ["each", "box"]

    plan = plan_bundle(repo, exported)
    load_bundle(importer, exported)

    kinds = [(o.op.value, o.kind.value) for o in plan.operations]
    assert kinds.index(("update", "attribute")) < kinds.index(("create", "relationship"))
    assert _edge_attribute(repo, "unit").allowed_values == ["each", "box"]


def test_a_v1_edge_retype_applies_before_the_relationship_using_it(importer, repo):
    exported = _kit_export_with_new_edge(importer, repo, {"quantity": "a few"})
    requires = by_key(exported["properties"], "identifier", "house_activity_requires_resource")
    by_key(requires["attributes"], "identifier", "quantity")["datatype"] = "string"

    load_bundle(importer, exported)

    assert str(getattr(_edge_attribute(repo, "quantity").datatype, "value", "")) == "string"


def test_a_v0_import_leaves_a_class_attribute_default_alone(importer, service, repo):
    load_bundle(importer, copy.deepcopy(BUNDLE))
    [estimate] = [
        a for a in repo.list_attribute_definitions(limit=None) if a.identifier == "house_estimate_minutes"
    ]
    service.update_attribute_definition(estimate.id, default_value="15")

    assert plan_bundle(repo, copy.deepcopy(BUNDLE)).changed == 0


def test_v1_defaults_are_typed_json(importer, repo, authored):
    exported = BundleExporter(repo).export(authored["taxonomy"].id)
    bed = by_key(exported["classes"], "identifier", "garden_bed")
    bed["attributes"] += [
        {"identifier": "g_int", "title": "Int", "datatype": "integer", "description": None, "default": 5},
        {"identifier": "g_flag", "title": "Flag", "datatype": "boolean", "description": None, "default": True},
        {"identifier": "g_text", "title": "Text", "datatype": "string", "description": None, "default": "x"},
    ]

    load_bundle(importer, exported)
    again = BundleExporter(repo).export(authored["taxonomy"].id)

    stored = {a.identifier: a.default_value for a in repo.list_attribute_definitions(limit=None)}
    assert (stored["g_int"], stored["g_flag"], stored["g_text"]) == ("5", "true", "x")
    defaults = {
        a["identifier"]: a.get("default")
        for a in by_key(again["classes"], "identifier", "garden_bed")["attributes"]
    }
    assert (defaults["g_int"], defaults["g_flag"], defaults["g_text"]) == (5, True, "x")
    assert plan_bundle(repo, again).changed == 0


def test_a_list_default_is_refused_by_name(repo, authored):
    exported = BundleExporter(repo).export(authored["taxonomy"].id)
    bed = by_key(exported["classes"], "identifier", "garden_bed")
    bed["attributes"].append(
        {"identifier": "g_list", "title": "List", "datatype": "string", "description": None, "default": [1]}
    )

    with pytest.raises(BundleError, match="g_list"):
        plan_bundle(repo, exported)


def test_v1_removes_a_derived_key_from_individual_data(importer, repo):
    bundle = copy.deepcopy(BUNDLE)
    bundle["individuals"][0]["data"] = {"aliases": ["clean"], "derived": "from kit"}
    load_bundle(importer, bundle)
    exported = BundleExporter(repo).export(_taxonomy_id(repo, "house"))
    individual = by_key(exported["individuals"], "id", bundle["individuals"][0]["id"])
    del individual["data"]["derived"]

    load_bundle(importer, exported)

    again = BundleExporter(repo).export(_taxonomy_id(repo, "house"))
    assert "derived" not in by_key(again["individuals"], "id", individual["id"])["data"]
