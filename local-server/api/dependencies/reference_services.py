"""
Dependency injection for Reference services

This module provides optimized dependency injection for reference-related services
using the service factory pattern for better performance.
"""


from services.service_factory import get_service_factory
from reference.service import ReferenceService
from schema_org.service import SchemaOrgService


def get_reference_service() -> ReferenceService:
    """
    Optimized dependency injection for ReferenceService using service factory.
    
    Returns:
        ReferenceService instance
    """
    factory = get_service_factory()
    return factory.create_reference_service()


def get_schema_org_service() -> SchemaOrgService:
    """
    Optimized dependency injection for SchemaOrgService using service factory.
    
    Returns:
        SchemaOrgService instance
    """
    factory = get_service_factory()
    return factory.create_schema_org_service()


def get_all_reference_services() -> tuple[ReferenceService, SchemaOrgService]:
    """
    Get all reference services in one dependency call for efficiency.
    
    Returns:
        Tuple of (ReferenceService, SchemaOrgService) instances
    """
    factory = get_service_factory()
    return (
        factory.create_reference_service(),
        factory.create_schema_org_service()
    )
