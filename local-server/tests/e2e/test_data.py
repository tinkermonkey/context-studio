"""
Stable test data for E2E baseline tests.

This module defines stable test concepts that are used across E2E tests
to ensure consistent behavior and comparison baselines.
"""

# Stable concepts used in E2E tests
STABLE_CONCEPTS = {
    "taxonomy_1": {
        "title": "E2E Test Taxonomy",
        "definition": "A taxonomy for testing end-to-end workflows",
        "type": "TAXONOMY",  # Node type mapping: TAXONOMY
    },
    "scheme_1": {
        "title": "E2E Concept Scheme",
        "definition": "A concept scheme within the test taxonomy",
        "type": "CONCEPT_SCHEME",  # Node type mapping: CONCEPT_SCHEME
    },
    "class_1": {
        "title": "E2E Test Class One",
        "definition": "First test class for taxonomy lifecycle testing",
        "type": "CLASS",  # Node type mapping: CLASS
    },
    "class_2": {
        "title": "E2E Test Class Two",
        "definition": "Second test class for hierarchy relationships",
        "type": "CLASS",
    },
    "class_3": {
        "title": "E2E Test Class Three",
        "definition": "Third test class for semantic search comparison",
        "type": "CLASS",
    },
    "property_1": {
        "title": "TestProperty",
        "definition": "A test property for testing property definitions",
        "datatype": "string",
        "cardinality": "single",
    },
    "predicate_1": {
        "title": "test_has_property",
        "definition": "A test predicate for linking classes to properties",
    },
}

# Test data for change event tracking
CHANGE_EVENT_CONCEPTS = {
    "change_test_taxonomy": {
        "title": "Change Event Test Taxonomy",
        "definition": "Taxonomy for change event tracking validation",
        "type": "TAXONOMY",
    },
    "change_test_scheme": {
        "title": "Change Event Test Scheme",
        "definition": "Concept scheme for change event tracking",
        "type": "CONCEPT_SCHEME",
    },
    "change_test_class_1": {
        "title": "Change Event Test Class 1",
        "definition": "Class for testing change events",
        "type": "CLASS",
    },
    "change_test_class_2": {
        "title": "Change Event Test Class 2",
        "definition": "Another class for relationship change events",
        "type": "CLASS",
    },
}

# Test data for embedding generation
EMBEDDING_TEST_CONCEPTS = {
    "embedding_base_class": {
        "title": "Base Embedding Test Class",
        "definition": "Original class for embedding generation testing",
        "type": "CLASS",
    },
    "embedding_similar_class": {
        "title": "Similar Embedding Test Class",
        "definition": "Semantically similar class for testing semantic search ranking",
        "type": "CLASS",
    },
    "embedding_different_class": {
        "title": "Different Embedding Test Class",
        "definition": "Semantically different class for testing ranking accuracy",
        "type": "CLASS",
    },
}
