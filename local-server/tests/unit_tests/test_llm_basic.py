"""
Basic test to verify LLM implementation structure.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from unittest.mock import Mock, patch
from llm.service import LLMService
from llm.models import DefinitionSuggestionRequest, ComponentTerm, SelectedRelation
from llm.exceptions import LLMConfigurationError


def test_llm_service_initialization_without_api_key():
    """Test that LLMService raises error without API key"""
    with patch.dict('os.environ', {}, clear=True):
        try:
            LLMService()
            assert False, "Should have raised LLMConfigurationError"
        except LLMConfigurationError as e:
            assert "OPENAI_API_KEY environment variable not set" in str(e)


def test_definition_suggestion_request_validation():
    """Test that request model validates correctly"""
    request = DefinitionSuggestionRequest(
        term="apple sauce",
        domain_title="Food and Cooking",
        domain_definition="The domain of culinary arts and food preparation",
        component_terms=[
            ComponentTerm(
                text="apple",
                selected_definitions=["A fruit from apple trees"],
                selected_relations=[
                    SelectedRelation(
                        predicate="used for",
                        object="making sauce",
                        weight=5.125,
                        text="apples are used for making sauce"
                    )
                ]
            )
        ],
        current_definition="A sauce made from apples",
        dbpedia_context={},
        wikidata_context={}
    )
    
    assert request.term == "apple sauce"
    assert request.domain_title == "Food and Cooking"
    assert len(request.component_terms) == 1
    assert request.component_terms[0].text == "apple"
    assert len(request.component_terms[0].selected_relations) == 1


if __name__ == "__main__":
    # Run basic validation tests
    test_llm_service_initialization_without_api_key()
    print("✓ API key validation test passed")
    
    test_definition_suggestion_request_validation()
    print("✓ Request model validation test passed")
    
    print("All basic tests passed!")
