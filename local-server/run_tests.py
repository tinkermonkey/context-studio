#!/usr/bin/env python3
"""Test runner script for external predicates tests."""

import sys
import os

# Add local-server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

if __name__ == "__main__":
    # Run with verbose output
    exit_code = pytest.main([
        "-v",
        "--tb=short",
        "tests/unit_tests/test_external_predicates.py"
    ])
    sys.exit(exit_code)
