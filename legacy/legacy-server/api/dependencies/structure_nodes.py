"""
Dependency injection for StructureNodes API

This module provides dependency injection functions for the structure_nodes endpoints,  # noqa: E501
using the optimized service factory pattern for better performance.
"""

from database.utils import get_db
from fastapi import Depends
from services.node_link_service import NodeLinkService
from services.node_service import NodeService
from services.reference_link_service import ReferenceLinkService
from services.service_factory import get_service_factory
from services.word_sense_service import WordSenseService
from sqlalchemy.orm import Session


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
    Lightweight dependency injection for NodeService without expensive dependencies.  # noqa: E501

    This is optimized for read-only operations that don't need version management  # noqa: E501
    or graph services. Use this for list, get, and count operations.

    Args:
        db: Database session from dependency injection

    Returns:
        NodeService instance with minimal dependencies
    """
    # Create NodeService directly without expensive dependencies
    return NodeService(
        db, graph_service=None, version_manager=None, working_tree_manager=None
    )


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


def get_reference_link_service(
    db: Session = Depends(get_db),
) -> ReferenceLinkService:
    """
    Dependency injection for ReferenceLinkService.

    Args:
        db: Database session from dependency injection

    Returns:
        Initialized ReferenceLinkService instance
    """
    return ReferenceLinkService(db)


def get_word_sense_service(db: Session = Depends(get_db)) -> WordSenseService:
    """
    Dependency injection for WordSenseService.

    Args:
        db: Database session from dependency injection

    Returns:
        Initialized WordSenseService instance
    """
    return WordSenseService(db)
