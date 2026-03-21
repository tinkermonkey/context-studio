"""
Database enums for Context Studio

This module contains enum definitions used across the database models
and custom types to avoid circular import issues.
"""

from enum import Enum


class NodeType(str, Enum):
    """
    Enumeration for ontology entity types in the database.

    This enum supports both new standard ontology terminology (primary) and legacy naming
    (deprecated) for backward compatibility during migration.

    New terminology (primary):
    - TAXONOMY: Top-level categorization system
    - CONCEPT_SCHEME: Collection of related concepts
    - CLASS: Concept or class definition

    Legacy terminology (deprecated, accepted for backward compatibility):
    - LAYER: Legacy name for TAXONOMY
    - DOMAIN: Legacy name for CONCEPT_SCHEME
    - TERM: Legacy name for CLASS
    """

    # New terminology (primary)
    TAXONOMY = "taxonomy"
    CONCEPT_SCHEME = "concept_scheme"
    CLASS = "class"
    # Legacy terminology (deprecated, for backward compatibility)
    LAYER = "layer"
    DOMAIN = "domain"
    TERM = "term"


class RecordType(str, Enum):
    """
    Enumeration for record types in the unified change_events table.

    New naming (primary):
    - ONTOLOGY_ENTITY: Represents ontology entities (taxonomies, concept schemes, classes)
    - RELATIONSHIP: Represents relationships between ontology entities
    - PROPERTY_DEFINITION: Represents property/predicate definitions

    Legacy naming (deprecated, for backward compatibility):
    - STRUCTURE_NODE: Legacy name for ONTOLOGY_ENTITY
    - STRUCTURE_NODE_LINK: Legacy name for RELATIONSHIP
    - PREDICATE: Legacy name for PROPERTY_DEFINITION
    """

    # New values (primary)
    ONTOLOGY_ENTITY = "ontology_entity"
    RELATIONSHIP = "relationship"
    PROPERTY_DEFINITION = "property_definition"
    # Legacy aliases — deprecated, for backward compatibility
    STRUCTURE_NODE = "structure_node"  # For layers, domains, terms
    STRUCTURE_NODE_LINK = (
        "structure_node_link"  # For relationships between structure nodes  # noqa: E501
    )
    PREDICATE = "predicate"  # For predicate definitions
