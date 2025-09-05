"""
Dependency injection for Nodes API

This module provides dependency injection functions for the nodes endpoints,
ensuring proper service initialization and database session management.
"""

from fastapi import Depends
from sqlalchemy.orm import Session
from database.utils import get_db
from services.node_service import NodeService
from services.node_link_service import NodeLinkService


def get_node_service(db: Session = Depends(get_db)) -> NodeService:
    """
    Dependency injection for NodeService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        Initialized NodeService instance
    """
    return NodeService(db)


def get_node_link_service(db: Session = Depends(get_db)) -> NodeLinkService:
    """
    Dependency injection for NodeLinkService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        Initialized NodeLinkService instance
    """
    return NodeLinkService(db)
