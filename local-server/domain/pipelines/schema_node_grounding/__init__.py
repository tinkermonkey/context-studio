"""
Schema Node Grounding pipeline module.

Grounds schema nodes (Classes, PropertyDefinitions) to external knowledge
sources (DBpedia, ConceptNet) and produces candidate external references
with match confidence scores.
"""

from domain.pipelines.schema_node_grounding.bootstrap import (
    register_schema_node_grounding,
)

__all__ = ["register_schema_node_grounding"]
