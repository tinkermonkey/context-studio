"""
Unit tests for multi-class Individual support in OntologyService.

Tests the service layer operations for managing class membership and
property attribute inheritance with first-class-wins conflict resolution.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.ontology.value_objects import DataPropertyValue
from domain.ontology.services import OntologyService
from domain.ontology.exceptions import EntityNotFoundError
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher


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
        scheme.id, "Database System",
        description="A system for data storage and retrieval"
    )
    class2 = svc.create_class(
        scheme.id, "SQL Dialect",
        description="A SQL database implementation"
    )
    class3 = svc.create_class(
        scheme.id, "Open Source Software",
        description="Software with open source code"
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
        """Create an individual with empty class list raises ValueError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        with pytest.raises(ValueError, match="at least one class"):
            svc.create_individual([], "Invalid")

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
        updated = svc.reorder_individual_classes(
            ind.id, [class3.id, class1.id, class2.id]
        )

        assert updated.class_ids == [class3.id, class1.id, class2.id]

    def test_reorder_individual_classes_invalid_raises(self, sample_ontology):
        """Reordering with wrong classes raises ValueError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        ind = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        with pytest.raises(ValueError, match="must contain exactly the same"):
            svc.reorder_individual_classes(
                ind.id, [class1.id, class3.id]
            )


class TestPropertyAttributeInheritance:
    """Tests for property attribute inheritance with first-class-wins conflict resolution."""

    def test_get_individual_properties_single_class(self, sample_ontology):
        """Get properties from a single parent class."""
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
        """Get properties from multiple classes with no naming conflicts."""
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
            DataPropertyValue(property_identifier="author", value="The PostgreSQL Global Development Group"),
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
        ind1 = svc.create_individual([class1.id, class2.id], "PostgreSQL")
        props1 = svc.get_individual_properties(ind1.id)
        prop1 = next(p for p in props1 if p.property_identifier == "release_type")
        assert prop1.value == "production"

        # Create individual with class2 first (reordered)
        ind2 = svc.create_individual([class2.id, class1.id], "MySQL")
        props2 = svc.get_individual_properties(ind2.id)
        prop2 = next(p for p in props2 if p.property_identifier == "release_type")
        assert prop2.value == "stable"

    def test_get_individual_properties_nonexistent_individual_raises(self, sample_ontology):
        """Getting properties for nonexistent individual raises EntityNotFoundError."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        with pytest.raises(EntityNotFoundError):
            svc.get_individual_properties("nonexistent")

    def test_get_individual_properties_three_way_conflict(self, sample_ontology):
        """Test conflict resolution with three classes declaring the same property."""
        svc, repo, tax, scheme, class1, class2, class3 = sample_ontology

        # All three classes have a "rating" property
        class1.data_properties = [
            DataPropertyValue(property_identifier="rating", value="5/5"),
        ]
        class2.data_properties = [
            DataPropertyValue(property_identifier="rating", value="4/5"),
        ]
        class3.data_properties = [
            DataPropertyValue(property_identifier="rating", value="3/5"),
        ]
        repo.save_class(class1)
        repo.save_class(class2)
        repo.save_class(class3)

        # Order: class1, class2, class3 - class1 should win
        ind = svc.create_individual(
            [class1.id, class2.id, class3.id], "TestEntity"
        )
        props = svc.get_individual_properties(ind.id)

        rating_prop = next(p for p in props if p.property_identifier == "rating")
        assert rating_prop.value == "5/5"

        # Reorder: class3, class2, class1 - class3 should now win
        svc.reorder_individual_classes(
            ind.id, [class3.id, class2.id, class1.id]
        )
        props = svc.get_individual_properties(ind.id)
        rating_prop = next(p for p in props if p.property_identifier == "rating")
        assert rating_prop.value == "3/5"
