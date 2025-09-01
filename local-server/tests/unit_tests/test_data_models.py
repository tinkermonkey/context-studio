"""
Comprehensive test for 10.2.4 Data Models implementation.
Tests all Pydantic models against exact specifications.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from pydantic import ValidationError
from llm.models import (
    SelectedRelation,
    ComponentTerm,
    DefinitionSuggestionRequest,
    DefinitionSuggestionResponse,
    LLMHealthResponse,
    LLMErrorResponse,
    LLMSuccessResponse
)


def test_selected_relation_model():
    """Test SelectedRelation model against specification"""
    print("🧪 Testing SelectedRelation Model")
    
    # Test with all fields
    relation = SelectedRelation(
        predicate="used for",
        object="label of target term",
        weight=5.125,
        text="text element from the relation definition"
    )
    
    assert relation.predicate == "used for"
    assert relation.object == "label of target term"
    assert relation.weight == 5.125
    assert relation.text == "text element from the relation definition"
    print("  ✓ All fields populated correctly")
    
    # Test with optional text field None
    relation_no_text = SelectedRelation(
        predicate="RelatedTo",
        object="another term",
        weight=2.5
    )
    
    assert relation_no_text.text is None
    print("  ✓ Optional text field works correctly")
    
    # Test validation - missing required fields
    try:
        SelectedRelation(predicate="test")
        assert False, "Should require object and weight"
    except ValidationError:
        print("  ✓ Validation works for missing required fields")


def test_component_term_model():
    """Test ComponentTerm model against specification"""
    print("🧪 Testing ComponentTerm Model")
    
    # Create test relations
    relations = [
        SelectedRelation(
            predicate="used for",
            object="target1",
            weight=5.0,
            text="text1"
        ),
        SelectedRelation(
            predicate="RelatedTo",
            object="target2",
            weight=3.5
        )
    ]
    
    # Test with all fields
    component = ComponentTerm(
        text="the term text",
        selected_definitions=["Selected sense 0", "Selected sense 1"],
        selected_relations=relations
    )
    
    assert component.text == "the term text"
    assert len(component.selected_definitions) == 2
    assert len(component.selected_relations) == 2
    assert component.selected_relations[0].weight == 5.0
    print("  ✓ All fields populated correctly")
    
    # Test with empty defaults
    component_minimal = ComponentTerm(text="minimal term")
    
    assert component_minimal.text == "minimal term"
    assert component_minimal.selected_definitions == []
    assert component_minimal.selected_relations == []
    print("  ✓ Default empty lists work correctly")


def test_definition_suggestion_request_model():
    """Test DefinitionSuggestionRequest model against exact requirements schema"""
    print("🧪 Testing DefinitionSuggestionRequest Model")
    
    # Test with exact JSON schema from requirements
    exact_schema_json = {
        "term": "term to be analyzed",
        "domain_title": "title of the domain to which the term belongs",
        "domain_definition": "definition of the domain to which the term belongs",
        "parent_term_title": "the title of the parent term (if any)",
        "parent_term_definition": "the definition of the parent term (if any)",
        "parent_relationship_predicate": "the predicate which defines the relationship to the parent (if any)",
        "component_terms": [
            {
                "text": "the term text",
                "selected_definitions": [
                    "Selected sense 0",
                    "Selected sense 1"
                ],
                "selected_relations": [
                    {
                        "predicate": "used for",
                        "object": "label of target term",
                        "weight": 5.125,
                        "text": "text element from the relation definition"
                    }
                ]
            }
        ],
        "current definition": "the current definition (if any)",  # Note: space in field name!
        "dbpedia_context": {"key": "value"},
        "wikidata_context": {"another_key": "another_value"}
    }
    
    request = DefinitionSuggestionRequest(**exact_schema_json)
    
    assert request.term == "term to be analyzed"
    assert request.domain_title == "title of the domain to which the term belongs"
    assert request.current_definition == "the current definition (if any)"
    assert len(request.component_terms) == 1
    assert request.component_terms[0].text == "the term text"
    assert len(request.component_terms[0].selected_relations) == 1
    assert request.component_terms[0].selected_relations[0].weight == 5.125
    assert request.dbpedia_context == {"key": "value"}
    assert request.wikidata_context == {"another_key": "another_value"}
    print("  ✓ Exact requirements JSON schema accepted")
    
    # Test minimal request (only required field)
    minimal_request = DefinitionSuggestionRequest(term="test term")
    
    assert minimal_request.term == "test term"
    assert minimal_request.domain_title is None
    assert minimal_request.component_terms == []
    assert minimal_request.dbpedia_context == {}
    assert minimal_request.wikidata_context == {}
    print("  ✓ Minimal request with defaults works")
    
    # Test field name with space using alias
    space_field_json = {
        "term": "test",
        "current definition": "definition with space in field name"
    }
    
    space_request = DefinitionSuggestionRequest(**space_field_json)
    assert space_request.current_definition == "definition with space in field name"
    print("  ✓ 'current definition' field with space works via alias")


def test_definition_suggestion_response_model():
    """Test DefinitionSuggestionResponse model against specification"""
    print("🧪 Testing DefinitionSuggestionResponse Model")
    
    # Test with all fields
    response = DefinitionSuggestionResponse(
        definition="The suggested 2-3 sentence definition here.",
        reasoning="Brief reasoning for the definitional choices made.",
        discrepancies="Notable discrepancies between sources identified."
    )
    
    assert response.definition == "The suggested 2-3 sentence definition here."
    assert response.reasoning == "Brief reasoning for the definitional choices made."
    assert response.discrepancies == "Notable discrepancies between sources identified."
    print("  ✓ All fields populated correctly")
    
    # Test without optional discrepancies
    response_no_disc = DefinitionSuggestionResponse(
        definition="Another definition.",
        reasoning="Another reasoning."
    )
    
    assert response_no_disc.discrepancies is None
    print("  ✓ Optional discrepancies field works")
    
    # Test validation - missing required fields
    try:
        DefinitionSuggestionResponse(definition="test")
        assert False, "Should require reasoning"
    except ValidationError:
        print("  ✓ Validation works for missing required fields")


def test_health_response_model():
    """Test LLMHealthResponse model"""
    print("🧪 Testing LLMHealthResponse Model")
    
    health = LLMHealthResponse(
        status="healthy",
        model_info={
            "model_name": "gpt-3.5-turbo",
            "temperature": 0,
            "initialized": True
        },
        timestamp="2025-09-01T07:46:31.000Z"
    )
    
    assert health.status == "healthy"
    assert health.model_info["model_name"] == "gpt-3.5-turbo"
    assert health.model_info["initialized"] is True
    assert health.timestamp == "2025-09-01T07:46:31.000Z"
    print("  ✓ All fields populated correctly")


def test_error_response_models():
    """Test LLMErrorResponse and LLMSuccessResponse models"""
    print("🧪 Testing Error and Success Response Models")
    
    # Test error response
    error = LLMErrorResponse(
        error="Test error message",
        error_type="LLMProcessingError",
        details="Additional error details here"
    )
    
    assert error.success is False  # Default value
    assert error.error == "Test error message"
    assert error.error_type == "LLMProcessingError"
    assert error.details == "Additional error details here"
    print("  ✓ Error response model works correctly")
    
    # Test error response without optional details
    error_no_details = LLMErrorResponse(
        error="Simple error",
        error_type="ConfigError"
    )
    
    assert error_no_details.details is None
    print("  ✓ Optional details field works")
    
    # Test success response
    test_response = DefinitionSuggestionResponse(
        definition="Test definition",
        reasoning="Test reasoning"
    )
    
    success = LLMSuccessResponse(data=test_response)
    
    assert success.success is True  # Default value
    assert success.data.definition == "Test definition"
    assert success.data.reasoning == "Test reasoning"
    print("  ✓ Success response model works correctly")


def test_json_serialization():
    """Test JSON serialization/deserialization for all models"""
    print("🧪 Testing JSON Serialization")
    
    # Create complex nested structure
    request = DefinitionSuggestionRequest(
        term="complex term",
        domain_title="Complex Domain",
        component_terms=[
            ComponentTerm(
                text="component1",
                selected_definitions=["def1", "def2"],
                selected_relations=[
                    SelectedRelation(
                        predicate="RelatedTo",
                        object="target",
                        weight=4.5,
                        text="relation text"
                    )
                ]
            )
        ],
        dbpedia_context={"nested": {"key": "value"}}
    )
    
    # Test serialization
    request_dict = request.model_dump()
    assert isinstance(request_dict, dict)
    assert request_dict["term"] == "complex term"
    assert len(request_dict["component_terms"]) == 1
    print("  ✓ Model serialization works")
    
    # Test deserialization
    request_back = DefinitionSuggestionRequest(**request_dict)
    assert request_back.term == request.term
    assert len(request_back.component_terms) == len(request.component_terms)
    assert request_back.component_terms[0].selected_relations[0].weight == 4.5
    print("  ✓ Model deserialization works")


if __name__ == "__main__":
    try:
        test_selected_relation_model()
        test_component_term_model()
        test_definition_suggestion_request_model()
        test_definition_suggestion_response_model()
        test_health_response_model()
        test_error_response_models()
        test_json_serialization()
        
        print("\n🎉 ALL DATA MODEL TESTS PASSED!")
        print("\n📋 10.2.4 Data Models Implementation Summary:")
        print("  ✓ SelectedRelation: ConceptNet relation with predicate, object, weight, text")
        print("  ✓ ComponentTerm: Term with definitions and relations collections")
        print("  ✓ DefinitionSuggestionRequest: Complete request model with exact schema compliance")
        print("  ✓ DefinitionSuggestionResponse: Structured response with definition/reasoning/discrepancies")
        print("  ✓ LLMHealthResponse: Health check response with status and model info")
        print("  ✓ LLMErrorResponse: Error response with success flag and details")
        print("  ✓ LLMSuccessResponse: Success wrapper for API responses")
        print("  ✓ JSON Serialization: Full round-trip compatibility")
        print("  ✓ Field Aliases: Support for 'current definition' with space")
        print("  ✓ Validation: Proper required/optional field validation")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
