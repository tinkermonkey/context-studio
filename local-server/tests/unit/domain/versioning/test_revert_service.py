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

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from domain.ontology.entities import Class, ConceptScheme, Individual, Relationship, PropertyDefinition, Taxonomy
from domain.ontology.value_objects import Status
from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import ChangeOperation
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_change_repository import FakeChangeRepository


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
    revert_svc.revert("run-1")
    state_after_first_revert = ontology_repo.get_class("cls-1")
    assert state_after_first_revert is None

    # Second revert (should not error and produce same state)
    # The revert events themselves have _reverted_ in the change_reason, so
    # subsequent reverts will skip them
    revert_svc.revert("run-1")
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
