#!/usr/bin/env python3
"""
QA Test Runner for External Predicates Phase 1

Runs all tests (unit, integration, e2e) and generates reports.
"""

import sys
import os
import subprocess
from datetime import datetime

# Add local-server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ANSI color codes
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"{BLUE}{text}{NC}")
    print(f"{'=' * 60}\n")


def print_step(step_num, text):
    """Print a step header."""
    print(f"\n{YELLOW}Step {step_num}: {text}{NC}")
    print("-" * 60)


def print_success(text):
    """Print success message."""
    print(f"{GREEN}✓ {text}{NC}")


def print_error(text):
    """Print error message."""
    print(f"{RED}✗ {text}{NC}")


def run_test_suite(name, test_path):
    """
    Run a test suite and return results.

    Args:
        name: Name of the test suite
        test_path: Path to test file

    Returns:
        tuple: (success: bool, exit_code: int, output: str)
    """
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', test_path, '-v', '--tb=short'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        success = result.returncode == 0
        return success, result.returncode, result.stdout

    except Exception as e:
        print_error(f"Failed to run {name}: {e}")
        return False, -1, str(e)


def run_coverage_report():
    """Generate coverage report for all tests."""
    try:
        test_files = [
            'tests/unit_tests/test_external_predicates.py',
            'tests/integration_tests/test_external_predicates_integration.py',
            'tests/integration_tests/test_external_predicates_e2e.py',
        ]

        result = subprocess.run(
            [
                sys.executable, '-m', 'pytest',
                *test_files,
                '--cov=reference_db',
                '--cov-report=term-missing',
                '--cov-report=html:htmlcov',
                '-v'
            ],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        return result.returncode == 0

    except Exception as e:
        print_error(f"Coverage generation failed: {e}")
        return False


def main():
    """Main test execution function."""
    print_header("External Predicates Test Suite - Phase 1")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # Step 1: Unit Tests
    print_step(1, "Running Unit Tests")
    success, exit_code, output = run_test_suite(
        "Unit Tests",
        "tests/unit_tests/test_external_predicates.py"
    )
    results['unit'] = {'success': success, 'exit_code': exit_code}

    if success:
        print_success("Unit tests passed")
    else:
        print_error(f"Unit tests failed with exit code {exit_code}")
        return 1

    # Step 2: Integration Tests
    print_step(2, "Running Integration Tests")
    success, exit_code, output = run_test_suite(
        "Integration Tests",
        "tests/integration_tests/test_external_predicates_integration.py"
    )
    results['integration'] = {'success': success, 'exit_code': exit_code}

    if success:
        print_success("Integration tests passed")
    else:
        print_error(f"Integration tests failed with exit code {exit_code}")
        return 1

    # Step 3: End-to-End Tests
    print_step(3, "Running End-to-End Tests")
    success, exit_code, output = run_test_suite(
        "End-to-End Tests",
        "tests/integration_tests/test_external_predicates_e2e.py"
    )
    results['e2e'] = {'success': success, 'exit_code': exit_code}

    if success:
        print_success("End-to-end tests passed")
    else:
        print_error(f"End-to-end tests failed with exit code {exit_code}")
        return 1

    # Step 4: Coverage Report
    print_step(4, "Generating Coverage Report")
    coverage_success = run_coverage_report()

    if coverage_success:
        print_success("Coverage report generated")
        print("   HTML report: htmlcov/index.html")
    else:
        print_error("Coverage generation failed (non-critical)")

    # Summary
    print_header("Test Execution Summary")
    print(f"{GREEN}All Tests Passed Successfully!{NC}\n")
    print("Results:")
    print(f"  - Unit Tests: {'PASSED' if results['unit']['success'] else 'FAILED'}")
    print(f"  - Integration Tests: {'PASSED' if results['integration']['success'] else 'FAILED'}")
    print(f"  - End-to-End Tests: {'PASSED' if results['e2e']['success'] else 'FAILED'}")
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
