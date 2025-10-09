"""
Reference database module for managing external knowledge sources.

This module provides tools for managing reference data from external sources
like Schema.org and WikiData, including:
- Data models (ReferenceNode, ReferenceLink)
- Configuration management (ReferenceConfig)
- Database operations (ReferenceManager)
"""

from reference_db.models import ReferenceNode, ReferenceLink, ExternalPredicate
from reference_db.config import ReferenceConfig, REFERENCE_SCHEMA_VERSION
from reference_db.manager import ReferenceManager

__all__ = [
    'ReferenceNode',
    'ReferenceLink',
    'ExternalPredicate',
    'ReferenceConfig',
    'ReferenceManager',
    'REFERENCE_SCHEMA_VERSION',
]
