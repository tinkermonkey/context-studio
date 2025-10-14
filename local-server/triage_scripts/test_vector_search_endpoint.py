"""
Quick test script to verify the vector search endpoint works correctly.
Run this after starting the API server.
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{BASE_URL}/api/predicates/external/search"

def test_search_endpoint():
    """Test the search endpoint with various queries."""
    
    test_cases = [
        {
            "name": "Basic search",
            "params": {"query": "person name"},
            "expect_results": True
        },
        {
            "name": "Search with source filter",
            "params": {"query": "location", "source": "schema_org"},
            "expect_results": True
        },
        {
            "name": "Search with threshold",
            "params": {"query": "temporal information", "threshold": 0.8},
            "expect_results": True
        },
        {
            "name": "Search with limit",
            "params": {"query": "property", "limit": 5},
            "expect_results": True
        },
    ]
    
    print("🧪 Testing External Predicates Vector Search Endpoint\n")
    print("=" * 60)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['name']}")
        print(f"   Params: {test['params']}")
        
        try:
            response = requests.get(API_ENDPOINT, params=test['params'], timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: {response.status_code}")
                print(f"   📊 Results: {data['total']} predicates found")
                print(f"   🔍 Query: '{data['query']}'")
                print(f"   📏 Threshold: {data['threshold']}")
                
                if data['data']:
                    print(f"\n   Top 3 Results:")
                    for j, pred in enumerate(data['data'][:3], 1):
                        print(f"      {j}. {pred['title']}")
                        print(f"         Similarity: {pred['similarity_score']:.2%}")
                        print(f"         Source: {pred['source']}")
                        if pred['definition']:
                            print(f"         Definition: {pred['definition'][:80]}...")
                
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection Error: Is the API server running?")
            return False
        except Exception as e:
            print(f"   ❌ Unexpected Error: {e}")
            return False
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    return True

def test_edge_cases():
    """Test edge cases and error handling."""
    
    print("\n\n🔬 Testing Edge Cases\n")
    print("=" * 60)
    
    edge_cases = [
        {
            "name": "Empty query (should fail)",
            "params": {"query": ""},
            "expect_error": True
        },
        {
            "name": "Invalid threshold (should fail)",
            "params": {"query": "test", "threshold": 2.0},
            "expect_error": True
        },
        {
            "name": "Invalid source (should fail)",
            "params": {"query": "test", "source": "invalid_source"},
            "expect_error": True
        },
    ]
    
    for i, test in enumerate(edge_cases, 1):
        print(f"\n{i}. {test['name']}")
        print(f"   Params: {test['params']}")
        
        try:
            response = requests.get(API_ENDPOINT, params=test['params'], timeout=10)
            
            if test['expect_error']:
                if response.status_code >= 400:
                    print(f"   ✅ Correctly returned error: {response.status_code}")
                    error_data = response.json()
                    print(f"   📝 Error message: {error_data.get('detail', 'N/A')}")
                else:
                    print(f"   ⚠️  Expected error but got: {response.status_code}")
            else:
                print(f"   Status: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Unexpected Error: {e}")

if __name__ == "__main__":
    print("\n" + "🚀 Vector Search API Test Suite" + "\n")
    
    # Test main functionality
    success = test_search_endpoint()
    
    # Test edge cases
    if success:
        test_edge_cases()
    
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print("   - Verify results are semantically relevant")
    print("   - Check similarity scores are reasonable (>= threshold)")
    print("   - Confirm source filtering works correctly")
    print("   - Validate error handling for invalid inputs")
    print("=" * 60 + "\n")
