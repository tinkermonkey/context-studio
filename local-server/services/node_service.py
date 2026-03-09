"""
DEPRECATED: This module is a backward-compatibility stub.

Use services.ontology_entity_service.OntologyEntityService instead.
This stub re-exports OntologyEntityService as NodeService for compatibility.
"""

from .ontology_entity_service import OntologyEntityService

NodeService = OntologyEntityService

__all__ = ["NodeService"]
