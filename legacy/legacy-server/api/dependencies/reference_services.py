"""
Dependency injection for Reference services

This module provides optimized dependency injection for reference-related services  # noqa: E501
using the service factory pattern for better performance.
"""

from reference_api.service import ReferenceService
from services.service_factory import get_service_factory


def get_reference_service() -> ReferenceService:
    """
    Optimized dependency injection for ReferenceService using service factory.

    Returns:
        ReferenceService instance
    """
    factory = get_service_factory()
    return factory.create_reference_service()
