"""
Unit tests for domain entities in the Ontology Management context.

These tests verify entity behavior in isolation — no infrastructure,
no fakes, just dataclass invariants and methods.
"""

import sys
import os
import struct

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.ontology.entities import Taxonomy, ConceptScheme, Class, Individual, Relationship, PropertyDefinition
from domain.ontology.value_objects import ExternalReference, LexicalSense, DataPropertyValue, OntologyMapping, SearchCriteria, NodeType
from types import MappingProxyType


class TestExternalReference:
    """Tests for ExternalReference value object."""

    def test_external_reference_creation(self):
        """Create an external reference."""
        ref = ExternalReference(identifier="dog_dbpedia", source="DBpedia", uri="http://dbpedia.org/resource/Dog_(animal)")
        assert ref.identifier == "dog_dbpedia"
        assert ref.source == "DBpedia"
        assert ref.uri == "http://dbpedia.org/resource/Dog_(animal)"
        assert ref.label is None
        assert ref.confidence is None
        assert ref.metadata is None

    def test_external_reference_with_optional_fields(self):
        """Create an external reference with optional fields."""
        ref = ExternalReference(
            identifier="dog_dbpedia",
            source="DBpedia",
            uri="http://dbpedia.org/resource/Dog_(animal)",
            label="Dog",
            confidence=0.95,
        )
        assert ref.label == "Dog"
        assert ref.confidence == 0.95

    def test_external_reference_with_metadata(self):
        """Create an external reference with immutable metadata."""
        metadata_dict = {"category": "animal", "population": 500000}
        metadata = MappingProxyType(metadata_dict)
        ref = ExternalReference(
            identifier="dog_dbpedia",
            source="DBpedia",
            uri="http://dbpedia.org/resource/Dog_(animal)",
            metadata=metadata,
        )
        assert ref.metadata is not None
        assert ref.metadata["category"] == "animal"
        assert ref.metadata["population"] == 500000

    def test_external_reference_metadata_is_immutable(self):
        """ExternalReference.metadata wrapped in MappingProxyType is immutable."""
        metadata_dict = {"category": "animal"}
        metadata = MappingProxyType(metadata_dict)
        ref = ExternalReference(
            identifier="dog_dbpedia",
            source="DBpedia",
            uri="http://dbpedia.org/resource/Dog_(animal)",
            metadata=metadata,
        )
        with pytest.raises(TypeError):
            ref.metadata["new_key"] = "new_value"

    def test_external_reference_is_frozen(self):
        """ExternalReference is frozen and immutable."""
        ref = ExternalReference(identifier="dog_dbpedia", source="DBpedia", uri="http://dbpedia.org/resource/Dog_(animal)")
        with pytest.raises(Exception):
            ref.identifier = "dog_schema"


class TestLexicalSense:
    """Tests for LexicalSense value object."""

    def test_lexical_sense_creation(self):
        """Create a lexical sense."""
        sense = LexicalSense(synset_id="dog.n.01", definition="a member of the genus Canis", lemma="dog")
        assert sense.synset_id == "dog.n.01"
        assert sense.definition == "a member of the genus Canis"
        assert sense.lemma == "dog"
        assert sense.confidence is None
        assert sense.source == "wordnet"

    def test_lexical_sense_with_confidence(self):
        """Create a lexical sense with confidence."""
        sense = LexicalSense(synset_id="dog.n.01", definition="a member of the genus Canis", lemma="dog", confidence=0.98)
        assert sense.confidence == 0.98

    def test_lexical_sense_with_custom_source(self):
        """Create a lexical sense with custom source."""
        sense = LexicalSense(synset_id="dog.n.01", definition="a member of the genus Canis", lemma="dog", source="custom_source")
        assert sense.source == "custom_source"

    def test_lexical_sense_is_frozen(self):
        """LexicalSense is frozen and immutable."""
        sense = LexicalSense(synset_id="dog.n.01", definition="a member of the genus Canis", lemma="dog")
        with pytest.raises(Exception):
            sense.synset_id = "cat.n.01"


class TestDataPropertyValue:
    """Tests for DataPropertyValue value object."""

    def test_data_property_value_creation(self):
        """Create a data property value."""
        prop = DataPropertyValue(property_identifier="age", value=5)
        assert prop.property_identifier == "age"
        assert prop.value == 5
        assert prop.datatype is None

    def test_data_property_value_with_datatype(self):
        """Create a data property value with datatype."""
        prop = DataPropertyValue(property_identifier="age", value=5, datatype="xsd:integer")
        assert prop.datatype == "xsd:integer"

    def test_data_property_value_with_different_types(self):
        """Create data property values with different value types."""
        str_prop = DataPropertyValue(property_identifier="name", value="Fido")
        float_prop = DataPropertyValue(property_identifier="weight", value=25.5)
        bool_prop = DataPropertyValue(property_identifier="vaccinated", value=True)
        assert str_prop.value == "Fido"
        assert float_prop.value == 25.5
        assert bool_prop.value is True

    def test_data_property_value_is_frozen(self):
        """DataPropertyValue is frozen and immutable."""
        prop = DataPropertyValue(property_identifier="age", value=5)
        with pytest.raises(Exception):
            prop.value = 6


class TestTaxonomy:
    """Tests for Taxonomy entity."""

    def test_taxonomy_creation(self):
        """Create a taxonomy with required fields."""
        tax = Taxonomy(id="tax-1", title="Biology")
        assert tax.id == "tax-1"
        assert tax.title == "Biology"
        assert tax.description is None
        assert tax.created_at is None
        assert tax.last_modified is None

    def test_taxonomy_creation_with_description(self):
        """Create a taxonomy with description."""
        tax = Taxonomy(id="tax-1", title="Biology", description="Life science taxonomy")
        assert tax.description == "Life science taxonomy"

    def test_taxonomy_rename(self):
        """Rename a taxonomy."""
        tax = Taxonomy(id="tax-1", title="Biology", created_at=None)
        tax.rename("Biology 2024")
        assert tax.title == "Biology 2024"
        assert tax.last_modified is not None

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
        assert cls.title_embedding is None
        assert cls.description_embedding is None
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
        """Create a class with title and description embeddings."""
        embedding_floats = [0.1, 0.2, 0.3, 0.4, 0.5]
        title_embedding = struct.pack('5f', *embedding_floats)
        description_embedding = struct.pack('5f', *[0.5, 0.4, 0.3, 0.2, 0.1])
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            title_embedding=title_embedding,
            description_embedding=description_embedding,
        )
        assert cls.title_embedding == title_embedding
        assert cls.description_embedding == description_embedding

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
            ExternalReference(identifier="dog_dbpedia", source="DBpedia", uri="http://dbpedia.org/resource/Dog_(animal)", label="Dog"),
            ExternalReference(identifier="animal_schema", source="schema.org", uri="http://schema.org/Animal", label="Animal"),
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
            LexicalSense(synset_id="dog.n.01", definition="a member of the genus Canis", lemma="dog"),
            LexicalSense(synset_id="dog.n.02", definition="a despicable person", lemma="dog"),
        ]
        cls = Class(
            id="class-1",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            lexical_senses=senses,
        )
        assert len(cls.lexical_senses) == 2
        assert cls.lexical_senses[1].lemma == "dog"


class TestIndividual:
    """Tests for Individual entity."""

    def test_individual_creation(self):
        """Create an individual."""
        ind = Individual(id="ind-1", class_id="class-1", title="Fido")
        assert ind.id == "ind-1"
        assert ind.class_id == "class-1"
        assert ind.title == "Fido"
        assert ind.description is None
        assert ind.data_properties == []

    def test_individual_creation_with_description(self):
        """Create an individual with description."""
        ind = Individual(id="ind-1", class_id="class-1", title="Fido", description="My pet dog")
        assert ind.description == "My pet dog"

    def test_individual_creation_with_data_properties(self):
        """Create an individual with data property values."""
        props = [
            DataPropertyValue(property_identifier="age", value=5, datatype="xsd:integer"),
            DataPropertyValue(property_identifier="name", value="Fido"),
        ]
        ind = Individual(id="ind-1", class_id="class-1", title="Fido", data_properties=props)
        assert len(ind.data_properties) == 2
        assert ind.data_properties[0].value == 5

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

    def test_property_definition_creation_with_definition(self):
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


class TestOntologyMapping:
    """Tests for OntologyMapping value object."""

    def test_ontology_mapping_creation(self):
        """Create an ontology mapping."""
        mapping = OntologyMapping(
            ontology="schema.org",
            uri="https://schema.org/Thing",
            label="Thing",
        )
        assert mapping.ontology == "schema.org"
        assert mapping.uri == "https://schema.org/Thing"
        assert mapping.label == "Thing"
        assert mapping.exact_match is False

    def test_ontology_mapping_with_exact_match_false(self):
        """Create ontology mappings with exact_match=False."""
        mapping = OntologyMapping(
            ontology="dbpedia",
            uri="http://dbpedia.org/ontology/SomeClass",
            label="Some Class",
            exact_match=False,
        )
        assert mapping.exact_match is False

    def test_ontology_mapping_without_label(self):
        """Create ontology mapping without label (optional)."""
        mapping = OntologyMapping(
            ontology="owl",
            uri="http://example.com/ontology/MyClass",
        )
        assert mapping.label is None
        assert mapping.exact_match is False

    def test_ontology_mapping_is_frozen(self):
        """OntologyMapping is frozen and immutable."""
        mapping = OntologyMapping(
            ontology="schema.org",
            uri="https://schema.org/Thing",
            label="Thing",
        )
        with pytest.raises(Exception):
            mapping.uri = "https://schema.org/Other"

    def test_ontology_mapping_in_property_definition(self):
        """PropertyDefinition can contain an OntologyMapping."""
        mapping = OntologyMapping(
            ontology="schema.org",
            uri="https://schema.org/Thing",
            label="Thing",
        )
        prop = PropertyDefinition(
            id="prop-1",
            identifier="skos:exactMatch",
            title="Exact Match",
            ontology_mapping=mapping,
        )
        assert prop.ontology_mapping == mapping
        assert prop.ontology_mapping.ontology == "schema.org"


class TestSearchCriteria:
    """Tests for SearchCriteria value object."""

    def test_search_criteria_defaults(self):
        """SearchCriteria with default values."""
        criteria = SearchCriteria()
        assert criteria.query is None
        assert criteria.node_types is None
        assert criteria.taxonomy_id is None
        assert criteria.scheme_id is None
        assert criteria.parent_id is None
        assert criteria.use_semantic_search is False
        assert criteria.limit == 20
        assert criteria.offset == 0

    def test_search_criteria_with_query(self):
        """SearchCriteria with text query."""
        criteria = SearchCriteria(query="dog")
        assert criteria.query == "dog"
        assert criteria.limit == 20

    def test_search_criteria_with_node_types(self):
        """SearchCriteria with node type filters."""
        node_types = (NodeType.CLASS, NodeType.INDIVIDUAL)
        criteria = SearchCriteria(node_types=node_types)
        assert criteria.node_types == node_types
        assert len(criteria.node_types) == 2

    def test_search_criteria_node_types_is_immutable(self):
        """SearchCriteria.node_types is a tuple and immutable."""
        node_types = (NodeType.CLASS, NodeType.INDIVIDUAL)
        criteria = SearchCriteria(node_types=node_types)
        with pytest.raises(AttributeError):
            criteria.node_types.append(NodeType.TAXONOMY)

    def test_search_criteria_is_frozen(self):
        """SearchCriteria is frozen and immutable."""
        criteria = SearchCriteria(query="dog", limit=10)
        with pytest.raises(Exception):
            criteria.query = "cat"

    def test_search_criteria_with_custom_limit(self):
        """SearchCriteria with custom limit."""
        criteria = SearchCriteria(query="dog", limit=50)
        assert criteria.limit == 50

    def test_search_criteria_with_offset(self):
        """SearchCriteria with pagination offset."""
        criteria = SearchCriteria(query="dog", limit=10, offset=20)
        assert criteria.offset == 20
        assert criteria.limit == 10

    def test_search_criteria_with_semantic_search(self):
        """SearchCriteria with semantic search enabled."""
        criteria = SearchCriteria(use_semantic_search=True)
        assert criteria.use_semantic_search is True

    def test_search_criteria_with_taxonomy_filter(self):
        """SearchCriteria with taxonomy filter."""
        criteria = SearchCriteria(taxonomy_id="tax-1")
        assert criteria.taxonomy_id == "tax-1"

    def test_search_criteria_with_concept_scheme_filter(self):
        """SearchCriteria with concept scheme filter."""
        criteria = SearchCriteria(scheme_id="scheme-1")
        assert criteria.scheme_id == "scheme-1"

    def test_search_criteria_with_parent_filter(self):
        """SearchCriteria with parent entity filter."""
        criteria = SearchCriteria(parent_id="class-1")
        assert criteria.parent_id == "class-1"
