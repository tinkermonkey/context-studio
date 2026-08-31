"""
Unit tests for OntologyService.

Tests cover all business logic: entity creation, duplicate detection, circular
reference prevention, embedding generation and updates, event emission, and
constraints enforcement. Uses in-memory fakes with zero infrastructure imports.
"""

import re
from unittest.mock import MagicMock

import pytest

import domain.ontology.services
from domain.ontology.events import (
    AttributeDefinitionCreated,
    AttributeDefinitionDeleted,
    AttributeDefinitionUpdated,
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    GraphInvalidated,
    PropertyDefinitionCreated,
    RelationshipCreated,
    RelationshipDeleted,
    SchemeCreated,
    SchemeDeleted,
    SchemeUpdated,
    TaxonomyCreated,
    TaxonomyDeleted,
    TaxonomyUpdated,
)
from domain.ontology.exceptions import (
    CircularReferenceError,
    DuplicateEntityError,
    EntityNotFoundError,
    OntologyError,
)
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


def slugify(text: str) -> str:
    """Generate a slug-style identifier from text."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


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
        assert tax.last_modified is not None

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
        scheme = service.create_scheme(
            taxonomy_id=tax.id, title="Animals", description="Animal kingdom"
        )

        assert scheme.id is not None
        assert scheme.taxonomy_id == tax.id
        assert scheme.title == "Animals"
        assert scheme.description == "Animal kingdom"

        # Verify event
        events = service._event_publisher.get_events_of_type(SchemeCreated)
        assert len(events) == 1
        assert events[0].concept_scheme_id == scheme.id

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

    def test_create_scheme_empty_title_raises(self, service):
        """Create scheme with empty title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_scheme(taxonomy_id=tax.id, title="")

    def test_create_scheme_whitespace_title_raises(self, service):
        """Create scheme with whitespace-only title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_scheme(taxonomy_id=tax.id, title="   ")


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
        assert events[0].old_values == {"title": "Biology"}
        assert events[0].new_values == {"title": "Life Sciences"}

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
        service.delete_scheme(concept_scheme_id=scheme.id)

        # Now deleting taxonomy should succeed
        service.delete_taxonomy(taxonomy_id=tax.id)

        with pytest.raises(EntityNotFoundError):
            service.get_taxonomy(tax.id)


class TestGetConceptScheme:
    """Tests for get_concept_scheme."""

    def test_get_concept_scheme_success(self, service):
        """Retrieve a concept scheme by ID."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        retrieved = service.get_concept_scheme(scheme.id)
        assert retrieved.id == scheme.id
        assert retrieved.title == "Animals"
        assert retrieved.taxonomy_id == tax.id

    def test_get_concept_scheme_nonexistent_raises(self, service):
        """Get nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.get_concept_scheme("nonexistent")


class TestRenameScheme:
    """Tests for rename_scheme."""

    def test_rename_scheme_success(self, service):
        """Rename a concept scheme and verify it's persisted and event is emitted."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        renamed = service.rename_scheme(concept_scheme_id=scheme.id, new_title="Animal Kingdom")
        assert renamed.title == "Animal Kingdom"

        # Verify it was saved
        retrieved = service.get_concept_scheme(scheme.id)
        assert retrieved.title == "Animal Kingdom"

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(SchemeUpdated)
        assert len(events) == 1
        assert events[0].concept_scheme_id == scheme.id
        assert events[0].taxonomy_id == tax.id
        assert events[0].changed_fields == ("title",)
        assert events[0].old_values == {"title": "Animals"}
        assert events[0].new_values == {"title": "Animal Kingdom"}

    def test_rename_scheme_nonexistent_raises(self, service):
        """Rename nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.rename_scheme(concept_scheme_id="nonexistent", new_title="NewTitle")

    def test_rename_scheme_duplicate_title_in_taxonomy_raises(self, service):
        """Rename to duplicate title within same taxonomy raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.rename_scheme(concept_scheme_id=scheme2.id, new_title="Animals")

    def test_rename_scheme_same_title_different_taxonomy_allowed(self, service):
        """Rename scheme to title that exists in different taxonomy is allowed."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        service.create_scheme(taxonomy_id=tax1.id, title="Elements")
        scheme2 = service.create_scheme(taxonomy_id=tax2.id, title="Compounds")

        # This should succeed because Elements is in a different taxonomy
        renamed = service.rename_scheme(concept_scheme_id=scheme2.id, new_title="Elements")
        assert renamed.title == "Elements"

    def test_rename_scheme_empty_title_raises(self, service):
        """Rename to empty title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.rename_scheme(concept_scheme_id=scheme.id, new_title="")

    def test_rename_scheme_whitespace_title_raises(self, service):
        """Rename to whitespace-only title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.rename_scheme(concept_scheme_id=scheme.id, new_title="   ")

    def test_rename_scheme_no_op_returns_unchanged(self, service):
        """Renaming to same title is a no-op and returns unchanged entity."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        # Get the initial count of SchemeUpdated events (should be 0 at this point)
        initial_update_count = len(service._event_publisher.get_events_of_type(SchemeUpdated))

        renamed = service.rename_scheme(concept_scheme_id=scheme.id, new_title="Animals")
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

        service.delete_scheme(concept_scheme_id=scheme.id)

        # Verify it's deleted
        with pytest.raises(EntityNotFoundError):
            service.get_concept_scheme(scheme.id)

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(SchemeDeleted)
        assert len(events) == 1
        assert events[0].concept_scheme_id == scheme.id
        assert events[0].taxonomy_id == tax.id
        assert events[0].title == "Animals"

    def test_delete_scheme_nonexistent_raises(self, service):
        """Delete nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.delete_scheme(concept_scheme_id="nonexistent")

    def test_delete_scheme_with_classes_raises(self, service):
        """Delete scheme with classes raises OntologyError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        service.create_class(concept_scheme_id=scheme.id, title="Dog")

        with pytest.raises(OntologyError, match="has.*class"):
            service.delete_scheme(concept_scheme_id=scheme.id)

    def test_delete_scheme_after_deleting_all_classes_succeeds(self, service):
        """Delete scheme succeeds after removing all classes."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        # First, delete the class
        service.delete_class(class_id=cls.id)

        # Now deleting scheme should succeed
        service.delete_scheme(concept_scheme_id=scheme.id)

        with pytest.raises(EntityNotFoundError):
            service.get_concept_scheme(scheme.id)


class TestCreateClass:
    """Tests for create_class."""

    def test_create_class_success(self, service):
        """Create a class with embedding generated."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(
            concept_scheme_id=scheme.id,
            title="Dog",
            description="Canine species",
        )

        assert cls.id is not None
        assert cls.concept_scheme_id == scheme.id
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
        parent = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        child = service.create_class(
            concept_scheme_id=scheme.id,
            title="Dog",
            parent_class_id=parent.id,
        )

        assert child.parent_class_id == parent.id

    def test_create_class_nonexistent_scheme_raises(self, service):
        """Create class in nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.create_class(concept_scheme_id="nonexistent", title="Dog")

    def test_create_class_nonexistent_parent_raises(self, service):
        """Create class with nonexistent parent raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.create_class(
                concept_scheme_id=scheme.id,
                title="Dog",
                parent_class_id="nonexistent",
            )

    def test_create_class_parent_different_scheme_raises(self, service):
        """Parent from different scheme raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        parent = service.create_class(concept_scheme_id=scheme1.id, title="Mammal")

        with pytest.raises(ValueError, match="not in the same scheme"):
            service.create_class(
                concept_scheme_id=scheme2.id,
                title="Tree",
                parent_class_id=parent.id,
            )

    def test_create_class_duplicate_title_in_scheme_raises(self, service):
        """Duplicate title in same scheme raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        service.create_class(concept_scheme_id=scheme.id, title="Dog")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.create_class(concept_scheme_id=scheme.id, title="Dog")

    def test_create_class_same_title_different_scheme_allowed(self, service):
        """Same title in different scheme is allowed."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        cls1 = service.create_class(concept_scheme_id=scheme1.id, title="Life")
        cls2 = service.create_class(concept_scheme_id=scheme2.id, title="Life")
        assert cls1.id != cls2.id

    def test_create_class_empty_title_raises(self, service):
        """Create class with empty title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_class(concept_scheme_id=scheme.id, title="")

    def test_create_class_whitespace_title_raises(self, service):
        """Create class with whitespace-only title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_class(concept_scheme_id=scheme.id, title="   ")


class TestUpdateClass:
    """Tests for update_class."""

    def test_update_class_title_regenerates_embedding(self, service):
        """Update class title regenerates embedding."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog", description="Canine")
        old_embedding = cls.embedding

        updated = service.update_class(class_id=cls.id, title="Canine")
        assert updated.title == "Canine"
        assert updated.embedding != old_embedding

        # Verify event
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 1
        assert "title" in events[0].changed_fields
        assert events[0].old_values == {"title": "Dog"}
        assert events[0].new_values == {"title": "Canine"}

    def test_update_class_description_regenerates_embedding(self, service):
        """Update class description regenerates embedding."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        old_embedding = cls.embedding

        updated = service.update_class(class_id=cls.id, description="Canine species")
        assert updated.description == "Canine species"
        assert updated.embedding != old_embedding

        # Verify event
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 1
        assert "description" in events[0].changed_fields
        assert events[0].old_values == {"description": None}
        assert events[0].new_values == {"description": "Canine species"}

    def test_update_class_title_and_description_together(self, service):
        """Update class with both title and description changed regenerates embedding once."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog", description="Canine")
        old_embedding = cls.embedding
        old_timestamp = cls.last_modified

        updated = service.update_class(
            class_id=cls.id, title="Canine", description="A domesticated animal"
        )
        assert updated.title == "Canine"
        assert updated.description == "A domesticated animal"
        assert updated.embedding != old_embedding
        assert updated.last_modified > old_timestamp

        # Verify event contains both fields
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 1
        assert "title" in events[0].changed_fields
        assert "description" in events[0].changed_fields
        assert events[0].old_values == {"title": "Dog", "description": "Canine"}
        assert events[0].new_values == {
            "title": "Canine",
            "description": "A domesticated animal",
        }

    def test_update_class_no_change_no_embedding_regen(self, service):
        """Update class with no title/description change does not regenerate embedding or emit
        event."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog", description="Canine")
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
        service.create_class(concept_scheme_id=scheme.id, title="Dog")
        cls2 = service.create_class(concept_scheme_id=scheme.id, title="Cat")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.update_class(class_id=cls2.id, title="Dog")

    def test_update_class_same_title_different_scheme_allowed(self, service):
        """Update class to title that exists in different scheme is allowed."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        service.create_class(concept_scheme_id=scheme1.id, title="Life")
        cls2 = service.create_class(concept_scheme_id=scheme2.id, title="Organism")

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
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog", parent_class_id=None)

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
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        dog = service.create_class(
            concept_scheme_id=scheme.id, title="Dog", parent_class_id=mammal.id
        )

        moved = service.move_class(class_id=dog.id, new_parent_id=None)
        assert moved.parent_class_id is None

    def test_move_class_self_parent_raises(self, service):
        """Move a class to itself as parent raises CircularReferenceError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        with pytest.raises(CircularReferenceError, match="own parent"):
            service.move_class(class_id=cls.id, new_parent_id=cls.id)

    def test_move_class_circular_reference_one_level_raises(self, service):
        """Circular reference A→B→A raises CircularReferenceError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        a = service.create_class(concept_scheme_id=scheme.id, title="A")
        b = service.create_class(concept_scheme_id=scheme.id, title="B", parent_class_id=a.id)

        # Try to move A under B, which would create B→A→B
        with pytest.raises(CircularReferenceError, match="circular reference"):
            service.move_class(class_id=a.id, new_parent_id=b.id)

    def test_move_class_circular_reference_deep_raises(self, service):
        """Circular reference A→B→C→A raises CircularReferenceError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        a = service.create_class(concept_scheme_id=scheme.id, title="A")
        b = service.create_class(concept_scheme_id=scheme.id, title="B", parent_class_id=a.id)
        c = service.create_class(concept_scheme_id=scheme.id, title="C", parent_class_id=b.id)

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
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        with pytest.raises(EntityNotFoundError, match="Class"):
            service.move_class(class_id=dog.id, new_parent_id="nonexistent")

    def test_move_class_cross_scheme_parent_raises(self, service):
        """Move a class to a parent in a different scheme raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")

        dog = service.create_class(concept_scheme_id=scheme1.id, title="Dog")
        tree = service.create_class(concept_scheme_id=scheme2.id, title="Tree")

        with pytest.raises(ValueError, match="not in the same scheme"):
            service.move_class(class_id=dog.id, new_parent_id=tree.id)

    def test_move_class_to_current_parent_is_noop(self, service):
        """Moving a class to its current parent is a no-op and does not emit events."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        dog = service.create_class(
            concept_scheme_id=scheme.id, title="Dog", parent_class_id=mammal.id
        )

        # Clear event history from creation
        service._event_publisher.clear()

        # Move dog to its current parent (mammal)
        result = service.move_class(class_id=dog.id, new_parent_id=mammal.id)

        # Verify the class is unchanged
        assert result.parent_class_id == mammal.id

        # Verify no events were emitted (no ClassMoved, no GraphInvalidated)
        class_moved_events = service._event_publisher.get_events_of_type(ClassMoved)
        assert len(class_moved_events) == 0

        invalidation_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        assert len(invalidation_events) == 0

    def test_move_class_to_root_current_parent_is_noop(self, service):
        """Moving a root class to root again is a no-op and does not emit events."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        root_class = service.create_class(concept_scheme_id=scheme.id, title="Root")

        # Clear event history from creation
        service._event_publisher.clear()

        # Move root class to root (None) again
        result = service.move_class(class_id=root_class.id, new_parent_id=None)

        # Verify the class is unchanged
        assert result.parent_class_id is None

        # Verify no events were emitted
        class_moved_events = service._event_publisher.get_events_of_type(ClassMoved)
        assert len(class_moved_events) == 0

        invalidation_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        assert len(invalidation_events) == 0

    def test_move_class_corrupted_hierarchy_raises(self, service):
        """Moving a class with a corrupted ancestor hierarchy raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        a = service.create_class(concept_scheme_id=scheme.id, title="A")
        b = service.create_class(concept_scheme_id=scheme.id, title="B", parent_class_id=a.id)
        c = service.create_class(concept_scheme_id=scheme.id, title="C", parent_class_id=b.id)

        # Corrupt the hierarchy by manually setting B's parent to a nonexistent class
        # (simulating data corruption)
        b_corrupted = b
        b_corrupted.parent_class_id = "nonexistent_parent_id"
        service._repository.save_class(b_corrupted)

        # Now try to move A under C. During ancestor traversal of C:
        # C -> B -> nonexistent -> should raise EntityNotFoundError
        with pytest.raises(EntityNotFoundError):
            service.move_class(class_id=a.id, new_parent_id=c.id)


class TestMoveClassToScheme:
    """Tests for move_class_to_scheme."""

    def test_move_class_to_scheme_success(self, service):
        """Move a class to a different scheme in the same taxonomy."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Organisms")
        cls = service.create_class(concept_scheme_id=scheme1.id, title="Dog")

        moved = service.move_class_to_scheme(class_id=cls.id, target_scheme_id=scheme2.id)
        assert moved.concept_scheme_id == scheme2.id

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 1
        assert events[0].class_id == cls.id
        assert events[0].changed_fields == ("concept_scheme_id",)
        assert events[0].old_values == {"concept_scheme_id": scheme1.id}
        assert events[0].new_values == {"concept_scheme_id": scheme2.id}

    def test_move_class_to_scheme_class_not_found_raises(self, service):
        """Move nonexistent class raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(EntityNotFoundError, match="Class"):
            service.move_class_to_scheme(class_id="nonexistent", target_scheme_id=scheme.id)

    def test_move_class_to_scheme_scheme_not_found_raises(self, service):
        """Move class to nonexistent scheme raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.move_class_to_scheme(class_id=cls.id, target_scheme_id="nonexistent")

    def test_move_class_to_scheme_cross_taxonomy_raises(self, service):
        """Move class to scheme in different taxonomy raises ValueError."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        scheme1 = service.create_scheme(taxonomy_id=tax1.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax2.id, title="Elements")
        cls = service.create_class(concept_scheme_id=scheme1.id, title="Dog")

        with pytest.raises(ValueError, match="different taxonomy"):
            service.move_class_to_scheme(class_id=cls.id, target_scheme_id=scheme2.id)

    def test_move_class_to_same_scheme_emits_event(self, service):
        """Moving a class to its current scheme still emits event."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        # Clear creation events
        service._event_publisher.clear()

        # Move class to its current scheme
        moved = service.move_class_to_scheme(class_id=cls.id, target_scheme_id=scheme.id)
        assert moved.concept_scheme_id == scheme.id

        # Verify event was still emitted (even though it's a no-op semantically)
        events = service._event_publisher.get_events_of_type(ClassUpdated)
        assert len(events) == 1
        assert events[0].class_id == cls.id
        assert events[0].old_values == {"concept_scheme_id": scheme.id}
        assert events[0].new_values == {"concept_scheme_id": scheme.id}


class TestDeleteClass:
    """Tests for delete_class."""

    def test_delete_class_success(self, service):
        """Delete a class with no subclasses."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

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
        parent = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        service.create_class(concept_scheme_id=scheme.id, title="Dog", parent_class_id=parent.id)

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
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
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
        assert rel_delete_events[0].source_id == dog.id
        assert rel_delete_events[0].target_id == mammal.id
        assert rel_delete_events[0].property_definition_id == prop.id

    def test_delete_class_cleans_up_orphaned_relationships_as_target(self, service):
        """Delete class cleans up relationships where it is the target."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
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
        assert rel_delete_events[0].source_id == dog.id
        assert rel_delete_events[0].target_id == mammal.id
        assert rel_delete_events[0].property_definition_id == prop.id

    def test_delete_class_cleans_up_multiple_orphaned_relationships(self, service):
        """Delete class cleans up multiple relationships."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        animal = service.create_class(concept_scheme_id=scheme.id, title="Animal")
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

    def test_delete_class_with_individuals_raises(self, service):
        """Delete class with individuals referencing it raises OntologyError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        service.create_individual(cls.id, title="Fido")

        with pytest.raises(OntologyError, match="has.*individual"):
            service.delete_class(class_id=cls.id)

    def test_delete_class_referenced_as_property_domain_raises(self, service):
        """Delete class referenced as a property definition's domain raises OntologyError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        service.create_property_definition(
            identifier="is_a", title="Is A", domain_class_id=dog.id, range_class_id=mammal.id
        )

        with pytest.raises(OntologyError, match="referenced as domain/range"):
            service.delete_class(class_id=dog.id)

    def test_delete_class_referenced_as_property_range_raises(self, service):
        """Delete class referenced as a property definition's range raises OntologyError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        service.create_property_definition(
            identifier="is_a", title="Is A", domain_class_id=dog.id, range_class_id=mammal.id
        )

        with pytest.raises(OntologyError, match="referenced as domain/range"):
            service.delete_class(class_id=mammal.id)


class TestCreateRelationship:
    """Tests for create_relationship."""

    def test_create_relationship_success(self, service):
        """Create a relationship between two classes."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
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
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
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
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")

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
        target = service.create_class(concept_scheme_id=scheme.id, title="Target")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        with pytest.raises(EntityNotFoundError, match="Entity.*nonexistent"):
            service.create_relationship(
                source_id="nonexistent",
                target_id=target.id,
                property_definition_id=prop.id,
            )

    def test_create_relationship_nonexistent_target_raises(self, service):
        """Create relationship with nonexistent target raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        source = service.create_class(concept_scheme_id=scheme.id, title="Source")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        with pytest.raises(EntityNotFoundError, match="Entity.*nonexistent"):
            service.create_relationship(
                source_id=source.id,
                target_id="nonexistent",
                property_definition_id=prop.id,
            )

    def test_create_relationship_with_valid_entities_emits_correct_taxonomy_id(self, service):
        """Create relationship correctly uses source class's taxonomy for graph invalidation."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
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

    def test_create_relationship_duplicate_triple_raises(self, service):
        """Create relationship with duplicate triple raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.create_relationship(
                source_id=dog.id,
                target_id=mammal.id,
                property_definition_id=prop.id,
            )


class TestDeleteRelationship:
    """Tests for delete_relationship."""

    def test_delete_relationship_success(self, service):
        """Delete a relationship."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
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
        assert events[0].source_id == dog.id
        assert events[0].target_id == mammal.id
        assert events[0].property_definition_id == prop.id

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

    def test_delete_relationship_with_deleted_source_class(self, service):
        """Delete relationship when source class is missing uses target class taxonomy."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        rel = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        # Delete the source class directly from repository to simulate external deletion
        service._repository.delete_class(dog.id)

        # Delete the relationship - should still emit valid GraphInvalidated with target's taxonomy
        service.delete_relationship(relationship_id=rel.id)

        # Verify the relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify GraphInvalidated event uses target class's taxonomy
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == 1
        # Should use target's taxonomy since source is missing
        assert delete_graph_events[0].taxonomy_id == tax.id

    def test_delete_relationship_with_deleted_source_and_target_classes(self, service):
        """Delete relationship when both source and target classes are missing emits no
        GraphInvalidated."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        rel = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop.id,
        )

        # Delete both source and target classes directly from repository
        service._repository.delete_class(dog.id)
        service._repository.delete_class(mammal.id)

        # Get current count of GraphInvalidated events before deletion
        existing_graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        existing_count = len(
            [e for e in existing_graph_events if e.reason == "relationship_deleted"]
        )

        # Delete the relationship - should not emit GraphInvalidated since no valid taxonomy found
        service.delete_relationship(relationship_id=rel.id)

        # Verify the relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify no new GraphInvalidated event was emitted (since taxonomy couldn't be determined)
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == existing_count

    def test_delete_relationship_with_individual_source(self, service):
        """Delete relationship where source is an Individual resolves taxonomy from its parent
        class."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        animal_class = service.create_class(concept_scheme_id=scheme.id, title="Animal")
        mammal_class = service.create_class(concept_scheme_id=scheme.id, title="Mammal")

        # Create an individual as the source
        individual = service.create_individual(class_ids=animal_class.id, title="Fluffy")

        prop = service.create_property_definition(identifier="is_a", title="Is A")
        rel = service.create_relationship(
            source_id=individual.id,
            target_id=mammal_class.id,
            property_definition_id=prop.id,
        )

        service.delete_relationship(relationship_id=rel.id)

        # Verify the relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify GraphInvalidated event uses the Individual's parent class taxonomy
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == 1
        assert delete_graph_events[0].taxonomy_id == tax.id

    def test_delete_relationship_with_individual_target(self, service):
        """Delete relationship where target is an Individual resolves taxonomy from its parent
        class."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        animal_class = service.create_class(concept_scheme_id=scheme.id, title="Animal")
        mammal_class = service.create_class(concept_scheme_id=scheme.id, title="Mammal")

        # Create an individual as the target
        individual = service.create_individual(class_ids=mammal_class.id, title="Fido")

        prop = service.create_property_definition(identifier="is_a", title="Is A")
        rel = service.create_relationship(
            source_id=animal_class.id,
            target_id=individual.id,
            property_definition_id=prop.id,
        )

        service.delete_relationship(relationship_id=rel.id)

        # Verify the relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify GraphInvalidated event uses the Individual's parent class taxonomy
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == 1
        assert delete_graph_events[0].taxonomy_id == tax.id

    def test_delete_relationship_with_both_individuals(self, service):
        """Delete relationship where both source and target are Individuals."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        animal_class = service.create_class(concept_scheme_id=scheme.id, title="Animal")

        # Create individuals for both source and target
        individual1 = service.create_individual(class_ids=animal_class.id, title="Fluffy")
        individual2 = service.create_individual(class_ids=animal_class.id, title="Fido")

        prop = service.create_property_definition(identifier="related_to", title="Related To")
        rel = service.create_relationship(
            source_id=individual1.id,
            target_id=individual2.id,
            property_definition_id=prop.id,
        )

        service.delete_relationship(relationship_id=rel.id)

        # Verify the relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify GraphInvalidated event uses the taxonomy
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == 1
        assert delete_graph_events[0].taxonomy_id == tax.id

    def test_delete_relationship_with_individual_source_deleted_parent_class(self, service):
        """Delete relationship where source Individual's parent class is deleted uses target class
        taxonomy."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        animal_class = service.create_class(concept_scheme_id=scheme.id, title="Animal")
        mammal_class = service.create_class(concept_scheme_id=scheme.id, title="Mammal")

        # Create an individual
        individual = service.create_individual(class_ids=animal_class.id, title="Fluffy")

        prop = service.create_property_definition(identifier="is_a", title="Is A")
        rel = service.create_relationship(
            source_id=individual.id,
            target_id=mammal_class.id,
            property_definition_id=prop.id,
        )

        # Delete the individual's parent class
        service._repository.delete_class(animal_class.id)

        # Delete the relationship - should use target class's taxonomy
        service.delete_relationship(relationship_id=rel.id)

        # Verify the relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify GraphInvalidated event uses target class taxonomy
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == 1
        assert delete_graph_events[0].taxonomy_id == tax.id

    def test_delete_relationship_with_individuals_and_deleted_parent_classes(
        self, service, monkeypatch
    ):
        """Delete relationship where both Individuals have deleted parent classes emits warning and
        no GraphInvalidated."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        animal_class = service.create_class(concept_scheme_id=scheme.id, title="Animal")
        mammal_class = service.create_class(concept_scheme_id=scheme.id, title="Mammal")

        # Create individuals for both source and target
        individual1 = service.create_individual(class_ids=animal_class.id, title="Fluffy")
        individual2 = service.create_individual(class_ids=mammal_class.id, title="Fido")

        prop = service.create_property_definition(identifier="related_to", title="Related To")
        rel = service.create_relationship(
            source_id=individual1.id,
            target_id=individual2.id,
            property_definition_id=prop.id,
        )

        # Delete both parent classes
        service._repository.delete_class(animal_class.id)
        service._repository.delete_class(mammal_class.id)

        # Get current count before deletion
        existing_graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        existing_count = len(
            [e for e in existing_graph_events if e.reason == "relationship_deleted"]
        )

        logger_mock = MagicMock()
        monkeypatch.setattr(domain.ontology.services, "_logger", logger_mock)

        # Delete the relationship - should not emit GraphInvalidated and should log warning
        service.delete_relationship(relationship_id=rel.id)

        # Verify the relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify no new GraphInvalidated event was emitted
        graph_events = service._event_publisher.get_events_of_type(GraphInvalidated)
        delete_graph_events = [e for e in graph_events if e.reason == "relationship_deleted"]
        assert len(delete_graph_events) == existing_count

        # Verify warning was logged
        warning_calls = [
            call
            for call in logger_mock.warning.call_args_list
            if call[0]
            and "Could not determine taxonomy for relationship deletion" in str(call[0][0])
        ]
        assert warning_calls


class TestGetPropertyDefinition:
    """Tests for get_property_definition."""

    def test_get_property_definition_success(self, service):
        """Retrieve a property description by ID."""
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        retrieved = service.get_property_definition(prop.id)
        assert retrieved.id == prop.id
        assert retrieved.identifier == "is_a"
        assert retrieved.title == "Is A"

    def test_get_property_definition_nonexistent_raises(self, service):
        """Get nonexistent property description raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="PropertyDefinition"):
            service.get_property_definition("nonexistent")


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

    def test_create_property_definition_with_domain_and_range_success(self, service):
        """Create a property definition with valid domain_class_id and range_class_id."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        domain_cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        range_cls = service.create_class(concept_scheme_id=scheme.id, title="Bone")

        prop = service.create_property_definition(
            identifier="chews",
            title="Chews",
            domain_class_id=domain_cls.id,
            range_class_id=range_cls.id,
        )

        assert prop.domain_class_id == domain_cls.id
        assert prop.range_class_id == range_cls.id

    def test_create_property_definition_with_external_references_success(self, service):
        """Create a property definition with external references."""
        from domain.ontology.value_objects import ExternalReference

        refs = [ExternalReference(source="wikidata", identifier="P31")]
        prop = service.create_property_definition(
            identifier="instance_of",
            title="Instance Of",
            external_references=refs,
        )

        assert prop.external_references == refs

    def test_create_property_definition_nonexistent_domain_class_raises(self, service):
        """Nonexistent domain_class_id raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.create_property_definition(
                identifier="chews",
                title="Chews",
                domain_class_id="nonexistent",
            )

    def test_create_property_definition_nonexistent_range_class_raises(self, service):
        """Nonexistent range_class_id raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.create_property_definition(
                identifier="chews",
                title="Chews",
                range_class_id="nonexistent",
            )


class TestUpdatePropertyDefinition:
    """Tests for update_property_definition."""

    def test_update_title_success(self, service):
        """Update title of a property definition."""
        from domain.ontology.events import PropertyDefinitionUpdated

        prop = service.create_property_definition(identifier="is_a", title="Is A")
        service._event_publisher.clear()

        updated = service.update_property_definition(property_id=prop.id, title="Is A Type")
        assert updated.title == "Is A Type"

        retrieved = service.get_property_definition(prop.id)
        assert retrieved.title == "Is A Type"

        events = service._event_publisher.get_events_of_type(PropertyDefinitionUpdated)
        assert len(events) == 1
        assert events[0].property_id == prop.id
        assert events[0].title == "Is A Type"

    def test_update_description_success(self, service):
        """Update description of a property definition."""
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        service._event_publisher.clear()

        updated = service.update_property_definition(
            property_id=prop.id, description="New description"
        )
        assert updated.description == "New description"

    def test_is_relevant_not_provided_preserves_existing_value(self, service):
        """When update_is_relevant is False, the is_relevant field is not changed."""
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        prop_with_value = service.update_property_definition(
            property_id=prop.id, is_relevant=True, update_is_relevant=True
        )
        assert prop_with_value.is_relevant is True

        # Now update without touching is_relevant
        updated = service.update_property_definition(property_id=prop.id, title="Is A Type")
        assert updated.is_relevant is True

    def test_is_relevant_set_to_none_clears_flag(self, service):
        """Explicitly passing is_relevant=None with update_is_relevant=True clears the flag."""
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        service.update_property_definition(
            property_id=prop.id, is_relevant=True, update_is_relevant=True
        )

        updated = service.update_property_definition(
            property_id=prop.id, is_relevant=None, update_is_relevant=True
        )
        assert updated.is_relevant is None

    def test_is_relevant_set_to_true(self, service):
        """Set is_relevant to True."""
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        updated = service.update_property_definition(
            property_id=prop.id, is_relevant=True, update_is_relevant=True
        )
        assert updated.is_relevant is True

    def test_is_relevant_set_to_false(self, service):
        """Set is_relevant to False."""
        prop = service.create_property_definition(identifier="is_a", title="Is A")
        updated = service.update_property_definition(
            property_id=prop.id, is_relevant=False, update_is_relevant=True
        )
        assert updated.is_relevant is False

    def test_update_duplicate_title_raises(self, service):
        """Updating to a duplicate title raises DuplicateEntityError."""
        service.create_property_definition(identifier="is_a", title="Is A")
        prop2 = service.create_property_definition(identifier="part_of", title="Part Of")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.update_property_definition(property_id=prop2.id, title="Is A")

    def test_update_empty_title_raises(self, service):
        """Updating to an empty title raises ValueError."""
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.update_property_definition(property_id=prop.id, title="")

    def test_update_nonexistent_property_raises(self, service):
        """Update of a nonexistent property raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="PropertyDefinition"):
            service.update_property_definition(property_id="nonexistent", title="New Title")

    def test_update_domain_and_range_class_success(self, service):
        """Update domain_class_id and range_class_id to valid classes."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        domain_cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        range_cls = service.create_class(concept_scheme_id=scheme.id, title="Bone")
        prop = service.create_property_definition(identifier="chews", title="Chews")

        updated = service.update_property_definition(
            property_id=prop.id,
            domain_class_id=domain_cls.id,
            range_class_id=range_cls.id,
            update_domain_class_id=True,
            update_range_class_id=True,
        )

        assert updated.domain_class_id == domain_cls.id
        assert updated.range_class_id == range_cls.id

    def test_domain_and_range_class_id_not_provided_preserves_existing_value(self, service):
        """When update_domain_class_id/update_range_class_id are False, the fields are unchanged."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        domain_cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        range_cls = service.create_class(concept_scheme_id=scheme.id, title="Bone")
        prop = service.create_property_definition(identifier="chews", title="Chews")
        service.update_property_definition(
            property_id=prop.id,
            domain_class_id=domain_cls.id,
            range_class_id=range_cls.id,
            update_domain_class_id=True,
            update_range_class_id=True,
        )

        updated = service.update_property_definition(property_id=prop.id, title="Chews Loudly")
        assert updated.domain_class_id == domain_cls.id
        assert updated.range_class_id == range_cls.id

    def test_domain_and_range_class_id_set_to_none_clears_them(self, service):
        """Explicitly passing None with update_domain/range_class_id=True clears them."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        domain_cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        range_cls = service.create_class(concept_scheme_id=scheme.id, title="Bone")
        prop = service.create_property_definition(identifier="chews", title="Chews")
        service.update_property_definition(
            property_id=prop.id,
            domain_class_id=domain_cls.id,
            range_class_id=range_cls.id,
            update_domain_class_id=True,
            update_range_class_id=True,
        )

        updated = service.update_property_definition(
            property_id=prop.id,
            domain_class_id=None,
            range_class_id=None,
            update_domain_class_id=True,
            update_range_class_id=True,
        )

        assert updated.domain_class_id is None
        assert updated.range_class_id is None

    def test_update_external_references_success(self, service):
        """Update external_references replaces the existing list."""
        from domain.ontology.value_objects import ExternalReference

        prop = service.create_property_definition(identifier="chews", title="Chews")
        refs = [ExternalReference(source="wikidata", identifier="P31")]

        updated = service.update_property_definition(property_id=prop.id, external_references=refs)

        assert updated.external_references == refs

    def test_update_nonexistent_domain_class_raises(self, service):
        """Updating domain_class_id to a nonexistent class raises EntityNotFoundError."""
        prop = service.create_property_definition(identifier="chews", title="Chews")

        with pytest.raises(EntityNotFoundError, match="Class"):
            service.update_property_definition(
                property_id=prop.id, domain_class_id="nonexistent", update_domain_class_id=True
            )

    def test_update_nonexistent_range_class_raises(self, service):
        """Updating range_class_id to a nonexistent class raises EntityNotFoundError."""
        prop = service.create_property_definition(identifier="chews", title="Chews")

        with pytest.raises(EntityNotFoundError, match="Class"):
            service.update_property_definition(
                property_id=prop.id, range_class_id="nonexistent", update_range_class_id=True
            )


class TestUpdateConceptScheme:
    """Tests for update_concept_scheme."""

    def test_update_title_success(self, service):
        """Update the title of a concept scheme."""
        from domain.ontology.events import ConceptSchemeUpdated

        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        service._event_publisher.clear()

        updated = service.update_concept_scheme(concept_scheme_id=scheme.id, title="Animal Kingdom")
        assert updated.title == "Animal Kingdom"

        retrieved = service.get_concept_scheme(scheme.id)
        assert retrieved.title == "Animal Kingdom"

        events = service._event_publisher.get_events_of_type(ConceptSchemeUpdated)
        assert len(events) == 1
        assert events[0].concept_scheme_id == scheme.id
        assert events[0].title == "Animal Kingdom"

    def test_update_description_success(self, service):
        """Update the description of a concept scheme."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        updated = service.update_concept_scheme(
            concept_scheme_id=scheme.id, description="Revised description"
        )
        assert updated.description == "Revised description"

    def test_update_color_success(self, service):
        """Update the color of a concept scheme."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        updated = service.update_concept_scheme(concept_scheme_id=scheme.id, color="#ff0000")
        assert updated.color == "#ff0000"

    def test_move_to_different_taxonomy_success(self, service):
        """Move a concept scheme to a different taxonomy."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        scheme = service.create_scheme(taxonomy_id=tax1.id, title="Animals")

        updated = service.update_concept_scheme(concept_scheme_id=scheme.id, taxonomy_id=tax2.id)
        assert updated.taxonomy_id == tax2.id

        retrieved = service.get_concept_scheme(scheme.id)
        assert retrieved.taxonomy_id == tax2.id

    def test_move_with_title_unique_in_target_taxonomy_succeeds(self, service):
        """Moving a scheme to a target taxonomy where the title is unique succeeds."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        service.create_scheme(taxonomy_id=tax2.id, title="Other Scheme")
        scheme = service.create_scheme(taxonomy_id=tax1.id, title="Animals")

        updated = service.update_concept_scheme(concept_scheme_id=scheme.id, taxonomy_id=tax2.id)
        assert updated.taxonomy_id == tax2.id

    def test_move_with_duplicate_title_in_target_taxonomy_raises(self, service):
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        service.create_scheme(taxonomy_id=tax2.id, title="Animals")
        scheme = service.create_scheme(taxonomy_id=tax1.id, title="Animals")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.update_concept_scheme(concept_scheme_id=scheme.id, taxonomy_id=tax2.id)

    def test_update_duplicate_title_in_same_taxonomy_raises(self, service):
        tax = service.create_taxonomy(title="Biology")
        service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.update_concept_scheme(concept_scheme_id=scheme2.id, title="Animals")

    def test_update_empty_title_raises(self, service):
        """Updating a scheme's title to an empty string raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.update_concept_scheme(concept_scheme_id=scheme.id, title="")

    def test_update_nonexistent_scheme_raises(self, service):
        """Updating a nonexistent scheme raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="ConceptScheme"):
            service.update_concept_scheme(concept_scheme_id="nonexistent", title="New Title")

    def test_move_to_nonexistent_taxonomy_raises(self, service):
        """Moving a scheme to a nonexistent taxonomy raises EntityNotFoundError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")

        with pytest.raises(EntityNotFoundError, match="Taxonomy"):
            service.update_concept_scheme(concept_scheme_id=scheme.id, taxonomy_id="nonexistent")

    def test_same_title_different_taxonomy_allowed(self, service):
        """A scheme can have the same title as one in a different taxonomy."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        service.create_scheme(taxonomy_id=tax1.id, title="Elements")
        scheme2 = service.create_scheme(taxonomy_id=tax2.id, title="Elements")

        # Updating title to same value (no-op check) should not raise
        updated = service.update_concept_scheme(
            concept_scheme_id=scheme2.id, description="Chemistry elements"
        )
        assert updated.description == "Chemistry elements"


class TestGetOrCreatePropertyDefinitionByIdentifier:
    """Tests for get_or_create_property_definition_by_identifier."""

    def test_get_or_create_creates_new_property(self, service):
        """First call with new identifier creates a new property definition."""
        prop = service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Is A",
            description="Taxonomic is-a relationship",
        )

        assert prop.id is not None
        assert prop.identifier == "is_a"
        assert prop.title == "Is A"
        assert prop.description == "Taxonomic is-a relationship"

        # Verify PropertyDefinitionCreated event was emitted
        events = service._event_publisher.get_events_of_type(PropertyDefinitionCreated)
        assert len(events) == 1
        assert events[0].property_id == prop.id

    def test_get_or_create_returns_existing_property(self, service):
        """Second call with same identifier returns existing property without creating duplicate."""
        # Create first
        prop1 = service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Is A",
        )

        # Clear event history from first creation
        service._event_publisher.clear()

        # Get or create again with same identifier
        prop2 = service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Is A",
        )

        # Should return the same property
        assert prop2.id == prop1.id
        assert prop2.identifier == prop1.identifier

        # No new event should be emitted
        events = service._event_publisher.get_events_of_type(PropertyDefinitionCreated)
        assert len(events) == 0

    def test_get_or_create_ignores_title_on_existing_lookup(self, service):
        """When property exists, provided title is ignored."""
        # Create with original title
        prop1 = service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Is A",
        )

        # Try to get with different title
        prop2 = service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Different Title",
        )

        # Should return the same property with original title
        assert prop2.id == prop1.id
        assert prop2.title == "Is A"  # Original title, not "Different Title"

    def test_get_or_create_empty_identifier_raises(self, service):
        """Empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            service.get_or_create_property_definition_by_identifier(
                identifier="",
                title="Is A",
            )

    def test_get_or_create_whitespace_identifier_raises(self, service):
        """Whitespace-only identifier raises ValueError."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            service.get_or_create_property_definition_by_identifier(
                identifier="   ",
                title="Is A",
            )

    def test_get_or_create_empty_title_when_creating_raises(self, service):
        """Empty title when creating new property raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty when creating"):
            service.get_or_create_property_definition_by_identifier(
                identifier="is_a",
                title="",
            )

    def test_get_or_create_whitespace_title_when_creating_raises(self, service):
        """Whitespace-only title when creating new property raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty when creating"):
            service.get_or_create_property_definition_by_identifier(
                identifier="is_a",
                title="   ",
            )

    def test_get_or_create_none_title_when_creating_raises(self, service):
        """None title when creating new property raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty when creating"):
            service.get_or_create_property_definition_by_identifier(
                identifier="is_a",
                title=None,
            )

    def test_get_or_create_duplicate_title_with_different_identifier_raises(self, service):
        """Creating with duplicate title but different identifier raises DuplicateEntityError."""
        service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Is A",
        )

        with pytest.raises(DuplicateEntityError, match="title"):
            service.get_or_create_property_definition_by_identifier(
                identifier="also_is_a",
                title="Is A",  # Duplicate title!
            )

    def test_get_or_create_with_description(self, service):
        """Create new property with optional description."""
        prop = service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Is A",
            description="Taxonomic relationship",
        )

        assert prop.description == "Taxonomic relationship"

    def test_get_or_create_with_none_description(self, service):
        """Create new property with None description."""
        prop = service.get_or_create_property_definition_by_identifier(
            identifier="is_a",
            title="Is A",
            description=None,
        )

        assert prop.description is None


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
        cls1 = service.create_class(concept_scheme_id=scheme1.id, title="Dog")
        service.create_class(concept_scheme_id=scheme2.id, title="Tree")
        classes = service.list_classes(concept_scheme_id=scheme1.id)
        assert len(classes) == 1
        assert classes[0].id == cls1.id

    def test_list_classes_filtered_by_parent(self, service):
        """List classes filtered by parent class."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        dog = service.create_class(
            concept_scheme_id=scheme.id, title="Dog", parent_class_id=mammal.id
        )
        cat = service.create_class(
            concept_scheme_id=scheme.id, title="Cat", parent_class_id=mammal.id
        )
        children = service.list_classes(parent_class_id=mammal.id)
        assert len(children) == 2
        assert any(c.id == dog.id for c in children)
        assert any(c.id == cat.id for c in children)

    def test_list_relationships_filtered(self, service):
        """List relationships with filters."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
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

        # Filter by property_id
        by_property = service.list_relationships(property_id=prop.id)
        assert len(by_property) == 1
        assert by_property[0].id == rel.id

    def test_list_relationships_filtered_by_property(self, service):
        """List relationships filtered by property_id."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        animal = service.create_class(concept_scheme_id=scheme.id, title="Animal")

        prop_is_a = service.create_property_definition(identifier="is_a", title="Is A")
        prop_part_of = service.create_property_definition(identifier="part_of", title="Part Of")

        # Create relationships with different property descriptions
        rel1 = service.create_relationship(
            source_id=dog.id,
            target_id=mammal.id,
            property_definition_id=prop_is_a.id,
        )
        rel2 = service.create_relationship(
            source_id=dog.id,
            target_id=animal.id,
            property_definition_id=prop_part_of.id,
        )

        # Filter by first property
        by_is_a = service.list_relationships(property_id=prop_is_a.id)
        assert len(by_is_a) == 1
        assert by_is_a[0].id == rel1.id

        # Filter by second property
        by_part_of = service.list_relationships(property_id=prop_part_of.id)
        assert len(by_part_of) == 1
        assert by_part_of[0].id == rel2.id

    def test_list_property_definitions(self, service):
        """List all property descriptions."""
        prop1 = service.create_property_definition(identifier="is_a", title="Is A")
        prop2 = service.create_property_definition(identifier="part_of", title="Part Of")
        props = service.list_property_definitions()
        assert len(props) == 2
        assert any(p.id == prop1.id for p in props)
        assert any(p.id == prop2.id for p in props)

    def test_list_property_definitions_filtered_by_is_relevant(self, service):
        """List property descriptions filtered by is_relevant flag."""
        # Create properties with different relevance states
        prop_relevant = service.create_property_definition(identifier="is_a", title="Is A")
        prop_relevant.is_relevant = True
        service._repository.save_property_definition(prop_relevant)

        prop_irrelevant = service.create_property_definition(identifier="part_of", title="Part Of")
        prop_irrelevant.is_relevant = False
        service._repository.save_property_definition(prop_irrelevant)

        service.create_property_definition(identifier="related_to", title="Related To")
        # is_relevant is None by default, no save needed

        # Filter for relevant properties
        relevant_props = service.list_property_definitions(is_relevant=True)
        assert len(relevant_props) == 1
        assert relevant_props[0].id == prop_relevant.id

        # Filter for irrelevant properties
        irrelevant_props = service.list_property_definitions(is_relevant=False)
        assert len(irrelevant_props) == 1
        assert irrelevant_props[0].id == prop_irrelevant.id

        # List all properties without filter
        all_props = service.list_property_definitions()
        assert len(all_props) == 3


class TestIndividualIndexSync:
    """The individual vector index is kept in sync on write (#1142)."""

    def _service_with_index(self):
        from tests.fakes.fake_individual_vector_index import FakeIndividualVectorIndex

        index = FakeIndividualVectorIndex()
        service = OntologyService(
            repository=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            event_publisher=FakeEventPublisher(),
            individual_index=index,
        )
        return service, index

    def _make_class(self, service):
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        return service.create_class(concept_scheme_id=scheme.id, title="Dog")

    def test_create_individual_indexes_it(self):
        """create_individual registers the individual in the wired index."""
        service, index = self._service_with_index()
        cls = self._make_class(service)

        individual = service.create_individual(cls.id, title="Fido")

        assert individual.id in index._individuals
        assert index._individuals[individual.id][0] == "Fido"

    def test_update_individual_reindexes_new_title(self):
        """update_individual re-indexes with the updated title."""
        service, index = self._service_with_index()
        cls = self._make_class(service)
        individual = service.create_individual(cls.id, title="Fido")

        service.update_individual(individual.id, title="Rex")

        assert index._individuals[individual.id][0] == "Rex"

    def test_index_sync_failure_does_not_fail_create(self):
        """A failure in the index must not fail the already-persisted write."""
        service, index = self._service_with_index()
        cls = self._make_class(service)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("index unavailable")

        index.index_individual = _boom  # type: ignore[method-assign]

        # Must not raise; the individual is still created and retrievable.
        individual = service.create_individual(cls.id, title="Fido")
        assert service.get_individual(individual.id).title == "Fido"

    def test_no_index_wired_is_noop(self, service):
        """With no index (default), create/update just work — no error."""
        cls = self._make_class(service)
        individual = service.create_individual(cls.id, title="Fido")
        service.update_individual(individual.id, title="Rex")
        assert service.get_individual(individual.id).title == "Rex"


class TestIndividualSchemaVectorIndexSync:
    """create_individual/update_individual sync the schema vector index too (#1137)."""

    def _service_with_index(self):
        from tests.fakes.fake_schema_vector_index import FakeSchemaVectorIndex

        index = FakeSchemaVectorIndex()
        service = OntologyService(
            repository=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            event_publisher=FakeEventPublisher(),
            schema_index=index,
        )
        return service, index

    def _make_class(self, service):
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        return service.create_class(concept_scheme_id=scheme.id, title="Dog")

    def test_create_individual_syncs_schema_index(self):
        """create_individual embeds the individual in the schema vector index."""
        service, index = self._service_with_index()
        cls = self._make_class(service)

        individual = service.create_individual(cls.id, title="Fido", description="A friendly dog")

        assert index._entities[individual.id] == ("Fido", "A friendly dog")

    def test_update_individual_resyncs_schema_index(self):
        """update_individual re-embeds with the updated title/description."""
        service, index = self._service_with_index()
        cls = self._make_class(service)
        individual = service.create_individual(cls.id, title="Fido")

        service.update_individual(individual.id, title="Rex", description="A loyal dog")

        assert index._entities[individual.id] == ("Rex", "A loyal dog")

    def test_schema_index_sync_failure_does_not_fail_create(self):
        """A failure in the schema index must not fail the already-persisted write."""
        service, index = self._service_with_index()
        cls = self._make_class(service)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("index unavailable")

        index.index_entity = _boom  # type: ignore[method-assign]

        individual = service.create_individual(cls.id, title="Fido")
        assert service.get_individual(individual.id).title == "Fido"

    def test_no_schema_index_wired_is_noop(self, service):
        """With no schema index wired (default), create/update just work — no error."""
        cls = self._make_class(service)
        individual = service.create_individual(cls.id, title="Fido")
        service.update_individual(individual.id, title="Rex")
        assert service.get_individual(individual.id).title == "Rex"


class TestCreateIndividual:
    """Tests for create_individual."""

    def test_create_individual_with_title_only(self, service):
        """Create individual with title only."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        individual = service.create_individual(cls.id, title="Fido")
        assert individual.id is not None
        assert individual.class_ids == [cls.id]
        assert individual.title == "Fido"
        assert individual.description is None
        assert individual.created_at is not None
        assert individual.last_modified is not None

    def test_create_individual_with_description(self, service):
        """Create individual with title and description."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        individual = service.create_individual(cls.id, title="Fido", description="A friendly dog")
        assert individual.title == "Fido"
        assert individual.description == "A friendly dog"

    def test_create_individual_nonexistent_class_raises(self, service):
        """Create individual with nonexistent class raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.create_individual("nonexistent", title="Test")

    def test_create_individual_empty_title_raises(self, service):
        """Create individual with empty title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_individual(cls.id, title="")

    def test_create_individual_whitespace_title_raises(self, service):
        """Create individual with whitespace-only title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_individual(cls.id, title="   ")

    def test_create_individual_duplicate_title_in_class_raises(self, service):
        """Create individual with duplicate title in same class raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        service.create_individual(cls.id, title="Fido")
        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.create_individual(cls.id, title="Fido")

    def test_create_individual_same_title_different_class_allowed(self, service):
        """Create individuals with same title in different classes is allowed."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls1 = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        cls2 = service.create_class(concept_scheme_id=scheme.id, title="Cat")

        ind1 = service.create_individual(cls1.id, title="Fluffy")
        ind2 = service.create_individual(cls2.id, title="Fluffy")
        assert ind1.class_ids == [cls1.id]
        assert ind2.class_ids == [cls2.id]
        assert ind1.title == ind2.title


class TestGetIndividual:
    """Tests for get_individual."""

    def test_get_individual_returns_created_individual(self, service):
        """Get individual returns the created individual."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        created = service.create_individual(cls.id, title="Fido")

        retrieved = service.get_individual(created.id)
        assert retrieved.id == created.id
        assert retrieved.title == "Fido"

    def test_get_individual_nonexistent_raises(self, service):
        """Get nonexistent individual raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Individual"):
            service.get_individual("nonexistent")


class TestListIndividuals:
    """Tests for list_individuals."""

    def test_list_individuals_empty(self, service):
        """List individuals returns empty list when none exist."""
        individuals = service.list_individuals()
        assert individuals == []

    def test_list_individuals_all(self, service):
        """List individuals returns all individuals."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls1 = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        cls2 = service.create_class(concept_scheme_id=scheme.id, title="Cat")

        ind1 = service.create_individual(cls1.id, title="Fido")
        ind2 = service.create_individual(cls1.id, title="Rover")
        ind3 = service.create_individual(cls2.id, title="Whiskers")

        individuals = service.list_individuals()
        assert len(individuals) == 3
        assert ind1 in individuals
        assert ind2 in individuals
        assert ind3 in individuals

    def test_list_individuals_filter_by_class(self, service):
        """List individuals filtered by class returns only individuals in that class."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls1 = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        cls2 = service.create_class(concept_scheme_id=scheme.id, title="Cat")

        ind1 = service.create_individual(cls1.id, title="Fido")
        ind2 = service.create_individual(cls1.id, title="Rover")
        service.create_individual(cls2.id, title="Whiskers")

        dog_individuals = service.list_individuals(class_id=cls1.id)
        assert len(dog_individuals) == 2
        assert ind1 in dog_individuals
        assert ind2 in dog_individuals


class TestUpdateIndividual:
    """Tests for update_individual."""

    def test_update_individual_title(self, service):
        """Update individual title."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        individual = service.create_individual(cls.id, title="Fido")
        old_timestamp = individual.last_modified

        updated = service.update_individual(individual.id, title="Buddy")
        assert updated.title == "Buddy"
        assert updated.last_modified > old_timestamp

    def test_update_individual_description(self, service):
        """Update individual description."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        individual = service.create_individual(cls.id, title="Fido")

        updated = service.update_individual(individual.id, description="A friendly dog")
        assert updated.description == "A friendly dog"

    def test_update_individual_title_and_description(self, service):
        """Update individual title and description together."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        individual = service.create_individual(cls.id, title="Fido", description="Old desc")

        updated = service.update_individual(individual.id, title="Buddy", description="New desc")
        assert updated.title == "Buddy"
        assert updated.description == "New desc"

    def test_update_individual_nonexistent_raises(self, service):
        """Update nonexistent individual raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Individual"):
            service.update_individual("nonexistent", title="NewTitle")

    def test_update_individual_empty_title_raises(self, service):
        """Update individual to empty title raises ValueError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        individual = service.create_individual(cls.id, title="Fido")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.update_individual(individual.id, title="")

    def test_update_individual_duplicate_title_raises(self, service):
        """Update individual to duplicate title in class raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")

        service.create_individual(cls.id, title="Fido")
        ind2 = service.create_individual(cls.id, title="Buddy")

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.update_individual(ind2.id, title="Fido")

    def test_update_individual_same_title_no_change(self, service):
        """Update individual to same title is allowed (no-op)."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        individual = service.create_individual(cls.id, title="Fido")

        # Updating to same title should not raise
        updated = service.update_individual(individual.id, title="Fido")
        assert updated.title == "Fido"


class TestDeleteIndividual:
    """Tests for delete_individual."""

    def test_delete_individual_succeeds(self, service):
        """Delete individual succeeds."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        cls = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        individual = service.create_individual(cls.id, title="Fido")

        service.delete_individual(individual.id)
        with pytest.raises(EntityNotFoundError):
            service.get_individual(individual.id)

    def test_delete_individual_nonexistent_raises(self, service):
        """Delete nonexistent individual raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Individual"):
            service.delete_individual("nonexistent")

    def test_delete_individual_cleans_up_orphaned_relationships_as_source(self, service):
        """Delete individual cleans up relationships where it is the source."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog_class = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal_class = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        fido = service.create_individual(dog_class.id, title="Fido")
        animal_ind = service.create_individual(mammal_class.id, title="Animal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        rel = service.create_relationship(
            source_id=fido.id,
            target_id=animal_ind.id,
            property_definition_id=prop.id,
        )

        # Delete the source individual
        service.delete_individual(individual_id=fido.id)

        # Verify relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify RelationshipDeleted event was emitted
        rel_delete_events = service._event_publisher.get_events_of_type(RelationshipDeleted)
        assert len(rel_delete_events) == 1
        assert rel_delete_events[0].relationship_id == rel.id
        assert rel_delete_events[0].source_id == fido.id
        assert rel_delete_events[0].target_id == animal_ind.id
        assert rel_delete_events[0].property_definition_id == prop.id

    def test_delete_individual_cleans_up_orphaned_relationships_as_target(self, service):
        """Delete individual cleans up relationships where it is the target."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog_class = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal_class = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        fido = service.create_individual(dog_class.id, title="Fido")
        animal_ind = service.create_individual(mammal_class.id, title="Animal")
        prop = service.create_property_definition(identifier="is_a", title="Is A")

        rel = service.create_relationship(
            source_id=fido.id,
            target_id=animal_ind.id,
            property_definition_id=prop.id,
        )

        # Delete the target individual
        service.delete_individual(individual_id=animal_ind.id)

        # Verify relationship is deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel.id)

        # Verify RelationshipDeleted event was emitted
        rel_delete_events = service._event_publisher.get_events_of_type(RelationshipDeleted)
        assert len(rel_delete_events) == 1
        assert rel_delete_events[0].relationship_id == rel.id
        assert rel_delete_events[0].source_id == fido.id
        assert rel_delete_events[0].target_id == animal_ind.id
        assert rel_delete_events[0].property_definition_id == prop.id

    def test_delete_individual_cleans_up_multiple_orphaned_relationships(self, service):
        """Delete individual cleans up multiple relationships."""
        tax = service.create_taxonomy(title="Biology")
        scheme = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        dog_class = service.create_class(concept_scheme_id=scheme.id, title="Dog")
        mammal_class = service.create_class(concept_scheme_id=scheme.id, title="Mammal")
        fido = service.create_individual(dog_class.id, title="Fido")
        buddy = service.create_individual(dog_class.id, title="Buddy")
        animal_ind = service.create_individual(mammal_class.id, title="Animal")
        prop1 = service.create_property_definition(identifier="is_friend_of", title="Is Friend Of")
        prop2 = service.create_property_definition(identifier="is_a", title="Is A")

        rel1 = service.create_relationship(
            source_id=fido.id,
            target_id=buddy.id,
            property_definition_id=prop1.id,
        )
        rel2 = service.create_relationship(
            source_id=fido.id,
            target_id=animal_ind.id,
            property_definition_id=prop2.id,
        )

        # Delete individual with multiple relationships
        service.delete_individual(individual_id=fido.id)

        # Verify both relationships are deleted
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel1.id)
        with pytest.raises(EntityNotFoundError):
            service.get_relationship(rel2.id)

        # Verify both RelationshipDeleted events were emitted
        rel_delete_events = service._event_publisher.get_events_of_type(RelationshipDeleted)
        assert len(rel_delete_events) == 2
        rel_ids = {event.relationship_id for event in rel_delete_events}
        assert rel_ids == {rel1.id, rel2.id}


class TestPaginationSortingAndSearch:
    """Test pagination, sorting, and text search functionality."""

    def test_list_taxonomies_pagination(self, service):
        """Test pagination of taxonomies."""
        tax1 = service.create_taxonomy(title="Alpha")
        tax2 = service.create_taxonomy(title="Beta")
        tax3 = service.create_taxonomy(title="Gamma")

        page1 = service.list_taxonomies(limit=2, offset=0)
        assert len(page1) == 2

        page2 = service.list_taxonomies(limit=2, offset=2)
        assert len(page2) == 1

        all_ids = {t.id for page in [page1, page2] for t in page}
        assert all_ids == {tax1.id, tax2.id, tax3.id}

    def test_list_taxonomies_sorting_by_title_asc(self, service):
        """Test sorting taxonomies by title ascending."""
        service.create_taxonomy(title="Gamma")
        service.create_taxonomy(title="Alpha")
        service.create_taxonomy(title="Beta")

        results = service.list_taxonomies(limit=None, sort_by="title", sort_order="asc")
        titles = [t.title for t in results]
        assert titles == ["Alpha", "Beta", "Gamma"]

    def test_list_taxonomies_sorting_by_title_desc(self, service):
        """Test sorting taxonomies by title descending."""
        service.create_taxonomy(title="Gamma")
        service.create_taxonomy(title="Alpha")
        service.create_taxonomy(title="Beta")

        results = service.list_taxonomies(limit=None, sort_by="title", sort_order="desc")
        titles = [t.title for t in results]
        assert titles == ["Gamma", "Beta", "Alpha"]

    def test_list_taxonomies_text_search(self, service):
        """Test text search on taxonomies."""
        service.create_taxonomy(title="Animals Taxonomy")
        service.create_taxonomy(title="Plants Taxonomy")
        service.create_taxonomy(title="Minerals Database")

        results = service.list_taxonomies(limit=None, query="animals")
        assert len(results) == 1
        assert results[0].title == "Animals Taxonomy"

    def test_list_concept_schemes_pagination(self, service):
        """Test pagination of concept schemes."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        service.create_scheme(tax.id, title="Scheme 1")
        service.create_scheme(tax.id, title="Scheme 2")
        service.create_scheme(tax.id, title="Scheme 3")

        page1 = service.list_concept_schemes(limit=2, offset=0)
        assert len(page1) == 2

        page2 = service.list_concept_schemes(limit=2, offset=2)
        assert len(page2) == 1

    def test_list_concept_schemes_sorting_by_title_asc(self, service):
        """Test sorting concept schemes by title ascending."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        service.create_scheme(tax.id, title="Zebra")
        service.create_scheme(tax.id, title="Apple")
        service.create_scheme(tax.id, title="Mango")

        results = service.list_concept_schemes(limit=None, sort_by="title", sort_order="asc")
        titles = [s.title for s in results]
        assert titles == ["Apple", "Mango", "Zebra"]

    def test_list_concept_schemes_text_search(self, service):
        """Test text search on concept schemes."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        service.create_scheme(tax.id, title="Animal Concepts")
        service.create_scheme(tax.id, title="Plant Concepts")
        service.create_scheme(tax.id, title="Mineral Taxonomy")

        results = service.list_concept_schemes(limit=None, query="plant")
        assert len(results) == 1
        assert results[0].title == "Plant Concepts"

    def test_list_relationships_pagination(self, service):
        """Test pagination of relationships."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        scheme = service.create_scheme(tax.id, title="Scheme")
        class1 = service.create_class(scheme.id, title="Class 1")
        class2 = service.create_class(scheme.id, title="Class 2")
        class3 = service.create_class(scheme.id, title="Class 3")
        class4 = service.create_class(scheme.id, title="Class 4")

        prop = service.create_property_definition(identifier="related_to", title="Related To")

        service.create_relationship(class1.id, class2.id, prop.id)
        service.create_relationship(class1.id, class3.id, prop.id)
        service.create_relationship(class1.id, class4.id, prop.id)

        page1 = service.list_relationships(limit=2, offset=0)
        assert len(page1) == 2

        page2 = service.list_relationships(limit=2, offset=2)
        assert len(page2) == 1

    def test_list_relationships_sorting_by_created_at(self, service):
        """Test sorting relationships by created_at."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        scheme = service.create_scheme(tax.id, title="Scheme")
        class1 = service.create_class(scheme.id, title="Class 1")
        class2 = service.create_class(scheme.id, title="Class 2")
        class3 = service.create_class(scheme.id, title="Class 3")
        class4 = service.create_class(scheme.id, title="Class 4")

        prop = service.create_property_definition(identifier="related_to", title="Related To")

        rel1 = service.create_relationship(class1.id, class2.id, prop.id)
        rel2 = service.create_relationship(class1.id, class3.id, prop.id)
        rel3 = service.create_relationship(class1.id, class4.id, prop.id)

        results_asc = service.list_relationships(limit=None, sort_by="created_at", sort_order="asc")
        ids_asc = [r.id for r in results_asc]
        assert ids_asc == [rel1.id, rel2.id, rel3.id]

    def test_list_property_definitions_pagination(self, service):
        """Test pagination of property definitions."""
        service.create_property_definition(identifier="prop1", title="Property 1")
        service.create_property_definition(identifier="prop2", title="Property 2")
        service.create_property_definition(identifier="prop3", title="Property 3")

        page1 = service.list_property_definitions(limit=2, offset=0)
        assert len(page1) == 2

        page2 = service.list_property_definitions(limit=2, offset=2)
        assert len(page2) == 1

    def test_list_property_definitions_sorting_by_title(self, service):
        """Test sorting property definitions by title."""
        service.create_property_definition(identifier="z_prop", title="Zebra")
        service.create_property_definition(identifier="a_prop", title="Apple")
        service.create_property_definition(identifier="m_prop", title="Mango")

        results = service.list_property_definitions(limit=None, sort_by="title", sort_order="asc")
        titles = [p.title for p in results]
        assert titles == ["Apple", "Mango", "Zebra"]

    def test_list_property_definitions_text_search(self, service):
        """Test text search on property definitions."""
        service.create_property_definition(identifier="related", title="Related To")
        service.create_property_definition(identifier="depends_on", title="Depends On")
        service.create_property_definition(identifier="parent", title="Parent Class")

        results = service.list_property_definitions(limit=None, query="parent")
        assert len(results) == 1
        assert results[0].title == "Parent Class"

    def test_count_taxonomies_with_query(self, service):
        """Test counting taxonomies with text search filter."""
        service.create_taxonomy(title="Animals")
        service.create_taxonomy(title="Animal Behavior")
        service.create_taxonomy(title="Plants")

        count = service.count_taxonomies(query="animal")
        assert count == 2

    def test_count_concept_schemes_with_taxonomy_filter(self, service):
        """Test counting concept schemes filtered by taxonomy."""
        tax1 = service.create_taxonomy(title="Taxonomy 1")
        tax2 = service.create_taxonomy(title="Taxonomy 2")

        service.create_scheme(tax1.id, title="Scheme 1.1")
        service.create_scheme(tax1.id, title="Scheme 1.2")
        service.create_scheme(tax2.id, title="Scheme 2.1")

        count = service.count_concept_schemes(taxonomy_id=tax1.id)
        assert count == 2

    def test_count_relationships_with_filters(self, service):
        """Test counting relationships with filters."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        class1 = service.create_class(scheme.id, title="Class 1")
        class2 = service.create_class(scheme.id, title="Class 2")
        class3 = service.create_class(scheme.id, title="Class 3")

        prop = service.create_property_definition(identifier="related_to", title="Related To")

        service.create_relationship(class1.id, class2.id, prop.id)
        service.create_relationship(class1.id, class3.id, prop.id)

        count = service.count_relationships(source_id=class1.id)
        assert count == 2

    def test_count_property_definitions_with_query(self, service):
        """Test counting property definitions with text search."""
        service.create_property_definition(identifier="parent", title="Parent Class")
        service.create_property_definition(identifier="child", title="Child Class")
        service.create_property_definition(identifier="related", title="Related To")

        count = service.count_property_definitions(query="class")
        assert count == 2


class TestPublishTaxonomy:
    """Test taxonomy publish functionality."""

    def test_publish_taxonomy_transitions_from_draft_to_published(self, service):
        """Test that publishing a taxonomy transitions its status to published."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        assert tax.status == "draft"

        published = service.publish_taxonomy(tax.id)
        assert published.status == "published"

    def test_publish_taxonomy_is_idempotent(self, service):
        """Test that publishing an already-published taxonomy doesn't error."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        published1 = service.publish_taxonomy(tax.id)
        assert published1.status == "published"

        published2 = service.publish_taxonomy(tax.id)
        assert published2.status == "published"

    def test_publish_nonexistent_taxonomy_raises_error(self, service):
        """Test that publishing a nonexistent taxonomy raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError):
            service.publish_taxonomy("nonexistent-id")

    def test_publish_taxonomy_emits_event(self, service):
        """Test that publishing a taxonomy emits a TaxonomyUpdated event with correct values."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        commit_message = "Publishing initial version"
        service.publish_taxonomy(tax.id, commit_message=commit_message)

        update_events = service._event_publisher.get_events_of_type(TaxonomyUpdated)
        assert len(update_events) >= 1

        event = update_events[0]
        assert event.taxonomy_id == tax.id
        assert "status" in event.changed_fields
        assert event.old_values == {"status": "draft"}
        assert event.new_values == {"status": "published"}
        assert event.commit_message == commit_message


class TestGetPublishDiffStats:
    """Test publish diff statistics calculation."""

    def test_get_publish_diff_stats_nonexistent_taxonomy_raises_error(self, service):
        """Test that requesting diff stats for a nonexistent taxonomy raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError):
            service.get_publish_diff_stats("nonexistent-id")

    def test_get_publish_diff_stats_draft_taxonomy_with_classes(self, service):
        """Test diff stats for a draft taxonomy with classes shows them as added."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        scheme = service.create_scheme(tax.id, title="Scheme")
        service.create_class(scheme.id, title="Class 1")
        service.create_class(scheme.id, title="Class 2")
        service.create_class(scheme.id, title="Class 3")

        stats = service.get_publish_diff_stats(tax.id)
        assert stats["added"] == 3
        assert stats["modified"] == 0
        assert stats["removed"] == 0

    def test_get_publish_diff_stats_draft_taxonomy_with_no_classes(self, service):
        """Test diff stats for an empty draft taxonomy shows no changes."""
        tax = service.create_taxonomy(title="Test Taxonomy")

        stats = service.get_publish_diff_stats(tax.id)
        assert stats["added"] == 0
        assert stats["modified"] == 0
        assert stats["removed"] == 0

    def test_get_publish_diff_stats_published_taxonomy_shows_no_changes(self, service):
        """Test diff stats for a published taxonomy shows no changes."""
        tax = service.create_taxonomy(title="Test Taxonomy")
        scheme = service.create_scheme(tax.id, title="Scheme")
        service.create_class(scheme.id, title="Class 1")
        service.publish_taxonomy(tax.id)

        stats = service.get_publish_diff_stats(tax.id)
        assert stats["added"] == 0
        assert stats["modified"] == 0
        assert stats["removed"] == 0


class TestCreateAttributeDefinition:
    """Tests for create_attribute_definition."""

    def test_create_attribute_definition_success(self, service):
        """Create an attribute definition and verify it's persisted and event is emitted."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
            description="The name attribute",
            is_required=True,
        )

        assert attr_def.id is not None
        assert attr_def.class_id == cls.id
        assert attr_def.identifier == "name"
        assert attr_def.title == "Name"
        assert attr_def.datatype == "string"
        assert attr_def.description == "The name attribute"
        assert attr_def.is_required is True
        assert attr_def.created_at is not None
        assert attr_def.last_modified is not None

        # Verify it was saved
        retrieved = service.get_attribute_definition(attr_def.id)
        assert retrieved.id == attr_def.id

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(AttributeDefinitionCreated)
        assert len(events) == 1
        assert events[0].attribute_definition_id == attr_def.id
        assert events[0].class_id == cls.id
        assert events[0].identifier == "name"
        assert events[0].title == "Name"

    def test_create_attribute_definition_nonexistent_class_raises(self, service):
        """Creating attribute definition for nonexistent class raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.create_attribute_definition(
                class_id="nonexistent-class-id",
                identifier="name",
                title="Name",
                datatype="string",
            )

    def test_create_attribute_definition_duplicate_identifier_in_same_class_raises(self, service):
        """Creating duplicate identifier within same class raises DuplicateEntityError."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        with pytest.raises(DuplicateEntityError, match="already exists"):
            service.create_attribute_definition(
                class_id=cls.id,
                identifier="name",
                title="Another Name",
                datatype="string",
            )

    def test_create_attribute_definition_same_identifier_different_classes_succeeds(self, service):
        """Same identifier in different classes is allowed."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls1 = service.create_class(scheme.id, title="Class 1")
        cls2 = service.create_class(scheme.id, title="Class 2")

        attr1 = service.create_attribute_definition(
            class_id=cls1.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        attr2 = service.create_attribute_definition(
            class_id=cls2.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        assert attr1.id != attr2.id
        assert attr1.class_id == cls1.id
        assert attr2.class_id == cls2.id

    def test_create_attribute_definition_empty_identifier_raises(self, service):
        """Creating attribute definition with empty identifier raises ValueError."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            service.create_attribute_definition(
                class_id=cls.id,
                identifier="",
                title="Name",
                datatype="string",
            )

    def test_create_attribute_definition_empty_title_raises(self, service):
        """Creating attribute definition with empty title raises ValueError."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        with pytest.raises(ValueError, match="Title cannot be empty"):
            service.create_attribute_definition(
                class_id=cls.id,
                identifier="name",
                title="",
                datatype="string",
            )

    def test_create_attribute_definition_empty_datatype_raises(self, service):
        """Creating attribute definition with empty datatype raises ValueError."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        with pytest.raises(ValueError, match="Datatype cannot be empty"):
            service.create_attribute_definition(
                class_id=cls.id,
                identifier="name",
                title="Name",
                datatype="",
            )

    def test_create_attribute_definition_with_enum_constraint(self, service):
        """Creating attribute definition with allowed_values."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="status",
            title="Status",
            datatype="string",
            allowed_values=["draft", "published", "archived"],
        )

        assert attr_def.allowed_values == ["draft", "published", "archived"]
        retrieved = service.get_attribute_definition(attr_def.id)
        assert retrieved.allowed_values == ["draft", "published", "archived"]

    def test_create_attribute_definition_with_valid_default_value(self, service):
        """Creating attribute definition with default_value in allowed_values."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="status",
            title="Status",
            datatype="string",
            allowed_values=["draft", "published", "archived"],
            default_value="draft",
        )

        assert attr_def.default_value == "draft"
        assert attr_def.allowed_values == ["draft", "published", "archived"]
        retrieved = service.get_attribute_definition(attr_def.id)
        assert retrieved.default_value == "draft"

    def test_create_attribute_definition_invalid_default_value_raises(self, service):
        """Raises ValueError when default_value is not in allowed_values."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        with pytest.raises(
            ValueError,
            match="Default value 'yellow' is not in allowed values",
        ):
            service.create_attribute_definition(
                class_id=cls.id,
                identifier="color",
                title="Color",
                datatype="string",
                allowed_values=["red", "green", "blue"],
                default_value="yellow",
            )

    def test_create_attribute_definition_default_value_without_allowed_values(self, service):
        """Creating attribute definition with default_value but no allowed_values succeeds."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
            default_value="John",
        )

        assert attr_def.default_value == "John"
        assert attr_def.allowed_values is None


class TestGetAttributeDefinition:
    """Tests for get_attribute_definition."""

    def test_get_attribute_definition_success(self, service):
        """Retrieve an attribute definition by ID."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        retrieved = service.get_attribute_definition(attr_def.id)
        assert retrieved.id == attr_def.id
        assert retrieved.class_id == cls.id
        assert retrieved.identifier == "name"

    def test_get_attribute_definition_nonexistent_raises(self, service):
        """Retrieving nonexistent attribute definition raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="AttributeDefinition"):
            service.get_attribute_definition("nonexistent-id")


class TestListAttributeDefinitions:
    """Tests for list_attribute_definitions."""

    def test_list_attribute_definitions_empty(self, service):
        """List attribute definitions when none exist."""
        results = service.list_attribute_definitions()
        assert results == []

    def test_list_attribute_definitions_all(self, service):
        """List all attribute definitions across classes."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls1 = service.create_class(scheme.id, title="Class 1")
        cls2 = service.create_class(scheme.id, title="Class 2")

        attr1 = service.create_attribute_definition(
            class_id=cls1.id, identifier="name", title="Name", datatype="string"
        )
        attr2 = service.create_attribute_definition(
            class_id=cls1.id, identifier="age", title="Age", datatype="integer"
        )
        attr3 = service.create_attribute_definition(
            class_id=cls2.id, identifier="name", title="Name", datatype="string"
        )

        results = service.list_attribute_definitions(limit=None)
        assert len(results) == 3
        ids = {r.id for r in results}
        assert attr1.id in ids
        assert attr2.id in ids
        assert attr3.id in ids

    def test_list_attribute_definitions_filter_by_class(self, service):
        """List attribute definitions filtered by class."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls1 = service.create_class(scheme.id, title="Class 1")
        cls2 = service.create_class(scheme.id, title="Class 2")

        attr1 = service.create_attribute_definition(
            class_id=cls1.id, identifier="name", title="Name", datatype="string"
        )
        attr2 = service.create_attribute_definition(
            class_id=cls1.id, identifier="age", title="Age", datatype="integer"
        )
        service.create_attribute_definition(
            class_id=cls2.id, identifier="name", title="Name", datatype="string"
        )

        results = service.list_attribute_definitions(class_id=cls1.id, limit=None)
        assert len(results) == 2
        ids = {r.id for r in results}
        assert attr1.id in ids
        assert attr2.id in ids

    def test_list_attribute_definitions_pagination(self, service):
        """Test pagination of attribute definitions."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        service.create_attribute_definition(
            class_id=cls.id, identifier="attr_a", title="Attr A", datatype="string"
        )
        service.create_attribute_definition(
            class_id=cls.id, identifier="attr_b", title="Attr B", datatype="string"
        )
        service.create_attribute_definition(
            class_id=cls.id, identifier="attr_c", title="Attr C", datatype="string"
        )

        page1 = service.list_attribute_definitions(class_id=cls.id, limit=2, offset=0)
        assert len(page1) == 2

        page2 = service.list_attribute_definitions(class_id=cls.id, limit=2, offset=2)
        assert len(page2) == 1


class TestUpdateAttributeDefinition:
    """Tests for update_attribute_definition."""

    def test_update_attribute_definition_title(self, service):
        """Update attribute definition title."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        original_version = attr_def.version
        updated = service.update_attribute_definition(
            attribute_definition_id=attr_def.id,
            title="Full Name",
        )

        assert updated.title == "Full Name"
        assert updated.version == original_version + 1

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(AttributeDefinitionUpdated)
        assert len(events) == 1
        assert events[0].attribute_definition_id == attr_def.id
        assert "title" in events[0].changed_fields
        assert events[0].old_values["title"] == "Name"
        assert events[0].new_values["title"] == "Full Name"

    def test_update_attribute_definition_multiple_fields(self, service):
        """Update multiple fields of attribute definition."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="status",
            title="Status",
            datatype="string",
            is_required=False,
        )

        updated = service.update_attribute_definition(
            attribute_definition_id=attr_def.id,
            title="Status Code",
            datatype="integer",
            is_required=True,
            allowed_values=["0", "1", "2"],
        )

        assert updated.title == "Status Code"
        assert updated.datatype == "integer"
        assert updated.is_required is True
        assert updated.allowed_values == ["0", "1", "2"]

    def test_update_attribute_definition_no_changes(self, service):
        """Updating with no actual changes doesn't emit event."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        original_version = attr_def.version
        original_event_count = len(service._event_publisher.get_events())

        updated = service.update_attribute_definition(
            attribute_definition_id=attr_def.id,
            title="Name",  # Same value
        )

        assert updated.version == original_version
        # Verify no new events were added
        assert len(service._event_publisher.get_events()) == original_event_count

    def test_update_attribute_definition_nonexistent_raises(self, service):
        """Updating nonexistent attribute definition raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="AttributeDefinition"):
            service.update_attribute_definition(
                attribute_definition_id="nonexistent-id",
                title="New Title",
            )

    def test_update_attribute_definition_valid_default_value(self, service):
        """Update attribute definition with default_value in allowed_values."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=["red", "green", "blue"],
        )

        updated = service.update_attribute_definition(
            attribute_definition_id=attr_def.id,
            default_value="red",
        )

        assert updated.default_value == "red"
        assert updated.allowed_values == ["red", "green", "blue"]

    def test_update_attribute_definition_invalid_default_value_raises(self, service):
        """Updating with default_value not in existing allowed_values raises ValueError."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=["red", "green", "blue"],
        )

        with pytest.raises(
            ValueError,
            match="Default value 'yellow' is not in allowed values",
        ):
            service.update_attribute_definition(
                attribute_definition_id=attr_def.id,
                default_value="yellow",
            )

    def test_update_attribute_definition_update_allowed_values_and_default_together(self, service):
        """Update both allowed_values and default_value together."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="status",
            title="Status",
            datatype="string",
            allowed_values=["draft", "published"],
            default_value="draft",
        )

        updated = service.update_attribute_definition(
            attribute_definition_id=attr_def.id,
            allowed_values=["draft", "published", "archived"],
            default_value="archived",
        )

        assert updated.allowed_values == ["draft", "published", "archived"]
        assert updated.default_value == "archived"

    def test_update_attribute_definition_update_allowed_values_conflicting_default_raises(
        self, service
    ):
        """Update allowed_values such that current default_value is no longer valid."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="status",
            title="Status",
            datatype="string",
            allowed_values=["draft", "published"],
            default_value="draft",
        )

        with pytest.raises(
            ValueError,
            match="Default value 'draft' is not in allowed values",
        ):
            service.update_attribute_definition(
                attribute_definition_id=attr_def.id,
                allowed_values=["archived", "deleted"],  # draft is no longer valid
            )

    def test_update_attribute_definition_set_default_value_without_allowed_values(self, service):
        """Update to add default_value when there are no allowed_values."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        updated = service.update_attribute_definition(
            attribute_definition_id=attr_def.id,
            default_value="John",
        )

        assert updated.default_value == "John"
        assert updated.allowed_values is None


class TestDeleteAttributeDefinition:
    """Tests for delete_attribute_definition."""

    def test_delete_attribute_definition_success(self, service):
        """Delete an attribute definition."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        attr_def = service.create_attribute_definition(
            class_id=cls.id,
            identifier="name",
            title="Name",
            datatype="string",
        )

        service.delete_attribute_definition(attr_def.id)

        with pytest.raises(EntityNotFoundError):
            service.get_attribute_definition(attr_def.id)

        # Verify event was emitted
        events = service._event_publisher.get_events_of_type(AttributeDefinitionDeleted)
        assert len(events) == 1
        assert events[0].attribute_definition_id == attr_def.id
        assert events[0].class_id == cls.id
        assert events[0].identifier == "name"
        assert events[0].title == "Name"

    def test_delete_attribute_definition_nonexistent_raises(self, service):
        """Deleting nonexistent attribute definition raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="AttributeDefinition"):
            service.delete_attribute_definition("nonexistent-id")


class TestCountAttributeDefinitions:
    """Tests for count_attribute_definitions."""

    def test_count_attribute_definitions_all(self, service):
        """Count all attribute definitions."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls1 = service.create_class(scheme.id, title="Class 1")
        cls2 = service.create_class(scheme.id, title="Class 2")

        service.create_attribute_definition(
            class_id=cls1.id, identifier="name", title="Name", datatype="string"
        )
        service.create_attribute_definition(
            class_id=cls1.id, identifier="age", title="Age", datatype="integer"
        )
        service.create_attribute_definition(
            class_id=cls2.id, identifier="name", title="Name", datatype="string"
        )

        count = service.count_attribute_definitions()
        assert count == 3

    def test_count_attribute_definitions_filter_by_class(self, service):
        """Count attribute definitions filtered by class."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls1 = service.create_class(scheme.id, title="Class 1")
        cls2 = service.create_class(scheme.id, title="Class 2")

        service.create_attribute_definition(
            class_id=cls1.id, identifier="name", title="Name", datatype="string"
        )
        service.create_attribute_definition(
            class_id=cls1.id, identifier="age", title="Age", datatype="integer"
        )
        service.create_attribute_definition(
            class_id=cls2.id, identifier="name", title="Name", datatype="string"
        )

        count = service.count_attribute_definitions(class_id=cls1.id)
        assert count == 2


class TestExistingServiceMethodsCompatibility:
    """Tests to verify existing service methods remain unchanged and functional."""

    def test_get_individual_properties_unchanged(self, service):
        """Verify get_individual_properties continues to work with existing behavior."""
        tax = service.create_taxonomy(title="Test")
        scheme = service.create_scheme(tax.id, title="Scheme")
        cls = service.create_class(scheme.id, title="Class")

        individual = service.create_individual(class_ids=[cls.id], title="Individual 1")

        properties = service.get_individual_properties(individual.id)
        assert isinstance(properties, list)
