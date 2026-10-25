"""Unit tests for ontology entity snapshots (delete snapshots that revert rebuilds from, #1295)."""

import json
from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.snapshots import entity_from_snapshot, entity_snapshot
from domain.ontology.value_objects import (
    DataPropertyValue,
    DataType,
    ExternalReference,
    LexicalSense,
    OntologyMapping,
    Status,
)

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
REF = ExternalReference(
    source="wikidata",
    identifier="Q1",
    uri="https://www.wikidata.org/wiki/Q1",
    metadata=MappingProxyType({"label": "universe"}),
)
SENSE = LexicalSense(label="animal", language_code="en", sense_type="synset")

ENTITIES = [
    (
        "taxonomy",
        Taxonomy(
            id="tx-1",
            title="Tax",
            identifier="tax",
            description="A taxonomy",
            color="#ffffff",
            created_at=NOW,
            last_modified=NOW,
            version=3,
            status=Status.PUBLISHED,
        ),
    ),
    (
        "concept_scheme",
        ConceptScheme(
            id="cs-1",
            taxonomy_id="tx-1",
            title="Scheme",
            identifier="scheme",
            description="A scheme",
            color="#000000",
            status=Status.PUBLISHED,
        ),
    ),
    (
        "class",
        Class(
            id="cls-1",
            concept_scheme_id="cs-1",
            taxonomy_id="tx-1",
            title="Animal",
            identifier="animal",
            description="An organism",
            color="#aabbcc",
            parent_class_id="cls-0",
            structural_property_id="prop-0",
            external_references=[REF],
            lexical_senses=[SENSE],
            data_properties=[DataPropertyValue("legs", 4, "xsd:integer")],
            created_at=NOW,
            status=Status.PUBLISHED,
            source_run_id="run-1",
        ),
    ),
    (
        "individual",
        Individual(
            id="ind-1",
            class_ids=["cls-1", "cls-2"],
            title="Rex",
            description="A dog",
            data_properties=[DataPropertyValue("age", 3), DataPropertyValue("good", True)],
            external_references=[REF],
            last_modified=NOW,
            version=2,
            status=Status.PUBLISHED,
            source_run_id="run-1",
        ),
    ),
    (
        "relationship",
        Relationship(
            id="rel-1",
            source_id="ind-1",
            target_id="ind-2",
            property_definition_id="prop-1",
            created_at=NOW,
            source_run_id="run-1",
        ),
    ),
    (
        "property_definition",
        PropertyDefinition(
            id="prop-1",
            identifier="owns",
            title="owns",
            description="Has as property",
            canonical_predicate="owns",
            ontology_mapping=OntologyMapping("prop-1", "ext-1", "exact_match"),
            domain_class_id="cls-1",
            range_class_id="cls-2",
            external_references=[REF],
            is_relevant=True,
            lexical_senses=[SENSE],
            status=Status.PUBLISHED,
        ),
    ),
    (
        "attribute_definition",
        AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="legs",
            title="Legs",
            datatype=DataType.INTEGER,
            description="Number of legs",
            is_required=True,
            allowed_values=["2", "4"],
            default_value="4",
            sort_order=1,
            external_references=[REF],
            created_at=NOW,
            status=Status.PUBLISHED,
            source_run_id="run-1",
        ),
    ),
]


@pytest.mark.parametrize("entity_type,entity", ENTITIES, ids=[e[0] for e in ENTITIES])
def test_snapshot_round_trips_every_field_through_json(entity_type, entity):
    """A snapshot survives JSON storage and rebuilds an equal entity."""
    stored = json.loads(json.dumps(entity_snapshot(entity)))

    assert entity_from_snapshot(entity_type, stored, entity.id) == entity


def test_snapshot_leaves_out_the_derived_embedding():
    """The class embedding is recomputed on re-index, so it is not snapshotted."""
    cls = Class(id="c", concept_scheme_id="cs", taxonomy_id="tx", title="T", embedding=[0.1])

    snapshot = entity_snapshot(cls)

    assert "embedding" not in snapshot
    assert entity_from_snapshot("class", snapshot, "c") == replace(cls, embedding=None)


def test_minimal_snapshot_missing_required_fields_raises_clear_error():
    """An older snapshot without class_ids cannot rebuild an individual."""
    with pytest.raises(ValueError, match="snapshot is incomplete"):
        entity_from_snapshot("individual", {"individual_id": "ind-1", "title": "Rex"}, "ind-1")


def test_unknown_entity_type_raises():
    with pytest.raises(ValueError, match="Unknown entity type"):
        entity_from_snapshot("widget", {"id": "w"}, "w")
