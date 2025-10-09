#!/usr/bin/env python3
"""
Test runner for external predicates test suite.
Executes all external predicates tests and provides detailed results.
"""

import sys
import os

# Add local-server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

def run_test_suite(test_file, test_name, expected_count):
    """Run a test suite and return results."""
    print(f"\n{'='*60}")
    print(f"{test_name} ({expected_count} tests expected)")
    print(f"{'='*60}\n")

    exit_code = pytest.main([
        test_file,
        '-v',
        '--tb=short'
    ])

    return {
        'name': test_name,
        'exit_code': exit_code,
        'expected': expected_count
    }

def main():
    """Main test execution function."""
    print("\n" + "="*60)
    print("EXTERNAL PREDICATES TEST SUITE EXECUTION")
    print("="*60)

    test_suites = [
        {
            'file': 'tests/unit_tests/test_external_predicates.py',
            'name': 'Unit Tests',
            'expected': 12
        },
        {
            'file': 'tests/integration_tests/test_external_predicates_integration.py',
            'name': 'Integration Tests',
            'expected': 20
        },
        {
            'file': 'tests/integration_tests/test_external_predicates_e2e.py',
            'name': 'End-to-End Tests',
            'expected': 11
        }
    ]

    results = []

    for suite in test_suites:
        result = run_test_suite(suite['file'], suite['name'], suite['expected'])
        results.append(result)

    # Print summary
    print("\n" + "="*60)
    print("TEST EXECUTION SUMMARY")
    print("="*60 + "\n")

    for result in results:
        status = "PASSED" if result['exit_code'] == 0 else "FAILED"
        print(f"{result['name']}: {status} (Exit Code: {result['exit_code']}, Expected: {result['expected']} tests)")

    print("\n" + "="*60)

    all_passed = all(r['exit_code'] == 0 for r in results)

    if all_passed:
        print("ALL TEST SUITES PASSED")
        return 0
    else:
        print("SOME TEST SUITES FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
