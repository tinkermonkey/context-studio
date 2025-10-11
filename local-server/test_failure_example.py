#!/usr/bin/env python3
"""
Simple example script showing how to use the TestFailureMapper class.
This demonstrates the core functionality requested in the user's example.
"""

import json
import subprocess
from test_runner import TestFailureMapper


def run_tests_with_file_mapping():
    """Run tests and map failures to source files - simplified version."""
    mapper = TestFailureMapper()
    
    # This implements the exact functionality from the user's request
    # Run a small subset for demo purposes
    result = subprocess.run(
        ['pytest', '--json-report', '--json-report-file=report.json', 'tests/unit_tests/', '-x'],
        capture_output=True
    )
    
    with open('report.json') as f:
        report = json.load(f)
    
    # Create deterministic mapping
    file_failures = {}
    for test in report['tests']:
        if test['outcome'] == 'failed':
            source_file = mapper.extract_source_file(test)
            if source_file not in file_failures:
                file_failures[source_file] = []
            file_failures[source_file].append({
                'test_name': test['nodeid'],
                'error': test['call']['longrepr'],
                'line': test['call']['lineno']
            })
    
    return file_failures


def enhanced_run_tests_with_file_mapping(test_pattern=None):
    """Enhanced version with better error handling and more features."""
    mapper = TestFailureMapper()
    
    # Prepare test arguments
    test_args = []
    if test_pattern:
        test_args.append(test_pattern)
    
    # Use the enhanced mapper
    results = mapper.run_tests_with_file_mapping(
        test_args=test_args,
        include_passed=False  # Only failures
    )
    
    return results


def print_failure_summary(file_failures):
    """Print a summary of test failures by source file."""
    print("🔍 Test Failure Summary by Source File")
    print("=" * 50)
    
    for source_file, failures in file_failures.items():
        if source_file == '_summary':
            continue
            
        print(f"\n📁 {source_file}")
        print(f"   {len(failures)} failure(s)")
        
        for failure in failures:
            print(f"   ❌ {failure['test_name']}")
            if failure.get('line'):
                print(f"      Line: {failure['line']}")


if __name__ == "__main__":
    # Example usage
    print("Running simple test failure mapping...")
    
    try:
        # Simple version (as requested by user)
        failures = run_tests_with_file_mapping()
        print_failure_summary(failures)
        
        print("\n" + "="*60)
        print("Enhanced version with additional features...")
        
        # Enhanced version
        enhanced_results = enhanced_run_tests_with_file_mapping("tests/unit_tests/")
        print(f"Found {len(enhanced_results)} files with test results")
        
    except FileNotFoundError:
        print("No report.json found. Please run pytest with --json-report first.")
    except Exception as e:
        print(f"Error: {e}")