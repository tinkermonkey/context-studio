#!/bin/bash
#
# Test execution script for External Predicates Phase 1
# This script runs all tests (unit, integration, e2e) and generates coverage reports
#

set -e

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "External Predicates Test Suite"
echo "Phase 1: Database Schema and Migration"
echo "========================================="
echo ""

# Navigate to local-server directory
cd "$(dirname "$0")/.."

# Set PYTHONPATH
export PYTHONPATH="$(pwd):$PYTHONPATH"

echo -e "${YELLOW}Step 1: Running Unit Tests${NC}"
echo "------------------------------------"
python3 -m pytest tests/unit_tests/test_external_predicates.py -v --tb=short
UNIT_EXIT=$?

if [ $UNIT_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo -e "${RED}✗ Unit tests failed with exit code $UNIT_EXIT${NC}"
    exit $UNIT_EXIT
fi

echo ""
echo -e "${YELLOW}Step 2: Running Integration Tests${NC}"
echo "------------------------------------"
python3 -m pytest tests/integration_tests/test_external_predicates_integration.py -v --tb=short
INTEGRATION_EXIT=$?

if [ $INTEGRATION_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Integration tests passed${NC}"
else
    echo -e "${RED}✗ Integration tests failed with exit code $INTEGRATION_EXIT${NC}"
    exit $INTEGRATION_EXIT
fi

echo ""
echo -e "${YELLOW}Step 3: Running End-to-End Tests${NC}"
echo "------------------------------------"
python3 -m pytest tests/integration_tests/test_external_predicates_e2e.py -v --tb=short
E2E_EXIT=$?

if [ $E2E_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ End-to-end tests passed${NC}"
else
    echo -e "${RED}✗ End-to-end tests failed with exit code $E2E_EXIT${NC}"
    exit $E2E_EXIT
fi

echo ""
echo -e "${YELLOW}Step 4: Generating Coverage Report${NC}"
echo "------------------------------------"
python3 -m pytest \
    tests/unit_tests/test_external_predicates.py \
    tests/integration_tests/test_external_predicates_integration.py \
    tests/integration_tests/test_external_predicates_e2e.py \
    --cov=reference_db \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    -v

COVERAGE_EXIT=$?

if [ $COVERAGE_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Coverage report generated${NC}"
    echo "   HTML report: htmlcov/index.html"
else
    echo -e "${RED}✗ Coverage generation failed${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}All Tests Passed Successfully!${NC}"
echo "========================================="
echo ""
echo "Summary:"
echo "  - Unit Tests: PASSED ($UNIT_EXIT)"
echo "  - Integration Tests: PASSED ($INTEGRATION_EXIT)"
echo "  - End-to-End Tests: PASSED ($E2E_EXIT)"
echo ""
