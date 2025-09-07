"""Integration tests for predicate-domain integration."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import uuid
import datetime
from database.models import Predicate, StructureNode, StructureNodeLink


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
            "node_type": "layer",
            "title": f"Test Layer {unique_id}",
            "definition": "Layer for testing predicate domain integration"
        }
        response = client.post("/api/structure_nodes/", json=layer_data)
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
            "node_type": "domain",
            "title": "Test Domain",
            "definition": "Domain for testing",
            "parent_node_id": test_data["layer"]["id"],
            "structural_predicate_id": primary_predicate_id
        }
        
        response = client.post("/api/structure_nodes/", json=domain_data)
        if response.status_code != 201:
            print(f"Response: {response.status_code} - {response.text}")
        assert response.status_code == 201
        
        data = response.json()
        assert data["structural_predicate_id"] == primary_predicate_id

    def test_create_domain_with_predicate_set(self, client, test_data):
        """Test creating domain with structural predicate (replaces predicate set concept)."""
        
        predicate_id = test_data["predicates"][1]["id"]  # Use second predicate
        
        domain_data = {
            "node_type": "domain",
            "title": "Test Domain 2",
            "definition": "Domain for testing",
            "parent_node_id": test_data["layer"]["id"],
            "structural_predicate_id": predicate_id
        }
        
        response = client.post("/api/structure_nodes/", json=domain_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["structural_predicate_id"] == predicate_id

    def test_create_domain_with_invalid_predicate_id(self, client, test_data):
        """Test creating domain with invalid predicate ID fails."""
        
        domain_data = {
            "node_type": "domain",
            "title": "Test Domain 3", 
            "definition": "Domain for testing",
            "parent_node_id": test_data["layer"]["id"],
            "structural_predicate_id": str(uuid.uuid4())  # Non-existent predicate
        }
        
        response = client.post("/api/structure_nodes/", json=domain_data)
        assert response.status_code == 400
        response_data = response.json()
        assert "does not exist" in response_data["detail"]

    def test_create_domain_with_invalid_predicate_set(self, client, test_data):
        """Test creating domain with invalid structural predicate fails."""
        
        # Create a predicate first, then try to delete it or use non-existent one
        domain_data = {
            "node_type": "domain",
            "title": "Test Domain 4",
            "definition": "Domain for testing", 
            "parent_node_id": test_data["layer"]["id"],
            "structural_predicate_id": str(uuid.uuid4())  # Non-existent predicate ID
        }
        
        response = client.post("/api/structure_nodes/", json=domain_data)
        assert response.status_code == 400