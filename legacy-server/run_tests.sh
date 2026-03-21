#!/bin/bash
# Test runner script for Context Studio back-end tests
# This script ensures tests are run with the virtual environment activated

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}Error: Virtual environment not found at .venv${NC}"
    echo "Please create a virtual environment first:"
    echo "  python -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source .venv/bin/activate

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found in virtual environment${NC}"
    echo "Please install dependencies:"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Run pytest with all arguments passed to this script
echo -e "${GREEN}Running tests...${NC}"
echo ""

if [ $# -eq 0 ]; then
    # No arguments provided, run all tests
    python -m pytest tests/
else
    # Run pytest with provided arguments
    python -m pytest "$@"
fi

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo ""
    echo -e "${RED}✗ Some tests failed${NC}"
fi

exit $exit_code
