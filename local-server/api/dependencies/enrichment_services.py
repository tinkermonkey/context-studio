"""
Dependency injection for Enrichment services

This module provides optimized dependency injection for enrichment-related services
using the service factory pattern for better performance.
"""


from services.service_factory import get_service_factory
from enrichment.service import EnrichmentService
from schema_org.service import SchemaOrgService


def get_enrichment_service() -> EnrichmentService:
    """
    Optimized dependency injection for EnrichmentService using service factory.
    
    Returns:
        EnrichmentService instance
    """
    factory = get_service_factory()
    return factory.create_enrichment_service()


def get_schema_org_service() -> SchemaOrgService:
    """
    Optimized dependency injection for SchemaOrgService using service factory.
    
    Returns:
        SchemaOrgService instance
    """
    factory = get_service_factory()
    return factory.create_schema_org_service()


def get_all_enrichment_services() -> tuple[EnrichmentService, SchemaOrgService]:
    """
    Get all enrichment services in one dependency call for efficiency.
    
    Returns:
        Tuple of (EnrichmentService, SchemaOrgService) instances
    """
    factory = get_service_factory()
    return (
        factory.create_enrichment_service(),
        factory.create_schema_org_service()
    )
