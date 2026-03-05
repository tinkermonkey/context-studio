"""
Compatibility bridge between legacy and new ontology terminology.

This module provides mappings between the old naming conventions (layer, domain, term)
and the new domain-driven terminology (taxonomy, concept_scheme, class).

TEMPORARY: This file will be removed in Phase 5 when all adapters have been
migrated to use domain types directly.
"""

from database.models import (
    StructureNode as LegacyStructureNode,
    StructureNodeLink as LegacyStructureNodeLink,
    Predicate as LegacyPredicate,
    ChangeEvent as LegacyChangeEvent,
    PipelineFlavor as LegacyPipelineFlavor,
)
from database.enums import NodeType as DatabaseNodeType

from domain.ontology.value_objects import NodeType

# Bidirectional string mappings between legacy and new NodeType values
# Using string values to maintain architecture boundaries
NODE_TYPE_LEGACY_TO_NEW: dict = {
    "layer": NodeType.TAXONOMY.value,
    "domain": NodeType.CONCEPT_SCHEME.value,
    "term": NodeType.CLASS.value,
}

NODE_TYPE_NEW_TO_LEGACY: dict = {v: k for k, v in NODE_TYPE_LEGACY_TO_NEW.items()}

# Export new domain entity types alongside legacy model aliases
__all__ = [
    "LegacyStructureNode",
    "LegacyStructureNodeLink",
    "LegacyPredicate",
    "LegacyChangeEvent",
    "LegacyPipelineFlavor",
    "NodeType",
    "NODE_TYPE_LEGACY_TO_NEW",
    "NODE_TYPE_NEW_TO_LEGACY",
]
