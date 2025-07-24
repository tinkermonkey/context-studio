#!/usr/bin/env python3
"""
Quick test to verify pagination functionality in the updated APIs.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pydantic import ValidationError
from api.terms import PaginatedTermsResponse, TermOut
from api.domains import PaginatedDomainsResponse, DomainOut  
from api.layers import PaginatedLayersResponse, LayerOut
from uuid import uuid4
import datetime

def test_pagination_models():
    """Test that the new pagination models work correctly."""
    
    # Test PaginatedTermsResponse
    term_out = TermOut(
        id=uuid4(),
        title="Test Term",
        definition="Test definition",
        domain_id=uuid4(),
        layer_id=uuid4(),
        parent_term_id=None,
        title_embedding=None,
        definition_embedding=None,
        created_at=datetime.datetime.now().isoformat(),
        version=1,
        last_modified=datetime.datetime.now().isoformat()
    )
    
    paginated_terms = PaginatedTermsResponse(
        data=[term_out],
        total=100,
        skip=0,
        limit=50
    )
    
    print("✓ PaginatedTermsResponse works correctly")
    print(f"  - Data count: {len(paginated_terms.data)}")
    print(f"  - Total: {paginated_terms.total}")
    print(f"  - Skip: {paginated_terms.skip}")
    print(f"  - Limit: {paginated_terms.limit}")
    
    # Test PaginatedDomainsResponse
    domain_out = DomainOut(
        id=uuid4(),
        title="Test Domain",
        definition="Test definition",
        layer_id=uuid4(),
        title_embedding=None,
        definition_embedding=None,
        created_at=datetime.datetime.now().isoformat(),
        version=1,
        last_modified=datetime.datetime.now().isoformat()
    )
    
    paginated_domains = PaginatedDomainsResponse(
        data=[domain_out],
        total=50,
        skip=10,
        limit=25
    )
    
    print("✓ PaginatedDomainsResponse works correctly")
    print(f"  - Data count: {len(paginated_domains.data)}")
    print(f"  - Total: {paginated_domains.total}")
    print(f"  - Skip: {paginated_domains.skip}")
    print(f"  - Limit: {paginated_domains.limit}")
    
    # Test PaginatedLayersResponse
    layer_out = LayerOut(
        id=uuid4(),
        title="Test Layer",
        definition="Test definition",
        primary_predicate="is_a",
        title_embedding=None,
        definition_embedding=None,
        created_at=datetime.datetime.now().isoformat(),
        version=1,
        last_modified=datetime.datetime.now().isoformat()
    )
    
    paginated_layers = PaginatedLayersResponse(
        data=[layer_out],
        total=25,
        skip=5,
        limit=10
    )
    
    print("✓ PaginatedLayersResponse works correctly")
    print(f"  - Data count: {len(paginated_layers.data)}")
    print(f"  - Total: {paginated_layers.total}")
    print(f"  - Skip: {paginated_layers.skip}")
    print(f"  - Limit: {paginated_layers.limit}")
    
    print("\n✅ All pagination models work correctly!")

if __name__ == "__main__":
    test_pagination_models()
