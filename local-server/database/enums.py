"""
Database enums for Context Studio

This module contains enum definitions used across the database models
and custom types to avoid circular import issues.
"""

from enum import Enum


class NodeType(str, Enum):
    """Enumeration for node types in the unified nodes table."""
    LAYER = "layer"
    DOMAIN = "domain" 
    TERM = "term"
