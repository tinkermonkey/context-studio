"""
Dependency injection for StructureNodes API

This module provides dependency injection functions for the structure_nodes endpoints,
using the optimized service factory pattern for better performance.
"""

from fastapi import Depends
from sqlalchemy.orm import Session
from database.utils import get_db
from services.service_factory import get_service_factory
from services.node_service import NodeService
from services.node_link_service import NodeLinkService


def get_node_service(db: Session = Depends(get_db)) -> NodeService:
    """
    Optimized dependency injection for NodeService using service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        Initialized NodeService instance
    """
    factory = get_service_factory()
    return factory.create_node_service(db)


def get_node_service_simple(db: Session = Depends(get_db)) -> NodeService:
    """
    Lightweight dependency injection for NodeService without expensive dependencies.

    This is optimized for read-only operations that don't need version management
    or graph services. Use this for list, get, and count operations.

    Args:
        db: Database session from dependency injection

    Returns:
        NodeService instance with minimal dependencies
    """
    # Create NodeService directly without expensive dependencies
    return NodeService(db, graph_service=None, version_manager=None, working_tree_manager=None)


def get_node_link_service(db: Session = Depends(get_db)) -> NodeLinkService:
    """
    Optimized dependency injection for NodeLinkService using service factory.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        Initialized NodeLinkService instance
    """
    factory = get_service_factory()
    return factory.create_node_link_service(db)
