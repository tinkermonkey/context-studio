"""
Integration tests for SQLiteOntologyRepository.

Tests the adapter against a real in-memory SQLite database to verify:
- CRUD operations on all entity types
- Relationship management and validation
- Hierarchy integrity (cycle detection, parent validation)
- Search and filtering
- Cascade deletion
"""

import sys
import os
import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    Relationship,
    PropertyDefinition,
)
from domain.ontology.value_objects import (
    ExternalReference,
    DataPropertyValue,
    SearchCriteria,
)

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    """Create a session factory for testing."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def repo(session_factory):
    """Create a repository instance for testing."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def sample_taxonomy(repo):
    """Create and return a sample taxonomy."""
    taxonomy = Taxonomy(
        id="tax-1",
        title="Biology",
        description="Biological classification",
    )
    return repo.save_taxonomy(taxonomy)


@pytest.fixture
def sample_concept_scheme(repo, sample_taxonomy):
    """Create and return a sample concept scheme."""
    scheme = ConceptScheme(
        id="scheme-1",
        taxonomy_id=sample_taxonomy.id,
        title="Organisms",
        description="Classification of living organisms",
    )
    return repo.save_concept_scheme(scheme)


@pytest.fixture
def sample_class(repo, sample_concept_scheme, sample_taxonomy):
    """Create and return a sample class."""
    cls = Class(
        id="class-1",
        concept_scheme_id=sample_concept_scheme.id,
        taxonomy_id=sample_taxonomy.id,
        title="Animal",
        description="A living organism of the kingdom Animalia",
    )
    return repo.save_class(cls)


@pytest.fixture
def sample_property_definition(repo):
    """Create and return a sample property definition."""
    prop = PropertyDefinition(
        id="prop-1",
        identifier="is_subclass_of",
        title="Is Subclass Of",
        description="Indicates a subclass relationship",
    )
    return repo.save_property_definition(prop)


class TestTaxonomyCRUD:
    """Tests for Taxonomy CRUD operations."""

    def test_save_and_get_taxonomy(self, repo):
        """Test creating and retrieving a taxonomy."""
        taxonomy = Taxonomy(
            id="tax-1",
            title="Test Taxonomy",
            description="A test taxonomy",
        )
        saved = repo.save_taxonomy(taxonomy)

        assert saved.id == "tax-1"
        assert saved.title == "Test Taxonomy"
        assert saved.version == 1
        assert saved.created_at is not None

        retrieved = repo.get_taxonomy("tax-1")
        assert retrieved is not None
        assert retrieved.title == "Test Taxonomy"

    def test_save_taxonomy_empty_title(self, repo):
        """Test that empty title raises ValueError."""
        taxonomy = Taxonomy(id="tax-1", title="")
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.save_taxonomy(taxonomy)

    def test_list_taxonomies(self, repo):
        """Test listing all taxonomies."""
        repo.save_taxonomy(Taxonomy(id="tax-1", title="Tax 1"))
        repo.save_taxonomy(Taxonomy(id="tax-2", title="Tax 2"))

        taxonomies = repo.list_taxonomies()
        assert len(taxonomies) == 2

    def test_delete_taxonomy(self, repo, sample_taxonomy):
        """Test deleting a taxonomy."""
        assert repo.get_taxonomy(sample_taxonomy.id) is not None

        deleted = repo.delete_taxonomy(sample_taxonomy.id)
        assert deleted is True
        assert repo.get_taxonomy(sample_taxonomy.id) is None

    def test_delete_nonexistent_taxonomy(self, repo):
        """Test deleting a taxonomy that doesn't exist."""
        deleted = repo.delete_taxonomy("nonexistent")
        assert deleted is False

    def test_update_taxonomy(self, repo, sample_taxonomy):
        """Test updating a taxonomy."""
        old_version = sample_taxonomy.version

        sample_taxonomy.title = "Updated Biology"
        updated = repo.save_taxonomy(sample_taxonomy)

        assert updated.title == "Updated Biology"
        assert updated.version == old_version + 1


class TestConceptSchemeCRUD:
    """Tests for ConceptScheme CRUD operations."""

    def test_save_and_get_concept_scheme(self, repo, sample_taxonomy):
        """Test creating and retrieving a concept scheme."""
        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id=sample_taxonomy.id,
            title="Test Scheme",
        )
        saved = repo.save_concept_scheme(scheme)

        assert saved.id == "scheme-1"
        assert saved.taxonomy_id == sample_taxonomy.id
        assert saved.title == "Test Scheme"

    def test_save_concept_scheme_nonexistent_taxonomy(self, repo):
        """Test that saving with nonexistent taxonomy raises ValueError."""
        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id="nonexistent",
            title="Test Scheme",
        )
        with pytest.raises(ValueError, match="does not exist"):
            repo.save_concept_scheme(scheme)

    def test_list_concept_schemes(self, repo, sample_taxonomy):
        """Test listing concept schemes."""
        scheme1 = ConceptScheme(id="s1", taxonomy_id=sample_taxonomy.id, title="S1")
        scheme2 = ConceptScheme(id="s2", taxonomy_id=sample_taxonomy.id, title="S2")
        repo.save_concept_scheme(scheme1)
        repo.save_concept_scheme(scheme2)

        schemes = repo.list_concept_schemes(sample_taxonomy.id)
        assert len(schemes) == 2

    def test_delete_concept_scheme(self, repo, sample_concept_scheme):
        """Test deleting a concept scheme."""
        deleted = repo.delete_concept_scheme(sample_concept_scheme.id)
        assert deleted is True


class TestClassCRUD:
    """Tests for Class CRUD operations."""

    def test_save_and_get_class(self, repo, sample_concept_scheme, sample_taxonomy):
        """Test creating and retrieving a class."""
        cls = Class(
            id="class-1",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Dog",
            description="A domesticated animal",
        )
        saved = repo.save_class(cls)

        assert saved.id == "class-1"
        assert saved.title == "Dog"

        retrieved = repo.get_class("class-1")
        assert retrieved is not None
        assert retrieved.title == "Dog"

    def test_save_class_with_external_references(
        self, repo, sample_concept_scheme, sample_taxonomy
    ):
        """Test saving a class with external references."""
        ref = ExternalReference(
            source="wikidata",
            identifier="Q2084",
            uri="https://www.wikidata.org/wiki/Q2084",
        )
        cls = Class(
            id="class-1",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Dog",
            external_references=[ref],
        )
        saved = repo.save_class(cls)

        assert len(saved.external_references) == 1
        assert saved.external_references[0].source == "wikidata"

    def test_save_class_with_data_properties(
        self, repo, sample_concept_scheme, sample_taxonomy
    ):
        """Test saving a class with data properties."""
        prop = DataPropertyValue(
            property_identifier="common_name",
            value="Dog",
            datatype="xsd:string",
        )
        cls = Class(
            id="class-1",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Canis familiaris",
            data_properties=[prop],
        )
        saved = repo.save_class(cls)

        assert len(saved.data_properties) == 1
        assert saved.data_properties[0].property_identifier == "common_name"

    def test_class_hierarchy(self, repo, sample_concept_scheme, sample_taxonomy):
        """Test class hierarchy with parent relationships."""
        parent = Class(
            id="parent",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Animal",
        )
        repo.save_class(parent)

        child = Class(
            id="child",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Dog",
            parent_class_id="parent",
        )
        saved_child = repo.save_class(child)

        assert saved_child.parent_class_id == "parent"

        # Retrieve children
        children = repo.list_classes(parent_class_id="parent")
        assert len(children) == 1
        assert children[0].id == "child"

    def test_class_self_parent_validation(
        self, repo, sample_concept_scheme, sample_taxonomy
    ):
        """Test that a class cannot be its own parent."""
        cls = Class(
            id="class-1",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Test",
            parent_class_id="class-1",  # Self-reference
        )
        with pytest.raises(ValueError, match="cannot be its own parent"):
            repo.save_class(cls)

    def test_class_cycle_detection(self, repo, sample_concept_scheme, sample_taxonomy):
        """Test that cycles in class hierarchy are detected."""
        parent = Class(
            id="a",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="A",
        )
        repo.save_class(parent)

        child = Class(
            id="b",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="B",
            parent_class_id="a",
        )
        repo.save_class(child)

        # Try to create a cycle: a <- b <- a
        parent.parent_class_id = "b"
        with pytest.raises(ValueError, match="would create a cycle"):
            repo.save_class(parent)

    def test_search_classes(self, repo, sample_concept_scheme, sample_taxonomy):
        """Test searching for classes."""
        repo.save_class(
            Class(
                id="dog",
                concept_scheme_id=sample_concept_scheme.id,
                taxonomy_id=sample_taxonomy.id,
                title="Dog",
                description="Canis familiaris",
            )
        )
        repo.save_class(
            Class(
                id="cat",
                concept_scheme_id=sample_concept_scheme.id,
                taxonomy_id=sample_taxonomy.id,
                title="Cat",
                description="Felis catus",
            )
        )

        criteria = SearchCriteria(query="Dog")
        results = repo.search_classes(criteria)
        assert len(results) == 1
        assert results[0].title == "Dog"

    def test_search_classes_by_description(
        self, repo, sample_concept_scheme, sample_taxonomy
    ):
        """Test searching for classes by description."""
        repo.save_class(
            Class(
                id="animal",
                concept_scheme_id=sample_concept_scheme.id,
                taxonomy_id=sample_taxonomy.id,
                title="Animal",
                description="A living creature",
            )
        )

        criteria = SearchCriteria(query="living")
        results = repo.search_classes(criteria)
        assert len(results) == 1

    def test_delete_class(self, repo, sample_class):
        """Test deleting a class."""
        deleted = repo.delete_class(sample_class.id)
        assert deleted is True
        assert repo.get_class(sample_class.id) is None


class TestIndividualCRUD:
    """Tests for Individual CRUD operations with multi-class support."""

    def test_save_and_get_individual_single_class(self, repo, sample_class):
        """Test creating and retrieving an individual with a single parent class."""
        individual = Individual(
            id="ind-1",
            class_ids=[sample_class.id],
            title="Fido",
            description="A specific dog",
        )
        saved = repo.save_individual(individual)

        assert saved.id == "ind-1"
        assert saved.class_ids == [sample_class.id]

        retrieved = repo.get_individual("ind-1")
        assert retrieved is not None
        assert retrieved.title == "Fido"
        assert retrieved.class_ids == [sample_class.id]

    def test_save_and_get_individual_multiple_classes(
        self, repo, sample_class, sample_concept_scheme, sample_taxonomy
    ):
        """Test creating and retrieving an individual with multiple parent classes."""
        # Create a second class
        class2 = Class(
            id="class-2",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Database Product",
        )
        repo.save_class(class2)

        individual = Individual(
            id="ind-1",
            class_ids=[sample_class.id, class2.id],
            title="PostgreSQL",
            description="A SQL database and a database product",
        )
        saved = repo.save_individual(individual)

        assert saved.id == "ind-1"
        assert saved.class_ids == [sample_class.id, class2.id]

        retrieved = repo.get_individual("ind-1")
        assert retrieved is not None
        assert retrieved.class_ids == [sample_class.id, class2.id]

    def test_save_individual_nonexistent_class(self, repo):
        """Test that saving with nonexistent class raises ValueError."""
        individual = Individual(
            id="ind-1",
            class_ids=["nonexistent"],
            title="Test Individual",
        )
        with pytest.raises(ValueError, match="does not exist"):
            repo.save_individual(individual)

    def test_save_individual_no_classes_raises(self, repo):
        """Test that creating an individual with no classes raises ValueError."""
        with pytest.raises(ValueError, match="at least one parent class"):
            Individual(
                id="ind-1",
                class_ids=[],
                title="Test Individual",
            )

    def test_list_individuals_by_class(
        self, repo, sample_class, sample_concept_scheme, sample_taxonomy
    ):
        """Test listing individuals filtered by class (including those with multiple classes)."""
        class2 = Class(
            id="class-2",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Database Product",
        )
        repo.save_class(class2)

        # Create individual with single class
        repo.save_individual(
            Individual(id="ind-1", class_ids=[sample_class.id], title="I1")
        )
        # Create individual with multiple classes including sample_class
        repo.save_individual(
            Individual(id="ind-2", class_ids=[sample_class.id, class2.id], title="I2")
        )
        # Create individual with only class2
        repo.save_individual(Individual(id="ind-3", class_ids=[class2.id], title="I3"))

        # Filter by sample_class should return ind-1 and ind-2
        individuals = repo.list_individuals(sample_class.id)
        assert len(individuals) == 2
        assert {ind.id for ind in individuals} == {"ind-1", "ind-2"}

        # Filter by class2 should return ind-2 and ind-3
        individuals = repo.list_individuals(class2.id)
        assert len(individuals) == 2
        assert {ind.id for ind in individuals} == {"ind-2", "ind-3"}

    def test_delete_individual(self, repo, sample_class):
        """Test deleting an individual."""
        individual = Individual(id="ind-1", class_ids=[sample_class.id], title="Test")
        repo.save_individual(individual)

        deleted = repo.delete_individual("ind-1")
        assert deleted is True

    def test_update_individual_class_membership(
        self, repo, sample_class, sample_concept_scheme, sample_taxonomy
    ):
        """Test updating an individual's class membership."""
        class2 = Class(
            id="class-2",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Category 2",
        )
        repo.save_class(class2)

        individual = Individual(id="ind-1", class_ids=[sample_class.id], title="Test")
        repo.save_individual(individual)

        # Update class membership
        individual.add_parent_class(class2.id)
        repo.save_individual(individual)

        retrieved = repo.get_individual("ind-1")
        assert retrieved.class_ids == [sample_class.id, class2.id]

    def test_individual_class_order_preserved(
        self, repo, sample_class, sample_concept_scheme, sample_taxonomy
    ):
        """Test that individual class membership order is preserved."""
        class2 = Class(
            id="class-2",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Class 2",
        )
        class3 = Class(
            id="class-3",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            title="Class 3",
        )
        repo.save_class(class2)
        repo.save_class(class3)

        individual = Individual(
            id="ind-1",
            class_ids=[class2.id, sample_class.id, class3.id],
            title="OrderTest",
        )
        repo.save_individual(individual)

        retrieved = repo.get_individual("ind-1")
        assert retrieved.class_ids == [class2.id, sample_class.id, class3.id]


class TestPropertyDefinitionCRUD:
    """Tests for PropertyDefinition CRUD operations."""

    def test_save_and_get_property_definition(self, repo):
        """Test creating and retrieving a property definition."""
        prop = PropertyDefinition(
            id="prop-1",
            identifier="subclass_of",
            title="Subclass Of",
        )
        saved = repo.save_property_definition(prop)

        assert saved.id == "prop-1"
        assert saved.identifier == "subclass_of"

        retrieved = repo.get_property_definition("prop-1")
        assert retrieved is not None
        assert retrieved.identifier == "subclass_of"

    def test_property_definition_unique_identifier(self, repo):
        """Test that property definition identifiers must be unique."""
        repo.save_property_definition(
            PropertyDefinition(
                id="prop-1",
                identifier="subclass_of",
                title="Subclass Of",
            )
        )

        with pytest.raises(ValueError, match="already exists"):
            repo.save_property_definition(
                PropertyDefinition(
                    id="prop-2",
                    identifier="subclass_of",
                    title="Another",
                )
            )

    def test_list_property_definitions(self, repo):
        """Test listing all property definitions."""
        repo.save_property_definition(
            PropertyDefinition(id="p1", identifier="id1", title="P1")
        )
        repo.save_property_definition(
            PropertyDefinition(id="p2", identifier="id2", title="P2")
        )

        props = repo.list_property_definitions()
        assert len(props) == 2

    def test_delete_property_definition(self, repo, sample_property_definition):
        """Test deleting a property definition."""
        deleted = repo.delete_property_definition(sample_property_definition.id)
        assert deleted is True


class TestRelationshipCRUD:
    """Tests for Relationship CRUD operations."""

    def test_save_and_get_relationship(
        self, repo, sample_class, sample_property_definition
    ):
        """Test creating and retrieving a relationship."""
        # Create two classes for relationship
        class2 = Class(
            id="class-2",
            concept_scheme_id=sample_class.concept_scheme_id,
            taxonomy_id=sample_class.taxonomy_id,
            title="Target Class",
        )
        repo.save_class(class2)

        rel = Relationship(
            id="rel-1",
            source_id=sample_class.id,
            target_id=class2.id,
            property_definition_id=sample_property_definition.id,
        )
        saved = repo.save_relationship(rel)

        assert saved.id == "rel-1"
        assert saved.source_id == sample_class.id
        assert saved.target_id == class2.id

        retrieved = repo.get_relationship("rel-1")
        assert retrieved is not None
        assert retrieved.source_id == sample_class.id

    def test_relationship_self_loop_validation(self, repo, sample_property_definition):
        """Test that relationships cannot have same source and target."""
        # The domain entity itself enforces this invariant in __post_init__
        with pytest.raises(ValueError, match="cannot have the same source and target"):
            Relationship(
                id="rel-1",
                source_id="entity-1",
                target_id="entity-1",
                property_definition_id=sample_property_definition.id,
            )

    def test_list_relationships(self, repo, sample_class, sample_property_definition):
        """Test listing relationships filtered by source or target."""
        # Create two classes for relationships
        class1 = sample_class
        class2 = Class(
            id="class-2",
            concept_scheme_id=class1.concept_scheme_id,
            taxonomy_id=class1.taxonomy_id,
            title="Class 2",
        )
        repo.save_class(class2)

        # Create relationships
        repo.save_relationship(
            Relationship(
                id="rel-1",
                source_id=class1.id,
                target_id=class2.id,
                property_definition_id=sample_property_definition.id,
            )
        )

        # List relationships by source
        rels = repo.list_relationships(source_id=class1.id)
        assert len(rels) == 1
        assert rels[0].source_id == class1.id

    def test_delete_relationship(self, repo, sample_class, sample_property_definition):
        """Test deleting a relationship."""
        class2 = Class(
            id="class-2",
            concept_scheme_id=sample_class.concept_scheme_id,
            taxonomy_id=sample_class.taxonomy_id,
            title="Class 2",
        )
        repo.save_class(class2)

        rel = Relationship(
            id="rel-1",
            source_id=sample_class.id,
            target_id=class2.id,
            property_definition_id=sample_property_definition.id,
        )
        repo.save_relationship(rel)

        deleted = repo.delete_relationship("rel-1")
        assert deleted is True
        assert repo.get_relationship("rel-1") is None
