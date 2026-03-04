"""
Compatibility bridge between legacy and new ontology terminology.

This module provides mappings between the old naming conventions (layer, domain, term)
and the new domain-driven terminology (taxonomy, concept_scheme, class).

TEMPORARY: This file will be removed in Phase 5 when all adapters have been
migrated to use domain types directly.

This is the ONLY file in domain/ that is permitted to import from database/.
"""

from database.enums import NodeType as LegacyNodeType

from domain.ontology.value_objects import NodeType as NewNodeType

# Bidirectional mapping between legacy and new NodeType values
NODE_TYPE_LEGACY_TO_NEW: dict = {
    LegacyNodeType.LAYER: NewNodeType.TAXONOMY,
    LegacyNodeType.DOMAIN: NewNodeType.CONCEPT_SCHEME,
    LegacyNodeType.TERM: NewNodeType.CLASS,
}

NODE_TYPE_NEW_TO_LEGACY: dict = {v: k for k, v in NODE_TYPE_LEGACY_TO_NEW.items()}
