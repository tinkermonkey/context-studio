"""
Unit Tests for domain ontology value objects

Tests the immutable value objects including NodeType, ExternalReference, LexicalSense,  # noqa: E501
DataPropertyValue, OntologyMapping, and SearchCriteria.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import types  # noqa: E402
from domain.ontology.value_objects import (  # noqa: E402
    NodeType,
    ExternalReference,
    LexicalSense,
    DataPropertyValue,
    OntologyMapping,
    SearchCriteria,
)


class TestNodeTypeFromLegacy:
    """Test suite for NodeType.from_legacy() backward compatibility method."""

    def test_from_legacy_layer_maps_to_taxonomy(self):
        """Test that legacy 'layer' maps to TAXONOMY."""
        result = NodeType.from_legacy("layer")
        assert result == NodeType.TAXONOMY
        assert result.value == "taxonomy"

    def test_from_legacy_domain_maps_to_concept_scheme(self):
        """Test that legacy 'domain' maps to CONCEPT_SCHEME."""
        result = NodeType.from_legacy("domain")
        assert result == NodeType.CONCEPT_SCHEME
        assert result.value == "concept_scheme"

    def test_from_legacy_term_maps_to_class(self):
        """Test that legacy 'term' maps to CLASS."""
        result = NodeType.from_legacy("term")
        assert result == NodeType.CLASS
        assert result.value == "class"

    def test_from_legacy_new_terminology_taxonomy(self):
        """Test that new 'taxonomy' maps to TAXONOMY."""
        result = NodeType.from_legacy("taxonomy")
        assert result == NodeType.TAXONOMY

    def test_from_legacy_new_terminology_concept_scheme(self):
        """Test that new 'concept_scheme' maps to CONCEPT_SCHEME."""
        result = NodeType.from_legacy("concept_scheme")
        assert result == NodeType.CONCEPT_SCHEME

    def test_from_legacy_new_terminology_class(self):
        """Test that new 'class' maps to CLASS."""
        result = NodeType.from_legacy("class")
        assert result == NodeType.CLASS

    def test_from_legacy_new_terminology_individual(self):
        """Test that new 'individual' maps to INDIVIDUAL."""
        result = NodeType.from_legacy("individual")
        assert result == NodeType.INDIVIDUAL

    def test_from_legacy_invalid_value_raises_error(self):
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError, match="Unknown node type"):
            NodeType.from_legacy("invalid_type")

    def test_from_legacy_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown node type"):
            NodeType.from_legacy("")

    def test_from_legacy_case_sensitive(self):
        """Test that from_legacy is case-sensitive."""
        # Valid lowercase
        result = NodeType.from_legacy("layer")
        assert result == NodeType.TAXONOMY

        # Invalid uppercase (should fail)
        with pytest.raises(ValueError):
            NodeType.from_legacy("LAYER")

    def test_from_legacy_uppercase_fails(self):
        """Test that uppercase legacy values are not accepted."""
        with pytest.raises(ValueError, match="Unknown node type"):
            NodeType.from_legacy("LAYER")

        with pytest.raises(ValueError):
            NodeType.from_legacy("DOMAIN")

        with pytest.raises(ValueError):
            NodeType.from_legacy("TERM")

    def test_from_legacy_mixed_case_fails(self):
        """Test that mixed case values are not accepted."""
        with pytest.raises(ValueError):
            NodeType.from_legacy("Layer")

        with pytest.raises(ValueError):
            NodeType.from_legacy("Domain")

    def test_from_legacy_whitespace_not_stripped(self):
        """Test that from_legacy does not automatically strip whitespace."""
        # These should fail because the mapping expects exact matches
        with pytest.raises(ValueError):
            NodeType.from_legacy(" layer")

        with pytest.raises(ValueError):
            NodeType.from_legacy("layer ")

        with pytest.raises(ValueError):
            NodeType.from_legacy(" layer ")

    def test_from_legacy_typos_fail(self):
        """Test that typos in legacy values are not accepted."""
        with pytest.raises(ValueError):
            NodeType.from_legacy("laer")  # typo

        with pytest.raises(ValueError):
            NodeType.from_legacy("domian")  # typo

        with pytest.raises(ValueError):
            NodeType.from_legacy("tern")  # typo

    def test_from_legacy_all_legacy_values_have_mapping(self):
        """Test that all legacy terminologies map correctly."""
        legacy_to_modern = {
            "layer": "taxonomy",
            "domain": "concept_scheme",
            "term": "class",
        }

        for legacy, modern in legacy_to_modern.items():
            result = NodeType.from_legacy(legacy)
            assert result.value == modern

    def test_from_legacy_idempotent_for_modern_values(self):
        """Test that modern values can be processed by from_legacy and return unchanged."""  # noqa: E501
        modern_values = ["taxonomy", "concept_scheme", "class", "individual"]

        for modern_value in modern_values:
            result = NodeType.from_legacy(modern_value)
            assert result.value == modern_value

    def test_from_legacy_symmetry(self):
        """Test that legacy and modern values produce the same NodeType enum."""  # noqa: E501
        # These pairs should all produce the same enum value
        pairs = [
            ("layer", "taxonomy"),
            ("domain", "concept_scheme"),
            ("term", "class"),
        ]

        for legacy, modern in pairs:
            legacy_result = NodeType.from_legacy(legacy)
            modern_result = NodeType.from_legacy(modern)
            assert legacy_result == modern_result

    def test_from_legacy_error_message_contains_valid_options(self):
        """Test that error message includes list of valid options."""
        try:
            NodeType.from_legacy("invalid")
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            # Check that the error message contains expected options
            assert "layer" in error_msg or "taxonomy" in error_msg

    def test_from_legacy_none_raises_error(self):
        """Test that None raises error."""
        with pytest.raises((ValueError, TypeError)):
            NodeType.from_legacy(None)

    def test_from_legacy_numeric_value_raises_error(self):
        """Test that numeric values raise error."""
        with pytest.raises((ValueError, TypeError)):
            NodeType.from_legacy(1)

    def test_from_legacy_multiple_calls_consistent(self):
        """Test that multiple calls to from_legacy return consistent results."""  # noqa: E501
        result1 = NodeType.from_legacy("layer")
        result2 = NodeType.from_legacy("layer")
        result3 = NodeType.from_legacy("layer")

        assert result1 == result2 == result3

    def test_from_legacy_returns_enum_instance(self):
        """Test that from_legacy returns a NodeType enum instance."""
        result = NodeType.from_legacy("layer")
        assert isinstance(result, NodeType)
        assert hasattr(result, "value")
        assert isinstance(result.value, str)


class TestExternalReferenceValueObject:
    """Test suite for ExternalReference immutable value object."""

    def test_external_reference_creation(self):
        """Test creating an ExternalReference."""
        ref = ExternalReference(
            source="wikidata",
            uri="https://www.wikidata.org/wiki/Q1234",
            label="Example Entity",
            confidence=0.95
        )

        assert ref.source == "wikidata"
        assert ref.uri == "https://www.wikidata.org/wiki/Q1234"
        assert ref.label == "Example Entity"
        assert ref.confidence == 0.95

    def test_external_reference_immutability(self):
        """Test that ExternalReference is immutable."""
        ref = ExternalReference(
            source="dbpedia",
            uri="http://dbpedia.org/resource/Example",
            label="Example",
            confidence=0.9
        )

        # Attempting to modify should raise error
        with pytest.raises((AttributeError, TypeError)):
            ref.source = "wikidata"

    def test_external_reference_metadata_immutable(self):
        """Test that metadata field is immutable."""
        ref = ExternalReference(
            source="dbpedia",
            uri="http://dbpedia.org/resource/Example",
            label="Example",
            confidence=0.9,
            metadata={"key": "value"}
        )

        # Metadata should be a MappingProxyType (read-only)
        assert isinstance(ref.metadata, types.MappingProxyType)

        # Attempting to modify metadata should fail
        with pytest.raises(TypeError):
            ref.metadata["key"] = "new_value"

    def test_external_reference_with_empty_metadata(self):
        """Test ExternalReference with no metadata."""
        ref = ExternalReference(
            source="wikidata",
            uri="https://example.com",
            label="Example",
            confidence=0.8
        )

        assert isinstance(ref.metadata, types.MappingProxyType)
        assert len(ref.metadata) == 0


class TestLexicalSenseValueObject:
    """Test suite for LexicalSense immutable value object."""

    def test_lexical_sense_creation(self):
        """Test creating a LexicalSense."""
        sense = LexicalSense(
            synset_id="synset-001",
            definition="A definition of the sense",
            lemma="example",
            confidence=0.9,
            source="wordnet"
        )

        assert sense.synset_id == "synset-001"
        assert sense.definition == "A definition of the sense"
        assert sense.lemma == "example"
        assert sense.confidence == 0.9
        assert sense.source == "wordnet"

    def test_lexical_sense_immutability(self):
        """Test that LexicalSense is immutable."""
        sense = LexicalSense(
            synset_id="synset-001",
            definition="Definition",
            lemma="word",
            confidence=0.85,
            source="wordnet"
        )

        with pytest.raises((AttributeError, TypeError)):
            sense.lemma = "new_word"


class TestDataPropertyValueValueObject:
    """Test suite for DataPropertyValue immutable value object."""

    def test_data_property_value_creation(self):
        """Test creating a DataPropertyValue."""
        prop = DataPropertyValue(
            key="color",
            value="red",
            datatype="xsd:string"
        )

        assert prop.key == "color"
        assert prop.value == "red"
        assert prop.datatype == "xsd:string"

    def test_data_property_value_immutability(self):
        """Test that DataPropertyValue is immutable."""
        prop = DataPropertyValue(
            key="age",
            value="25",
            datatype="xsd:integer"
        )

        with pytest.raises((AttributeError, TypeError)):
            prop.value = "30"


class TestOntologyMappingValueObject:
    """Test suite for OntologyMapping immutable value object."""

    def test_ontology_mapping_creation(self):
        """Test creating an OntologyMapping."""
        mapping = OntologyMapping(
            ontology="skos",
            uri="http://www.w3.org/2004/02/skos/core#Concept",
            label="Concept",
            exact_match=True
        )

        assert mapping.ontology == "skos"
        assert mapping.uri == "http://www.w3.org/2004/02/skos/core#Concept"
        assert mapping.label == "Concept"
        assert mapping.exact_match is True

    def test_ontology_mapping_immutability(self):
        """Test that OntologyMapping is immutable."""
        mapping = OntologyMapping(
            ontology="rdfs",
            uri="http://example.com/resource",
            label="Resource",
            exact_match=False
        )

        with pytest.raises((AttributeError, TypeError)):
            mapping.exact_match = True


class TestSearchCriteriaValueObject:
    """Test suite for SearchCriteria immutable value object."""

    def test_search_criteria_basic(self):
        """Test creating basic SearchCriteria."""
        criteria = SearchCriteria(query="animal")

        assert criteria.query == "animal"
        assert criteria.node_type is None
        assert criteria.taxonomy_id is None
        assert criteria.use_semantic_search is False
        assert criteria.limit == 20
        assert criteria.offset == 0

    def test_search_criteria_with_filters(self):
        """Test creating SearchCriteria with filters."""
        criteria = SearchCriteria(
            query="animal",
            node_type=NodeType.CLASS,
            taxonomy_id="tax-001",
            scheme_id="scheme-001",
            parent_id="parent-001",
            use_semantic_search=True,
            limit=50,
            offset=10
        )

        assert criteria.query == "animal"
        assert criteria.node_type == NodeType.CLASS
        assert criteria.taxonomy_id == "tax-001"
        assert criteria.scheme_id == "scheme-001"
        assert criteria.parent_id == "parent-001"
        assert criteria.use_semantic_search is True
        assert criteria.limit == 50
        assert criteria.offset == 10

    def test_search_criteria_immutability(self):
        """Test that SearchCriteria is immutable."""
        criteria = SearchCriteria(query="test")

        with pytest.raises((AttributeError, TypeError)):
            criteria.limit = 100


class TestNodeTypeEnumBehavior:
    """Test suite for NodeType enum behavior."""

    def test_node_type_enum_values(self):
        """Test that NodeType enum has correct values."""
        assert NodeType.TAXONOMY.value == "taxonomy"
        assert NodeType.CONCEPT_SCHEME.value == "concept_scheme"
        assert NodeType.CLASS.value == "class"
        assert NodeType.INDIVIDUAL.value == "individual"

    def test_node_type_enum_membership(self):
        """Test NodeType enum membership."""
        assert NodeType.TAXONOMY in NodeType
        assert NodeType.CONCEPT_SCHEME in NodeType
        assert NodeType.CLASS in NodeType
        assert NodeType.INDIVIDUAL in NodeType

    def test_node_type_enum_comparison(self):
        """Test NodeType enum comparison."""
        assert NodeType.TAXONOMY == NodeType.TAXONOMY
        assert NodeType.TAXONOMY != NodeType.CLASS
        assert NodeType.CLASS != NodeType.CONCEPT_SCHEME

    def test_node_type_is_string_enum(self):
        """Test that NodeType values can be used as strings."""
        node_type = NodeType.TAXONOMY
        # Should be usable as string in comparisons
        assert node_type == "taxonomy"
        assert "taxonomy" == node_type

    def test_node_type_string_representation(self):
        """Test string representation of NodeType."""
        assert str(NodeType.TAXONOMY) == "NodeType.TAXONOMY"
        assert str(NodeType.CLASS) == "NodeType.CLASS"

    def test_node_type_value_representation(self):
        """Test value representation of NodeType."""
        assert NodeType.TAXONOMY.value == "taxonomy"
        assert repr(NodeType.TAXONOMY.value) == "'taxonomy'"
