"""
Database enums for Context Studio

This module contains enum definitions used across the database models
and custom types to avoid circular import issues.

IMPORTANT: NodeType Deprecation Notice
=======================================

This module defines a LEGACY NodeType enum with values (LAYER, DOMAIN, TERM).
A new, incompatible NodeType enum exists in domain/ontology/value_objects.py
with values (TAXONOMY, CONCEPT_SCHEME, CLASS, INDIVIDUAL).

Migration Path:
- LAYER → TAXONOMY
- DOMAIN → CONCEPT_SCHEME
- TERM → CLASS

The domain/ontology/value_objects.NodeType is the authoritative definition
for new code. The database.enums.NodeType is maintained for backwards
compatibility with the existing ORM models and database schema only.

Existing service code imports from database.enums.NodeType per current
architecture, but during the re-architecture (Phase 2+), services will be
refactored to use domain types. The compatibility bridge in
domain/ontology/compat.py provides mapping utilities for gradual migration.

Issue #270 tracks consolidation of these duplicate enums.
"""

from enum import Enum


class NodeType(str, Enum):
    """
    Enumeration for structure_node types in the unified structure_nodes table.

    DEPRECATED: This enum represents the legacy naming convention. Use
    domain/ontology/value_objects.NodeType for new domain code. See module
    docstring for migration path.
    """
    LAYER = "layer"
    DOMAIN = "domain"
    TERM = "term"


class RecordType(str, Enum):
    """Enumeration for record types in the unified change_events table."""
    STRUCTURE_NODE = "structure_node"  # For layers, domains, terms
    STRUCTURE_NODE_LINK = "structure_node_link"  # For relationships between structure nodes  # noqa: E501
    PREDICATE = "predicate"  # For predicate definitions
