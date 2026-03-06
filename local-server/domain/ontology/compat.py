"""
Compatibility bridge between legacy and new ontology terminology.

This module provides mappings between the old naming conventions (layer, domain, term)
and the new domain-driven terminology (taxonomy, concept_scheme, class).

Purpose
=======

This module exists to support the gradual migration from legacy database-centric
types (database.enums.NodeType) to domain-driven types
(domain.ontology.value_objects.NodeType). The re-architecture creates two
separate NodeType enums intentionally:

- database.enums.NodeType with values LAYER, DOMAIN, TERM
  - Represents the legacy naming from the database schema
  - Used by ORM models and existing service code
  - Status: Deprecated

- domain.ontology.value_objects.NodeType with values TAXONOMY, CONCEPT_SCHEME, CLASS, INDIVIDUAL
  - Represents the domain's semantic understanding
  - Used by domain entities and new domain code
  - Status: Authoritative

This bridge provides:
1. Bidirectional mapping dicts (NODE_TYPE_LEGACY_TO_NEW, NODE_TYPE_NEW_TO_LEGACY)
2. Re-exports of new domain types for convenience
3. Clear documentation of the migration path

The only file in the domain/ layer that imports from database/ is
domain/ontology/compat.py - this is intentional and whitelisted by the
import boundary linter (see scripts/check_domain_imports.py).

TEMPORARY: This file will be removed during Phase 5 (Completion) once all
adapters have been migrated to use domain types directly.

Migration Timeline
==================

- Phase 0 (Foundation): ✓ Create parallel type definitions with mappings
- Phase 1 (SQLite Adapter): Use mappings to convert between legacy/domain types
- Phase 2 (Service Migration): Adapt service layer to return domain types
- Phase 3-4 (Extraction, Sync): Use domain types throughout
- Phase 5 (Completion): Remove compat.py and legacy database.enums.NodeType

See issue #270 (Duplicate NodeType Enums) for tracking.
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
