"""Integration tests for predicate-domain integration."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import uuid
import datetime
from database.models import Predicate, Domain, Layer, Term, TermRelationship


class TestPredicateDomainIntegration:
    """Integration tests for predicate-domain integration."""

    @pytest.fixture
    def test_data(self, client, db_session):
        """Create test data for predicate-domain integration tests."""
        
        # Create test predicates via API to ensure they exist
        predicates = []
        predicate_data_list = [
            {"title": "Test Synonym", "identifier": "test_synonym_pd"},
            {"title": "Test Antonym", "identifier": "test_antonym_pd"},
            {"title": "Test Related To", "identifier": "test_related_to_pd"},
            {"title": "Test Part Of", "identifier": "test_part_of_pd"}
        ]
        
        for pred_data in predicate_data_list:
            response = client.post("/api/predicates/", json=pred_data)
            assert response.status_code == 201
            predicates.append(response.json())
        
        # Create test layer via API to ensure it exists
        unique_id = str(uuid.uuid4())[:8]
        layer_data = {
            "title": f"Test Layer {unique_id}",
            "definition": "Layer for testing predicate domain integration"
        }
        response = client.post("/api/layers/", json=layer_data)
        assert response.status_code == 201
        layer = response.json()
        
        return {
            "layer": layer,
            "predicates": predicates
        }

    def test_create_domain_with_primary_predicate_id(self, client, test_data):
        """Test creating domain with primary predicate ID."""
        
        primary_predicate_id = test_data["predicates"][0]["id"]
        
        domain_data = {
            "title": "Test Domain",
            "definition": "Domain for testing",
            "layer_id": test_data["layer"]["id"],
            "primary_predicate_id": primary_predicate_id
        }
        
        response = client.post("/api/domains/", json=domain_data)
        if response.status_code != 201:
            print(f"Response: {response.status_code} - {response.text}")
        assert response.status_code == 201
        
        data = response.json()
        assert data["primary_predicate_id"] == primary_predicate_id

    def test_create_domain_with_predicate_set(self, client, test_data):
        """Test creating domain with predicate set."""
        
        predicate_identifiers = [p["identifier"] for p in test_data["predicates"][:2]]
        
        domain_data = {
            "title": "Test Domain 2",
            "definition": "Domain for testing",
            "layer_id": test_data["layer"]["id"],
            "predicate_set": predicate_identifiers
        }
        
        response = client.post("/api/domains/", json=domain_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["predicate_set"] is not None

    def test_create_domain_with_invalid_predicate_id(self, client, test_data):
        """Test creating domain with invalid predicate ID fails."""
        
        domain_data = {
            "title": "Test Domain 3", 
            "definition": "Domain for testing",
            "layer_id": test_data["layer"]["id"],
            "primary_predicate_id": str(uuid.uuid4())  # Non-existent predicate
        }
        
        response = client.post("/api/domains/", json=domain_data)
        assert response.status_code == 400

    def test_create_domain_with_invalid_predicate_set(self, client, test_data):
        """Test creating domain with invalid predicate set fails."""
        
        domain_data = {
            "title": "Test Domain 4",
            "definition": "Domain for testing", 
            "layer_id": test_data["layer"]["id"],
            "predicate_set": ["non_existent_predicate_xyz"]
        }
        
        response = client.post("/api/domains/", json=domain_data)
        assert response.status_code == 400