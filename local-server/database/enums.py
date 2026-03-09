"""
Database enums for Context Studio

This module contains enum definitions used across the database models
and custom types to avoid circular import issues.
"""

from enum import Enum


class NodeType(str, Enum):
    """
    Enumeration for structure_node types in the unified structure_nodes table.

    DEPRECATED: This enum represents the legacy naming convention (LAYER, DOMAIN, TERM).
    A new NodeType enum exists in domain/ontology/value_objects.py with domain-driven
    terminology (TAXONOMY, CONCEPT_SCHEME, CLASS, INDIVIDUAL).
    See domain/ontology/compat.py for the migration path and mapping utilities.
    Issue #270 tracks the consolidation of these duplicate enums.
    """

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

    Legacy naming (deprecated, will be removed in Phase 5):
    - STRUCTURE_NODE: Legacy name for ONTOLOGY_ENTITY
    - STRUCTURE_NODE_LINK: Legacy name for RELATIONSHIP
    - PREDICATE: Legacy name for PROPERTY_DEFINITION
    """

    # New values (primary)
    ONTOLOGY_ENTITY = "ontology_entity"
    RELATIONSHIP = "relationship"
    PROPERTY_DEFINITION = "property_definition"
    # Legacy aliases — deprecated, will be removed in Phase 5
    STRUCTURE_NODE = "structure_node"  # For layers, domains, terms
    STRUCTURE_NODE_LINK = (
        "structure_node_link"  # For relationships between structure nodes  # noqa: E501
    )
    PREDICATE = "predicate"  # For predicate definitions
