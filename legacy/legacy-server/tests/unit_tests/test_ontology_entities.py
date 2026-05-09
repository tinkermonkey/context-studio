"""
Unit Tests for domain ontology entities

Tests the business logic validation in Class, Taxonomy, ConceptScheme, and other domain entities.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from domain.ontology.entities import (
    Class,
    Taxonomy,
    ConceptScheme,
    Individual,
)  # noqa: E402, E501
from domain.ontology.value_objects import (
    NodeType,
    ExternalReference,
    LexicalSense,
)  # noqa: E402, E501


class TestClassEntity:
    """Test suite for Class domain entity."""

    @pytest.fixture
    def sample_class(self):
        """Create sample Class entity for testing."""
        return Class(
            id="class-001",
            title="Animal",
            definition="A living organism classified in the kingdom Animalia",
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            subclass_of=[],
        )

    def test_class_creation(self, sample_class):
        """Test creating a Class entity."""
        assert sample_class.id == "class-001"
        assert sample_class.title == "Animal"
        assert (
            sample_class.definition
            == "A living organism classified in the kingdom Animalia"
        )
        assert sample_class.node_type == NodeType.CLASS
        assert sample_class.subclass_of == []

    def test_class_rename_valid_title(self, sample_class):
        """Test renaming class with valid title."""
        sample_class.rename("Organism")
        assert sample_class.title == "Organism"

    def test_class_rename_strips_whitespace(self, sample_class):
        """Test that rename strips leading/trailing whitespace."""
        sample_class.rename("  Organism  ")
        assert sample_class.title == "Organism"

    def test_class_rename_empty_string_raises_error(self, sample_class):
        """Test that rename with empty string raises ValueError."""
        with pytest.raises(ValueError, match="Class title cannot be empty"):
            sample_class.rename("")

    def test_class_rename_whitespace_only_raises_error(self, sample_class):
        """Test that rename with whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Class title cannot be empty"):
            sample_class.rename("   ")

    def test_class_rename_none_raises_error(self, sample_class):
        """Test that rename with None raises ValueError."""
        with pytest.raises(ValueError, match="Class title cannot be empty"):
            sample_class.rename(None)

    def test_class_rename_unicode_title(self, sample_class):
        """Test renaming class with unicode characters."""
        sample_class.rename("Organismo 生物")
        assert sample_class.title == "Organismo 生物"

    def test_class_rename_special_characters(self, sample_class):
        """Test renaming class with special characters."""
        sample_class.rename("Org@n!sm (with symbols)")
        assert sample_class.title == "Org@n!sm (with symbols)"

    def test_add_subclass_of_valid_parent(self, sample_class):
        """Test adding a valid parent class relationship."""
        parent_id = "class-parent-001"
        sample_class.add_subclass_of(parent_id)
        assert parent_id in sample_class.subclass_of
        assert len(sample_class.subclass_of) == 1

    def test_add_subclass_of_prevents_self_reference(self, sample_class):
        """Test that add_subclass_of prevents self-reference."""
        with pytest.raises(ValueError, match="A class cannot be a subclass of itself"):
            sample_class.add_subclass_of("class-001")

    def test_add_subclass_of_multiple_parents(self, sample_class):
        """Test adding multiple parent class relationships."""
        parent1 = "parent-001"
        parent2 = "parent-002"

        sample_class.add_subclass_of(parent1)
        sample_class.add_subclass_of(parent2)

        assert parent1 in sample_class.subclass_of
        assert parent2 in sample_class.subclass_of
        assert len(sample_class.subclass_of) == 2

    def test_add_subclass_of_duplicate_parent_not_added_twice(self, sample_class):
        """Test that duplicate parent relationships are not added."""
        parent_id = "parent-001"

        sample_class.add_subclass_of(parent_id)
        sample_class.add_subclass_of(parent_id)

        assert sample_class.subclass_of.count(parent_id) == 1
        assert len(sample_class.subclass_of) == 1

    def test_add_subclass_of_maintains_order(self, sample_class):
        """Test that subclass relationships maintain insertion order."""
        parents = ["parent-001", "parent-002", "parent-003"]

        for parent in parents:
            sample_class.add_subclass_of(parent)

        assert sample_class.subclass_of == parents

    def test_class_with_multiple_relationships(self, sample_class):
        """Test class with multiple types of relationships."""
        # Add external references
        sample_class.external_references = [
            ExternalReference(
                source="DBpedia",
                uri="http://dbpedia.org/resource/Animal",
                label="Animal (DBpedia)",
                confidence=0.95,
            )
        ]

        # Add lexical senses
        sample_class.lexical_senses = [
            LexicalSense(
                synset_id="synset-001",
                definition="A living being",
                lemma="animal",
                confidence=0.9,
                source="wordnet",
            )
        ]

        # Add parent relationships
        sample_class.add_subclass_of("parent-001")

        # Verify all relationships exist
        assert len(sample_class.external_references) == 1
        assert len(sample_class.lexical_senses) == 1
        assert len(sample_class.subclass_of) == 1

    def test_class_with_parent_id_field(self):
        """Test class with parent_id field (different from subclass_of)."""
        parent_class = Class(
            id="parent-001",
            title="Parent",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        child_class = Class(
            id="child-001",
            title="Child",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=parent_class.id,  # Direct parent
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        assert child_class.parent_id == parent_class.id

    def test_class_embedding_storage(self, sample_class):
        """Test that class can store embedding bytes."""
        embedding_bytes = b"\x00\x01\x02\x03"
        sample_class.embedding = embedding_bytes

        assert sample_class.embedding == embedding_bytes

    def test_class_rename_and_add_subclass_of_together(self, sample_class):
        """Test combining rename and add_subclass_of operations."""
        sample_class.rename("NewName")
        sample_class.add_subclass_of("parent-001")
        sample_class.add_subclass_of("parent-002")

        assert sample_class.title == "NewName"
        assert len(sample_class.subclass_of) == 2


class TestTaxonomyEntity:
    """Test suite for Taxonomy domain entity."""

    @pytest.fixture
    def sample_taxonomy(self):
        """Create sample Taxonomy entity for testing."""
        return Taxonomy(
            id="taxonomy-001",
            title="Technology",
            description="Technology ontology",
            node_type=NodeType.TAXONOMY,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            concept_schemes=[],
        )

    def test_taxonomy_creation(self, sample_taxonomy):
        """Test creating a Taxonomy entity."""
        assert sample_taxonomy.id == "taxonomy-001"
        assert sample_taxonomy.title == "Technology"
        assert sample_taxonomy.node_type == NodeType.TAXONOMY
        assert sample_taxonomy.concept_schemes == []

    def test_taxonomy_with_concept_schemes(self, sample_taxonomy):
        """Test taxonomy with concept schemes."""
        scheme_ids = ["scheme-001", "scheme-002", "scheme-003"]
        sample_taxonomy.concept_schemes = scheme_ids

        assert len(sample_taxonomy.concept_schemes) == 3
        assert all(sid in sample_taxonomy.concept_schemes for sid in scheme_ids)


class TestConceptSchemeEntity:
    """Test suite for ConceptScheme domain entity."""

    @pytest.fixture
    def sample_concept_scheme(self):
        """Create sample ConceptScheme entity for testing."""
        return ConceptScheme(
            id="scheme-001",
            title="Programming Languages",
            description="Programming language concepts",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CONCEPT_SCHEME,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            classes=[],
        )

    def test_concept_scheme_creation(self, sample_concept_scheme):
        """Test creating a ConceptScheme entity."""
        assert sample_concept_scheme.id == "scheme-001"
        assert sample_concept_scheme.title == "Programming Languages"
        assert sample_concept_scheme.node_type == NodeType.CONCEPT_SCHEME
        assert sample_concept_scheme.classes == []

    def test_concept_scheme_with_classes(self, sample_concept_scheme):
        """Test concept scheme with class relationships."""
        class_ids = ["class-001", "class-002", "class-003"]
        sample_concept_scheme.classes = class_ids

        assert len(sample_concept_scheme.classes) == 3
        assert all(cid in sample_concept_scheme.classes for cid in class_ids)


class TestIndividualEntity:
    """Test suite for Individual domain entity."""

    @pytest.fixture
    def sample_individual(self):
        """Create sample Individual entity for testing."""
        return Individual(
            id="individual-001",
            title="Python",
            class_id="class-programming-language",
            node_type=NodeType.INDIVIDUAL,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def test_individual_creation(self, sample_individual):
        """Test creating an Individual entity."""
        assert sample_individual.id == "individual-001"
        assert sample_individual.title == "Python"
        assert sample_individual.class_id == "class-programming-language"
        assert sample_individual.node_type == NodeType.INDIVIDUAL


class TestClassBusinessLogicInvariants:
    """Test suite for Class entity business logic invariants."""

    def test_class_cannot_be_subclass_of_itself_immediate(self):
        """Test that immediate self-reference is caught."""
        cls = Class(
            id="class-001",
            title="Self",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Attempting to make a class a subclass of itself should fail
        with pytest.raises(ValueError, match="A class cannot be a subclass of itself"):
            cls.add_subclass_of(cls.id)

    def test_class_title_cannot_become_empty_through_rename(self):
        """Test that class title validation is always enforced."""
        cls = Class(
            id="class-001",
            title="Original",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        # First rename succeeds
        cls.rename("First")
        assert cls.title == "First"

        # Attempting empty rename should fail
        with pytest.raises(ValueError):
            cls.rename("")

        # Title should remain unchanged after failed rename
        assert cls.title == "First"

    def test_class_subclass_relationships_form_directed_graph(self):
        """Test that subclass relationships can form complex directed structures."""
        # Create a diamond-shaped inheritance graph
        # Animal <- (Mammal, Bird)
        # Mammal <- (Dog, Cat)

        Class(
            id="animal",
            title="Animal",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        mammal = Class(
            id="mammal",
            title="Mammal",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        dog = Class(
            id="dog",
            title="Dog",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Build the graph
        mammal.add_subclass_of("animal")
        dog.add_subclass_of("mammal")
        dog.add_subclass_of("animal")  # Multiple inheritance

        assert "animal" in mammal.subclass_of
        assert "mammal" in dog.subclass_of
        assert "animal" in dog.subclass_of
        assert len(dog.subclass_of) == 2

    def test_class_rename_validates_each_call(self):
        """Test that rename validation applies to every invocation."""
        cls = Class(
            id="class-001",
            title="Original",
            definition=None,
            scheme_id="scheme-001",
            taxonomy_id="taxonomy-001",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Multiple valid renames
        cls.rename("Name1")
        assert cls.title == "Name1"

        cls.rename("Name2")
        assert cls.title == "Name2"

        # Invalid rename between valid ones
        with pytest.raises(ValueError):
            cls.rename("")

        # Title should not change
        assert cls.title == "Name2"
