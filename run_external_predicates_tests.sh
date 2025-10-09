#!/bin/bash
set -e

echo "========================================="
echo "EXTERNAL PREDICATES TEST SUITE"
echo "========================================="
echo ""

cd /workspace/local-server

echo "========================================="
echo "1. UNIT TESTS (12 tests expected)"
echo "========================================="
python3 -m pytest tests/unit_tests/test_external_predicates.py -v --tb=short
UNIT_EXIT=$?
echo ""

echo "========================================="
echo "2. INTEGRATION TESTS (20 tests expected)"
echo "========================================="
python3 -m pytest tests/integration_tests/test_external_predicates_integration.py -v --tb=short
INTEGRATION_EXIT=$?
echo ""

echo "========================================="
echo "3. END-TO-END TESTS (11 tests expected)"
echo "========================================="
python3 -m pytest tests/integration_tests/test_external_predicates_e2e.py -v --tb=short
E2E_EXIT=$?
echo ""

echo "========================================="
echo "TEST EXECUTION SUMMARY"
echo "========================================="
echo "Unit Tests Exit Code: $UNIT_EXIT"
echo "Integration Tests Exit Code: $INTEGRATION_EXIT"
echo "E2E Tests Exit Code: $E2E_EXIT"
echo ""

if [ $UNIT_EXIT -eq 0 ] && [ $INTEGRATION_EXIT -eq 0 ] && [ $E2E_EXIT -eq 0 ]; then
    echo "ALL TESTS PASSED ✓"
    exit 0
else
    echo "SOME TESTS FAILED ✗"
    exit 1
fi
