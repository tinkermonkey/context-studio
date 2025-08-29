"""
Schema.org integration package.

Exports manager, service, and api router for easy inclusion in the main app.
"""

from .manager import SchemaOrgManager
from .service import SchemaOrgService
from .api import router

__all__ = [
    "SchemaOrgManager",
    "SchemaOrgService",
    "router",
]
