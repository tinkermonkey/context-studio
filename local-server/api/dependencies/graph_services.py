"""
Dependency injection for Graph services

This module provides optimized dependency injection for all graph-related services
using the service factory pattern for better performance.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from database.utils import get_db
from services.service_factory import get_service_factory
from graph.graph_service import GraphService
from graph.network_service import NetworkService
from graph.sparql_service import SPARQLService


def get_graph_service(db: Session = Depends(get_db)) -> GraphService:
    """
    Optimized dependency injection for GraphService using service factory.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        GraphService instance configured with the request's database session
    """
    factory = get_service_factory()
    return factory.create_graph_service(db)


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
    db: Session = Depends(get_db)
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
        factory.create_sparql_service(db)
    )
