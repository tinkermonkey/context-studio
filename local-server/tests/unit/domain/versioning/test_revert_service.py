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
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )))
)

import pytest

from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.versioning.revert_service import RevertService
from domain.versioning.value_objects import ChangeOperation
from tests.fakes.fake_change_repository import FakeChangeRepository
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

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
        entity_type="Class",
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
        entity_type="Individual",
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
        entity_type="Class",
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
        entity_type="Class",
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
        entity_type="Class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-1", "title": "Animal"},
        batch_run_id="run-1",
    )
    change_repo.record_change(
        entity_id="ind-1",
        entity_type="Individual",
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
        entity_type="Class",
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
        entity_type="Class",
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
        entity_type="Class",
        operation=ChangeOperation.CREATE,
        new_state={"id": "cls-service", "title": "Service"},
        batch_run_id="run-schema",
    )
    change_repo.record_change(
        entity_id="prop-1",
        entity_type="PropertyDefinition",
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
        entity_type="Individual",
        operation=ChangeOperation.CREATE,
        new_state={"id": "ind-alice", "class_ids": ["cls-person"], "title": "Alice"},
        batch_run_id="run-individual",
    )
    change_repo.record_change(
        entity_id="ind-bob",
        entity_type="Individual",
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
        entity_type="Relationship",
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
