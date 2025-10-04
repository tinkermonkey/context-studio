"""
Reference database module for multi-source reference data.

This module provides a unified database for storing reference nodes and links
from multiple sources (DBpedia, ConceptNet, Wikidata, Schema.org).
"""

from .models import ReferenceNode, ReferenceLink, Base
from .config import ReferenceConfig
from .manager import ReferenceManager

__all__ = ["ReferenceNode", "ReferenceLink", "Base", "ReferenceConfig", "ReferenceManager"]
