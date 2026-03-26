"""
Unit tests for domain entities in the Ontology Management context.

These tests verify entity behavior in isolation — no infrastructure,
no fakes, just dataclass invariants and methods.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime

from domain.ontology.entities import Taxonomy, ConceptScheme, Class, Individual, Relationship, PropertyDefinition
from domain.ontology.value_objects import ExternalReference, LexicalSense, DataPropertyValue


class TestTaxonomy:
    """Tests for Taxonomy entity."""

    def test_taxonomy_creation(self):
        """Create a taxonomy with required fields."""
        tax = Taxonomy(id="tax-1", title="Biology")
        assert tax.id == "tax-1"
        assert tax.title == "Biology"
        assert tax.description is None
        assert tax.created_at is not None
        assert tax.updated_at is not None

    def test_taxonomy_creation_with_description(self):
        """Create a taxonomy with description."""
        tax = Taxonomy(id="tax-1", title="Biology", description="Life science taxonomy")
        assert tax.description == "Life science taxonomy"

    def test_taxonomy_rename(self):
        """Rename a taxonomy."""
        tax = Taxonomy(id="tax-1", title="Biology")
        original_created = tax.created_at
        tax.rename("Biology 2024")
        assert tax.title == "Biology 2024"
        assert tax.updated_at > original_created

    def test_taxonomy_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        tax = Taxonomy(id="tax-1", title="Biology")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            tax.rename("")

    def test_taxonomy_rename_whitespace_only_raises(self):
        """Rename with whitespace-only string raises ValueError."""
        tax = Taxonomy(id="tax-1", title="Biology")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            tax.rename("   ")


class TestConceptScheme:
    """Tests for ConceptScheme entity."""

    def test_concept_scheme_creation(self):
        """Create a concept scheme."""
        scheme = ConceptScheme(id="scheme-1", taxonomy_id="tax-1", title="Animal Classification")
        assert scheme.id == "scheme-1"
        assert scheme.taxonomy_id == "tax-1"
        assert scheme.title == "Animal Classification"
        assert scheme.description is None

    def test_concept_scheme_creation_with_description(self):
        """Create a concept scheme with description."""
        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id="tax-1",
            title="Animal Classification",
            description="Classification by species",
        )
        assert scheme.description == "Classification by species"

    def test_concept_scheme_rename(self):
        """Rename a concept scheme."""
        scheme = ConceptScheme(id="scheme-1", taxonomy_id="tax-1", title="Animals")
        scheme.rename("Animalia")
        assert scheme.title == "Animalia"

    def test_concept_scheme_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        scheme = ConceptScheme(id="scheme-1", taxonomy_id="tax-1", title="Animals")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            scheme.rename("")


class TestClass:
    """Tests for Class entity."""

    def test_class_creation(self):
        """Create a class."""
        cls = Class(id="class-1", scheme_id="scheme-1", taxonomy_id="tax-1", title="Dog")
        assert cls.id == "class-1"
        assert cls.scheme_id == "scheme-1"
        assert cls.taxonomy_id == "tax-1"
        assert cls.title == "Dog"
        assert cls.description is None
        assert cls.parent_class_id is None
        assert cls.embedding is None
        assert cls.external_references == []
        assert cls.lexical_senses == []

    def test_class_creation_with_description(self):
        """Create a class with description."""
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            description="Canine species",
        )
        assert cls.description == "Canine species"

    def test_class_creation_with_parent(self):
        """Create a class with parent."""
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            parent_class_id="class-0",
        )
        assert cls.parent_class_id == "class-0"

    def test_class_creation_with_embedding(self):
        """Create a class with embedding."""
        embedding = b"test-embedding-bytes"
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            embedding=embedding,
        )
        assert cls.embedding == embedding

    def test_class_rename(self):
        """Rename a class."""
        cls = Class(id="class-1", scheme_id="scheme-1", taxonomy_id="tax-1", title="Dog")
        cls.rename("Canine")
        assert cls.title == "Canine"

    def test_class_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        cls = Class(id="class-1", scheme_id="scheme-1", taxonomy_id="tax-1", title="Dog")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            cls.rename("")

    def test_class_add_subclass_of(self):
        """Add a parent class."""
        cls = Class(id="class-1", scheme_id="scheme-1", taxonomy_id="tax-1", title="Dog")
        assert cls.parent_class_id is None
        cls.add_subclass_of("class-0")
        assert cls.parent_class_id == "class-0"

    def test_class_add_subclass_of_self_raises(self):
        """Add self as parent raises ValueError."""
        cls = Class(id="class-1", scheme_id="scheme-1", taxonomy_id="tax-1", title="Dog")
        with pytest.raises(ValueError, match="A class cannot be its own parent"):
            cls.add_subclass_of("class-1")

    def test_class_remove_subclass_of(self):
        """Remove the parent class."""
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            parent_class_id="class-0",
        )
        assert cls.parent_class_id == "class-0"
        cls.remove_subclass_of()
        assert cls.parent_class_id is None

    def test_class_with_external_references(self):
        """Create a class with external references."""
        refs = [
            ExternalReference(source="DBpedia", identifier="Dog_(animal)", uri="http://dbpedia.org/..."),
            ExternalReference(source="schema.org", identifier="Animal"),
        ]
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            external_references=refs,
        )
        assert len(cls.external_references) == 2
        assert cls.external_references[0].source == "DBpedia"

    def test_class_with_lexical_senses(self):
        """Create a class with lexical senses."""
        senses = [
            LexicalSense(label="Dog", language_code="en", sense_type="preferred"),
            LexicalSense(label="Chien", language_code="fr", sense_type="alternative"),
        ]
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            lexical_senses=senses,
        )
        assert len(cls.lexical_senses) == 2
        assert cls.lexical_senses[1].label == "Chien"


class TestIndividual:
    """Tests for Individual entity."""

    def test_individual_creation(self):
        """Create an individual."""
        ind = Individual(id="ind-1", class_id="class-1", title="Fido")
        assert ind.id == "ind-1"
        assert ind.class_id == "class-1"
        assert ind.title == "Fido"
        assert ind.description is None
        assert ind.data_property_values == []

    def test_individual_creation_with_description(self):
        """Create an individual with description."""
        ind = Individual(id="ind-1", class_id="class-1", title="Fido", description="My pet dog")
        assert ind.description == "My pet dog"

    def test_individual_creation_with_data_properties(self):
        """Create an individual with data property values."""
        props = [
            DataPropertyValue(property_identifier="age", value="5", datatype="xsd:integer"),
            DataPropertyValue(property_identifier="name", value="Fido"),
        ]
        ind = Individual(id="ind-1", class_id="class-1", title="Fido", data_property_values=props)
        assert len(ind.data_property_values) == 2
        assert ind.data_property_values[0].value == "5"

    def test_individual_rename(self):
        """Rename an individual."""
        ind = Individual(id="ind-1", class_id="class-1", title="Fido")
        ind.rename("Max")
        assert ind.title == "Max"

    def test_individual_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        ind = Individual(id="ind-1", class_id="class-1", title="Fido")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            ind.rename("")


class TestRelationship:
    """Tests for Relationship entity."""

    def test_relationship_creation(self):
        """Create a relationship."""
        rel = Relationship(
            id="rel-1",
            source_id="class-1",
            target_id="class-2",
            property_definition_id="prop-1",
        )
        assert rel.id == "rel-1"
        assert rel.source_id == "class-1"
        assert rel.target_id == "class-2"
        assert rel.property_definition_id == "prop-1"
        assert rel.created_at is not None

    def test_relationship_self_loop_raises(self):
        """Create a relationship with same source and target raises ValueError."""
        with pytest.raises(ValueError, match="A relationship cannot have the same source and target"):
            Relationship(
                id="rel-1",
                source_id="class-1",
                target_id="class-1",
                property_definition_id="prop-1",
            )


class TestPropertyDefinition:
    """Tests for PropertyDefinition entity."""

    def test_property_definition_creation(self):
        """Create a property definition."""
        prop = PropertyDefinition(id="prop-1", identifier="is_a", title="Is A")
        assert prop.id == "prop-1"
        assert prop.identifier == "is_a"
        assert prop.title == "Is A"
        assert prop.description is None

    def test_property_definition_creation_with_description(self):
        """Create a property definition with description."""
        prop = PropertyDefinition(
            id="prop-1",
            identifier="is_a",
            title="Is A",
            description="Taxonomic is-a relationship",
        )
        assert prop.description == "Taxonomic is-a relationship"

    def test_property_definition_rename(self):
        """Rename a property definition."""
        prop = PropertyDefinition(id="prop-1", identifier="is_a", title="Is A")
        prop.rename("Is-A Relationship")
        assert prop.title == "Is-A Relationship"

    def test_property_definition_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        prop = PropertyDefinition(id="prop-1", identifier="is_a", title="Is A")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            prop.rename("")
