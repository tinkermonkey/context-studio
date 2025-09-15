"""Unified Context Facade for reference sources"""

from .models import (
    ReferenceSource,
    UnifiedNode,
    UnifiedLink,
    UnifiedSearchRequest,
    UnifiedSearchResponse,
    UnifiedLinksRequest,
    UnifiedLinksResponse
)
from .service import UnifiedReferenceService

__all__ = [
    "ReferenceSource",
    "UnifiedNode",
    "UnifiedLink",
    "UnifiedSearchRequest",
    "UnifiedSearchResponse",
    "UnifiedLinksRequest",
    "UnifiedLinksResponse",
    "UnifiedReferenceService",
]