"""
Reference database module for managing external knowledge sources.

This module provides tools for managing reference data from external sources
like Schema.org and WikiData, including:
- Data models (ReferenceNode, ReferenceLink)
- Configuration management (ReferenceConfig)
- Database operations (ReferenceManager)
"""

from reference_db.config import REFERENCE_SCHEMA_VERSION, ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.models import ExternalPredicate, ReferenceLink, ReferenceNode

__all__ = [
    "REFERENCE_SCHEMA_VERSION",
    "ExternalPredicate",
    "ReferenceConfig",
    "ReferenceLink",
    "ReferenceManager",
    "ReferenceNode",
]
