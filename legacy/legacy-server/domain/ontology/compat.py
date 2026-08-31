"""
Compatibility bridge between legacy and new ontology terminology.

This module provides mappings between the old naming conventions (layer, domain, term)
and the new domain-driven terminology (taxonomy, concept_scheme, class).

Purpose
=======

The re-architecture maintains two separate NodeType enums during migration:

1. database.enums.NodeType (legacy)
   - Values: LAYER, DOMAIN, TERM
   - Used by: ORM models and existing service code
   - Status: Deprecated

2. domain.ontology.value_objects.NodeType (new, authoritative)
   - Values: TAXONOMY, CONCEPT_SCHEME, CLASS, INDIVIDUAL
   - Used by: Domain entities and domain code
   - Status: Authoritative

This bridge provides:
- Bidirectional mappings: NODE_TYPE_LEGACY_TO_NEW, NODE_TYPE_NEW_TO_LEGACY
- Re-exports of new domain types for convenience
- The only file in domain/ that imports from database/ (explicitly whitelisted in
  local-server/scripts/check_domain_imports.py)

TEMPORARY: This file will be removed once all consumers have been migrated to
use domain types directly. See issue #270 for tracking.
"""


# Import legacy NodeType enum from database layer.
# NOTE: This is a pure Python enum, not an ORM model dependency, making it an acceptable
# bridge import during the re-architecture phase. Issue #270 (Duplicate NodeType Enums)
# tracks the consolidation of duplicate NodeType definitions, which will eliminate this import.
from database.enums import NodeType as LegacyNodeType

from domain.ontology.entities import (
    Class,
    ConceptScheme,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import NodeType

# Bidirectional mappings between legacy and new NodeType enum instances
NODE_TYPE_LEGACY_TO_NEW: dict[LegacyNodeType, NodeType] = {
    LegacyNodeType.LAYER: NodeType.TAXONOMY,
    LegacyNodeType.DOMAIN: NodeType.CONCEPT_SCHEME,
    LegacyNodeType.TERM: NodeType.CLASS,
}

NODE_TYPE_NEW_TO_LEGACY: dict[NodeType, LegacyNodeType] = {
    v: k for k, v in NODE_TYPE_LEGACY_TO_NEW.items()
}

# Export new domain entity types and type mappings
__all__ = [
    "NODE_TYPE_LEGACY_TO_NEW",
    "NODE_TYPE_NEW_TO_LEGACY",
    "Class",
    "ConceptScheme",
    "LegacyNodeType",
    "NodeType",
    "PropertyDefinition",
    "Relationship",
    "Taxonomy",
]
