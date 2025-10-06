#!/usr/bin/env python
"""
QA Test Runner for Phase 1: schema_org_path removal
Runs all tests without requiring full app dependencies
"""

import sys
import subprocess
from pathlib import Path

def run_unit_tests():
    """Run unit tests"""
    print("\n" + "="*80)
    print("RUNNING UNIT TESTS - Phase 1")
    print("="*80 + "\n")

    test_file = Path(__file__).parent / "tests" / "unit_tests" / "test_config_phase1.py"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
        "--noconftest"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode

def run_integration_tests():
    """Run integration tests"""
    print("\n" + "="*80)
    print("RUNNING INTEGRATION TESTS - Phase 1")
    print("="*80 + "\n")

    test_file = Path(__file__).parent / "tests" / "integration_tests" / "test_config_phase1_integration.py"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
        "--noconftest"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode

def run_e2e_tests():
    """Run end-to-end tests"""
    print("\n" + "="*80)
    print("RUNNING END-TO-END TESTS - Phase 1")
    print("="*80 + "\n")

    test_file = Path(__file__).parent / "tests" / "integration_tests" / "test_config_phase1_e2e.py"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
        "--noconftest"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode

def run_coverage():
    """Run coverage analysis"""
    print("\n" + "="*80)
    print("RUNNING COVERAGE ANALYSIS - Phase 1")
    print("="*80 + "\n")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/unit_tests/test_config_phase1.py",
        "tests/integration_tests/test_config_phase1_integration.py",
        "tests/integration_tests/test_config_phase1_e2e.py",
        "--cov=config",
        "--cov-report=term-missing",
        "--cov-report=json",
        "--noconftest"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("QA TEST SUITE - PHASE 1: schema_org_path Removal")
    print("="*80 + "\n")

    results = {}

    # Run unit tests
    results['unit'] = run_unit_tests()

    # Run integration tests
    results['integration'] = run_integration_tests()

    # Run e2e tests
    results['e2e'] = run_e2e_tests()

    # Run coverage
    results['coverage'] = run_coverage()

    # Summary
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)

    for test_type, code in results.items():
        status = "✓ PASSED" if code == 0 else "✗ FAILED"
        print(f"{test_type.upper()}: {status}")

    total_failures = sum(1 for code in results.values() if code != 0)

    if total_failures == 0:
        print("\n✓ ALL TESTS PASSED - PRODUCTION READY")
        return 0
    else:
        print(f"\n✗ {total_failures} TEST SUITE(S) FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
