"""
Unit tests for domain entities in the Ontology Management context.

These tests verify entity behavior in isolation — no infrastructure,
no fakes, just dataclass invariants and methods.
"""

from types import MappingProxyType

import pytest

from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import (
    DataPropertyValue,
    ExternalReference,
    LexicalSense,
    NodeType,
    OntologyMapping,
    SearchCriteria,
)


class TestExternalReference:
    """Tests for ExternalReference value object."""

    def test_external_reference_creation(self):
        """Create an external reference."""
        ref = ExternalReference(
            source="DBpedia",
            identifier="dog_dbpedia",
            uri="http://dbpedia.org/resource/Dog_(animal)",
        )
        assert ref.source == "DBpedia"
        assert ref.identifier == "dog_dbpedia"
        assert ref.uri == "http://dbpedia.org/resource/Dog_(animal)"
        assert ref.metadata is None

    def test_external_reference_without_uri(self):
        """Create an external reference without URI (optional)."""
        ref = ExternalReference(source="DBpedia", identifier="dog_dbpedia")
        assert ref.source == "DBpedia"
        assert ref.identifier == "dog_dbpedia"
        assert ref.uri is None

    def test_external_reference_with_metadata(self):
        """Create an external reference with immutable metadata."""
        metadata_dict = {"category": "animal", "population": 500000}
        metadata = MappingProxyType(metadata_dict)
        ref = ExternalReference(
            source="DBpedia",
            identifier="dog_dbpedia",
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
            source="DBpedia",
            identifier="dog_dbpedia",
            uri="http://dbpedia.org/resource/Dog_(animal)",
            metadata=metadata,
        )
        with pytest.raises(TypeError):
            ref.metadata["new_key"] = "new_value"

    def test_external_reference_is_frozen(self):
        """ExternalReference is frozen and immutable."""
        ref = ExternalReference(
            source="DBpedia",
            identifier="dog_dbpedia",
            uri="http://dbpedia.org/resource/Dog_(animal)",
        )
        with pytest.raises(Exception):
            ref.identifier = "dog_schema"


class TestLexicalSense:
    """Tests for LexicalSense value object."""

    def test_lexical_sense_creation(self):
        """Create a lexical sense."""
        sense = LexicalSense(label="dog", language_code="en", sense_type="synset")
        assert sense.label == "dog"
        assert sense.language_code == "en"
        assert sense.sense_type == "synset"

    def test_lexical_sense_with_different_language(self):
        """Create a lexical sense with different language."""
        sense = LexicalSense(label="gato", language_code="es", sense_type="synset")
        assert sense.language_code == "es"
        assert sense.label == "gato"

    def test_lexical_sense_with_different_sense_type(self):
        """Create a lexical sense with different sense type."""
        sense = LexicalSense(label="dog", language_code="en", sense_type="word_form")
        assert sense.sense_type == "word_form"

    def test_lexical_sense_is_frozen(self):
        """LexicalSense is frozen and immutable."""
        sense = LexicalSense(label="dog", language_code="en", sense_type="synset")
        with pytest.raises(Exception):
            sense.label = "cat"


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
        tax = Taxonomy(id="tax-1", identifier="tax_test", title="Biology")
        assert tax.id == "tax-1"
        assert tax.title == "Biology"
        assert tax.description is None
        assert tax.created_at is None
        assert tax.last_modified is None

    def test_taxonomy_creation_with_description(self):
        """Create a taxonomy with description."""
        tax = Taxonomy(id="tax-1", identifier="tax_test", title="Biology", description="Life science taxonomy")
        assert tax.description == "Life science taxonomy"

    def test_taxonomy_rename(self):
        """Rename a taxonomy."""
        tax = Taxonomy(id="tax-1", identifier="tax_test", title="Biology", created_at=None)
        tax.rename("Biology 2024")
        assert tax.title == "Biology 2024"
        assert tax.last_modified is not None

    def test_taxonomy_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        tax = Taxonomy(id="tax-1", identifier="tax_test", title="Biology")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            tax.rename("")

    def test_taxonomy_rename_whitespace_only_raises(self):
        """Rename with whitespace-only string raises ValueError."""
        tax = Taxonomy(id="tax-1", identifier="tax_test", title="Biology")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            tax.rename("   ")


class TestConceptScheme:
    """Tests for ConceptScheme entity."""

    def test_concept_scheme_creation(self):
        """Create a concept scheme."""
        scheme = ConceptScheme(id="scheme-1", taxonomy_id="tax-1", identifier="scheme_test", title="Animal Classification")
        assert scheme.id == "scheme-1"
        assert scheme.taxonomy_id == "tax-1"
        assert scheme.title == "Animal Classification"
        assert scheme.description is None

    def test_concept_scheme_creation_with_description(self):
        """Create a concept scheme with description."""
        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id="tax-1",
            identifier="scheme_test",
            title="Animal Classification",
            description="Classification by species",
        )
        assert scheme.description == "Classification by species"

    def test_concept_scheme_rename(self):
        """Rename a concept scheme."""
        scheme = ConceptScheme(id="scheme-1", taxonomy_id="tax-1", identifier="scheme_test", title="Animals")
        scheme.rename("Animalia")
        assert scheme.title == "Animalia"

    def test_concept_scheme_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        scheme = ConceptScheme(id="scheme-1", taxonomy_id="tax-1", identifier="scheme_test", title="Animals")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            scheme.rename("")


class TestClass:
    """Tests for Class entity."""

    def test_class_creation(self):
        """Create a class."""
        cls = Class(id="class-1", concept_scheme_id="scheme-1", taxonomy_id="tax-1", identifier="cls_test", title="Dog")
        assert cls.id == "class-1"
        assert cls.concept_scheme_id == "scheme-1"
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
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            identifier="cls_test",
            title="Dog",
            description="Canine species",
        )
        assert cls.description == "Canine species"

    def test_class_creation_with_parent(self):
        """Create a class with parent."""
        cls = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            identifier="cls_test",
            title="Dog",
            parent_class_id="class-0",
        )
        assert cls.parent_class_id == "class-0"

    def test_class_creation_with_embedding(self):
        """Create a class with semantic embedding."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        cls = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            identifier="cls_test",
            title="Dog",
            embedding=embedding,
        )
        assert cls.embedding == embedding

    def test_class_rename(self):
        """Rename a class."""
        cls = Class(id="class-1", concept_scheme_id="scheme-1", taxonomy_id="tax-1", identifier="cls_test", title="Dog")
        cls.rename("Canine")
        assert cls.title == "Canine"

    def test_class_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        cls = Class(id="class-1", concept_scheme_id="scheme-1", taxonomy_id="tax-1", identifier="cls_test", title="Dog")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            cls.rename("")

    def test_class_add_subclass_of(self):
        """Add a parent class."""
        cls = Class(id="class-1", concept_scheme_id="scheme-1", taxonomy_id="tax-1", identifier="cls_test", title="Dog")
        assert cls.parent_class_id is None
        cls.add_subclass_of("class-0")
        assert cls.parent_class_id == "class-0"

    def test_class_add_subclass_of_self_raises(self):
        """Add self as parent raises ValueError."""
        cls = Class(id="class-1", concept_scheme_id="scheme-1", taxonomy_id="tax-1", identifier="cls_test", title="Dog")
        with pytest.raises(ValueError, match="A class cannot be its own parent"):
            cls.add_subclass_of("class-1")

    def test_class_remove_subclass_of(self):
        """Remove the parent class."""
        cls = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            identifier="cls_test",
            title="Dog",
            parent_class_id="class-0",
        )
        assert cls.parent_class_id == "class-0"
        cls.remove_subclass_of()
        assert cls.parent_class_id is None

    def test_class_with_external_references(self):
        """Create a class with external references."""
        refs = [
            ExternalReference(
                source="DBpedia",
                identifier="dog_dbpedia",
                uri="http://dbpedia.org/resource/Dog_(animal)",
            ),
            ExternalReference(
                source="schema.org",
                identifier="animal_schema",
                uri="http://schema.org/Animal",
            ),
        ]
        cls = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            identifier="cls_test",
            title="Dog",
            external_references=refs,
        )
        assert len(cls.external_references) == 2
        assert cls.external_references[0].source == "DBpedia"

    def test_class_with_lexical_senses(self):
        """Create a class with lexical senses."""
        senses = [
            LexicalSense(label="dog", language_code="en", sense_type="synset"),
            LexicalSense(label="dog", language_code="en", sense_type="word_form"),
        ]
        cls = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            identifier="cls_test",
            title="Dog",
            lexical_senses=senses,
        )
        assert len(cls.lexical_senses) == 2
        assert cls.lexical_senses[1].label == "dog"


class TestIndividual:
    """Tests for Individual entity with multi-class support."""

    def test_individual_creation_single_class(self):
        """Create an individual with a single parent class."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="Fido")
        assert ind.id == "ind-1"
        assert ind.class_ids == ["class-1"]
        assert ind.title == "Fido"
        assert ind.description is None
        assert ind.data_properties == []

    def test_individual_creation_multiple_classes(self):
        """Create an individual with multiple parent classes."""
        ind = Individual(id="ind-1", class_ids=["class-1", "class-2"], title="PostgreSQL")
        assert ind.class_ids == ["class-1", "class-2"]
        assert len(ind.class_ids) == 2

    def test_individual_creation_with_description(self):
        """Create an individual with description."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="Fido", description="My pet dog")
        assert ind.description == "My pet dog"

    def test_individual_creation_with_data_properties(self):
        """Create an individual with data property values."""
        props = [
            DataPropertyValue(property_identifier="age", value=5, datatype="xsd:integer"),
            DataPropertyValue(property_identifier="name", value="Fido"),
        ]
        ind = Individual(id="ind-1", class_ids=["class-1"], title="Fido", data_properties=props)
        assert len(ind.data_properties) == 2
        assert ind.data_properties[0].value == 5

    def test_individual_no_classes_raises(self):
        """Create an individual with no parent classes raises ValueError."""
        with pytest.raises(ValueError, match="Individual must have at least one parent class"):
            Individual(id="ind-1", class_ids=[], title="Fido")

    def test_individual_rename(self):
        """Rename an individual."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="Fido")
        ind.rename("Max")
        assert ind.title == "Max"
        assert ind.last_modified is not None

    def test_individual_rename_empty_raises(self):
        """Rename with empty string raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="Fido")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            ind.rename("")

    def test_individual_rename_whitespace_only_raises(self):
        """Rename with whitespace-only string raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="Fido")
        with pytest.raises(ValueError, match="Title cannot be empty"):
            ind.rename("   ")

    def test_add_parent_class(self):
        """Add a parent class to an individual."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="PostgreSQL")
        ind.add_parent_class("class-2")
        assert ind.class_ids == ["class-1", "class-2"]
        assert ind.last_modified is not None

    def test_add_parent_class_duplicate_raises(self):
        """Adding a parent class that is already assigned raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="PostgreSQL")
        with pytest.raises(ValueError, match="Class class-1 is already a parent"):
            ind.add_parent_class("class-1")

    def test_remove_parent_class(self):
        """Remove a parent class from an individual."""
        ind = Individual(id="ind-1", class_ids=["class-1", "class-2"], title="PostgreSQL")
        ind.remove_parent_class("class-2")
        assert ind.class_ids == ["class-1"]
        assert ind.last_modified is not None

    def test_remove_parent_class_not_found_raises(self):
        """Removing a non-existent parent class raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="PostgreSQL")
        with pytest.raises(ValueError, match="Class class-3 is not a parent"):
            ind.remove_parent_class("class-3")

    def test_remove_last_parent_class_raises(self):
        """Removing the last parent class raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="PostgreSQL")
        with pytest.raises(ValueError, match="Cannot remove the last parent class"):
            ind.remove_parent_class("class-1")

    def test_reorder_parent_classes(self):
        """Reorder parent classes."""
        ind = Individual(
            id="ind-1", class_ids=["class-1", "class-2", "class-3"], title="PostgreSQL"
        )
        ind.reorder_parent_classes(["class-3", "class-1", "class-2"])
        assert ind.class_ids == ["class-3", "class-1", "class-2"]
        assert ind.last_modified is not None

    def test_reorder_parent_classes_empty_raises(self):
        """Reordering with empty list raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1"], title="PostgreSQL")
        with pytest.raises(ValueError, match="Individual must have at least one parent class"):
            ind.reorder_parent_classes([])

    def test_reorder_parent_classes_duplicates_raises(self):
        """Reordering with duplicate classes raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1", "class-2"], title="PostgreSQL")
        with pytest.raises(ValueError, match="contains duplicates"):
            ind.reorder_parent_classes(["class-1", "class-1"])

    def test_reorder_parent_classes_mismatch_raises(self):
        """Reordering with different classes raises ValueError."""
        ind = Individual(id="ind-1", class_ids=["class-1", "class-2"], title="PostgreSQL")
        with pytest.raises(ValueError, match="must contain exactly the same classes"):
            ind.reorder_parent_classes(["class-1", "class-3"])


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
        with pytest.raises(
            ValueError, match="A relationship cannot have the same source and target"
        ):
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
            source_id="source-uuid",
            target_id="target-uuid",
            mapping_type="exact_match",
        )
        assert mapping.source_id == "source-uuid"
        assert mapping.target_id == "target-uuid"
        assert mapping.mapping_type == "exact_match"

    def test_ontology_mapping_with_related_match(self):
        """Create ontology mapping with related_match type."""
        mapping = OntologyMapping(
            source_id="source-uuid",
            target_id="target-uuid",
            mapping_type="related_match",
        )
        assert mapping.mapping_type == "related_match"

    def test_ontology_mapping_is_frozen(self):
        """OntologyMapping is frozen and immutable."""
        mapping = OntologyMapping(
            source_id="source-uuid",
            target_id="target-uuid",
            mapping_type="exact_match",
        )
        with pytest.raises(Exception):
            mapping.target_id = "other-uuid"

    def test_ontology_mapping_in_property_definition(self):
        """PropertyDefinition can contain an OntologyMapping."""
        mapping = OntologyMapping(
            source_id="prop-1",
            target_id="schema-org-prop",
            mapping_type="exact_match",
        )
        prop = PropertyDefinition(
            id="prop-1",
            identifier="skos:exactMatch",
            title="Exact Match",
            ontology_mapping=mapping,
        )
        assert prop.ontology_mapping == mapping
        assert prop.ontology_mapping.mapping_type == "exact_match"


class TestSearchCriteria:
    """Tests for SearchCriteria value object."""

    def test_search_criteria_defaults(self):
        """SearchCriteria with default values."""
        criteria = SearchCriteria()
        assert criteria.query is None
        assert criteria.node_types is None
        assert criteria.taxonomy_id is None
        assert criteria.concept_scheme_id is None
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
        criteria = SearchCriteria(concept_scheme_id="scheme-1")
        assert criteria.concept_scheme_id == "scheme-1"

    def test_search_criteria_with_parent_filter(self):
        """SearchCriteria with parent entity filter."""
        criteria = SearchCriteria(parent_id="class-1")
        assert criteria.parent_id == "class-1"
