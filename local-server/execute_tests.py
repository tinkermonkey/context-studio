#!/usr/bin/env python3
"""
Simple test executor for external predicates tests
"""
import subprocess
import sys
import os

# Change to the local-server directory
os.chdir('/workspace/local-server')

# Add local-server to Python path
sys.path.insert(0, '/workspace/local-server')

# Import pytest and run tests programmatically
import pytest

print("=" * 80)
print("EXECUTING EXTERNAL PREDICATES TEST SUITE")
print("=" * 80)
print()

# Run unit tests
print("📋 Running Unit Tests...")
print("-" * 80)
unit_result = pytest.main([
    'tests/unit_tests/test_external_predicates.py',
    '-v',
    '--tb=short'
])
print()

# Run integration tests
print("🔗 Running Integration Tests...")
print("-" * 80)
integration_result = pytest.main([
    'tests/integration_tests/test_external_predicates_integration.py',
    '-v',
    '--tb=short'
])
print()

# Run e2e tests
print("🌐 Running End-to-End Tests...")
print("-" * 80)
e2e_result = pytest.main([
    'tests/integration_tests/test_external_predicates_e2e.py',
    '-v',
    '--tb=short'
])
print()

# Summary
print("=" * 80)
print("TEST EXECUTION SUMMARY")
print("=" * 80)
print(f"Unit Tests: {'✅ PASSED' if unit_result == 0 else '❌ FAILED'}")
print(f"Integration Tests: {'✅ PASSED' if integration_result == 0 else '❌ FAILED'}")
print(f"End-to-End Tests: {'✅ PASSED' if e2e_result == 0 else '❌ FAILED'}")
print()

# Exit with combined result
sys.exit(max(unit_result, integration_result, e2e_result))
