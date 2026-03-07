"""
Stable test data for E2E baseline tests.

This module defines stable test concepts and predicates that are used across
all E2E baseline tests to ensure consistent behavior and regression testing.

All data is designed with the SentenceTransformer embedding model in mind
and produces stable, reproducible results across test runs.
"""

# Stable taxonomy used consistently across all four baseline tests
# These concepts produce predictable semantic embeddings
STABLE_TAXONOMY = {
    "layer": {
        "title": "Computer Science",
        "definition": "The study of computation and information",
    },
    "scheme": {
        "title": "Data Management",
        "definition": "Technologies and methods for storing and retrieving data",
    },
    "classes": [
        {
            "title": "Database",
            "definition": "An organized collection of structured information",
        },
        {
            "title": "Relational Database",
            "definition": "A database based on the relational model of data",
        },
        {
            "title": "SQL",
            "definition": "Structured Query Language for managing relational databases",
        },
        {
            "title": "Index",
            "definition": "A data structure that improves the speed of data retrieval",
        },
    ],
}

# Stable predicates for relationship definition
STABLE_PREDICATES = [
    {
        "title": "Is A",
        "identifier": "is_a",
        "definition": "Subtype relationship",
    },
    {
        "title": "Used By",
        "identifier": "used_by",
        "definition": "Indicates usage by another concept",
    },
    {
        "title": "Part Of",
        "identifier": "part_of",
        "definition": "Indicates a part-whole relationship",
    },
]

# Stable relationships between concepts
# Format: (source_title, target_title, predicate_identifier)
STABLE_RELATIONSHIPS = [
    ("Relational Database", "Database", "is_a"),
    ("SQL", "Relational Database", "used_by"),
    ("Index", "Database", "part_of"),
]

# Test data for embedding generation (semantically varied classes)
EMBEDDING_TEST_CONCEPTS = {
    "embedding_base_class": {
        "title": "Data Storage",
        "definition": "Systems for persisting and retrieving data",
    },
    "embedding_similar_class": {
        "title": "Database System",
        "definition": "An organized collection for data management",
    },
    "embedding_different_class": {
        "title": "Firewall",
        "definition": "A network security system that monitors traffic",
    },
}

# Backward compatibility: STABLE_CONCEPTS for existing tests
# Maps the old-style concept keys to the current STABLE_TAXONOMY structure
STABLE_CONCEPTS = {
    "taxonomy_1": STABLE_TAXONOMY["layer"],
    "scheme_1": STABLE_TAXONOMY["scheme"],
    "class_1": STABLE_TAXONOMY["classes"][0],
    "class_2": STABLE_TAXONOMY["classes"][1],
    "class_3": STABLE_TAXONOMY["classes"][2],
}
