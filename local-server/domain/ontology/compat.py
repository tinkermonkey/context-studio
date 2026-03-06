"""
Compatibility bridge between legacy and new ontology terminology.

This module provides mappings between the old naming conventions (layer, domain, term)
and the new domain-driven terminology (taxonomy, concept_scheme, class).

TEMPORARY: This file will be removed when all adapters have been migrated to use
domain types directly. See issue #269 (Empty Adapter Layer) for tracking this migration.
"""

from typing import Dict

# Import legacy NodeType enum from database layer.
# NOTE: This is a pure Python enum, not an ORM model dependency, making it an acceptable
# bridge import during the re-architecture phase. Issue #270 (Duplicate NodeType Enums)
# tracks the consolidation of duplicate NodeType definitions, which will eliminate this import.
from database.enums import NodeType as LegacyNodeType
from domain.ontology.value_objects import NodeType
from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Relationship,
    PropertyDefinition,
)

# Bidirectional mappings between legacy and new NodeType enum instances
NODE_TYPE_LEGACY_TO_NEW: Dict[LegacyNodeType, NodeType] = {
    LegacyNodeType.LAYER: NodeType.TAXONOMY,
    LegacyNodeType.DOMAIN: NodeType.CONCEPT_SCHEME,
    LegacyNodeType.TERM: NodeType.CLASS,
}

NODE_TYPE_NEW_TO_LEGACY: Dict[NodeType, LegacyNodeType] = {v: k for k, v in NODE_TYPE_LEGACY_TO_NEW.items()}

# Export new domain entity types and type mappings
__all__ = [
    "LegacyNodeType",
    "NodeType",
    "Taxonomy",
    "ConceptScheme",
    "Class",
    "Relationship",
    "PropertyDefinition",
    "NODE_TYPE_LEGACY_TO_NEW",
    "NODE_TYPE_NEW_TO_LEGACY",
]
