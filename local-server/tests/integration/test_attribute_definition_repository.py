"""
Integration tests for AttributeDefinition CRUD operations in SQLiteOntologyRepository.

Tests the adapter against a real SQLite database to verify:
- CRUD operations on AttributeDefinition entities
- Unique constraint on (class_id, identifier)
- Cascade deletion when a Class is deleted
- Sorting by sort_order
- FK constraint validation
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Taxonomy,
)
from domain.ontology.value_objects import ExternalReference, Status


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    # Enable foreign key constraints for CASCADE deletes
    with engine.begin() as conn:
        conn.connection.execute("PRAGMA foreign_keys = ON")

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
        identifier="tax_biology",
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
        identifier="scheme_organisms",
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
        identifier="cls_animal",
        title="Animal",
        description="A living organism of the kingdom Animalia",
    )
    return repo.save_class(cls)


class TestAttributeDefinitionGet:
    """Tests for get_attribute_definition."""

    def test_get_existing_attribute_definition(self, repo, sample_class):
        """Test retrieving an existing attribute definition."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
            description="The name of the animal",
        )
        saved = repo.save_attribute_definition(attr_def)

        retrieved = repo.get_attribute_definition(saved.id)
        assert retrieved is not None
        assert retrieved.id == saved.id
        assert retrieved.class_id == sample_class.id
        assert retrieved.identifier == "attr_name"
        assert retrieved.title == "Name"
        assert retrieved.datatype == "string"

    def test_get_nonexistent_attribute_definition(self, repo):
        """Test retrieving a non-existent attribute definition."""
        result = repo.get_attribute_definition("nonexistent-id")
        assert result is None


class TestAttributeDefinitionList:
    """Tests for list_attribute_definitions."""

    def test_list_empty(self, repo, sample_class):
        """Test listing when no attribute definitions exist."""
        result = repo.list_attribute_definitions(class_id=sample_class.id)
        assert result == []

    def test_list_by_class(self, repo, sample_class):
        """Test listing attribute definitions for a class."""
        attr_def1 = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
            sort_order=1,
        )
        attr_def2 = AttributeDefinition(
            id="attr-2",
            class_id=sample_class.id,
            identifier="attr_age",
            title="Age",
            datatype="integer",
            sort_order=0,
        )
        repo.save_attribute_definition(attr_def1)
        repo.save_attribute_definition(attr_def2)

        result = repo.list_attribute_definitions(class_id=sample_class.id)
        assert len(result) == 2
        # Should be ordered by sort_order
        assert result[0].sort_order == 0
        assert result[1].sort_order == 1

    def test_list_ordered_by_sort_order(self, repo, sample_class):
        """Test that list_attribute_definitions returns results ordered by sort_order."""
        for i in [2, 0, 1]:
            attr_def = AttributeDefinition(
                id=f"attr-{i}",
                class_id=sample_class.id,
                identifier=f"attr_{i}",
                title=f"Attribute {i}",
                datatype="string",
                sort_order=i,
            )
            repo.save_attribute_definition(attr_def)

        result = repo.list_attribute_definitions(class_id=sample_class.id)
        assert len(result) == 3
        assert [r.sort_order for r in result] == [0, 1, 2]

    def test_list_pagination(self, repo, sample_class):
        """Test pagination of attribute definitions."""
        for i in range(5):
            attr_def = AttributeDefinition(
                id=f"attr-{i}",
                class_id=sample_class.id,
                identifier=f"attr_{i}",
                title=f"Attribute {i}",
                datatype="string",
                sort_order=i,
            )
            repo.save_attribute_definition(attr_def)

        result = repo.list_attribute_definitions(class_id=sample_class.id, limit=2, offset=1)
        assert len(result) == 2
        assert result[0].sort_order == 1
        assert result[1].sort_order == 2


class TestAttributeDefinitionSave:
    """Tests for save_attribute_definition."""

    def test_save_new_attribute_definition(self, repo, sample_class):
        """Test saving a new attribute definition."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
            description="The name of the animal",
        )

        saved = repo.save_attribute_definition(attr_def)
        assert saved.id == attr_def.id
        assert saved.class_id == sample_class.id
        assert saved.identifier == "attr_name"
        assert saved.title == "Name"
        assert saved.version == 1

    def test_update_existing_attribute_definition(self, repo, sample_class):
        """Test updating an existing attribute definition."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
        )
        saved = repo.save_attribute_definition(attr_def)
        assert saved.version == 1

        attr_def.title = "Updated Name"
        attr_def.version = 1
        updated = repo.save_attribute_definition(attr_def)
        assert updated.title == "Updated Name"
        assert updated.version == 2

    def test_save_with_external_references(self, repo, sample_class):
        """Test saving attribute definition with external references."""
        refs = [
            ExternalReference(
                source="dr_spec",
                identifier="some.attribute.id",
                uri="http://example.com/attr",
                metadata={"provenance": "import"},
            )
        ]
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
            external_references=refs,
        )

        saved = repo.save_attribute_definition(attr_def)
        assert len(saved.external_references) == 1
        assert saved.external_references[0].source == "dr_spec"

    def test_save_empty_title_raises_error(self, repo, sample_class):
        """Test that saving with empty title raises ValueError."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="",
            datatype="string",
        )

        with pytest.raises(ValueError, match="title cannot be empty"):
            repo.save_attribute_definition(attr_def)

    def test_save_empty_identifier_raises_error(self, repo, sample_class):
        """Test that creating with empty identifier raises ValueError in domain layer."""
        # Domain validates identifier in __post_init__, before repo sees it
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            AttributeDefinition(
                id="attr-1",
                class_id=sample_class.id,
                identifier="",
                title="Name",
                datatype="string",
            )

    def test_save_nonexistent_parent_class_raises_error(self, repo):
        """Test that saving with nonexistent parent class raises ValueError."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="nonexistent-class-id",
            identifier="attr_name",
            title="Name",
            datatype="string",
        )

        with pytest.raises(ValueError, match="Parent class"):
            repo.save_attribute_definition(attr_def)

    def test_save_duplicate_identifier_raises_error(self, repo, sample_class):
        """Test that saving with duplicate (class_id, identifier) raises ValueError."""
        attr_def1 = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
        )
        repo.save_attribute_definition(attr_def1)

        attr_def2 = AttributeDefinition(
            id="attr-2",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Different Name",
            datatype="string",
        )

        with pytest.raises(ValueError, match="already exists"):
            repo.save_attribute_definition(attr_def2)


class TestAttributeDefinitionDelete:
    """Tests for delete_attribute_definition."""

    def test_delete_existing_attribute_definition(self, repo, sample_class):
        """Test deleting an existing attribute definition."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
        )
        saved = repo.save_attribute_definition(attr_def)

        result = repo.delete_attribute_definition(saved.id)
        assert result is True

        retrieved = repo.get_attribute_definition(saved.id)
        assert retrieved is None

    def test_delete_nonexistent_attribute_definition(self, repo):
        """Test deleting a non-existent attribute definition."""
        result = repo.delete_attribute_definition("nonexistent-id")
        assert result is False


class TestAttributeDefinitionCount:
    """Tests for count_attribute_definitions."""

    def test_count_empty(self, repo, sample_class):
        """Test counting when no attribute definitions exist."""
        count = repo.count_attribute_definitions(class_id=sample_class.id)
        assert count == 0

    def test_count_by_class(self, repo, sample_class):
        """Test counting attribute definitions for a class."""
        for i in range(3):
            attr_def = AttributeDefinition(
                id=f"attr-{i}",
                class_id=sample_class.id,
                identifier=f"attr_{i}",
                title=f"Attribute {i}",
                datatype="string",
            )
            repo.save_attribute_definition(attr_def)

        count = repo.count_attribute_definitions(class_id=sample_class.id)
        assert count == 3

    def test_count_all(self, repo, sample_class, sample_taxonomy, sample_concept_scheme):
        """Test counting all attribute definitions regardless of class."""
        cls2 = Class(
            id="class-2",
            concept_scheme_id=sample_concept_scheme.id,
            taxonomy_id=sample_taxonomy.id,
            identifier="cls_plant",
            title="Plant",
        )
        repo.save_class(cls2)

        attr_def1 = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
        )
        attr_def2 = AttributeDefinition(
            id="attr-2",
            class_id=cls2.id,
            identifier="attr_height",
            title="Height",
            datatype="integer",
        )
        repo.save_attribute_definition(attr_def1)
        repo.save_attribute_definition(attr_def2)

        count = repo.count_attribute_definitions()
        assert count == 2


class TestAttributeDefinitionCascadeDelete:
    """Tests for cascade deletion when parent Class is deleted."""

    def test_cascade_delete_on_class_deletion(self, repo, sample_class):
        """Test that deleting a class cascades to delete its attribute definitions."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id=sample_class.id,
            identifier="attr_name",
            title="Name",
            datatype="string",
        )
        saved = repo.save_attribute_definition(attr_def)

        # Delete the class
        repo.delete_class(sample_class.id)

        # Verify the attribute definition is gone
        retrieved = repo.get_attribute_definition(saved.id)
        assert retrieved is None

    def test_multiple_attribute_definitions_cascade_delete(
        self, repo, sample_class
    ):
        """Test that cascade deletion works for multiple attribute definitions."""
        attr_defs = []
        for i in range(3):
            attr_def = AttributeDefinition(
                id=f"attr-{i}",
                class_id=sample_class.id,
                identifier=f"attr_{i}",
                title=f"Attribute {i}",
                datatype="string",
            )
            saved = repo.save_attribute_definition(attr_def)
            attr_defs.append(saved)

        # Verify they exist
        assert repo.count_attribute_definitions(class_id=sample_class.id) == 3

        # Delete the class
        repo.delete_class(sample_class.id)

        # Verify all attribute definitions are gone
        for attr_def in attr_defs:
            retrieved = repo.get_attribute_definition(attr_def.id)
            assert retrieved is None
