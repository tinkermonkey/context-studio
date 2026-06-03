"""
Unit tests for multi-class Individual support in OntologyService.

Tests the service layer operations for managing class membership and
property attribute inheritance with first-class-wins conflict resolution.
"""

import pytest

from domain.ontology.events import (
    IndividualCreated,
    IndividualDeleted,
    IndividualUpdated,
)
from domain.ontology.exceptions import DuplicateEntityError, EntityNotFoundError
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import DataPropertyValue
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


@pytest.fixture
def service():
    """Create a service instance with fake dependencies."""
    repo = FakeOntologyRepository()
    embedding = FakeEmbeddingService()
    event_pub = FakeEventPublisher()
    return OntologyService(repo, embedding, event_pub), repo


@pytest.fixture
def sample_ontology(service):
    """Create a sample ontology structure."""
    svc, repo = service

    # Create taxonomy and scheme
    tax = svc.create_taxonomy("Test Taxonomy")
    scheme = svc.create_scheme(tax.id, "Test Scheme")

    # Create three test classes
    class1 = svc.create_class(
        scheme.id,
        "Database System",
        description="A system for data storage and retrieval",
    )
    class2 = svc.create_class(scheme.id, "SQL Dialect", description="A SQL database implementation")
    class3 = svc.create_class(
        scheme.id, "Open Source Software", description="Software with open source code"
    )

    return svc, repo, tax, scheme, class1, class2, class3


class TestIndividualMultiClassOperations:
    """Tests for Individual multi-class membership operations in OntologyService."""

    def test_create_individual_with_single_class(self, sample_ontology):
        """Create an individual with a single parent class."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "MySQL")
        assert ind.class_ids == [class1.id]
        assert ind.title == "MySQL"

    def test_create_individual_with_multiple_classes(self, sample_ontology):
        """Create an individual with multiple parent classes."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        assert ind.class_ids == [class1.id, class2.id]

    def test_create_individual_backwards_compat_single_string(self, sample_ontology):
        """Create an individual with backwards-compatible string parameter."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "MySQL")
        assert ind.class_ids == [class1.id]

    def test_create_individual_no_classes_raises(self, sample_ontology):
        """Create individual with empty class list raises ValueError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        with pytest.raises(ValueError, match="at least one"):
            svc.create_individual([], "MySQL")

    def test_add_class_to_individual(self, sample_ontology):
        """Add a class to an individual."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "PostgreSQL")
        updated = svc.add_class_to_individual(ind.id, class2.id)

        assert updated.class_ids == [class1.id, class2.id]

    def test_add_class_duplicate_raises(self, sample_ontology):
        """Adding a duplicate class raises ValueError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        with pytest.raises(ValueError, match="already a parent"):
            svc.add_class_to_individual(ind.id, class1.id)

    def test_add_class_nonexistent_individual_raises(self, sample_ontology):
        """Adding a class to nonexistent individual raises EntityNotFoundError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        with pytest.raises(EntityNotFoundError):
            svc.add_class_to_individual("nonexistent", class1.id)

    def test_add_class_nonexistent_class_raises(self, sample_ontology):
        """Adding nonexistent class raises EntityNotFoundError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "PostgreSQL")
        with pytest.raises(EntityNotFoundError):
            svc.add_class_to_individual(ind.id, "nonexistent")

    def test_add_class_duplicate_title_in_class_raises(self, sample_ontology):
        """Add class with duplicate title in target class raises DuplicateEntityError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        # Create two individuals with same title in different classes
        svc.create_individual(class1.id, "MySQL")
        ind2 = svc.create_individual(class2.id, "PostgreSQL")

        # Try to add ind2 to class1 (where "PostgreSQL" already exists) should fail
        svc.create_individual(class1.id, "PostgreSQL")
        with pytest.raises(DuplicateEntityError, match="already exists"):
            svc.add_class_to_individual(ind2.id, class1.id)

    def test_remove_class_from_individual(self, sample_ontology):
        """Remove a class from an individual."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        updated = svc.remove_class_from_individual(ind.id, class2.id)

        assert updated.class_ids == [class1.id]

    def test_remove_last_class_raises(self, sample_ontology):
        """Removing the last class raises ValueError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "PostgreSQL")
        with pytest.raises(ValueError, match="Cannot remove the last"):
            svc.remove_class_from_individual(ind.id, class1.id)

    def test_reorder_individual_classes(self, sample_ontology):
        """Reorder an individual's parent classes."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id, class3.id], "PostgreSQL")
        updated = svc.reorder_individual_classes(ind.id, [class3.id, class1.id, class2.id])

        assert updated.class_ids == [class3.id, class1.id, class2.id]

    def test_reorder_individual_classes_invalid_raises(self, sample_ontology):
        """Reordering with wrong classes raises ValueError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        with pytest.raises(ValueError, match="must contain exactly the same"):
            svc.reorder_individual_classes(ind.id, [class1.id, class3.id])

    def test_get_individual_properties_single_class(self, sample_ontology):
        """Get properties for individual with single parent class."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        # Add properties to class1
        class1.data_properties = [
            DataPropertyValue(property_identifier="version", value="5.0"),
            DataPropertyValue(property_identifier="license", value="BSD"),
        ]
        repo.save_class(class1)

        ind = svc.create_individual(class1.id, "PostgreSQL")
        props = svc.get_individual_properties(ind.id)

        assert len(props) == 2
        assert any(p.property_identifier == "version" for p in props)
        assert any(p.property_identifier == "license" for p in props)

    def test_get_individual_properties_multiple_classes_no_conflict(self, sample_ontology):
        """Get properties for individual with multiple classes, no property conflicts."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        # Add different properties to each class
        class1.data_properties = [
            DataPropertyValue(property_identifier="version", value="5.0"),
        ]
        class2.data_properties = [
            DataPropertyValue(property_identifier="sql_dialect", value="ANSI-SQL"),
        ]
        repo.save_class(class1)
        repo.save_class(class2)

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        props = svc.get_individual_properties(ind.id)

        assert len(props) == 2
        assert any(p.property_identifier == "version" for p in props)
        assert any(p.property_identifier == "sql_dialect" for p in props)

    def test_get_individual_properties_conflict_resolution(self, sample_ontology):
        """Test first-class-wins conflict resolution for naming conflicts."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        # Both classes have a "license" property with different values
        class1.data_properties = [
            DataPropertyValue(property_identifier="license", value="BSD"),
            DataPropertyValue(property_identifier="version", value="5.0"),
        ]
        class2.data_properties = [
            DataPropertyValue(property_identifier="license", value="MIT"),
            DataPropertyValue(
                property_identifier="author",
                value="The PostgreSQL Global Development Group",
            ),
        ]
        repo.save_class(class1)
        repo.save_class(class2)

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        props = svc.get_individual_properties(ind.id)

        # Should have 3 unique properties: license (from class1), version, author
        assert len(props) == 3
        license_prop = next(p for p in props if p.property_identifier == "license")
        # First class wins: should be BSD
        assert license_prop.value == "BSD"

    def test_get_individual_properties_order_matters(self, sample_ontology):
        """Test that class order determines conflict resolution winner."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        # Both classes have a "release_type" property
        class1.data_properties = [
            DataPropertyValue(property_identifier="release_type", value="production"),
        ]
        class2.data_properties = [
            DataPropertyValue(property_identifier="release_type", value="stable"),
        ]
        repo.save_class(class1)
        repo.save_class(class2)

        # Create individual with class1 first
        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        props = svc.get_individual_properties(ind.id)
        prop = next(p for p in props if p.property_identifier == "release_type")
        assert prop.value == "production"

        # Reorder: class2, class1 - class2 should now win
        svc.reorder_individual_classes(ind.id, [class2.id, class1.id])
        props = svc.get_individual_properties(ind.id)
        prop = next(p for p in props if p.property_identifier == "release_type")
        assert prop.value == "stable"

    def test_get_individual_properties_nonexistent_individual_raises(self, sample_ontology):
        """Get properties for nonexistent individual raises EntityNotFoundError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        with pytest.raises(EntityNotFoundError, match="Individual"):
            svc.get_individual_properties("nonexistent")

    def test_get_individual_properties_three_way_conflict(self, sample_ontology):
        """Test property resolution with three-way conflict."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        # Add same property with different values to each class
        class1.data_properties = [
            DataPropertyValue(property_identifier="rating", value="1/5"),
        ]
        class2.data_properties = [
            DataPropertyValue(property_identifier="rating", value="2/5"),
        ]
        class3.data_properties = [
            DataPropertyValue(property_identifier="rating", value="3/5"),
        ]
        repo.save_class(class1)
        repo.save_class(class2)
        repo.save_class(class3)

        # Create with class order: class1, class2, class3
        ind = svc.create_individual([class1.id, class2.id, class3.id], "TestEntity")
        props = svc.get_individual_properties(ind.id)

        rating_prop = next(p for p in props if p.property_identifier == "rating")
        assert rating_prop.value == "1/5"

        # Reorder: class3, class2, class1 - class3 should now win
        svc.reorder_individual_classes(ind.id, [class3.id, class2.id, class1.id])
        props = svc.get_individual_properties(ind.id)
        rating_prop = next(p for p in props if p.property_identifier == "rating")
        assert rating_prop.value == "3/5"


class TestIndividualEventEmission:
    """Tests for event emission in Individual CRUD operations."""

    def test_create_individual_emits_event(self, sample_ontology):
        """Creating an individual emits IndividualCreated event."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology
        svc._event_publisher.clear()

        ind = svc.create_individual(class1.id, "MySQL")

        created_events = svc._event_publisher.get_events_of_type(IndividualCreated)
        assert len(created_events) == 1
        assert created_events[0].individual_id == ind.id

    def test_update_individual_emits_event(self, sample_ontology):
        """Updating an individual emits IndividualUpdated event."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "MySQL")
        svc._event_publisher.clear()

        svc.update_individual(ind.id, title="MariaDB")

        updated_events = svc._event_publisher.get_events_of_type(IndividualUpdated)
        assert len(updated_events) == 1
        assert updated_events[0].individual_id == ind.id

    def test_delete_individual_emits_event(self, sample_ontology):
        """Deleting an individual emits IndividualDeleted event."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "MySQL")
        svc._event_publisher.clear()

        svc.delete_individual(ind.id)

        deleted_events = svc._event_publisher.get_events_of_type(IndividualDeleted)
        assert len(deleted_events) == 1
        assert deleted_events[0].individual_id == ind.id

    def test_add_class_emits_individual_updated_event(self, sample_ontology):
        """Adding a class to individual emits IndividualUpdated event."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "PostgreSQL")
        svc._event_publisher.clear()

        svc.add_class_to_individual(ind.id, class2.id)

        updated_events = svc._event_publisher.get_events_of_type(IndividualUpdated)
        assert len(updated_events) == 1
        assert updated_events[0].individual_id == ind.id
        assert updated_events[0].changed_fields == ("class_ids",)

    def test_remove_class_emits_individual_updated_event(self, sample_ontology):
        """Removing a class from individual emits IndividualUpdated event."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        svc._event_publisher.clear()

        svc.remove_class_from_individual(ind.id, class2.id)

        updated_events = svc._event_publisher.get_events_of_type(IndividualUpdated)
        assert len(updated_events) == 1
        assert updated_events[0].individual_id == ind.id
        assert updated_events[0].changed_fields == ("class_ids",)

    def test_reorder_classes_emits_individual_updated_event(self, sample_ontology):
        """Reordering classes emits IndividualUpdated event."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id, class3.id], "PostgreSQL")
        svc._event_publisher.clear()

        svc.reorder_individual_classes(ind.id, [class3.id, class1.id, class2.id])

        updated_events = svc._event_publisher.get_events_of_type(IndividualUpdated)
        assert len(updated_events) == 1
        assert updated_events[0].individual_id == ind.id
        assert updated_events[0].changed_fields == ("class_ids",)


class TestIndividualRelationships:
    """Tests for relationships involving individuals."""

    def test_create_relationship_with_individual_source(self, sample_ontology):
        """Creating a relationship with an individual as source works."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual(class1.id, "MySQL")
        target_cls = class2

        # Create a property definition for relationships
        prop = svc.create_property_definition(
            identifier="depends_on",
            title="Depends On",
            description="Indicates a dependency relationship",
        )

        # Create a relationship from individual to class
        rel = svc.create_relationship(
            source_id=ind.id,
            target_id=target_cls.id,
            property_definition_id=prop.id,
        )

        assert rel.source_id == ind.id
        assert rel.target_id == target_cls.id

    def test_create_relationship_with_individual_target(self, sample_ontology):
        """Creating a relationship with an individual as target works."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        source_cls = class1
        ind = svc.create_individual(class2.id, "MySQL")

        # Create a property definition for relationships
        prop = svc.create_property_definition(
            identifier="has_instance",
            title="Has Instance",
            description="Indicates an instance relationship",
        )

        # Create a relationship from class to individual
        rel = svc.create_relationship(
            source_id=source_cls.id,
            target_id=ind.id,
            property_definition_id=prop.id,
        )

        assert rel.source_id == source_cls.id
        assert rel.target_id == ind.id
