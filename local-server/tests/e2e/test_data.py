"""
Stable test data for E2E baseline tests.

This module defines stable test concepts and predicates for baseline tests
to ensure consistent behavior and regression testing.

All data is designed with the SentenceTransformer embedding model in mind
and produces stable, reproducible results across test runs.
"""

from typing import Any, Dict

# Stable taxonomy used in baseline tests
# These concepts produce predictable semantic embeddings
STABLE_TAXONOMY: Dict[str, Any] = {
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

