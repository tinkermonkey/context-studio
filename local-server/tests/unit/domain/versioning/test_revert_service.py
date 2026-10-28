"""
Unit tests for RevertService.

Tests that:
1. Revert walks change_events in reverse and applies inverse operations
2. Revert is idempotent (calling twice produces same state)
3. Revert emits new change_events with batch_run_id tracking
4. Round-trip: apply -> revert yields original ontology state
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

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
from domain.ontology.events import GraphInvalidated
from domain.ontology.snapshots import entity_snapshot
from domain.ontology.value_objects import DataType, ExternalReference
from domain.versioning.exceptions import RevertConflictError
from domain.versioning.revert_service import RevertService
from domain.versioning.value_objects import ChangeOperation
from tests.fakes.fake_change_repository import FakeChangeRepository
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_individual_vector_index import FakeIndividualVectorIndex
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_schema_vector_index import FakeSchemaVectorIndex

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def ontology_repo():
    repo = FakeOntologyRepository()
    tx = Taxonomy(id="tx-1", identifier="test_tax", title="Test Taxonomy")
    scheme = ConceptScheme(
        id="scheme-1",
        taxonomy_id="tx-1",
        identifier="test_scheme",
        title="Test Scheme",
    )
    repo.save_taxonomy(tx)
    repo.save_concept_scheme(scheme)
    return repo


@pytest.fixture()
def change_repo():
    return FakeChangeRepository()


@pytest.fixture()
def revert_svc(change_repo, ontology_repo):
    return RevertService(change_repo, ontology_repo)


# ============================================================================
# Revert Class Creation
# ============================================================================


def test_revert_deletes_created_class(ontology_repo, change_repo, revert_svc):
    """Reverting a CREATE operation deletes the created class."""
    # Create a class
    cls = Class(
        id="cls-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Animal",
    )
    ontology_repo.save_class(cls)

    # Record the creation event
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "cls-1",
            "concept_scheme_id": "scheme-1",
            "taxonomy_id": "tx-1",
            "title": "Animal",
        },
        batch_run_id="run-1",
    )

    # Verify class exists
    assert ontology_repo.get_class("cls-1") is not None

    # Revert
    events_reverted = revert_svc.revert("run-1")
    assert events_reverted == 1

    # Verify class is deleted
    assert ontology_repo.get_class("cls-1") is None


def test_revert_individual_creation(ontology_repo, change_repo, revert_svc):
    """Reverting a created individual deletes it."""
    # Create an individual
    ind = Individual(
        id="ind-1",
        class_ids=["cls-1"],
        title="Alice",
    )
    ontology_repo.save_individual(ind)

    # Record the creation event
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "ind-1",
            "class_ids": ["cls-1"],
            "title": "Alice",
            "status": "draft",
        },
        batch_run_id="run-1",
    )

    # Revert
    events_reverted = revert_svc.revert("run-1")
    assert events_reverted == 1
    assert ontology_repo.get_individual("ind-1") is None


# ============================================================================
# Revert Updates
# ============================================================================


def test_revert_class_update(ontology_repo, change_repo, revert_svc):
    """Reverting an UPDATE operation restores previous state."""
    # Create and save a class with initial description
    cls = Class(
        id="cls-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Animal",
        description="An organism",
    )
    ontology_repo.save_class(cls)

    # Record an update event that changed the description
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"description": "An organism"},
        new_state={"description": "A living being"},
        batch_run_id="run-1",
    )

    # Update the class manually to simulate the change
    cls.description = "A living being"
    ontology_repo.save_class(cls)

    # Verify updated state
    assert ontology_repo.get_class("cls-1").description == "A living being"

    # Revert
    events_reverted = revert_svc.revert("run-1")
    assert events_reverted == 1

    # Verify previous state is restored
    assert ontology_repo.get_class("cls-1").description == "An organism"


def test_revert_changes_nothing_when_an_event_cannot_be_undone(
    ontology_repo, change_repo, revert_svc
):
    """An event the revert can't undo is caught before any other event is undone."""
    ontology_repo.save_class(
        Class(
            id="cls-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tx-1",
            title="Animal",
            description="A living being",
        )
    )
    # Undone last (oldest): names a field the class doesn't have.
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"parent_id": None},
        new_state={"parent_id": "cls-0"},
        batch_run_id="run-1",
    )
    # Undone first (newest): fine on its own.
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"description": "An organism"},
        new_state={"description": "A living being"},
        batch_run_id="run-1",
    )

    with pytest.raises(ValueError, match=r"nothing was changed.*unknown fields \['parent_id'\]"):
        revert_svc.revert("run-1")

    assert ontology_repo.get_class("cls-1").description == "A living being"


def test_revert_chained_updates_restores_oldest_state(ontology_repo, change_repo, revert_svc):
    """Two updates in one run revert newest first, ending at the original state."""
    cls = Class(
        id="cls-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Animal",
        description="C",
    )
    ontology_repo.save_class(cls)
    for previous, new in (("A", "B"), ("B", "C")):
        change_repo.record_change(
            entity_id="cls-1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"description": previous},
            new_state={"description": new},
            batch_run_id="run-1",
        )

    assert revert_svc.revert("run-1") == 2

    assert ontology_repo.get_class("cls-1").description == "A"


# ============================================================================
# Idempotence Tests
# ============================================================================


def test_revert_is_idempotent(ontology_repo, change_repo, revert_svc):
    """Calling revert twice produces the same state without error."""
    cls = Class(
        id="cls-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Animal",
    )
    ontology_repo.save_class(cls)

    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-1", "title": "Animal"},
        batch_run_id="run-1",
    )

    # First revert
    events_reverted_first = revert_svc.revert("run-1")
    assert events_reverted_first == 1
    state_after_first_revert = ontology_repo.get_class("cls-1")
    assert state_after_first_revert is None

    # Second revert (should not error and produce same state)
    # The original events are skipped because a corresponding revert event exists for them
    events_reverted_second = revert_svc.revert("run-1")
    assert events_reverted_second == 0
    state_after_second_revert = ontology_repo.get_class("cls-1")

    # State should be identical
    assert state_after_second_revert is None
    assert state_after_first_revert == state_after_second_revert


def test_revert_multiple_operations_same_run(ontology_repo, change_repo, revert_svc):
    """Revert handles multiple operations in the same run correctly."""
    # Create multiple entities
    cls = Class(
        id="cls-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Animal",
    )
    ontology_repo.save_class(cls)

    ind = Individual(id="ind-1", class_ids=["cls-1"], title="Alice")
    ontology_repo.save_individual(ind)

    # Record events in order
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-1", "title": "Animal"},
        batch_run_id="run-1",
    )
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.CREATE,
        new_state={"id": "ind-1", "class_ids": ["cls-1"], "title": "Alice"},
        batch_run_id="run-1",
    )

    # Revert
    events_reverted = revert_svc.revert("run-1")
    assert events_reverted == 2

    # Both entities should be deleted
    assert ontology_repo.get_class("cls-1") is None
    assert ontology_repo.get_individual("ind-1") is None


# ============================================================================
# Round-Trip Tests (Apply → Revert)
# ============================================================================


def test_revert_restores_ontology_after_apply(ontology_repo, change_repo, revert_svc):
    """Apply then revert returns ontology to original state."""
    # Save initial state
    initial_class_count = len(list(ontology_repo.list_classes(limit=None)))

    # Apply: create a class
    cls = Class(
        id="cls-new",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="NewClass",
    )
    ontology_repo.save_class(cls)

    change_repo.record_change(
        entity_id="cls-new",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-new", "title": "NewClass"},
        batch_run_id="run-1",
    )

    # Verify class was created
    assert len(list(ontology_repo.list_classes(limit=None))) == initial_class_count + 1

    # Revert
    revert_svc.revert("run-1")

    # Verify ontology returned to initial state
    assert len(list(ontology_repo.list_classes(limit=None))) == initial_class_count


# ============================================================================
# Change Event Emission
# ============================================================================


def test_revert_emits_change_events_with_batch_run_id(ontology_repo, change_repo, revert_svc):
    """Revert emits new change_events tagged with originating run_id."""
    cls = Class(
        id="cls-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Animal",
    )
    ontology_repo.save_class(cls)

    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-1", "title": "Animal"},
        batch_run_id="run-1",
    )

    # Revert
    revert_svc.revert("run-1")

    # Check that new events were recorded
    history = change_repo.get_changes(limit=None)
    revert_events = [e for e in history.events if "_reverted_" in (e.change_reason or "")]
    assert len(revert_events) > 0
    assert all(e.batch_run_id == "run-1" for e in revert_events)


# ============================================================================
# Round-Trip Tests per Pipeline Type (Simulated Apply → Revert)
# ============================================================================


def test_schema_extraction_roundtrip(ontology_repo, change_repo, revert_svc):
    """Simulate schema extraction: create class and property, then revert."""
    # Simulate apply: create class and property definition
    cls = Class(
        id="cls-service",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Service",
    )
    prop = PropertyDefinition(
        id="prop-1",
        identifier="has_client",
        title="Has Client",
    )
    ontology_repo.save_class(cls)
    ontology_repo.save_property_definition(prop)

    # Record creation events (as apply service would)
    change_repo.record_change(
        entity_id="cls-service",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-service", "title": "Service"},
        batch_run_id="run-schema",
    )
    change_repo.record_change(
        entity_id="prop-1",
        entity_type="property_definition",
        operation=ChangeOperation.CREATE,
        new_state={"id": "prop-1", "identifier": "has_client", "title": "Has Client"},
        batch_run_id="run-schema",
    )

    # Verify entities exist
    assert ontology_repo.get_class("cls-service") is not None
    assert ontology_repo.get_property_definition("prop-1") is not None

    # Revert
    events_reverted = revert_svc.revert("run-schema")
    assert events_reverted == 2

    # Verify entities are deleted
    assert ontology_repo.get_class("cls-service") is None
    assert ontology_repo.get_property_definition("prop-1") is None


def test_individual_extraction_roundtrip(ontology_repo, change_repo, revert_svc):
    """Simulate individual extraction: create individuals and relationships, then revert."""
    # Create classes first
    cls = Class(
        id="cls-person",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Person",
    )
    ontology_repo.save_class(cls)

    # Simulate apply: create individuals
    ind1 = Individual(id="ind-alice", class_ids=["cls-person"], title="Alice")
    ind2 = Individual(id="ind-bob", class_ids=["cls-person"], title="Bob")
    ontology_repo.save_individual(ind1)
    ontology_repo.save_individual(ind2)

    # Record creation events
    change_repo.record_change(
        entity_id="ind-alice",
        entity_type="individual",
        operation=ChangeOperation.CREATE,
        new_state={"id": "ind-alice", "class_ids": ["cls-person"], "title": "Alice"},
        batch_run_id="run-individual",
    )
    change_repo.record_change(
        entity_id="ind-bob",
        entity_type="individual",
        operation=ChangeOperation.CREATE,
        new_state={"id": "ind-bob", "class_ids": ["cls-person"], "title": "Bob"},
        batch_run_id="run-individual",
    )

    # Verify entities exist
    assert ontology_repo.get_individual("ind-alice") is not None
    assert ontology_repo.get_individual("ind-bob") is not None

    # Revert
    events_reverted = revert_svc.revert("run-individual")
    assert events_reverted == 2

    # Verify entities are deleted
    assert ontology_repo.get_individual("ind-alice") is None
    assert ontology_repo.get_individual("ind-bob") is None


def test_connection_refinement_roundtrip(ontology_repo, change_repo, revert_svc):
    """Simulate connection refinement: create relationships, then revert."""
    # Create classes and property definition first
    cls1 = Class(
        id="cls-service",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Service",
    )
    cls2 = Class(
        id="cls-client",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Client",
    )
    prop = PropertyDefinition(
        id="prop-1",
        identifier="has_client",
        title="Has Client",
    )
    ontology_repo.save_class(cls1)
    ontology_repo.save_class(cls2)
    ontology_repo.save_property_definition(prop)

    # Simulate apply: create relationship
    rel = Relationship(
        id="rel-1",
        source_id="cls-service",
        target_id="cls-client",
        property_definition_id="prop-1",
    )
    ontology_repo.save_relationship(rel)

    # Record creation event
    change_repo.record_change(
        entity_id="rel-1",
        entity_type="relationship",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "rel-1",
            "source_id": "cls-service",
            "target_id": "cls-client",
            "property_definition_id": "prop-1",
        },
        batch_run_id="run-connection",
    )

    # Verify relationship exists
    assert ontology_repo.get_relationship("rel-1") is not None

    # Revert
    events_reverted = revert_svc.revert("run-connection")
    assert events_reverted == 1

    # Verify relationship is deleted
    assert ontology_repo.get_relationship("rel-1") is None


def test_schema_node_definition_refinement_roundtrip(ontology_repo, change_repo, revert_svc):
    """Simulate schema node definition refinement: update class, then revert."""
    # Create a class first
    cls = Class(
        id="cls-microservice",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Microservice",
        description="Old definition",
    )
    ontology_repo.save_class(cls)

    # Simulate apply: update the class description
    original_description = "Old definition"
    refined_description = "A small, independent service"
    cls.description = refined_description
    ontology_repo.save_class(cls)

    # Record update event
    change_repo.record_change(
        entity_id="cls-microservice",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"description": original_description},
        new_state={"description": refined_description},
        batch_run_id="run-definition-refinement",
    )

    # Verify class has refined description
    assert ontology_repo.get_class("cls-microservice").description == refined_description

    # Revert
    events_reverted = revert_svc.revert("run-definition-refinement")
    assert events_reverted == 1

    # Verify class has original description
    assert ontology_repo.get_class("cls-microservice").description == original_description


def test_schema_node_grounding_roundtrip(ontology_repo, change_repo, revert_svc):
    """Simulate schema node grounding: add external references, then revert."""
    # Create a class first
    cls = Class(
        id="cls-service",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Service",
    )
    ontology_repo.save_class(cls)

    # Simulate apply: add external reference via relationship
    # (Grounding typically creates relationships to external entities)
    prop = PropertyDefinition(
        id="prop-grounded-in",
        identifier="grounded_in",
        title="Grounded In",
    )
    ontology_repo.save_property_definition(prop)

    rel = Relationship(
        id="rel-grounding-1",
        source_id="cls-service",
        target_id="wikidata-q1",  # External reference ID
        property_definition_id="prop-grounded-in",
    )
    ontology_repo.save_relationship(rel)

    # Record creation events
    change_repo.record_change(
        entity_id="rel-grounding-1",
        entity_type="relationship",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "rel-grounding-1",
            "source_id": "cls-service",
            "target_id": "wikidata-q1",
            "property_definition_id": "prop-grounded-in",
        },
        batch_run_id="run-grounding",
    )

    # Verify relationship (grounding) exists
    assert ontology_repo.get_relationship("rel-grounding-1") is not None

    # Revert
    events_reverted = revert_svc.revert("run-grounding")
    assert events_reverted == 1

    # Verify relationship is deleted
    assert ontology_repo.get_relationship("rel-grounding-1") is None


# ============================================================================
# _inverse_delete Tests (DELETE Revert)
# ============================================================================


def test_inverse_delete_taxonomy(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete recreates a deleted taxonomy from new_state."""
    # Record a DELETE event for a taxonomy (as if it was deleted)
    taxonomy_state = {
        "id": "tax-deleted",
        "title": "Deleted Taxonomy",
        "identifier": "del_tax",
        "description": "A deleted taxonomy",
        "color": "#ff0000",
        "status": "published",
    }
    change_repo.record_change(
        entity_id="tax-deleted",
        entity_type="taxonomy",
        operation=ChangeOperation.DELETE,
        new_state=taxonomy_state,
        batch_run_id="run-delete",
    )

    # Verify taxonomy doesn't exist
    assert ontology_repo.get_taxonomy("tax-deleted") is None

    # Revert (this will apply _inverse_delete)
    events_reverted = revert_svc.revert("run-delete")
    assert events_reverted == 1

    # Verify taxonomy was recreated with correct state
    recreated = ontology_repo.get_taxonomy("tax-deleted")
    assert recreated is not None
    assert recreated.title == "Deleted Taxonomy"
    assert recreated.identifier == "del_tax"
    assert recreated.description == "A deleted taxonomy"
    assert recreated.color == "#ff0000"


def test_inverse_delete_concept_scheme(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete recreates a deleted concept scheme."""
    concept_scheme_state = {
        "id": "scheme-deleted",
        "taxonomy_id": "tx-1",
        "title": "Deleted Scheme",
        "identifier": "del_scheme",
        "description": "A deleted scheme",
        "status": "published",
    }
    change_repo.record_change(
        entity_id="scheme-deleted",
        entity_type="concept_scheme",
        operation=ChangeOperation.DELETE,
        new_state=concept_scheme_state,
        batch_run_id="run-delete",
    )

    # Verify doesn't exist
    assert ontology_repo.get_concept_scheme("scheme-deleted") is None

    # Revert
    events_reverted = revert_svc.revert("run-delete")
    assert events_reverted == 1

    # Verify was recreated
    recreated = ontology_repo.get_concept_scheme("scheme-deleted")
    assert recreated is not None
    assert recreated.title == "Deleted Scheme"
    assert recreated.taxonomy_id == "tx-1"


def _move_scheme_in_run(ontology_repo, change_repo):
    """Move scheme-1 (with one class) from tx-1 to tx-2 and record it in run-move."""
    ontology_repo.save_taxonomy(Taxonomy(id="tx-2", identifier="other_tax", title="Other"))
    ontology_repo.save_class(
        Class(id="cls-1", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Animal")
    )
    scheme = ontology_repo.get_concept_scheme("scheme-1")
    scheme.taxonomy_id = "tx-2"
    ontology_repo.save_concept_scheme(scheme)
    change_repo.record_change(
        entity_id="scheme-1",
        entity_type="concept_scheme",
        operation=ChangeOperation.UPDATE,
        previous_state={"taxonomy_id": "tx-1"},
        new_state={"taxonomy_id": "tx-2"},
        batch_run_id="run-move",
    )


def test_revert_scheme_move_restores_scheme_and_classes(ontology_repo, change_repo, revert_svc):
    """Reverting a run that moved a scheme moves it, and its classes, back."""
    _move_scheme_in_run(ontology_repo, change_repo)
    assert ontology_repo.get_class("cls-1").taxonomy_id == "tx-2"

    assert revert_svc.revert("run-move") == 1

    assert ontology_repo.get_concept_scheme("scheme-1").taxonomy_id == "tx-1"
    assert ontology_repo.get_class("cls-1").taxonomy_id == "tx-1"


def test_revert_scheme_move_invalidates_graph_for_both_taxonomies(ontology_repo, change_repo):
    """The graph is rebuilt after a revert moves a scheme back."""
    publisher = FakeEventPublisher()
    revert_svc = RevertService(change_repo, ontology_repo, event_publisher=publisher)
    _move_scheme_in_run(ontology_repo, change_repo)

    revert_svc.revert("run-move")

    invalidated = publisher.get_events_of_type(GraphInvalidated)
    assert sorted(e.taxonomy_id for e in invalidated) == ["tx-1", "tx-2"]


def _publishing_revert_svc(change_repo, ontology_repo):
    publisher = FakeEventPublisher()
    return RevertService(change_repo, ontology_repo, event_publisher=publisher), publisher


def _invalidated_taxonomies(publisher):
    return sorted(e.taxonomy_id for e in publisher.get_events_of_type(GraphInvalidated))


def test_revert_class_reparent_invalidates_graph(ontology_repo, change_repo):
    """Undoing a class re-parent rebuilds the graph."""
    revert_svc, publisher = _publishing_revert_svc(change_repo, ontology_repo)
    for cls_id in ("cls-a", "cls-b"):
        ontology_repo.save_class(
            Class(id=cls_id, concept_scheme_id="scheme-1", taxonomy_id="tx-1", title=cls_id)
        )
    ontology_repo.save_class(
        Class(
            id="cls-child",
            concept_scheme_id="scheme-1",
            taxonomy_id="tx-1",
            title="Child",
            parent_class_id="cls-b",
        )
    )
    change_repo.record_change(
        entity_id="cls-child",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"parent_class_id": "cls-a"},
        new_state={"parent_class_id": "cls-b"},
        batch_run_id="run-reparent",
    )

    revert_svc.revert("run-reparent")

    assert ontology_repo.get_class("cls-child").parent_class_id == "cls-a"
    assert _invalidated_taxonomies(publisher) == ["tx-1"]


def test_revert_text_edit_invalidates_graph(ontology_repo, change_repo):
    """Any revert that changes the ontology rebuilds the graph, text edits included."""
    revert_svc, publisher = _publishing_revert_svc(change_repo, ontology_repo)
    change_repo.record_change(
        entity_id="scheme-1",
        entity_type="concept_scheme",
        operation=ChangeOperation.UPDATE,
        previous_state={"description": "Old"},
        new_state={"description": "New"},
        batch_run_id="run-edit",
    )

    revert_svc.revert("run-edit")

    assert ontology_repo.get_concept_scheme("scheme-1").description == "Old"
    assert _invalidated_taxonomies(publisher) == ["tx-1"]


def test_revert_individual_create_invalidates_every_taxonomy(ontology_repo, change_repo):
    """Every taxonomy is invalidated, not only the one the reverted individual was in."""
    revert_svc, publisher = _publishing_revert_svc(change_repo, ontology_repo)
    ontology_repo.save_taxonomy(Taxonomy(id="tx-2", identifier="other_tax", title="Other"))
    ontology_repo.save_class(
        Class(id="cls-1", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Animal")
    )
    ontology_repo.save_individual(Individual(id="ind-1", class_ids=["cls-1"], title="Rex"))
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.CREATE,
        new_state={"title": "Rex", "class_ids": ["cls-1"]},
        batch_run_id="run-ind",
    )

    revert_svc.revert("run-ind")

    assert ontology_repo.get_individual("ind-1") is None
    assert _invalidated_taxonomies(publisher) == ["tx-1", "tx-2"]


def test_revert_taxonomy_create_invalidates_the_deleted_taxonomy(ontology_repo, change_repo):
    """A taxonomy the revert deletes is still invalidated."""
    revert_svc, publisher = _publishing_revert_svc(change_repo, ontology_repo)
    ontology_repo.save_taxonomy(Taxonomy(id="tx-new", identifier="new_tax", title="New"))
    change_repo.record_change(
        entity_id="tx-new",
        entity_type="taxonomy",
        operation=ChangeOperation.CREATE,
        new_state={"title": "New"},
        batch_run_id="run-tax",
    )

    revert_svc.revert("run-tax")

    assert ontology_repo.get_taxonomy("tx-new") is None
    assert _invalidated_taxonomies(publisher) == ["tx-1", "tx-new"]


def test_revert_that_fails_partway_still_invalidates_graph(ontology_repo, change_repo):
    """Inverses applied before a failure are committed, so the graph is still invalidated."""
    revert_svc, publisher = _publishing_revert_svc(change_repo, ontology_repo)
    for cls_id in ("cls-first", "cls-second"):
        ontology_repo.save_class(
            Class(id=cls_id, concept_scheme_id="scheme-1", taxonomy_id="tx-1", title=cls_id)
        )
        change_repo.record_change(
            entity_id=cls_id,
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"title": cls_id},
            batch_run_id="run-fail",
        )
    delete_class = ontology_repo.delete_class

    def failing_delete(class_id):
        if class_id == "cls-first":
            raise RuntimeError("database is locked")
        return delete_class(class_id)

    ontology_repo.delete_class = failing_delete

    with pytest.raises(RuntimeError):
        revert_svc.revert("run-fail")

    # Newest first: cls-second was deleted before cls-first failed.
    assert ontology_repo.get_class("cls-second") is None
    assert _invalidated_taxonomies(publisher) == ["tx-1"]


def test_revert_that_changes_nothing_leaves_the_graph_alone(ontology_repo, change_repo):
    """A revert whose entities are already gone does not invalidate the graph."""
    revert_svc, publisher = _publishing_revert_svc(change_repo, ontology_repo)
    change_repo.record_change(
        entity_id="cls-gone",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"title": "Gone"},
        batch_run_id="run-gone",
    )

    assert revert_svc.revert("run-gone") == 0
    assert publisher.get_events_of_type(GraphInvalidated) == []


# ============================================================================
# Extraction runs
# ============================================================================


def _record_extraction_completed(change_repo, run_id):
    """The event ChangeEventRecorder writes when an extraction run completes."""
    change_repo.record_change(
        entity_id=run_id,
        entity_type="extraction_result",
        operation=ChangeOperation.CREATE,
        new_state={"result_id": run_id, "entity_count": 13, "duration_ms": 21066},
        change_reason="Extraction processing completed",
        batch_run_id=run_id,
    )


def test_revert_extraction_run_skips_its_extraction_result(ontology_repo, change_repo):
    """An extraction run reverts cleanly: its record-only event is left alone."""
    revert_svc, publisher = _publishing_revert_svc(change_repo, ontology_repo)
    _record_extraction_completed(change_repo, "run-extract")

    result = revert_svc.revert_with_summary("run-extract")

    assert result.events_reverted == 0
    events = change_repo.get_changes(batch_run_id="run-extract", limit=None).events
    assert [e.entity_type for e in events] == ["extraction_result"]
    assert publisher.get_events_of_type(GraphInvalidated) == []
    # Reverting again is still fine.
    assert revert_svc.revert("run-extract") == 0


def test_revert_run_with_extraction_result_undoes_its_ontology_changes(
    ontology_repo, change_repo, revert_svc
):
    """Ontology events in the same run as an extraction_result are still undone."""
    ontology_repo.save_class(
        Class(id="cls-x", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="X")
    )
    change_repo.record_change(
        entity_id="cls-x",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"title": "X"},
        batch_run_id="run-mixed",
    )
    _record_extraction_completed(change_repo, "run-mixed")

    assert revert_svc.revert("run-mixed") == 1
    assert ontology_repo.get_class("cls-x") is None


def test_revert_refuses_unknown_entity_type_before_changing_anything(
    ontology_repo, change_repo, revert_svc
):
    """A CREATE of an unknown type is caught by the pre-check, not halfway through."""
    ontology_repo.save_class(
        Class(id="cls-y", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Y")
    )
    change_repo.record_change(
        entity_id="cls-y",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"title": "Y"},
        batch_run_id="run-odd",
    )
    change_repo.record_change(
        entity_id="thing-1",
        entity_type="mystery_thing",
        operation=ChangeOperation.CREATE,
        new_state={},
        batch_run_id="run-odd",
    )

    with pytest.raises(ValueError, match="unknown entity type"):
        revert_svc.revert("run-odd")
    assert ontology_repo.get_class("cls-y") is not None


def test_inverse_delete_class(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete recreates a deleted class."""
    class_state = {
        "id": "cls-deleted",
        "taxonomy_id": "tx-1",
        "concept_scheme_id": "scheme-1",
        "title": "Deleted Class",
        "description": "A deleted class",
        "status": "published",
    }
    change_repo.record_change(
        entity_id="cls-deleted",
        entity_type="class",
        operation=ChangeOperation.DELETE,
        new_state=class_state,
        batch_run_id="run-delete",
    )

    # Verify doesn't exist
    assert ontology_repo.get_class("cls-deleted") is None

    # Revert
    events_reverted = revert_svc.revert("run-delete")
    assert events_reverted == 1

    # Verify was recreated
    recreated = ontology_repo.get_class("cls-deleted")
    assert recreated is not None
    assert recreated.title == "Deleted Class"
    assert recreated.taxonomy_id == "tx-1"
    assert recreated.concept_scheme_id == "scheme-1"


def test_inverse_delete_individual(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete recreates a deleted individual."""
    individual_state = {
        "id": "ind-deleted",
        "class_ids": ["cls-1", "cls-2"],
        "title": "Deleted Individual",
        "status": "published",
    }
    change_repo.record_change(
        entity_id="ind-deleted",
        entity_type="individual",
        operation=ChangeOperation.DELETE,
        new_state=individual_state,
        batch_run_id="run-delete",
    )

    # Verify doesn't exist
    assert ontology_repo.get_individual("ind-deleted") is None

    # Revert
    events_reverted = revert_svc.revert("run-delete")
    assert events_reverted == 1

    # Verify was recreated
    recreated = ontology_repo.get_individual("ind-deleted")
    assert recreated is not None
    assert recreated.title == "Deleted Individual"
    assert recreated.class_ids == ["cls-1", "cls-2"]


def test_inverse_delete_relationship(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete recreates a deleted relationship."""
    relationship_state = {
        "id": "rel-deleted",
        "source_id": "cls-1",
        "target_id": "cls-2",
        "property_definition_id": "prop-1",
    }
    change_repo.record_change(
        entity_id="rel-deleted",
        entity_type="relationship",
        operation=ChangeOperation.DELETE,
        new_state=relationship_state,
        batch_run_id="run-delete",
    )

    # Verify doesn't exist
    assert ontology_repo.get_relationship("rel-deleted") is None

    # Revert
    events_reverted = revert_svc.revert("run-delete")
    assert events_reverted == 1

    # Verify was recreated
    recreated = ontology_repo.get_relationship("rel-deleted")
    assert recreated is not None
    assert recreated.source_id == "cls-1"
    assert recreated.target_id == "cls-2"
    assert recreated.property_definition_id == "prop-1"


def test_inverse_delete_relationship_from_recorder_previous_state(
    ontology_repo, change_repo, revert_svc
):
    """A recorder-style DELETE (snapshot in previous_state, empty new_state) reverts."""
    change_repo.record_change(
        entity_id="rel-removed",
        entity_type="relationship",
        operation=ChangeOperation.DELETE,
        new_state={},
        previous_state={
            "relationship_id": "rel-removed",
            "source_id": "cls-1",
            "target_id": "cls-2",
            "property_definition_id": "prop-1",
        },
        batch_run_id="run-recorder-delete",
    )

    assert revert_svc.revert("run-recorder-delete") == 1

    recreated = ontology_repo.get_relationship("rel-removed")
    assert recreated is not None
    assert recreated.source_id == "cls-1"
    assert recreated.target_id == "cls-2"
    # The inverse audit row carries the restored snapshot.
    inverse = [
        e
        for e in change_repo.get_changes(batch_run_id="run-recorder-delete", limit=None).events
        if e.operation == ChangeOperation.CREATE
    ]
    assert inverse and inverse[0].previous_state["source_id"] == "cls-1"


def test_inverse_update_restores_external_references(ontology_repo, change_repo, revert_svc):
    """UPDATE events carrying external_references as dicts restore ExternalReference objects."""
    ontology_repo.save_class(
        Class(
            id="cls-grounded",
            concept_scheme_id="scheme-1",
            taxonomy_id="tx-1",
            title="Grounded",
            external_references=[
                ExternalReference(source="wikidata", identifier="Q1", uri="u1"),
                ExternalReference(source="dbpedia", identifier="D1", uri="u2"),
            ],
        )
    )
    change_repo.record_change(
        entity_id="cls-grounded",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        new_state={"external_references": []},
        previous_state={
            "external_references": [
                {"source": "wikidata", "identifier": "Q1", "uri": "u1", "metadata": None}
            ]
        },
        batch_run_id="run-grounding",
    )

    assert revert_svc.revert("run-grounding") == 1

    restored = ontology_repo.get_class("cls-grounded")
    assert restored.external_references == [
        ExternalReference(source="wikidata", identifier="Q1", uri="u1")
    ]


def test_inverse_delete_property_definition(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete recreates a deleted property definition."""
    property_state = {
        "id": "prop-deleted",
        "identifier": "has_deleted",
        "title": "Deleted Property",
        "description": "A deleted property",
        "status": "published",
    }
    change_repo.record_change(
        entity_id="prop-deleted",
        entity_type="property_definition",
        operation=ChangeOperation.DELETE,
        new_state=property_state,
        batch_run_id="run-delete",
    )

    # Verify doesn't exist
    assert ontology_repo.get_property_definition("prop-deleted") is None

    # Revert
    events_reverted = revert_svc.revert("run-delete")
    assert events_reverted == 1

    # Verify was recreated
    recreated = ontology_repo.get_property_definition("prop-deleted")
    assert recreated is not None
    assert recreated.title == "Deleted Property"
    assert recreated.identifier == "has_deleted"
    assert recreated.description == "A deleted property"


def test_inverse_delete_multiple_entities(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete handles multiple deleted entities correctly."""
    # Record DELETE events for multiple entities
    change_repo.record_change(
        entity_id="cls-del-1",
        entity_type="class",
        operation=ChangeOperation.DELETE,
        new_state={
            "id": "cls-del-1",
            "taxonomy_id": "tx-1",
            "concept_scheme_id": "scheme-1",
            "title": "Class 1",
        },
        batch_run_id="run-delete-multi",
    )
    change_repo.record_change(
        entity_id="cls-del-2",
        entity_type="class",
        operation=ChangeOperation.DELETE,
        new_state={
            "id": "cls-del-2",
            "taxonomy_id": "tx-1",
            "concept_scheme_id": "scheme-1",
            "title": "Class 2",
        },
        batch_run_id="run-delete-multi",
    )
    change_repo.record_change(
        entity_id="ind-del-1",
        entity_type="individual",
        operation=ChangeOperation.DELETE,
        new_state={
            "id": "ind-del-1",
            "class_ids": ["cls-del-1"],
            "title": "Individual 1",
        },
        batch_run_id="run-delete-multi",
    )

    # Verify none exist
    assert ontology_repo.get_class("cls-del-1") is None
    assert ontology_repo.get_class("cls-del-2") is None
    assert ontology_repo.get_individual("ind-del-1") is None

    # Revert
    events_reverted = revert_svc.revert("run-delete-multi")
    assert events_reverted == 3

    # Verify all were recreated
    assert ontology_repo.get_class("cls-del-1") is not None
    assert ontology_repo.get_class("cls-del-2") is not None
    assert ontology_repo.get_individual("ind-del-1") is not None


def test_revert_changes_nothing_when_a_delete_snapshot_is_incomplete(
    ontology_repo, change_repo, revert_svc
):
    """A snapshot too thin to rebuild its entity is caught before anything is undone."""
    ontology_repo.save_class(
        Class(
            id="cls-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tx-1",
            title="Animal",
            description="A living being",
        )
    )
    # Undone last (oldest): the individual's snapshot lacks class_ids.
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.DELETE,
        new_state={},
        previous_state={"id": "ind-1", "title": "Rex"},
        batch_run_id="run-1",
    )
    # Undone first (newest): fine on its own.
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"description": "An organism"},
        new_state={"description": "A living being"},
        batch_run_id="run-1",
    )

    with pytest.raises(ValueError, match="nothing was changed.*snapshot is incomplete"):
        revert_svc.revert("run-1")

    assert ontology_repo.get_class("cls-1").description == "A living being"
    assert ontology_repo.get_individual("ind-1") is None


def test_inverse_delete_with_missing_state_raises_error(ontology_repo, change_repo, revert_svc):
    """Test _inverse_delete raises error when new_state is missing."""
    # Record a DELETE event with empty new_state
    change_repo.record_change(
        entity_id="cls-bad",
        entity_type="class",
        operation=ChangeOperation.DELETE,
        new_state={},  # Missing new_state
        batch_run_id="run-bad",
    )

    # Revert should raise an error
    with pytest.raises(ValueError, match="no snapshot of the deleted entity"):
        revert_svc.revert("run-bad")


# ============================================================================
# Silent No-Op Tests (Issue #1: Independent Entity Deletion)
# ============================================================================


def test_independent_entity_deletion_no_op(ontology_repo, change_repo, revert_svc):
    """
    Test that reverting an entity independently deleted before revert is called
    correctly returns 0 reverted events and does not record a false revert event.

    Scenario: An entity is created by a batch run (CREATE event recorded), but then
    is independently deleted from the ontology before revert is called. When revert
    is called, the entity is already gone, so the inverse operation should be skipped
    and no change event should be recorded.

    This tests the core fix for Issue #1: the revert service should not produce
    false audit trail entries for operations that were never actually performed.
    """
    cls = Class(
        id="cls-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Animal",
    )
    ontology_repo.save_class(cls)

    # Record the creation event for this class
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "cls-1",
            "concept_scheme_id": "scheme-1",
            "taxonomy_id": "tx-1",
            "title": "Animal",
        },
        batch_run_id="run-1",
    )

    # Verify class exists
    assert ontology_repo.get_class("cls-1") is not None

    # Independently delete the entity (not via revert)
    ontology_repo.delete_class("cls-1")
    assert ontology_repo.get_class("cls-1") is None

    # Now try to revert - the entity is already gone
    events_reverted = revert_svc.revert("run-1")

    # Assert that no events were reported as reverted
    # (the inverse operation was not applied because the entity is gone)
    assert events_reverted == 0

    # Verify that no revert change event was recorded
    # (this is the critical fix for Issue #1 - no false audit trail entry)
    history = change_repo.get_changes(limit=None)
    revert_events = [e for e in history.events if "_reverted_" in (e.change_reason or "")]
    assert len(revert_events) == 0, "Should not record a revert event for skipped operation"


# ============================================================================
# Summary Fields Tests
# ============================================================================


def test_revert_with_summary_tracks_taxonomies_deleted(ontology_repo, change_repo, revert_svc):
    """Test that revert_with_summary correctly increments taxonomies_deleted."""
    # Create a taxonomy
    tax = Taxonomy(id="tax-new", identifier="new_tax", title="New Taxonomy for Summary")
    ontology_repo.save_taxonomy(tax)

    # Record the creation event
    change_repo.record_change(
        entity_id="tax-new",
        entity_type="taxonomy",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "tax-new",
            "identifier": "new_tax",
            "title": "New Taxonomy for Summary",
        },
        batch_run_id="run-tax-summary",
    )

    # Revert and get summary
    result = revert_svc.revert_with_summary("run-tax-summary")

    # Verify the taxonomy was deleted and counted
    assert result.taxonomies_deleted == 1
    assert result.events_reverted == 1
    assert ontology_repo.get_taxonomy("tax-new") is None


def test_revert_with_summary_tracks_concept_schemes_deleted(ontology_repo, change_repo, revert_svc):
    """Test that revert_with_summary correctly increments concept_schemes_deleted."""
    # Create a concept scheme
    scheme = ConceptScheme(
        id="scheme-new",
        taxonomy_id="tx-1",
        identifier="new_scheme",
        title="New Scheme for Summary",
    )
    ontology_repo.save_concept_scheme(scheme)

    # Record the creation event
    change_repo.record_change(
        entity_id="scheme-new",
        entity_type="concept_scheme",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "scheme-new",
            "taxonomy_id": "tx-1",
            "identifier": "new_scheme",
            "title": "New Scheme for Summary",
        },
        batch_run_id="run-scheme-summary",
    )

    # Revert and get summary
    result = revert_svc.revert_with_summary("run-scheme-summary")

    # Verify the concept scheme was deleted and counted
    assert result.concept_schemes_deleted == 1
    assert result.events_reverted == 1
    assert ontology_repo.get_concept_scheme("scheme-new") is None


def test_revert_with_summary_mixed_entity_types(ontology_repo, change_repo, revert_svc):
    """Test that revert_with_summary correctly counts all entity type deletions."""
    # Create various entity types
    tax = Taxonomy(id="tax-mixed", identifier="tax_mixed", title="Tax Mixed")
    scheme = ConceptScheme(
        id="scheme-mixed",
        taxonomy_id="tx-1",
        identifier="scheme_mixed",
        title="Scheme Mixed",
    )
    cls = Class(
        id="cls-mixed",
        concept_scheme_id="scheme-1",
        taxonomy_id="tx-1",
        title="Class Mixed",
    )
    ind = Individual(id="ind-mixed", class_ids=["cls-mixed"], title="Individual Mixed")

    ontology_repo.save_taxonomy(tax)
    ontology_repo.save_concept_scheme(scheme)
    ontology_repo.save_class(cls)
    ontology_repo.save_individual(ind)

    # Record creation events for all entity types
    change_repo.record_change(
        entity_id="tax-mixed",
        entity_type="taxonomy",
        operation=ChangeOperation.CREATE,
        new_state={"id": "tax-mixed", "identifier": "tax_mixed", "title": "Tax Mixed"},
        batch_run_id="run-mixed",
    )
    change_repo.record_change(
        entity_id="scheme-mixed",
        entity_type="concept_scheme",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "scheme-mixed",
            "taxonomy_id": "tx-1",
            "identifier": "scheme_mixed",
            "title": "Scheme Mixed",
        },
        batch_run_id="run-mixed",
    )
    change_repo.record_change(
        entity_id="cls-mixed",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "cls-mixed",
            "concept_scheme_id": "scheme-1",
            "title": "Class Mixed",
        },
        batch_run_id="run-mixed",
    )
    change_repo.record_change(
        entity_id="ind-mixed",
        entity_type="individual",
        operation=ChangeOperation.CREATE,
        new_state={
            "id": "ind-mixed",
            "class_ids": ["cls-mixed"],
            "title": "Individual Mixed",
        },
        batch_run_id="run-mixed",
    )

    # Revert and get summary
    result = revert_svc.revert_with_summary("run-mixed")

    # Verify all counts
    assert result.events_reverted == 4
    assert result.taxonomies_deleted == 1
    assert result.concept_schemes_deleted == 1
    assert result.classes_deleted == 1
    assert result.individuals_deleted == 1


def test_revert_with_summary_delete_operations_count_as_restored(
    ontology_repo, change_repo, revert_svc
):
    """Test that reverting DELETE operations counts as entities_restored."""
    # Record a DELETE event
    change_repo.record_change(
        entity_id="cls-restored",
        entity_type="class",
        operation=ChangeOperation.DELETE,
        new_state={
            "id": "cls-restored",
            "taxonomy_id": "tx-1",
            "concept_scheme_id": "scheme-1",
            "title": "Restored Class",
        },
        batch_run_id="run-restore",
    )

    # Revert and get summary
    result = revert_svc.revert_with_summary("run-restore")

    # Verify the entity was restored and counted correctly
    assert result.events_reverted == 1
    assert result.entities_restored == 1
    assert ontology_repo.get_class("cls-restored") is not None


def test_revert_refused_when_entities_outside_the_run_depend_on_it(
    ontology_repo, change_repo, revert_svc
):
    """A revert that would delete a class another run's individual uses changes nothing."""
    ontology_repo.save_class(
        Class(id="cls-1", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Service")
    )
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-1"},
        batch_run_id="run-1",
    )
    ontology_repo.save_individual(Individual(id="ind-1", class_ids=["cls-1"], title="API"))

    with pytest.raises(RevertConflictError) as excinfo:
        revert_svc.revert("run-1")

    assert excinfo.value.blocking == [("individual", "ind-1", "cls-1")]
    assert ontology_repo.get_class("cls-1") is not None
    assert change_repo.get_changes(limit=None).total == 1


def _run_types_existing_individual_into_new_class(ontology_repo, change_repo, other_change):
    """Run-1 creates cls-1 and adds it to the existing ind-1; optionally another field changes."""
    ontology_repo.save_individual(Individual(id="ind-1", class_ids=["cls-0"], title="API"))
    ontology_repo.save_class(
        Class(id="cls-1", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Service")
    )
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-1"},
        batch_run_id="run-1",
    )
    previous, new = (
        ({"title": "API"}, {"title": "Public API"})
        if other_change
        else ({"class_ids": ["cls-0"]}, {"class_ids": ["cls-0", "cls-1"]})
    )
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.UPDATE,
        new_state=new,
        previous_state=previous,
        batch_run_id="run-1",
    )
    ind = ontology_repo.get_individual("ind-1")
    ind.class_ids = ["cls-0", "cls-1"]
    ind.title = new.get("title", ind.title)
    ontology_repo.save_individual(ind)


def test_revert_allowed_when_the_run_itself_added_the_dependency(
    ontology_repo, change_repo, revert_svc
):
    """Undoing the run's own membership change removes the dependency before the delete."""
    _run_types_existing_individual_into_new_class(ontology_repo, change_repo, other_change=False)

    assert revert_svc.revert("run-1") == 2
    assert ontology_repo.get_class("cls-1") is None
    assert ontology_repo.get_individual("ind-1").class_ids == ["cls-0"]


def test_revert_refused_when_the_run_changed_the_dependent_but_not_the_reference(
    ontology_repo, change_repo, revert_svc
):
    """The run only retitled the individual; its membership of cls-1 survives the revert."""
    _run_types_existing_individual_into_new_class(ontology_repo, change_repo, other_change=True)

    with pytest.raises(RevertConflictError) as excinfo:
        revert_svc.revert("run-1")
    assert excinfo.value.blocking == [("individual", "ind-1", "cls-1")]


# ============================================================================
# Vector index sync (#1293)
# ============================================================================


@pytest.fixture()
def schema_index():
    return FakeSchemaVectorIndex()


@pytest.fixture()
def individual_index(ontology_repo):
    return FakeIndividualVectorIndex(repo=ontology_repo)


@pytest.fixture()
def indexed_revert_svc(change_repo, ontology_repo, schema_index, individual_index):
    return RevertService(
        change_repo,
        ontology_repo,
        schema_index=schema_index,
        individual_index=individual_index,
    )


def _save_parent_class(ontology_repo):
    ontology_repo.save_class(
        Class(id="cls-1", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Animal")
    )


def test_revert_create_removes_individual_from_recognition_index(
    ontology_repo, change_repo, individual_index, indexed_revert_svc
):
    """A reverted (deleted) individual no longer appears in the recognition index."""
    _save_parent_class(ontology_repo)
    ontology_repo.save_individual(Individual(id="ind-1", class_ids=["cls-1"], title="Rex"))
    individual_index.index_individual("ind-1", "Rex", None)
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.CREATE,
        new_state={"id": "ind-1", "class_ids": ["cls-1"], "title": "Rex"},
        batch_run_id="run-1",
    )

    indexed_revert_svc.revert("run-1")

    assert "ind-1" not in individual_index._individuals


def test_revert_update_reindexes_individual_with_restored_title(
    ontology_repo, change_repo, schema_index, individual_index, indexed_revert_svc
):
    """Restoring an individual's title re-embeds it in both indexes."""
    _save_parent_class(ontology_repo)
    ontology_repo.save_individual(
        Individual(id="ind-1", class_ids=["cls-1"], title="Rex the Dog", description="New")
    )
    individual_index.index_individual("ind-1", "Rex the Dog", "New")
    schema_index.index_entity("ind-1", "Rex the Dog", "New")
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.UPDATE,
        previous_state={"title": "Rex", "description": "Old"},
        new_state={"title": "Rex the Dog", "description": "New"},
        batch_run_id="run-1",
    )

    indexed_revert_svc.revert("run-1")

    assert individual_index._individuals["ind-1"] == ("Rex", ["cls-1"], "Old")
    assert schema_index._entities["ind-1"] == ("Rex", "Old")


def test_revert_update_reindexes_class_with_restored_definition(
    ontology_repo, change_repo, schema_index, indexed_revert_svc
):
    """Restoring a class definition re-embeds it in the schema index."""
    ontology_repo.save_class(
        Class(
            id="cls-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tx-1",
            title="Animal",
            description="A living being",
        )
    )
    schema_index.index_entity("cls-1", "Animal", "A living being")
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"description": "An organism"},
        new_state={"description": "A living being"},
        batch_run_id="run-1",
    )

    indexed_revert_svc.revert("run-1")

    assert schema_index._entities["cls-1"] == ("Animal", "An organism")


def test_revert_update_reindexes_property_definition(
    ontology_repo, change_repo, schema_index, indexed_revert_svc
):
    """Restoring a property definition's title re-embeds it in the schema index."""
    ontology_repo.save_property_definition(
        PropertyDefinition(id="prop-1", identifier="uses", title="makes use of")
    )
    change_repo.record_change(
        entity_id="prop-1",
        entity_type="property_definition",
        operation=ChangeOperation.UPDATE,
        previous_state={"title": "uses"},
        new_state={"title": "makes use of"},
        batch_run_id="run-1",
    )

    indexed_revert_svc.revert("run-1")

    assert schema_index._entities["prop-1"] == ("uses", None)


def test_revert_delete_indexes_restored_individual(
    ontology_repo, change_repo, schema_index, individual_index, indexed_revert_svc
):
    """A restored individual is indexed again so recognition can find it."""
    _save_parent_class(ontology_repo)
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="individual",
        operation=ChangeOperation.DELETE,
        new_state={},
        previous_state={"id": "ind-1", "class_ids": ["cls-1"], "title": "Rex"},
        batch_run_id="run-1",
    )

    indexed_revert_svc.revert("run-1")

    assert individual_index._individuals["ind-1"] == ("Rex", ["cls-1"], None)
    assert schema_index._entities["ind-1"] == ("Rex", None)


def test_revert_delete_indexes_restored_class(
    ontology_repo, change_repo, schema_index, indexed_revert_svc
):
    """A restored class is indexed again so schema retrieval can find it."""
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.DELETE,
        new_state={},
        previous_state={
            "id": "cls-1",
            "concept_scheme_id": "scheme-1",
            "taxonomy_id": "tx-1",
            "title": "Animal",
            "description": "An organism",
        },
        batch_run_id="run-1",
    )

    indexed_revert_svc.revert("run-1")

    assert schema_index._entities["cls-1"] == ("Animal", "An organism")


def test_revert_of_create_then_update_does_not_index_the_deleted_entity(
    ontology_repo, change_repo, schema_index, indexed_revert_svc
):
    """An entity created and then updated by the run ends deleted, so nothing re-indexes it."""
    ontology_repo.save_class(
        Class(id="cls-1", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Beast")
    )
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-1", "title": "Animal"},
        batch_run_id="run-1",
    )
    change_repo.record_change(
        entity_id="cls-1",
        entity_type="class",
        operation=ChangeOperation.UPDATE,
        previous_state={"title": "Animal"},
        new_state={"title": "Beast"},
        batch_run_id="run-1",
    )

    indexed_revert_svc.revert("run-1")

    assert ontology_repo.get_class("cls-1") is None
    assert "cls-1" not in schema_index._entities


def test_inverse_delete_attribute_definition(ontology_repo, change_repo, revert_svc):
    """Reverting an attribute definition's delete recreates it from its snapshot."""
    ontology_repo.save_class(
        Class(id="cls-1", concept_scheme_id="scheme-1", taxonomy_id="tx-1", title="Animal")
    )
    attr = AttributeDefinition(
        id="attr-1",
        class_id="cls-1",
        identifier="legs",
        title="Legs",
        datatype=DataType.INTEGER,
        allowed_values=["2", "4"],
    )
    change_repo.record_change(
        entity_id="attr-1",
        entity_type="attribute_definition",
        operation=ChangeOperation.DELETE,
        new_state={},
        previous_state=entity_snapshot(attr),
        batch_run_id="run-1",
    )

    result = revert_svc.revert_with_summary("run-1")

    assert result.entities_restored == 1
    assert ontology_repo.get_attribute_definition("attr-1") == attr
