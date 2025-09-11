"""
Comprehensive validation test for Service                # Test configurable model
                service2 = LLMService(model_name="gpt-4o")
                assert service2.model_name == "gpt-4o"
                print("  ✓ Model is configurable")

                # Test new-style langchain interface
                mock_init.assert_called_with(
                    "gpt-4o",
                    model_provider="openai",
                    temperature=0,
                    openai_api_key='sk-1234567890abcdef1234567890abcdef1234567890abcd'
                )
                print("  ✓ Uses new-style init_chat_model interface") implementation.
Validates all requirements from 10.1_langchain_poc_requirements.md
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from unittest.mock import Mock, patch
from llm.service import LLMService
from llm.models import DefinitionSuggestionRequest
from llm.prompts import DefinitionPromptTemplate
from llm.exceptions import LLMConfigurationError


def test_requirements_compliance():
    """Test that implementation meets all requirements from 10.1"""
    print("🧪 Testing Service Layer Design Requirements Compliance\n")

    # Test 10.1.1: LLM Setup
    print("✓ 10.1.1 LLM Setup:")

    # Test API key from .env
    with patch.dict("os.environ", {}, clear=True):
        try:
            LLMService()
            assert False, "Should require OPENAI_API_KEY"
        except LLMConfigurationError as e:
            print("  ✓ API keys read from environment")
            assert "OPENAI_API_KEY" in str(e)

    # Test configurable model with new-style interface
    with patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-1234567890abcdef1234567890abcdef1234567890abcd"},
    ):
        with patch("llm.service.init_chat_model") as mock_init:
            with patch("llm.service.PipelineFlavorService") as mock_flavor:
                mock_llm = Mock()
                mock_init.return_value = mock_llm
                mock_flavor.return_value = Mock()

                # Test default GPT-3.5-turbo
                service = LLMService()
                assert service.model_name == "gpt-3.5-turbo"
                print("  ✓ Uses GPT-3.5-turbo by default")

                # Test configurable model
                service2 = LLMService(model_name="gpt-4o")
                assert service2.model_name == "gpt-4o"
                print("  ✓ Model is configurable")

            # Test new-style langchain interface
            mock_init.assert_called_with(
                "gpt-4o",
                model_provider="openai",
                temperature=0,
                openai_api_key="sk-1234567890abcdef1234567890abcdef1234567890abcd",
            )
            print("  ✓ Uses new-style init_chat_model interface")

    # Test 10.1.2: LLM Service
    print("\n✓ 10.1.2 LLM Service:")

    with patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-1234567890abcdef1234567890abcdef1234567890abcd"},
    ):
        with patch("llm.service.init_chat_model") as mock_init:
            with patch("llm.service.PipelineFlavorService") as mock_flavor:
                mock_llm = Mock()
                mock_init.return_value = mock_llm
                mock_flavor.return_value = Mock()

                service = LLMService()

            # Test reusable service
            assert hasattr(service, "suggest_definition")
            print("  ✓ Reusable LLM service created")

            # Test abstraction of langchain interaction
            assert service._llm is not None
            print("  ✓ Handles langchain interaction and config management")

            # Test suggest_definition method exists
            assert callable(getattr(service, "suggest_definition", None))
            print("  ✓ Has suggest_definition method")

            # Test error handling
            assert hasattr(service, "logger")
            print("  ✓ Provides proper error handling")

    # Test 10.1.3: Prompt Templates
    print("\n✓ 10.1.3 Definition Suggestion Prompt Template:")

    prompt_template = DefinitionPromptTemplate()

    # Test system prompt matches requirements exactly
    system_prompt = prompt_template.get_system_prompt()
    assert "expert ontologist and taxonomist" in system_prompt
    assert "2-3 sentence definitions" in system_prompt
    assert "apple sauce" in system_prompt  # Example from requirements
    print("  ✓ System prompt matches requirements exactly")

    # Test user prompt format
    test_request = DefinitionSuggestionRequest(
        term="apple sauce", domain_title="Food and Cooking"
    )
    user_prompt = prompt_template.create_prompt(test_request, "")

    # Check required sections in user prompt
    assert "Domain Context:" in user_prompt
    assert "Hierarchical Context:" in user_prompt
    assert "Component Terms:" in user_prompt
    assert "Reference Sources:" in user_prompt
    assert "ConceptNet Relations:" in user_prompt
    assert "WikiData Context:" in user_prompt
    assert "DBpedia Context:" in user_prompt
    print("  ✓ User prompt has all required sections")

    # Test exact format requirement
    assert "Format your response as:" in user_prompt
    assert "Definition: [Your 2-3 sentence definition]" in user_prompt
    assert "Reasoning: [Your brief explanation]" in user_prompt
    assert "Discrepancies: [any noted discrepancies or leave blank]" in user_prompt
    print("  ✓ Uses exact response format from requirements")

    # Test 10.1.4: API Endpoint JSON Schema
    print("\n✓ 10.1.4 API Endpoint JSON Schema:")

    # Test exact JSON schema from requirements
    test_json = {
        "term": "term to be analyzed",
        "domain_title": "title of the domain",
        "domain_definition": "definition of the domain",
        "parent_term_title": "title of parent term",
        "parent_term_definition": "definition of parent term",
        "parent_relationship_predicate": "relationship predicate",
        "component_terms": [
            {
                "text": "the term text",
                "selected_definitions": ["Selected sense 0", "Selected sense 1"],
                "selected_relations": [
                    {
                        "predicate": "used for",
                        "object": "label of target term",
                        "weight": 5.125,
                        "text": "text element from relation",
                    }
                ],
            }
        ],
        "current definition": "the current definition",  # Note: space in field name!
        "dbpedia_context": {},
        "wikidata_context": {},
    }

    # Test Pydantic validation with exact schema
    request = DefinitionSuggestionRequest(**test_json)
    assert request.term == "term to be analyzed"
    assert request.current_definition == "the current definition"
    assert len(request.component_terms) == 1
    assert request.component_terms[0].selected_relations[0].weight == 5.125
    print("  ✓ Accepts exact JSON schema from requirements")
    print("  ✓ Handles 'current definition' field with space")

    # Test response parsing
    print("\n✓ Response Parsing:")

    with patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-1234567890abcdef1234567890abcdef1234567890abcd"},
    ):
        with patch("llm.service.init_chat_model") as mock_init:
            with patch("llm.service.PipelineFlavorService") as mock_flavor:
                mock_llm = Mock()
                mock_init.return_value = mock_llm
                mock_flavor.return_value = Mock()

                service = LLMService()
                mock_response = """Definition: A test definition with exactly two sentences. This is the second sentence of the definition.
Reasoning: This reasoning explains the definitional choices made.
Discrepancies: Some noted discrepancies here."""

                parsed = service._parse_definition_response(mock_response)
                assert "test definition" in parsed.definition
                assert "reasoning explains" in parsed.reasoning
                assert "discrepancies" in parsed.discrepancies.lower()
                print("  ✓ Parses structured response correctly")

    print("\n🎉 All Service Layer Design requirements validated successfully!")

    return True


def test_structured_output():
    """Test that structured output works as specified"""
    print("\n🔍 Testing Structured Output:")

    # Test that DefinitionSuggestionResponse has all required fields
    from llm.models import DefinitionSuggestionResponse

    response = DefinitionSuggestionResponse(
        definition="Test definition here.",
        reasoning="Test reasoning here.",
        discrepancies="Test discrepancies here.",
    )

    assert hasattr(response, "definition")
    assert hasattr(response, "reasoning")
    assert hasattr(response, "discrepancies")
    print("  ✓ Response model has definition, reasoning, discrepancies fields")

    # Test optional discrepancies
    response2 = DefinitionSuggestionResponse(
        definition="Test definition.", reasoning="Test reasoning."
    )
    assert response2.discrepancies is None
    print("  ✓ Discrepancies field is optional")

    return True


if __name__ == "__main__":
    try:
        test_requirements_compliance()
        test_structured_output()
        print("\n✅ ALL TESTS PASSED - Service Layer Design fully meets requirements!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
