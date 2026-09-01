"""
Dependency injection for Graph services

This module provides optimized dependency injection for all graph-related services  # noqa: E501
using the service factory pattern for better performance.
"""

from database.utils import get_db
from fastapi import Depends
from graph.graph_service import GraphService
from graph.network_service import NetworkService
from graph.sparql_service import SPARQLService
from services.service_factory import get_service_factory
from sqlalchemy.orm import Session


def get_graph_service(db: Session = Depends(get_db)) -> GraphService:
    """
    Get shared, cached GraphService instance for fast graph operations.

    This uses a singleton pattern to share the same pre-loaded graph
    across all requests, avoiding expensive rebuilding.

    Args:
        db: Database session from dependency injection (for compatibility)

    Returns:
        Shared GraphService instance with pre-loaded graph data
    """
    # Import here to avoid circular imports
    from api.graph import get_cached_graph_service
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.debug("get_graph_service called - using cached service")

    service = get_cached_graph_service()
    logger.debug(f"get_graph_service returning cached service: {id(service)}")
    return service


def get_network_service(db: Session = Depends(get_db)) -> NetworkService:
    """
    Optimized dependency injection for NetworkService using service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        NetworkService instance configured with the request's database session
    """
    factory = get_service_factory()
    return factory.create_network_service(db)


def get_sparql_service(db: Session = Depends(get_db)) -> SPARQLService:
    """
    Optimized dependency injection for SPARQLService using service factory.

    Args:
        db: Database session from dependency injection

    Returns:
        SPARQLService instance configured with the request's database session
    """
    factory = get_service_factory()
    return factory.create_sparql_service(db)


def get_all_graph_services(
    db: Session = Depends(get_db),
) -> tuple[GraphService, NetworkService, SPARQLService]:
    """
    Get all graph services in one dependency call for efficiency.

    Args:
        db: Database session from dependency injection

    Returns:
        Tuple of (GraphService, NetworkService, SPARQLService) instances
    """
    factory = get_service_factory()
    return (
        factory.create_graph_service(db),
        factory.create_network_service(db),
        factory.create_sparql_service(db),
    )
