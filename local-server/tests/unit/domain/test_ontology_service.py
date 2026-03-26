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
from uuid import uuid4

from domain.ontology.services import OntologyService
from domain.ontology.entities import Taxonomy, ConceptScheme, Class, Relationship, PropertyDefinition
from domain.ontology.events import (
    TaxonomyCreated, SchemeCreated, ClassCreated, ClassUpdated, ClassDeleted,
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
        child = service.create_class(scheme_id=scheme.id, title="Dog", parent_class_id=parent.id)

        with pytest.raises(OntologyError, match="has.*subclass"):
            service.delete_class(class_id=parent.id)

    def test_delete_class_nonexistent_raises(self, service):
        """Delete nonexistent class raises EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError, match="Class"):
            service.delete_class(class_id="nonexistent")


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
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        schemes = service.list_concept_schemes()
        assert len(schemes) == 2

    def test_list_concept_schemes_filtered_by_taxonomy(self, service):
        """List concept schemes filtered by taxonomy."""
        tax1 = service.create_taxonomy(title="Biology")
        tax2 = service.create_taxonomy(title="Chemistry")
        scheme1 = service.create_scheme(taxonomy_id=tax1.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax2.id, title="Elements")
        schemes = service.list_concept_schemes(taxonomy_id=tax1.id)
        assert len(schemes) == 1
        assert schemes[0].id == scheme1.id

    def test_list_classes_filtered_by_scheme(self, service):
        """List classes filtered by scheme."""
        tax = service.create_taxonomy(title="Biology")
        scheme1 = service.create_scheme(taxonomy_id=tax.id, title="Animals")
        scheme2 = service.create_scheme(taxonomy_id=tax.id, title="Plants")
        cls1 = service.create_class(scheme_id=scheme1.id, title="Dog")
        cls2 = service.create_class(scheme_id=scheme2.id, title="Tree")
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
