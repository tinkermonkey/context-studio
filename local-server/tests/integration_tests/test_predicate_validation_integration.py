"""Integration tests for validation logic in API endpoints."""

import sys
import os
import json
import datetime
from uuid import uuid4

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from database.models import Domain, Term, Predicate, TermRelationship


@pytest.fixture(scope="function")
def test_data(client):
    """Set up test data for validation tests using API calls."""
    
    # Create predicates via API
    predicates = {}
    predicate_data = [
        {"identifier": "test_synonym", "title": "Test Synonym", "definition": "Test synonym predicate"},
        {"identifier": "test_antonym", "title": "Test Antonym", "definition": "Test antonym predicate"},
        {"identifier": "test_related_to", "title": "Test RelatedTo", "definition": "Test related_to predicate"},
        {"identifier": "test_hypernym", "title": "Test Hypernym", "definition": "Test hypernym predicate"}
    ]
    
    for pred_data in predicate_data:
        response = client.post("/api/predicates/", json=pred_data)
        assert response.status_code == 201
        predicate = response.json()
        predicates[pred_data["identifier"].replace("test_", "")] = predicate
    
    # Create layers via API
    layer1_response = client.post("/api/layers/", json={
        "title": "Test Layer 1",
        "definition": "Test layer for domain with predicates"
    })
    assert layer1_response.status_code == 201
    layer1 = layer1_response.json()
    
    layer2_response = client.post("/api/layers/", json={
        "title": "Test Layer 2", 
        "definition": "Test layer for domain without predicates"
    })
    assert layer2_response.status_code == 201
    layer2 = layer2_response.json()
    
    # Create domains via API
    domain_with_predicates_response = client.post("/api/domains/", json={
        "layer_id": layer1["id"],
        "title": "Restricted Domain",
        "definition": "Domain with predicate restrictions",
        "predicate_set": ["test_synonym", "test_related_to"]  # Use test predicate identifiers
    })
    assert domain_with_predicates_response.status_code == 201
    domain_with_predicates = domain_with_predicates_response.json()

    domain_without_predicates_response = client.post("/api/domains/", json={
        "layer_id": layer2["id"],
        "title": "Open Domain",
        "definition": "Domain without predicate restrictions"
        # No predicate_set specified
    })
    assert domain_without_predicates_response.status_code == 201
    domain_without_predicates = domain_without_predicates_response.json()

    # Create terms via API
    terms = []
    term_data = [
        {"domain_id": domain_with_predicates["id"], "layer_id": layer1["id"], "title": "Term 0", "definition": "Test term 0"},
        {"domain_id": domain_with_predicates["id"], "layer_id": layer1["id"], "title": "Term 1", "definition": "Test term 1"},
        {"domain_id": domain_without_predicates["id"], "layer_id": layer2["id"], "title": "Term 2", "definition": "Test term 2"}
    ]
    
    for term_data_item in term_data:
        response = client.post("/api/terms/", json=term_data_item)
        assert response.status_code == 201
        terms.append(response.json())
    
    return {
        "domain_with_predicates": domain_with_predicates,
        "domain_without_predicates": domain_without_predicates,
        "layer_with_predicates": layer1,
        "layer_without_predicates": layer2,
        "predicates": predicates,
        "terms": terms
    }


class TestPredicateValidationAPI:
    """Tests for predicate identifier validation in API."""
    
    def test_create_predicate_unique_identifier(self, client, test_data):
        """Test creating predicate with unique identifier."""
        response = client.post("/api/predicates/", json={
            "title": "New Predicate",
            "definition": "A new test predicate",
            "identifier": "unique_identifier"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["identifier"] == "unique_identifier"
    
    def test_create_predicate_duplicate_identifier(self, client, test_data):
        """Test creating predicate with duplicate identifier fails."""
        response = client.post("/api/predicates/", json={
            "title": "Duplicate Predicate",
            "definition": "A predicate with duplicate identifier",
            "identifier": "test_synonym"  # Already exists from test_data
        })

        assert response.status_code == 409
        response_data = response.json()
        assert "already exists" in str(response_data)

    def test_update_predicate_unique_identifier(self, client, test_data):
        """Test updating predicate with unique identifier."""
        predicate = test_data["predicates"]["synonym"]
        
        response = client.put(f"/api/predicates/{predicate['id']}", json={
            "identifier": "new_unique_identifier"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["identifier"] == "new_unique_identifier"
    
    def test_update_predicate_duplicate_identifier(self, client, test_data):
        """Test updating predicate with duplicate identifier fails."""
        predicate = test_data["predicates"]["synonym"]
        
        response = client.put(f"/api/predicates/{predicate['id']}", json={
            "identifier": "test_antonym"  # Already exists
        })
        
        assert response.status_code == 409
        response_data = response.json()
        assert "already exists" in str(response_data)
    
    def test_update_predicate_same_identifier(self, client, test_data):
        """Test updating predicate with same identifier succeeds."""
        predicate = test_data["predicates"]["synonym"]
        
        response = client.put(f"/api/predicates/{predicate['id']}", json={
            "identifier": "test_synonym",  # Same identifier
            "definition": "Updated definition"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["identifier"] == "test_synonym"
        assert data["definition"] == "Updated definition"


class TestTermRelationshipValidationAPI:
    """Tests for term relationship predicate validation in API."""
    
    def test_create_relationship_same_domain_allowed_predicate(self, client, test_data):
        """Test creating relationship with allowed predicate in same domain."""
        term1 = test_data["terms"][0]  # Domain with predicates
        term2 = test_data["terms"][1]  # Same domain
        predicate = test_data["predicates"]["synonym"]  # Allowed
        
        response = client.post("/api/term-relationships/", json={
            "source_term_id": term1["id"],
            "target_term_id": term2["id"],
            "predicate": predicate["identifier"],
            "predicate_id": predicate["id"]
        })
        
        assert response.status_code == 201
    
    def test_create_relationship_same_domain_disallowed_predicate(self, client, test_data):
        """Test creating relationship with disallowed predicate in same domain fails."""
        term1 = test_data["terms"][0]  # Domain with predicates
        term2 = test_data["terms"][1]  # Same domain
        predicate = test_data["predicates"]["antonym"]  # Not allowed
        
        response = client.post("/api/term-relationships/", json={
            "source_term_id": term1["id"],
            "target_term_id": term2["id"],
            "predicate": predicate["identifier"],
            "predicate_id": predicate["id"]
        })
        
        assert response.status_code == 400
        response_data = response.json()
        assert "not allowed" in str(response_data)
    
    def test_create_relationship_different_domains_any_predicate(self, client, test_data):
        """Test creating relationship with any predicate across different domains."""
        term1 = test_data["terms"][0]  # Domain with predicates
        term2 = test_data["terms"][2]  # Different domain
        predicate = test_data["predicates"]["antonym"]  # Would be disallowed in same domain
        
        response = client.post("/api/term-relationships/", json={
            "source_term_id": term1["id"],
            "target_term_id": term2["id"],
            "predicate": predicate["identifier"],
            "predicate_id": predicate["id"]
        })
        
        assert response.status_code == 201
    
    def test_update_relationship_same_domain_allowed_predicate(self, client, test_data):
        """Test updating relationship with allowed predicate in same domain."""
        # First create a relationship
        term1 = test_data["terms"][0]
        term2 = test_data["terms"][1]
        predicate1 = test_data["predicates"]["synonym"]
        
        create_response = client.post("/api/term-relationships/", json={
            "source_term_id": term1["id"],
            "target_term_id": term2["id"],
            "predicate": predicate1["identifier"],
            "predicate_id": predicate1["id"]
        })
        assert create_response.status_code == 201
        relationship_id = create_response.json()["id"]
        
        # Update with another allowed predicate
        predicate2 = test_data["predicates"]["related_to"]
        
        response = client.put(f"/api/term-relationships/{relationship_id}", json={
            "predicate": predicate2["identifier"],
            "predicate_id": predicate2["id"]
        })
        
        assert response.status_code == 200
    
    def test_update_relationship_same_domain_disallowed_predicate(self, client, test_data):
        """Test updating relationship with disallowed predicate in same domain fails."""
        # First create a relationship
        term1 = test_data["terms"][0]
        term2 = test_data["terms"][1]
        predicate1 = test_data["predicates"]["synonym"]
        
        create_response = client.post("/api/term-relationships/", json={
            "source_term_id": term1["id"],
            "target_term_id": term2["id"],
            "predicate": predicate1["identifier"],
            "predicate_id": predicate1["id"]
        })
        assert create_response.status_code == 201
        relationship_id = create_response.json()["id"]
        
        # Try to update with disallowed predicate
        predicate2 = test_data["predicates"]["antonym"]
        
        response = client.put(f"/api/term-relationships/{relationship_id}", json={
            "predicate": predicate2["identifier"],
            "predicate_id": predicate2["id"]
        })
        
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]
    
    def test_create_relationship_no_domain_predicate_set(self, client, test_data):
        """Test creating relationship in domain without predicate set allows any predicate."""
        # Create terms in domain without predicate set
        domain = test_data["domain_without_predicates"]
        
        # Create terms via API
        term1_response = client.post("/api/terms/", json={
            "title": "Open Term 1",
            "definition": "Test term 1",
            "domain_id": domain["id"],
            "layer_id": test_data["layer_without_predicates"]["id"]  # use the second layer
        })
        assert term1_response.status_code == 201
        term1 = term1_response.json()
        
        term2_response = client.post("/api/terms/", json={
            "title": "Open Term 2",
            "definition": "Test term 2",
            "domain_id": domain["id"],
            "layer_id": test_data["layer_without_predicates"]["id"]  # use the second layer
        })
        assert term2_response.status_code == 201
        term2 = term2_response.json()
        
        predicate = test_data["predicates"]["antonym"]
        
        response = client.post("/api/term-relationships/", json={
            "source_term_id": term1["id"],
            "target_term_id": term2["id"],
            "predicate": predicate["identifier"],
            "predicate_id": predicate["id"]
        })
        
        assert response.status_code == 201


if __name__ == "__main__":
    pytest.main([__file__])
