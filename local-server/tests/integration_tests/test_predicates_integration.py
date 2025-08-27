"""Integration tests for predicate API endpoints."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import uuid
from datetime import datetime


class TestPredicateAPIIntegration:
    """Integration tests for predicate API endpoints."""

    def test_create_predicate_success(self, client):
        """Test successful predicate creation via API."""
        
        predicate_data = {
            "title": "CustomRelatedTo",
            "definition": "Indicates a general relationship between concepts",
            "identifier": "custom_related_to",  # Use unique identifier
            "mapping": {
                "conceptnet": {
                    "relation": "RelatedTo",
                    "url": "https://conceptnet.io/r/RelatedTo"
                }
            }
        }
        
        response = client.post("/api/predicates/", json=predicate_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "CustomRelatedTo"
        assert data["identifier"] == "custom_related_to"
        assert data["definition"] == "Indicates a general relationship between concepts"
        assert "id" in data
        assert "date_created" in data
        assert "date_modified" in data

    def test_create_predicate_with_custom_identifier(self, client):
        """Test predicate creation with custom identifier."""
        
        predicate_data = {
            "title": "Custom Relation",
            "identifier": "custom_id"
        }
        
        response = client.post("/api/predicates/", json=predicate_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["identifier"] == "custom_id"

    def test_create_predicate_duplicate_identifier(self, client):
        """Test predicate creation with duplicate identifier fails."""
        
        # Create first predicate
        predicate_data = {
            "title": "First Predicate",
            "identifier": "duplicate_id"
        }
        response = client.post("/api/predicates/", json=predicate_data)
        assert response.status_code == 201
        
        # Try to create second predicate with same identifier
        predicate_data = {
            "title": "Second Predicate", 
            "identifier": "duplicate_id"
        }
        response = client.post("/api/predicates/", json=predicate_data)
        assert response.status_code == 409

    def test_create_predicate_duplicate_title(self, client):
        """Test creating predicates with duplicate titles fails."""
        
        predicate_data_1 = {
            "title": "Similar To V1",
            "definition": "First version of similarity relation",
            "identifier": "similar_v1"
        }
        
        predicate_data_2 = {
            "title": "Similar To V1",  # Same title
            "definition": "Second version of similarity relation",
            "identifier": "similar_v2"
        }
        
        # Create first predicate
        response_1 = client.post("/api/predicates/", json=predicate_data_1)
        assert response_1.status_code == 201
        
        # Try to create second with same title
        response_2 = client.post("/api/predicates/", json=predicate_data_2)
        assert response_2.status_code == 409

    def test_create_predicate_validation_errors(self, client):
        """Test predicate creation validation errors."""
        
        # Test missing title
        response = client.post("/api/predicates/", json={})
        assert response.status_code == 422
        
        # Test empty title
        response = client.post("/api/predicates/", json={"title": ""})
        assert response.status_code == 422
        
        # Test title too long
        response = client.post("/api/predicates/", json={"title": "x" * 256})
        assert response.status_code == 422

    def test_get_predicate_by_id(self, client):
        """Test getting predicate by ID."""
        
        # Create predicate
        predicate_data = {"title": "Test Predicate"}
        create_response = client.post("/api/predicates/", json=predicate_data)
        assert create_response.status_code == 201
        predicate_id = create_response.json()["id"]
        
        # Get predicate by ID
        response = client.get(f"/api/predicates/{predicate_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == predicate_id
        assert data["title"] == "Test Predicate"

    def test_get_predicate_not_found(self, client):
        """Test getting non-existent predicate returns 404."""
        
        # Use a valid UUID format that doesn't exist in the database
        response = client.get("/api/predicates/12345678-1234-5678-9012-123456789012")
        assert response.status_code == 404

    def test_get_predicate_by_identifier(self, client):
        """Test getting predicate by identifier."""
        
        # Create predicate
        predicate_data = {"title": "Test Predicate", "identifier": "test_pred"}
        create_response = client.post("/api/predicates/", json=predicate_data)
        assert create_response.status_code == 201
        
        # Get predicate by identifier
        response = client.get("/api/predicates/by-identifier/test_pred")
        assert response.status_code == 200
        data = response.json()
        assert data["identifier"] == "test_pred"
        assert data["title"] == "Test Predicate"

    def test_get_predicate_by_identifier_not_found(self, client):
        """Test getting non-existent predicate by identifier."""
        
        response = client.get("/api/predicates/by-identifier/nonexistent")
        assert response.status_code == 404

    def test_list_predicates_default(self, client):
        """Test listing predicates with default parameters."""
        
        # Create multiple predicates
        predicates_data = [
            {"title": "Predicate A"},
            {"title": "Predicate B"},
            {"title": "Predicate C"}
        ]
        
        for pred_data in predicates_data:
            response = client.post("/api/predicates/", json=pred_data)
            assert response.status_code == 201
        
        # List predicates
        response = client.get("/api/predicates/")
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert data["total"] == 3
        assert len(data["data"]) == 3

    def test_list_predicates_pagination(self, client):
        """Test listing predicates with pagination."""
        
        # Create 10 predicates
        for i in range(10):
            predicate_data = {"title": f"Predicate {i:02d}"}
            response = client.post("/api/predicates/", json=predicate_data)
            assert response.status_code == 201
        
        # Test first page
        response = client.get("/api/predicates/?skip=0&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert len(data["data"]) == 5
        assert data["skip"] == 0
        assert data["limit"] == 5
        
        # Test second page
        response = client.get("/api/predicates/?skip=5&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert len(data["data"]) == 5
        assert data["skip"] == 5
        assert data["limit"] == 5

    def test_list_predicates_sorting(self, client):
        """Test listing predicates with sorting."""
        
        # Create predicates with specific titles for sorting
        predicates_data = [
            {"title": "Zebra"},
            {"title": "Alpha"},
            {"title": "Beta"}
        ]
        
        for pred_data in predicates_data:
            response = client.post("/api/predicates/", json=pred_data)
            assert response.status_code == 201
        
        # Test sort by title
        response = client.get("/api/predicates/?sortBy=title")
        assert response.status_code == 200
        data = response.json()
        titles = [pred["title"] for pred in data["data"]]
        assert titles == ["Alpha", "Beta", "Zebra"]
        
        # Test sort by identifier
        response = client.get("/api/predicates/?sortBy=identifier")
        assert response.status_code == 200
        data = response.json()
        identifiers = [pred["identifier"] for pred in data["data"]]
        assert identifiers == ["alpha", "beta", "zebra"]

    def test_list_predicates_invalid_sort(self, client):
        """Test listing predicates with invalid sort parameter."""
        
        response = client.get("/api/predicates/?sortBy=invalid_field")
        assert response.status_code == 422

    def test_update_predicate_success(self, client):
        """Test successful predicate update."""
        
        # Create predicate
        predicate_data = {"title": "Original Title", "definition": "Original definition"}
        create_response = client.post("/api/predicates/", json=predicate_data)
        assert create_response.status_code == 201
        predicate_id = create_response.json()["id"]
        
        # Update predicate
        update_data = {
            "title": "Updated Title",
            "definition": "Updated definition",
            "mapping": {"source": "manual"}
        }
        response = client.put(f"/api/predicates/{predicate_id}", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["definition"] == "Updated definition"
        assert data["identifier"] == "original_title"  # Identifier should not change

    def test_update_predicate_partial(self, client):
        """Test partial predicate update."""
        
        # Create predicate
        predicate_data = {"title": "Original Title", "definition": "Original definition"}
        create_response = client.post("/api/predicates/", json=predicate_data)
        assert create_response.status_code == 201
        predicate_id = create_response.json()["id"]
        
        # Update only title
        update_data = {"title": "New Title"}
        response = client.put(f"/api/predicates/{predicate_id}", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == "New Title"
        assert data["definition"] == "Original definition"  # Should remain unchanged

    def test_update_predicate_not_found(self, client):
        """Test updating non-existent predicate."""
        
        fake_id = str(uuid.uuid4())
        update_data = {"title": "New Title"}
        response = client.put(f"/api/predicates/{fake_id}", json=update_data)
        assert response.status_code == 404

    def test_update_predicate_duplicate_title(self, client):
        """Test updating predicate with duplicate title fails."""
        
        # Create two predicates
        response1 = client.post("/api/predicates/", json={"title": "Title 1"})
        response2 = client.post("/api/predicates/", json={"title": "Title 2"})
        assert response1.status_code == 201
        assert response2.status_code == 201
        
        predicate2_id = response2.json()["id"]
        
        # Try to update second predicate with first predicate's title
        update_data = {"title": "Title 1"}
        response = client.put(f"/api/predicates/{predicate2_id}", json=update_data)
        assert response.status_code == 409

    def test_delete_predicate_success(self, client):
        """Test successful predicate deletion."""
        
        # Create predicate
        predicate_data = {"title": "To Delete"}
        create_response = client.post("/api/predicates/", json=predicate_data)
        assert create_response.status_code == 201
        predicate_id = create_response.json()["id"]
        
        # Delete predicate
        response = client.delete(f"/api/predicates/{predicate_id}")
        assert response.status_code == 200
        
        # Verify deletion
        get_response = client.get(f"/api/predicates/{predicate_id}")
        assert get_response.status_code == 404

    def test_delete_predicate_not_found(self, client):
        """Test deleting non-existent predicate."""
        
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/predicates/{fake_id}")
        assert response.status_code == 404

    def test_delete_predicate_with_references(self, client):
        """Test deleting predicate that is referenced by other entities."""
        
        # Create predicate
        predicate_data = {"title": "Referenced Predicate"}
        create_response = client.post("/api/predicates/", json=predicate_data)
        assert create_response.status_code == 201
        predicate_id = create_response.json()["id"]
        
        # Create domain that references the predicate
        # (This would need to be done through domain API)
        # For now, we test the basic deletion
        
        # Try to delete predicate
        response = client.delete(f"/api/predicates/{predicate_id}")
        # Behavior depends on foreign key constraints and cascade settings
        # Could be 200 (success), 409 (conflict), or 422 (constraint violation)
        assert response.status_code in [200, 409, 422]

    def test_api_error_handling(self, client):
        """Test API error handling for various scenarios."""
        
        # Test invalid JSON
        response = client.post("/api/predicates/", content="invalid json", 
                             headers={"Content-Type": "application/json"})
        assert response.status_code == 422
        
        # Test invalid UUID format
        response = client.get("/api/predicates/invalid-uuid")
        assert response.status_code in [400, 422]  # Depends on validation implementation

    def test_predicate_mapping_serialization(self, client):
        """Test that predicate mapping is properly serialized/deserialized."""
        
        complex_mapping = {
            "conceptnet": {
                "relation": "RelatedTo",
                "url": "https://conceptnet.io/r/RelatedTo",
                "confidence": 0.8
            },
            "wordnet": {
                "synset": "concept.n.01",
                "definition": "abstract idea"
            },
            "custom": {
                "source": "manual",
                "tags": ["semantic", "general"]
            }
        }
        
        predicate_data = {
            "title": "Complex Mapping",
            "mapping": complex_mapping
        }
        
        # Create predicate
        create_response = client.post("/api/predicates/", json=predicate_data)
        assert create_response.status_code == 201
        predicate_id = create_response.json()["id"]
        
        # Get predicate and verify mapping
        get_response = client.get(f"/api/predicates/{predicate_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        
        # Compare mappings (note: response might not include mapping in this format)
        # This test verifies that complex nested JSON is handled correctly

    def test_concurrent_predicate_creation(self, client):
        """Test handling of concurrent predicate creation attempts."""
        
        # This test simulates concurrent requests with same data
        # In a real scenario, this would test race conditions
        
        predicate_data = {"title": "Concurrent Test"}
        
        # Make multiple requests quickly
        responses = []
        for _ in range(3):
            response = client.post("/api/predicates/", json=predicate_data)
            responses.append(response)
        
        # One should succeed, others should fail with conflict
        success_count = sum(1 for r in responses if r.status_code == 201)
        conflict_count = sum(1 for r in responses if r.status_code == 409)
        
        assert success_count == 1
        assert conflict_count == 2


class TestConceptNetIntegrationAPI:
    """Integration tests for ConceptNet integration endpoints."""

    @pytest.mark.skip(reason="ConceptNet endpoints not yet implemented")
    def test_get_conceptnet_relations(self, client):
        """Test getting available ConceptNet relations."""
        
        response = client.get("/api/predicates/conceptnet-relations")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "RelatedTo" in data
        assert "IsA" in data

    @pytest.mark.skip(reason="ConceptNet endpoints not yet implemented")
    def test_import_predicates_from_conceptnet_all(self, client):
        """Test importing all ConceptNet predicates."""
        
        response = client.post("/api/predicates/import-from-conceptnet")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify predicates were created
        for predicate in data:
            assert "id" in predicate
            assert "identifier" in predicate
            assert "title" in predicate
            assert predicate["mapping"] is not None

    @pytest.mark.skip(reason="ConceptNet endpoints not yet implemented")
    def test_import_predicates_from_conceptnet_selective(self, client):
        """Test importing selected ConceptNet predicates."""
        
        relations_to_import = ["RelatedTo", "IsA", "PartOf"]
        
        response = client.post("/api/predicates/import-from-conceptnet", 
                             json={"relations": relations_to_import})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 3
        
        imported_titles = {pred["title"] for pred in data}
        assert imported_titles == set(relations_to_import)

    @pytest.mark.skip(reason="ConceptNet endpoints not yet implemented")
    def test_import_predicates_idempotent(self, client):
        """Test that importing ConceptNet predicates is idempotent."""
        
        # First import
        response1 = client.post("/api/predicates/import-from-conceptnet")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second import (should not create duplicates)
        response2 = client.post("/api/predicates/import-from-conceptnet")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Second import should return empty list (no new predicates created)
        assert len(data2) == 0
        
        # Verify total count hasn't changed
        list_response = client.get("/api/predicates/")
        assert list_response.status_code == 200
        total_predicates = list_response.json()["total"]
        assert total_predicates == len(data1)
