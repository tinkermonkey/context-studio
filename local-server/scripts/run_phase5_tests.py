#!/usr/bin/env python
"""Standalone test runner for Phase 5 tests (no pytest fixtures needed)."""

import sys
from pathlib import Path

# Add local-server to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the test classes
from tests.unit_tests.test_phase5_cleanup import TestDeprecatedCodeRemoval, TestMetricsImplementation

def run_tests():
    """Run all Phase 5 tests."""
    test_count = 0
    failed_count = 0

    # Test deprecated code removal
    print("=" * 60)
    print("Testing Deprecated Code Removal")
    print("=" * 60)

    removal_tests = TestDeprecatedCodeRemoval()
    for method_name in dir(removal_tests):
        if method_name.startswith("test_"):
            test_count += 1
            try:
                method = getattr(removal_tests, method_name)
                method()
                print(f"✓ {method_name}")
            except AssertionError as e:
                failed_count += 1
                print(f"✗ {method_name}: {e}")
            except Exception as e:
                failed_count += 1
                print(f"✗ {method_name}: Unexpected error: {e}")

    # Test metrics implementation
    print("\n" + "=" * 60)
    print("Testing Metrics Implementation")
    print("=" * 60)

    metrics_tests = TestMetricsImplementation()
    for method_name in dir(metrics_tests):
        if method_name.startswith("test_"):
            test_count += 1
            try:
                method = getattr(metrics_tests, method_name)
                method()
                print(f"✓ {method_name}")
            except AssertionError as e:
                failed_count += 1
                print(f"✗ {method_name}: {e}")
            except Exception as e:
                failed_count += 1
                print(f"✗ {method_name}: Unexpected error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print(f"Tests run: {test_count}")
    print(f"Passed: {test_count - failed_count}")
    print(f"Failed: {failed_count}")
    print("=" * 60)

    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    sys.exit(run_tests())
