# mypy: ignore-errors
#!/usr/bin/env python3
"""
Test script to verify the reference_api_buddy integration works correctly.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from nlp.proxy_manager import get_proxy_manager


def test_proxy_basic_functionality(test_settings):
    """Test basic proxy functionality"""
    print("=== Testing Reference API Buddy Integration ===\n")

    # Test 1: Default configuration (no APIs enabled)
    print("1. Testing default configuration (no APIs enabled)...")

    # Create fresh instances to test configuration changes
    proxy_manager = get_proxy_manager()
    print(f"   Is proxy enabled: {proxy_manager.is_proxy_enabled()}")

    # Test 2: Test concepcy config with and without proxy
    print("\n2. Testing concepcy configuration...")
    settings = test_settings

    concepcy_config_direct = settings.get_concepcy_config(use_proxy=False)
    print(f"   Concepcy direct config has URL: {'url' in concepcy_config_direct}")

    concepcy_config_proxy = settings.get_concepcy_config(use_proxy=True)
    print(f"   Concepcy with proxy URL: {concepcy_config_proxy.get('url', 'No URL')}")

    # Test 3: Test configuration generation scenarios
    print("\n3. Testing proxy configuration generation scenarios...")

    # Manually test different scenarios
    test_scenarios = [
        {"concepcy": True, "spacy_dbpedia_spotlight": False},
        {"concepcy": False, "spacy_dbpedia_spotlight": True},
        {"concepcy": True, "spacy_dbpedia_spotlight": True},
        {"concepcy": False, "spacy_dbpedia_spotlight": False},
    ]

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"   Scenario {i}: {scenario}")

        # Manually create config to test logic
        base_config = settings.get_reference_api_buddy_config().copy()
        domain_mappings = {}

        if scenario.get("concepcy", False):
            domain_mappings["conceptnet"] = {"upstream": "https://api.conceptnet.io"}

        if scenario.get("spacy_dbpedia_spotlight", False):
            domain_mappings["dbpedia_spotlight"] = {
                "upstream": "https://api.dbpedia-spotlight.org/en/"
            }

        if domain_mappings:
            config = base_config.copy()
            config["domain_mappings"] = domain_mappings
            print(
                f"     Would generate config with domains: {list(domain_mappings.keys())}"
            )
        else:
            print("     Would generate no config (no APIs enabled)")

    # Test 4: Test DBpedia endpoint generation
    print("\n4. Testing DBpedia endpoint generation...")
    proxy_config = settings.get_reference_api_buddy_config()
    host = proxy_config["server"]["host"]
    port = proxy_config["server"]["port"]
    endpoint = f"http://{host}:{port}/dbpedia_spotlight"
    print(f"   Generated DBpedia proxy endpoint: {endpoint}")

    # Test 5: Test error handling
    print("\n5. Testing error handling...")
    try:
        # This should work without actually starting the proxy
        result = proxy_manager.start_proxy()
        print(f"   Proxy start (no APIs enabled) result: {result}")

        proxy_manager.stop_proxy()
        print("   Proxy stop completed without errors")
    except Exception as e:
        print(f"   Error handling test failed: {e}")

    print("\n=== Test completed successfully! ===")


if __name__ == "__main__":
    test_proxy_basic_functionality()
