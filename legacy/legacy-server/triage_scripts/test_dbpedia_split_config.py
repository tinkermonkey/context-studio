#!/usr/bin/env python3
"""
Smoke test for DBpedia split configuration (dbpedia_lookup + dbpedia_sparql).

This script tests:
1. Configuration loads correctly with split DBpedia sources
2. DBpedia lookup service works (search/data retrieval)
3. DBpedia SPARQL service works (SPARQL queries)
4. Proxy routing is correct for both services
"""

import asyncio
import sys
from pathlib import Path

# Add local-server to path
sys.path.insert(0, str(Path(__file__).parent))

from config import SourceType, get_settings
from reference_api.sources.dbpedia import DBpediaSource


async def test_configuration():
    """Test that configuration loads correctly."""
    print("\n🔧 Testing Configuration")
    print("=" * 60)

    try:
        settings = get_settings()

        # Check that both new sources exist
        assert hasattr(
            settings.reference_sources, "dbpedia_lookup"
        ), "❌ dbpedia_lookup not found in configuration"
        print("✅ dbpedia_lookup configuration found")

        assert hasattr(
            settings.reference_sources, "dbpedia_sparql"
        ), "❌ dbpedia_sparql not found in configuration"
        print("✅ dbpedia_sparql configuration found")

        # Check URLs
        lookup_config = settings.reference_sources.dbpedia_lookup
        sparql_config = settings.reference_sources.dbpedia_sparql

        assert (
            lookup_config.upstream_url == "https://lookup.dbpedia.org"
        ), f"❌ Wrong lookup URL: {lookup_config.upstream_url}"
        print(f"✅ dbpedia_lookup URL: {lookup_config.upstream_url}")

        assert (
            sparql_config.upstream_url == "https://dbpedia.org"
        ), f"❌ Wrong SPARQL URL: {sparql_config.upstream_url}"
        print(f"✅ dbpedia_sparql URL: {sparql_config.upstream_url}")

        # Check proxy settings
        print(f"   dbpedia_lookup proxy enabled: {lookup_config.use_proxy}")
        print(f"   dbpedia_sparql proxy enabled: {sparql_config.use_proxy}")

        # Check that both are in enabled sources
        enabled_sources = settings.get_enabled_sources()
        assert (
            "dbpedia_lookup" in enabled_sources
        ), "❌ dbpedia_lookup not in enabled sources"
        assert (
            "dbpedia_sparql" in enabled_sources
        ), "❌ dbpedia_sparql not in enabled sources"
        print(f"✅ Both sources in enabled list: {enabled_sources}")

        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def test_dbpedia_lookup():
    """Test DBpedia lookup service (search)."""
    print("\n🔍 Testing DBpedia Lookup Service")
    print("=" * 60)

    try:
        settings = get_settings()
        lookup_config = settings.reference_sources.dbpedia_lookup

        # Create source instance
        async with DBpediaSource(SourceType.DBPEDIA, lookup_config) as source:
            print("📡 Testing search for 'Python'...")

            # Test search
            response = await source.search("Python", limit=3)

            if response.success:
                print(f"✅ Search successful! Found {response.total_results} results")
                if response.results:
                    for i, result in enumerate(response.results[:3], 1):
                        # Results are model objects, access attributes directly
                        label = (
                            result.label
                            if hasattr(result, "label")
                            else result.get("label", "N/A")
                        )
                        uri = (
                            result.uri
                            if hasattr(result, "uri")
                            else result.get("uri", "N/A")
                        )
                        print(f"   {i}. {label} - {uri}")
                return True
            else:
                print(f"❌ Search failed: {response.error}")
                return False

    except Exception as e:
        print(f"❌ Lookup test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_dbpedia_sparql():
    """Test DBpedia SPARQL service."""
    print("\n📊 Testing DBpedia SPARQL Service")
    print("=" * 60)

    try:
        settings = get_settings()
        sparql_config = settings.reference_sources.dbpedia_sparql

        # Create source instance
        async with DBpediaSource(SourceType.DBPEDIA, sparql_config) as source:
            print("📡 Testing SPARQL query for RDF properties...")

            # Simple SPARQL query to get a few properties
            sparql_query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT DISTINCT ?property ?label
            WHERE {
              ?property rdf:type rdf:Property .
              OPTIONAL { ?property rdfs:label ?label . FILTER(lang(?label) = 'en') }
            }
            LIMIT 5
            """

            response = await source.sparql_query(sparql_query, format="json")

            if response.success:
                print("✅ SPARQL query successful!")
                if response.results:
                    # Handle different response formats
                    if isinstance(response.results, dict):
                        if "results" in response.results:
                            bindings = response.results["results"].get("bindings", [])
                        elif "bindings" in response.results:
                            bindings = response.results["bindings"]
                        else:
                            bindings = []
                    else:
                        bindings = []

                    print(f"   Found {len(bindings)} properties:")
                    for i, binding in enumerate(bindings[:5], 1):
                        prop = binding.get("property", {}).get("value", "N/A")
                        label = binding.get("label", {}).get("value", "N/A")
                        print(f"   {i}. {label} ({prop})")
                else:
                    print("   Query returned no results")
                return True
            else:
                print(f"❌ SPARQL query failed: {response.error}")
                return False

    except Exception as e:
        print(f"❌ SPARQL test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_proxy_routing():
    """Test that proxy routing is configured correctly."""
    print("\n🔀 Testing Proxy Routing")
    print("=" * 60)

    try:
        settings = get_settings()

        # Get proxy domain mappings
        if settings.proxy_server.enabled:
            mappings = settings.get_proxy_domain_mappings()

            print(
                f"✅ Proxy is enabled on {settings.proxy_server.host}:{settings.proxy_server.port}"
            )
            print(f"   Domain mappings configured: {list(mappings.keys())}")

            if "dbpedia_lookup" in mappings:
                lookup_mapping = mappings["dbpedia_lookup"]
                print("✅ dbpedia_lookup mapping:")
                print(f"   → Upstream: {lookup_mapping['upstream']}")
                print(f"   → Keys: {lookup_mapping.get('enabled_keys', [])}")
            else:
                print(
                    "⚠️  dbpedia_lookup not in proxy mappings (proxy may be disabled)"
                )

            if "dbpedia_sparql" in mappings:
                sparql_mapping = mappings["dbpedia_sparql"]
                print("✅ dbpedia_sparql mapping:")
                print(f"   → Upstream: {sparql_mapping['upstream']}")
                print(f"   → Keys: {sparql_mapping.get('enabled_keys', [])}")
            else:
                print(
                    "⚠️  dbpedia_sparql not in proxy mappings (proxy may be disabled)"
                )

            return True
        else:
            print("⚠️  Proxy server is disabled in configuration")
            return True

    except Exception as e:
        print(f"❌ Proxy routing test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all smoke tests."""
    print("\n" + "=" * 60)
    print("🚬 DBpedia Split Configuration Smoke Test")
    print("=" * 60)

    results = []

    # Test 1: Configuration
    results.append(("Configuration", await test_configuration()))

    # Test 2: Proxy Routing
    results.append(("Proxy Routing", await test_proxy_routing()))

    # Test 3: DBpedia Lookup
    results.append(("DBpedia Lookup", await test_dbpedia_lookup()))

    # Test 4: DBpedia SPARQL
    results.append(("DBpedia SPARQL", await test_dbpedia_sparql()))

    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("⚠️  Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
