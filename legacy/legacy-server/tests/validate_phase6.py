"""
Validation script for Phase 6 implementation.
Tests the core functionality without requiring full test infrastructure.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():  # noqa: E302
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        import services.reference_filter_service  # noqa: F401
        import reference_db.models  # noqa: F401
        import reference_db.manager  # noqa: F401
        import reference_db.config  # noqa: F401
        import database.models  # noqa: F401
        import config  # noqa: F401

        print("  ✓ All imports successful")
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_configuration():
    """Test that configuration includes filtering settings."""
    print("\nTesting configuration...")
    try:
        from config import get_settings

        settings = get_settings()

        # Check for enable_relevance_filtering setting
        assert hasattr(
            settings.reference_sources, "enable_relevance_filtering"
        ), "Missing enable_relevance_filtering setting"  # noqa: E501

        # Check for filter_cache_ttl setting
        assert hasattr(
            settings.reference_sources, "filter_cache_ttl"
        ), "Missing filter_cache_ttl setting"

        print(
            f"  ✓ enable_relevance_filtering: {settings.reference_sources.enable_relevance_filtering}"
        )  # noqa: E501
        print(
            f"  ✓ filter_cache_ttl: {settings.reference_sources.filter_cache_ttl}"
        )  # noqa: E501
        return True
    except Exception as e:
        print(f"  ✗ Configuration test failed: {e}")
        return False


def test_api_endpoint():
    """Test that API endpoint includes filtering parameter."""
    print("\nTesting API endpoint...")
    try:
        from api import reference
        import inspect

        # Get the get_node_links function
        func = reference.get_node_links

        # Check if it has apply_relevance_filter parameter
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        assert (
            "apply_relevance_filter" in params
        ), "Missing apply_relevance_filter parameter in get_node_links"

        print("  ✓ get_node_links has apply_relevance_filter parameter")
        print(f"  ✓ Parameters: {', '.join(params)}")
        return True
    except Exception as e:
        print(f"  ✗ API endpoint test failed: {e}")
        return False


def test_filter_service_basic():
    """Test basic filter service functionality."""
    print("\nTesting filter service...")
    try:
        from services.reference_filter_service import ReferenceFilterService
        from unittest.mock import Mock
        from reference_db.models import ReferenceLink

        # Create mocks
        mock_session = Mock()
        mock_manager = Mock()

        # Mock query to return empty predicates
        mock_session.query.return_value.all.return_value = []

        # Create service
        service = ReferenceFilterService(mock_session, mock_manager)

        # Test with no predicates marked
        mock_links = [Mock(spec=ReferenceLink) for _ in range(3)]
        filtered, stats = service.filter_links(mock_links)

        assert (
            len(filtered) == 3
        ), "Should return all links when no filtering configured"  # noqa: E501
        assert (
            stats["filtering_active"] is False
        ), "Filtering should not be active"  # noqa: E501
        assert stats["total_before"] == 3, "Should track total_before"
        assert stats["total_after"] == 3, "Should track total_after"
        assert stats["filtered_count"] == 0, "Should track filtered_count"

        print("  ✓ Filter service creates successfully")
        print("  ✓ Returns all links when no predicates marked")
        print("  ✓ Statistics calculated correctly")
        return True
    except Exception as e:
        print(f"  ✗ Filter service test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_filter_statistics():
    """Test filter statistics endpoint."""
    print("\nTesting filter statistics...")
    try:
        from services.reference_filter_service import ReferenceFilterService
        from unittest.mock import Mock

        # Create mocks
        mock_session = Mock()
        mock_manager = Mock()

        # Mock predicates with different relevance states
        mock_preds = [
            Mock(
                id="p1",
                is_relevant=True,
                mapping=json.dumps([{"source": "test", "external_id": "test1"}]),
            ),  # noqa: E501
            Mock(
                id="p2",
                is_relevant=False,
                mapping=json.dumps([{"source": "test", "external_id": "test2"}]),
            ),  # noqa: E501
            Mock(
                id="p3",
                is_relevant=None,
                mapping=json.dumps([{"source": "test", "external_id": "test3"}]),
            ),  # noqa: E501
        ]
        mock_session.query.return_value.all.return_value = mock_preds

        service = ReferenceFilterService(mock_session, mock_manager)
        stats = service.get_filter_statistics()

        assert stats["total_predicates"] == 3, "Should count total predicates"
        assert stats["relevant_count"] == 1, "Should count relevant predicates"
        assert (
            stats["irrelevant_count"] == 1
        ), "Should count irrelevant predicates"  # noqa: E501
        assert stats["unmapped_count"] == 1, "Should count unmapped predicates"
        assert (
            len(stats["relevant_external_predicates"]) == 1
        ), "Should list relevant external predicates"  # noqa: E501
        assert (
            len(stats["irrelevant_external_predicates"]) == 1
        ), "Should list irrelevant external predicates"  # noqa: E501

        print("  ✓ Statistics calculated correctly")
        print(f"    - Total: {stats['total_predicates']}")
        print(f"    - Relevant: {stats['relevant_count']}")
        print(f"    - Irrelevant: {stats['irrelevant_count']}")
        print(f"    - Unmapped: {stats['unmapped_count']}")
        return True
    except Exception as e:
        print(f"  ✗ Statistics test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Phase 6 Implementation Validation")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_configuration()))
    results.append(("API Endpoint", test_api_endpoint()))
    results.append(("Filter Service", test_filter_service_basic()))
    results.append(("Filter Statistics", test_filter_statistics()))

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All validation tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
