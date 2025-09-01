"""
Example of how to use the LLM API endpoint for definition suggestion.

This demonstrates the request format and expected response structure.
"""

import json

# Example request payload that matches the requirements
example_request = {
    "term": "apple sauce",
    "domain_title": "Food and Cooking",
    "domain_definition": "The domain of culinary arts and food preparation",
    "parent_term_title": "sauce",
    "parent_term_definition": "A liquid or semi-liquid substance served with food",
    "parent_relationship_predicate": "is a type of",
    "component_terms": [
        {
            "text": "apple",
            "selected_definitions": [
                "A fruit from apple trees",
                "Round fruit with red or green skin and white flesh"
            ],
            "selected_relations": [
                {
                    "predicate": "used for",
                    "object": "making sauce",
                    "weight": 5.125,
                    "text": "apples are used for making sauce"
                },
                {
                    "predicate": "has property",
                    "object": "sweet",
                    "weight": 4.2,
                    "text": "apples have the property of being sweet"
                }
            ]
        },
        {
            "text": "sauce",
            "selected_definitions": [
                "A liquid or semi-liquid accompaniment to food",
                "A condiment or dressing for food"
            ],
            "selected_relations": [
                {
                    "predicate": "used for",
                    "object": "flavoring food",
                    "weight": 6.0,
                    "text": "sauce is used for flavoring food"
                }
            ]
        }
    ],
    "current definition": "A sauce made from apples",
    "dbpedia_context": {
        "resource": "http://dbpedia.org/resource/Apple_sauce",
        "description": "Apple sauce is a puree made from apples"
    },
    "wikidata_context": {
        "entity": "Q618070",
        "label": "apple sauce",
        "properties": {
            "P31": "food",
            "P186": "apple"
        }
    }
}

# Expected response structure
expected_response_structure = {
    "success": True,
    "data": {
        "definition": "A sweet, pureed condiment made from cooked apples that serves as a versatile accompaniment to both savory and sweet dishes. This sauce combines the natural sweetness and texture of apples with cooking techniques to create a smooth, semi-liquid preparation. Apple sauce functions as both a standalone dessert and a complementary sauce that enhances the flavor profile of various foods, particularly in American and European cuisine.",
        "reasoning": "The definition synthesizes the component meanings of 'apple' (fruit with sweet properties) and 'sauce' (liquid accompaniment to food) while emphasizing the emergent concept of a distinct culinary preparation. The hierarchical relationship to 'sauce' is maintained while highlighting the unique characteristics that distinguish apple sauce from other sauces.",
        "discrepancies": "No significant discrepancies found between sources - all references consistently describe apple sauce as a pureed apple preparation used as a food accompaniment."
    }
}

def print_example():
    """Print the example request and response format"""
    print("=== LLM API Endpoint: /api/llm/suggest_definition ===\n")
    
    print("REQUEST FORMAT:")
    print("POST /api/llm/suggest_definition")
    print("Content-Type: application/json\n")
    print(json.dumps(example_request, indent=2))
    
    print("\n" + "="*60 + "\n")
    
    print("EXPECTED RESPONSE FORMAT:")
    print("HTTP 200 OK")
    print("Content-Type: application/json\n")
    print(json.dumps(expected_response_structure, indent=2))
    
    print("\n" + "="*60 + "\n")
    
    print("ENVIRONMENT SETUP:")
    print("1. Copy .env.example to .env")
    print("2. Add your OpenAI API key: OPENAI_API_KEY=your_key_here")
    print("3. Optionally configure model: LLM_MODEL_NAME=gpt-3.5-turbo")
    print("4. Start the server: python app.py")
    print("5. Test the endpoint: curl -X POST http://localhost:8000/api/llm/suggest_definition \\")
    print("   -H 'Content-Type: application/json' \\")
    print("   -d @request_payload.json")

if __name__ == "__main__":
    print_example()
