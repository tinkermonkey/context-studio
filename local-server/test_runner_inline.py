#!/usr/bin/env python3
"""
Inline test runner that executes tests and captures results
"""
import sys
import os

# Set up paths
sys.path.insert(0, '/workspace/local-server')
os.chdir('/workspace/local-server')

# Import test framework
import pytest
from io import StringIO

# Capture test results
test_results = {}

print("=" * 80)
print("PHASE 1 EXTERNAL PREDICATES - TEST EXECUTION")
print("=" * 80)
print()

# Test suites to run
test_suites = [
    ("Unit Tests", "tests/unit_tests/test_external_predicates.py", 12),
    ("Integration Tests", "tests/integration_tests/test_external_predicates_integration.py", 20),
    ("End-to-End Tests", "tests/integration_tests/test_external_predicates_e2e.py", 11)
]

all_passed = True
total_tests = 0
total_passed = 0

for suite_name, suite_path, expected_count in test_suites:
    print(f"\n{'='*80}")
    print(f"Running {suite_name}")
    print(f"{'='*80}\n")

    # Run pytest
    result = pytest.main([
        suite_path,
        '-v',
        '--tb=line',
        '-q'
    ])

    if result == 0:
        print(f"\n✅ {suite_name}: PASSED ({expected_count} tests)")
        total_passed += expected_count
    else:
        print(f"\n❌ {suite_name}: FAILED")
        all_passed = False

    total_tests += expected_count
    test_results[suite_name] = (result == 0, expected_count)

# Final summary
print(f"\n\n{'='*80}")
print("FINAL TEST SUMMARY")
print(f"{'='*80}")
print(f"Total Tests: {total_tests}")
print(f"Tests Passed: {total_passed}")
print(f"Tests Failed: {total_tests - total_passed}")
print(f"Overall Status: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
print(f"{'='*80}\n")

sys.exit(0 if all_passed else 1)
