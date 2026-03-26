"""
Unit tests for OntologyService.

Tests cover all business logic: entity creation, duplicate detection, circular
reference prevention, embedding generation and updates, event emission, and
constraints enforcement. Uses in-memory fakes with zero infrastructure imports.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.ontology.services import OntologyService
from domain.ontology.events import (
    TaxonomyCreated, TaxonomyUpdated, TaxonomyDeleted,
    SchemeCreated, SchemeUpdated, SchemeDeleted,
    ClassCreated, ClassUpdated, ClassDeleted,
    ClassMoved, RelationshipCreated, RelationshipDeleted,
    PropertyDefinitionCreated, GraphInvalidated
)
from domain.ontology.exceptions import EntityNotFoundError, CircularReferenceError, DuplicateEntityError, OntologyError
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher


@pytest.fixture
def service():
    """Create a fresh OntologyService with in-memory fakes for each test."""
    return OntologyService(
        repository=FakeOntologyRepository(),
        embedding_service=FakeEmbeddingService(),
        event_publisher=FakeEventPublisher(),
    )


class TestCreateTaxonomy:
    """Tests for create_taxonomy."""

    def test_create_taxonomy_success(self, service):
        """Create a taxonomy and verify it's persisted and event is emitted."""
        tax = service.create_taxonomy(title="Biology", description="Life sciences")
        assert tax.id is not None
        assert tax.title == "Biology"
        assert tax.description == "Life sciences"
        assert tax.created_at is not None
        assert tax.updated_at is not None

        # Verify it was saved
        retrieved = service.get_taxonomy(tax.id)
        assert retrieved.id == tax.id

        # Verify event was emitted
        events = service._event_publisher.get_events()
        assert len(events) == 1
        assert isinstance(events[0], TaxonomyCreated)
        assert events[0].taxonomy_id == tax.id
        assert events[0].title == "Biology"

    def test_create_taxonomy_duplicate_title_raises(self, service):
        """Create taxonomy with duplicate title raises DuplicateEntityError."""
        service.create_taxonomy(title="Biology")
        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.create_taxonomy(title="Biology")

    def test_create_taxonomy_empty_title_raises(self, service):
        """Create taxonomy with empty title raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_taxonomy(title="")

    def test_create_taxonomy_whitespace_title_raises(self, service):
        """Create taxonomy with whitespace-only title raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_taxonomy(title="   ")


class TestCreateScheme:
    """Tests for create_scheme."""

    def test_create_scheme_success(self, service):
        """Create a concept scheme in a taxonomy."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals", description="Animal kingdom")

        assert scheme.id is not None
        assert scheme.taxonomy_id == tax.id
        assert scheme.title == "Animals"
        assert scheme.description == "Animal kingdom"

        # Verify event
        events = service._event_publisher.get_events_of_type(SchemeCreated)
        assert len(events) == 1
        assert events[0].scheme_id == scheme.id

    def test_create_scheme_nonexistent_taxonomy_raises(self, service):
        """Create scheme in nonexistent taxonomy raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Taxonomy"):
            service.create_scheme(taxonomy_id="nonexistent", title="Animals")

    def test_create_scheme_duplicate_title_in_taxonomy_raises(self, service):
        """Create scheme with duplicate title in same taxonomy raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        service.create_scheme(taxonomy_id=tax.id, title="Animals")
        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.create_scheme(taxonomy_id=tax.id, title="Animals")

    def test_create_scheme_same_title_different_taxonomy_allowed(self, service):
        """Same title in different taxonomy is allowed."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        scheme1 = service.create_scheme(taxonomy_id=tax1.id, title="Elements")
        scheme2 = service.create_scheme(taxonomy_id=tax2.id, title="Elements")
        assert scheme1.id != scheme2.id


class TestRenameTaxonomy:
    """Tests for rename_taxonomy."""

    def test_rename_taxonomy_success(self, service):
        """Rename a taxonomy and verify it's persisted and event is emitted."""
        tax = service.create_taxonomy(title="Biology")

        renamed = service.rename_taxonomy(taxonomy_id=tax.id, new_title="Life Sciences")
        assert renamed.title == "Life Sciences"

        # Verify it was saved
        retrieved = service.get_taxonomy(tax.id)
        assert retrieved.title == "Life Sciences"

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(TaxonomyUpdated)
        assert len(events) == 1
        assert events[0].taxonomy_id == tax.id
        assert events[0].changed_fields == ("title",)

    def test_rename_taxonomy_nonexistent_raises(self, service):
        """Rename nonexistent taxonomy raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Taxonomy"):
            service.rename_taxonomy(taxonomy_id="nonexistent", new_title="NewTitle")

    def test_rename_taxonomy_duplicate_title_raises(self, service):
        """Rename to duplicate title raises DuplicateEntityError."""
        service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.rename_taxonomy(taxonomy_id=tax2.id, new_title="Biology")

    def test_rename_taxonomy_empty_title_raises(self, service):
        """Rename to empty title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.rename_taxonomy(taxonomy_id=tax.id, new_title="")

    def test_rename_taxonomy_whitespace_title_raises(self, service):
        """Rename to whitespace-only title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.rename_taxonomy(taxonomy_id=tax.id, new_title="   ")

    def test_rename_taxonomy_no_op_returns_unchanged(self, service):
        """Renaming to same title is a no-op and returns unchanged entity."""
        tax = service.create_taxonomy(title="Biology")
        # Get the initial count of TaxonomyUpdated events (should be 0 at this point)
        initial_update_count = len(service._event_publisher.get_events_of_type(TaxonomyUpdated))

        renamed = service.rename_taxonomy(taxonomy_id=tax.id, new_title="Biology")
        assert renamed.title == "Biology"

        # No event should be emitted for no-op
        events = service._event_publisher.get_events_of_type(TaxonomyUpdated)
        assert len(events) == initial_update_count


class TestDeleteTaxonomy:
    """Tests for delete_taxonomy."""

    def test_delete_taxonomy_success(self, service):
        """Delete an empty taxonomy."""
        tax = service.create_taxonomy(title="Biology")

        service.delete_taxonomy(taxonomy_id=tax.id)

        # Verify it's deleted
        with pytest.raises(EntityNotFoundError):
            service.get_taxonomy(tax.id)

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(TaxonomyDeleted)
        assert len(events) == 1
        assert events[0].taxonomy_id == tax.id
        assert events[0].title == "Biology"

    def test_delete_taxonomy_nonexistent_raises(self, service):
        """Delete nonexistent taxonomy raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Taxonomy"):
            service.delete_taxonomy(taxonomy_id="nonexistent")

    def test_delete_taxonomy_with_schemes_raises(self, service):
        """Delete taxonomy with concept schemes raises OntologyError."""
        tax = service.create_taxonomy(title="Biology")
        service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(OntologyError, match="has.*concept scheme"):
            service.delete_taxonomy(taxonomy_id=tax.id)

    def test_delete_taxonomy_after_deleting_all_schemes_succeeds(self, service):
        """Delete taxonomy succeeds after removing all schemes."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        # First, delete the scheme
        service.delete_scheme(scheme_id=scheme.id)

        # Now deleting taxonomy should succeed
        service.delete_taxonomy(taxonomy_id=tax.id)

        with pytest.raises(EntityNotFoundError):
            service.get_taxonomy(tax.id)


class TestRenameScheme:
    """Tests for rename_scheme."""

    def test_rename_scheme_success(self, service):
        """Rename a concept scheme and verify it's persisted and event is emitted."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        renamed = service.rename_scheme(scheme_id=scheme.id, new_title="Animal Kingdom")
        assert renamed.title == "Animal Kingdom"

        # Verify it was saved
        retrieved = service.get_concept_scheme(scheme.id)
        assert retrieved.title == "Animal Kingdom"

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(SchemeUpdated)
        assert len(events) == 1
        assert events[0].scheme_id == scheme.id
        assert events[0].taxonomy_id == tax.id
        assert events[0].changed_fields == ("title",)

    def test_rename_scheme_nonexistent_raises(self, service):
        """Rename nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.rename_scheme(scheme_id="nonexistent", new_title="NewTitle")

    def test_rename_scheme_duplicate_title_in_taxonomy_raises(self, service):
        """Rename to duplicate title within same taxonomy raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.rename_scheme(scheme_id=scheme2.id, new_title="Animals")

    def test_rename_scheme_same_title_different_taxonomy_allowed(self, service):
        """Rename scheme to title that exists in different taxonomy is allowed."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        service.create_scheme(taxonomy_id=tax1.id, title="Elements")
        scheme2 = service.create_scheme(taxonomy_id=tax2.id, title="Compounds")

        # This should succeed because Elements is in a different taxonomy
        renamed = service.rename_scheme(scheme_id=scheme2.id, new_title="Elements")
        assert renamed.title == "Elements"

    def test_rename_scheme_empty_title_raises(self, service):
        """Rename to empty title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.rename_scheme(scheme_id=scheme.id, new_title="")

    def test_rename_scheme_whitespace_title_raises(self, service):
        """Rename to whitespace-only title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.rename_scheme(scheme_id=scheme.id, new_title="   ")

    def test_rename_scheme_no_op_returns_unchanged(self, service):
        """Renaming to same title is a no-op and returns unchanged entity."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        # Get the initial count of SchemeUpdated events (should be 0 at this point)
        initial_update_count = len(service._event_publisher.get_events_of_type(SchemeUpdated))

        renamed = service.rename_scheme(scheme_id=scheme.id, new_title="Animals")
        assert renamed.title == "Animals"

        # No event should be emitted for no-op
        events = service._event_publisher.get_events_of_type(SchemeUpdated)
        assert len(events) == initial_update_count


class TestDeleteScheme:
    """Tests for delete_scheme."""

    def test_delete_scheme_success(self, service):
        """Delete an empty concept scheme."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        service.delete_scheme(scheme_id=scheme.id)

        # Verify it's deleted
        with pytest.raises(EntityNotFoundError):
            service.get_concept_scheme(scheme.id)

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(SchemeDeleted)
        assert len(events) == 1
        assert events[0].scheme_id == scheme.id
        assert events[0].taxonomy_id == tax.id
        assert events[0].title == "Animals"

    def test_delete_scheme_nonexistent_raises(self, service):
        """Delete nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.delete_scheme(scheme_id="nonexistent")

    def test_delete_scheme_with_classes_raises(self, service):
        """Delete scheme with classes raises OntologyError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        service.create_class(scheme_id=scheme.id, title="Dog")

        with pytest.raises(OntologyError, match="has.*class"):
            service.delete_scheme(scheme_id=scheme.id)

    def test_delete_scheme_after_deleting_all_classes_succeeds(self, service):
        """Delete scheme succeeds after removing all classes."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(scheme_id=scheme.id, title="Dog")

        # First, delete the class
        service.delete_class(class_id=cls.id)

        # Now deleting scheme should succeed
        service.delete_scheme(scheme_id=scheme.id)

        with pytest.raises(EntityNotFoundError):
            service.get_concept_scheme(scheme.id)


class TestCreateClass:
    """Tests for create_class."""

    def test_create_class_success(self, service):
        """Create a class with embedding generated."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(
            scheme_id=scheme.id,
            title="Dog",
            description="Canine species",
        )

        assert cls.id is not None
        assert cls.scheme_id == scheme.id
        assert cls.taxonomy_id == tax.id
        assert cls.title == "Dog"
        assert cls.description == "Canine species"
        assert cls.embedding is not None  # Embedding should be generated
        assert cls.parent_class_id is None

        # Verify event
        events = service._event_publisher.get_events_of_type(ClassCreated)
        assert len(events) == 1
        assert events[0].class_id == cls.id

    def test_create_class_with_parent(self, service):
        """Create a class with parent class."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        parent = service.create_class(scheme_id=scheme.id, title="Mammal")
        child = service.create_class(
            scheme_id=scheme.id,
            title="Dog",
            parent_class_id=parent.id,
        )

        assert child.parent_class_id == parent.id

    def test_create_class_nonexistent_scheme_raises(self, service):
        """Create class in nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.create_class(scheme_id="nonexistent", title="Dog")

    def test_create_class_nonexistent_parent_raises(self, service):
        """Create class with nonexistent parent raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.create_class(
                scheme_id=scheme.id,
                title="Dog",
                parent_class_id="nonexistent",
            )

    def test_create_class_parent_different_scheme_raises(self, service):
        """Parent from different scheme raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        parent = service.create_class(scheme_id=scheme1.id, title="Mammal")

        with pytest.raises(ValueError, match="not in the same scheme"):
            service.create_class(
                scheme_id=scheme2.id,
                title="Tree",
                parent_class_id=parent.id,
            )

    def test_create_class_duplicate_title_in_scheme_raises(self, service):
        """Duplicate title in same scheme raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        service.create_class(scheme_id=scheme.id, title="Dog")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.create_class(scheme_id=scheme.id, title="Dog")

    def test_create_class_same_title_different_scheme_allowed(self, service):
        """Same title in different scheme is allowed."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        cls1 = service.create_class(scheme_id=scheme1.id, title="Life")
        cls2 = service.create_class(scheme_id=scheme2.id, title="Life")
        assert cls1.id != cls2.id


class TestUpdateClass:
    """Tests for update_class."""

    def test_update_class_title_regenerates_embedding(self, service):
        """Update class title regenerates embedding."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(scheme_id=scheme.id, title="Dog", description="Canine")
        old_embedding = cls.embedding

        updated = service.update_class(class_id=cls.id, title="Canine")
        assert updated.title == "Canine"
        assert updated.embedding != old_embedding

        # Verify event
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 1
        assert "title" in events[0].changed_fields

    def test_update_class_description_regenerates_embedding(self, service):
        """Update class description regenerates embedding."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(scheme_id=scheme.id, title="Dog")
        old_embedding = cls.embedding

        updated = service.update_class(class_id=cls.id, description="Canine species")
        assert updated.description == "Canine species"
        assert updated.embedding != old_embedding

        # Verify event
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 1
        assert "description" in events[0].changed_fields

    def test_update_class_no_change_no_embedding_regen(self, service):
        """Update class with no title/description change does not regenerate embedding or emit event."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(scheme_id=scheme.id, title="Dog", description="Canine")
        old_embedding = cls.embedding

        # Call with empty update (no title, no description)
        updated = service.update_class(class_id=cls.id)
        assert updated.embedding == old_embedding

        # Verify no ClassUpdated event is emitted when no changes
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 0

    def test_update_class_duplicate_title_in_scheme_raises(self, service):
        """Update class to duplicate title in same scheme raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        service.create_class(scheme_id=scheme.id, title="Dog")
        cls2 = service.create_class(scheme_id=scheme.id, title="Cat")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.update_class(class_id=cls2.id, title="Dog")

    def test_update_class_same_title_different_scheme_allowed(self, service):
        """Update class to title that exists in different scheme is allowed."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        service.create_class(scheme_id=scheme1.id, title="Life")
        cls2 = service.create_class(scheme_id=scheme2.id, title="Organism")

        # This should succeed because Life is in a different scheme
        updated = service.update_class(class_id=cls2.id, title="Life")
        assert updated.title == "Life"

    def test_update_class_nonexistent_raises(self, service):
        """Update nonexistent class raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.update_class(class_id="nonexistent", title="NewTitle")


class TestMoveClass:
    """Tests for move_class (circular reference detection)."""

    def test_move_class_to_new_parent(self, service):
        """Move a class to a new parent."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        dog = service.create_class(scheme_id=scheme.id, title="Dog", parent_class_id=None)

        moved = service.move_class(class_id=dog.id, new_parent_id=mammal.id)
        assert moved.parent_class_id == mammal.id

        # Verify events
        events = service._event_publisher.get_events_of_type(ClassMoved)
        assert len(events) == 1
        assert events[0].class_id == dog.id
        assert events[0].new_parent_id == mammal.id

        invalidations = service._event_publisher.get_events_of_type(GraphInvalidated)
        assert any(e.reason == "class_moved" for e in invalidations)

    def test_move_class_to_root(self, service):
        """Move a class to root (parent_id=None)."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        dog = service.create_class(scheme_id=scheme.id, title="Dog", parent_class_id=mammal.id)

        moved = service.move_class(class_id=dog.id, new_parent_id=None)
        assert moved.parent_class_id is None

    def test_move_class_self_parent_raises(self, service):
        """Move a class to itself as parent raises CircularReferenceError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(scheme_id=scheme.id, title="Dog")

        with pytest.raises(CircularReferenceError, match="own parent"):
            service.move_class(class_id=cls.id, new_parent_id=cls.id)

    def test_move_class_circular_reference_one_level_raises(self, service):
        """Circular reference A→B→A raises CircularReferenceError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        a = service.create_class(scheme_id=scheme.id, title="A")
        b = service.create_class(scheme_id=scheme.id, title="B", parent_class_id=a.id)

        # Try to move A under B, which would create B→A→B
        with pytest.raises(CircularReferenceError, match="circular reference"):
            service.move_class(class_id=a.id, new_parent_id=b.id)

    def test_move_class_circular_reference_deep_raises(self, service):
        """Circular reference A→B→C→A raises CircularReferenceError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        a = service.create_class(scheme_id=scheme.id, title="A")
        b = service.create_class(scheme_id=scheme.id, title="B", parent_class_id=a.id)
        c = service.create_class(scheme_id=scheme.id, title="C", parent_class_id=b.id)

        # Try to move A under C, which would create C→A→B→C
        with pytest.raises(CircularReferenceError, match="circular reference"):
            service.move_class(class_id=a.id, new_parent_id=c.id)

    def test_move_class_nonexistent_raises(self, service):
        """Move nonexistent class raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.move_class(class_id="nonexistent", new_parent_id=None)

    def test_move_class_nonexistent_parent_raises(self, service):
        """Move a class to a nonexistent parent raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")

        with pytest.raises(EntityNotFoundError, match="Class"):
            service.move_class(class_id=dog.id, new_parent_id="nonexistent")

    def test_move_class_cross_scheme_parent_raises(self, service):
        """Move a class to a parent in a different scheme raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")

        dog = service.create_class(scheme_id=scheme1.id, title="Dog")
        tree = service.create_class(scheme_id=scheme2.id, title="Tree")

        with pytest.raises(ValueError, match="not in the same scheme"):
            service.move_class(class_id=dog.id, new_parent_id=tree.id)


class TestDeleteClass:
    """Tests for delete_class."""

    def test_delete_class_success(self, service):
        """Delete a class with no subclasses."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(scheme_id=scheme.id, title="Dog")

        service.delete_class(class_id=cls.id)

        # Verify it's deleted
        with pytest.raises(EntityNotFoundError):
            service.get_class(cls.id)

        # Verify events
        deleted_events = service._event_publisher.get_events_of_type(ClassDeleted)
        assert len(deleted_events) == 1
        assert deleted_events[0].class_id == cls.id

        invalidations = service._event_publisher.get_events_of_type(GraphInvalidated)
        assert any(e.reason == "class_deleted" for e in invalidations)

    def test_delete_class_with_subclasses_raises(self, service):
        """Delete class with subclasses raises OntologyError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        parent = service.create_class(scheme_id=scheme.id, title="Mammal")
        service.create_class(scheme_id=scheme.id, title="Dog", parent_class_id=parent.id)

        with pytest.raises(OntologyError, match="has.*subclass"):
            service.delete_class(class_id=parent.id)

    def test_delete_class_nonexistent_raises(self, service):
        """Delete nonexistent class raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.delete_class(class_id="nonexistent")

    def test_delete_class_cleans_up_orphaned_relationships_as_source(self, service):
        """Delete class cleans up relationships where it is the source."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        rel = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        # Delete the source class
        service.delete_class(class_id=dog.id)

        # Verify relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify RelationshipDeleted event was emitted
        rel_delete_events = service._event_publisher.get_events_of_type(RelationshipDeleted)
        assert len(rel_delete_events) == 1
        assert rel_delete_events[0].relationship_id == rel.id

    def test_delete_class_cleans_up_orphaned_relationships_as_target(self, service):
        """Delete class cleans up relationships where it is the target."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        rel = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        # Delete the target class
        service.delete_class(class_id=mammal.id)

        # Verify relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify RelationshipDeleted event was emitted
        rel_delete_events = service._event_publisher.get_events_of_type(RelationshipDeleted)
        assert len(rel_delete_events) == 1
        assert rel_delete_events[0].relationship_id == rel.id

    def test_delete_class_cleans_up_multiple_orphaned_relationships(self, service):
        """Delete class cleans up multiple relationships."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        animal = service.create_class(scheme_id=scheme.id, title="Animal")
        prop1 = service.create_property_definition(identifier="is_a", title="Is A")
        prop2 = service.create_property_definition(identifier="part_of", title="Part Of")

        rel1 = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop1.id,
        )
        rel2 = service.create_relationship(
            source_id=mammal.id,
            target_id=animal.id,
            property_definition_id=prop2.id,
        )

        # Delete the middle class (mammal) which is both source and target
        service.delete_class(class_id=mammal.id)

        # Verify both relationships are deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel1.id)
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel2.id)

        # Verify two RelationshipDeleted events were emitted
        rel_delete_events = service._event_publisher.get_events_of_type(RelationshipDeleted)
        assert len(rel_delete_events) == 2
        rel_ids = {e.relationship_id for e in rel_delete_events}
        assert rel1.id in rel_ids
        assert rel2.id in rel_ids


class TestCreateRelationship:
    """Tests for create_relationship."""

    def test_create_relationship_success(self, service):
        """Create a relationship between two classes."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        rel = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        assert rel.id is not None
        assert rel.source_id == dog.id
        assert rel.target_id == mammal.id
        assert rel.property_definition_id == prop.id

        # Verify events
        rel_events = service._event_publisher.get_events_of_type(RelationshipCreated)
        assert len(rel_events) == 1
        assert rel_events[0].relationship_id == rel.id

        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        assert any(e.reason == "relationship_created" for e in graph_events)

    def test_create_relationship_self_loop_raises(self, service):
        """Create relationship with same source and target raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        with pytest.raises(ValueError, match="same source and target"):
            service.create_relationship(
                source_id=dog.id,
                target_id=dog.id,
                property_definition_id=prop.id,
            )

    def test_create_relationship_nonexistent_property_raises(self, service):
        """Create relationship with nonexistent property raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")

        with pytest.raises(EntityNotFoundError, match="PropertyDefinition"):
            service.create_relationship(
                source_id=dog.id,
                target_id="target",
                property_definition_id="nonexistent",
            )

    def test_create_relationship_nonexistent_source_raises(self, service):
        """Create relationship with nonexistent source raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        target = service.create_class(scheme_id=scheme.id, title="Target")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        with pytest.raises(EntityNotFoundError, match="Class.*nonexistent"):
            service.create_relationship(
                source_id="nonexistent",
                target_id=target.id,
                property_definition_id=prop.id,
            )

    def test_create_relationship_nonexistent_target_raises(self, service):
        """Create relationship with nonexistent target raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        source = service.create_class(scheme_id=scheme.id, title="Source")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        with pytest.raises(EntityNotFoundError, match="Class.*nonexistent"):
            service.create_relationship(
                source_id=source.id,
                target_id="nonexistent",
                property_definition_id=prop.id,
            )

    def test_create_relationship_with_valid_entities_emits_correct_taxonomy_id(self, service):
        """Create relationship correctly uses source class's taxonomy for graph invalidation."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        # Verify GraphInvalidated event has the correct taxonomy_id from source
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        graph_invalid_from_rel = [e for e in graph_events if e.reason == "relationship_created"]
        assert len(graph_invalid_from_rel) == 1
        assert graph_invalid_from_rel[0].taxonomy_id == tax.id


class TestDeleteRelationship:
    """Tests for delete_relationship."""

    def test_delete_relationship_success(self, service):
        """Delete a relationship."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        rel = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        service.delete_relationship(relationship_id=rel.id)

        # Verify it's deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify RelationshipDeleted event
        events = service._event_publisher.get_events_of_type(RelationshipDeleted)
        assert len(events) == 1
        assert events[0].relationship_id == rel.id

        # Verify GraphInvalidated event
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        assert len(graph_events) >= 1
        # Find the one from delete (not from create_relationship)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == 1
        assert delete_graph_events[0].taxonomy_id == tax.id

    def test_delete_relationship_nonexistent_raises(self, service):
        """Delete nonexistent relationship raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Relationship"):
            service.delete_relationship(relationship_id="nonexistent")


class TestCreatePropertyDefinition:
    """Tests for create_property_definition."""

    def test_create_property_definition_success(self, service):
        """Create a property definition."""
        prop = service.create_property_definition(
            identifier="is_a",
            title="Is A",
            description="Taxonomic is-a relationship",
        )

        assert prop.id is not None
        assert prop.identifier == "is_a"
        assert prop.title == "Is A"
        assert prop.description == "Taxonomic is-a relationship"

        # Verify event
        events = service._event_publisher.get_events_of_type(PropertyDefinitionCreated)
        assert len(events) == 1
        assert events[0].property_id == prop.id

    def test_create_property_definition_duplicate_identifier_raises(self, service):
        """Duplicate identifier raises DuplicateEntityError."""
        service.create_property_definition(identifier="is_a", title="Is A")
        with pytest.raises(DuplicateEntityError, match="identifier"):
            service.create_property_definition(identifier="is_a", title="Is Also A")

    def test_create_property_definition_duplicate_title_raises(self, service):
        """Duplicate title raises DuplicateEntityError."""
        service.create_property_definition(identifier="is_a", title="Is A")
        with pytest.raises(DuplicateEntityError, match="title"):
            service.create_property_definition(identifier="also_is_a", title="Is A")

    def test_create_property_definition_empty_identifier_raises(self, service):
        """Empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            service.create_property_definition(identifier="", title="Is A")

    def test_create_property_definition_empty_title_raises(self, service):
        """Empty title raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_property_definition(identifier="is_a", title="")


class TestGetAndListOperations:
    """Tests for all get_* and list_* read operations."""

    def test_list_taxonomies_empty(self, service):
        """List taxonomies when none exist returns empty list."""
        taxonomies = service.list_taxonomies()
        assert taxonomies == []

    def test_list_taxonomies_multiple(self, service):
        """List taxonomies returns all created taxonomies."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        taxonomies = service.list_taxonomies()
        assert len(taxonomies) == 2
        assert any(t.id == tax1.id for t in taxonomies)
        assert any(t.id == tax2.id for t in taxonomies)

    def test_list_concept_schemes_all(self, service):
        """List all concept schemes."""
        tax = service.create_taxonomy(title="Biology")
        service.create_scheme(taxonomy_id=tax.id, title="Animals")
        service.create_scheme(taxonomy_id=tax.id, title="Plants")
        schemes = service.list_concept_schemes()
        assert len(schemes) == 2

    def test_list_concept_schemes_filtered_by_taxonomy(self, service):
        """List concept schemes filtered by taxonomy."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        scheme1 = service.create_scheme(taxonomy_id=tax1.id, title="Animals")
        service.create_scheme(taxonomy_id=tax2.id, title="Elements")
        schemes = service.list_concept_schemes(taxonomy_id=tax1.id)
        assert len(schemes) == 1
        assert schemes[0].id == scheme1.id

    def test_list_classes_filtered_by_scheme(self, service):
        """List classes filtered by scheme."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        cls1 = service.create_class(scheme_id=scheme1.id, title="Dog")
        service.create_class(scheme_id=scheme2.id, title="Tree")
        classes = service.list_classes(scheme_id=scheme1.id)
        assert len(classes) == 1
        assert classes[0].id == cls1.id

    def test_list_classes_filtered_by_parent(self, service):
        """List classes filtered by parent class."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        dog = service.create_class(scheme_id=scheme.id, title="Dog", parent_class_id=mammal.id)
        cat = service.create_class(scheme_id=scheme.id, title="Cat", parent_class_id=mammal.id)
        children = service.list_classes(parent_class_id=mammal.id)
        assert len(children) == 2
        assert any(c.id == dog.id for c in children)
        assert any(c.id == cat.id for c in children)

    def test_list_relationships_filtered(self, service):
        """List relationships with filters."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        rel = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        # Filter by source
        by_source = service.list_relationships(source_id=dog.id)
        assert len(by_source) == 1
        assert by_source[0].id == rel.id

        # Filter by target
        by_target = service.list_relationships(target_id=mammal.id)
        assert len(by_target) == 1
        assert by_target[0].id == rel.id

    def test_list_property_definitions(self, service):
        """List all property definitions."""
        prop1 = service.create_property_definition(identifier="is_a", title="Is A")
        prop2 = service.create_property_definition(identifier="part_of", title="Part Of")
        props = service.list_property_definitions()
        assert len(props) == 2
        assert any(p.id == prop1.id for p in props)
        assert any(p.id == prop2.id for p in props)
