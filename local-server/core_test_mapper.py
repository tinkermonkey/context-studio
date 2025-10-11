#!/usr/bin/env python3
"""
Core test failure mapping utility - clean implementation of the requested functionality.

This module provides the exact function signature and behavior requested by the user,
along with some enhancements for practical usage.
"""

import subprocess
import json
import re
import os
from pathlib import Path
from typing import Dict, List, Any


def extract_source_file(test: Dict[str, Any]) -> str:
    """
    Extract the primary source file being tested from test information.
    
    Args:
        test: Test information from pytest JSON report
        
    Returns:
        Relative path to the source file being tested
    """
    # Get the test file path
    test_file = test.get('nodeid', '').split('::')[0]
    
    # Try to map test file to source file using common patterns
    if test_file:
        # Common test file naming patterns
        patterns = [
            # test_module.py -> module.py
            (r'^test_(.+)\.py$', r'\1.py'),
            # test_module_integration.py -> module.py (in api/ or other dirs)
            (r'^test_(.+?)_(?:integration|unit|e2e)\.py$', r'\1.py'),
            # For files in tests/ directory, look for corresponding source
            (r'^tests/.*/test_(.+)\.py$', r'api/\1.py'),
            (r'^tests/.*/test_(.+)\.py$', r'\1.py'),
        ]
        
        test_path = Path(test_file)
        
        for pattern, replacement in patterns:
            if match := re.match(pattern, str(test_path)):
                candidate = re.sub(pattern, replacement, str(test_path))
                
                # Check if the source file exists
                potential_paths = [
                    candidate,
                    f'api/{Path(candidate).name}',
                    f'llm/{Path(candidate).name}',
                    f'database/{Path(candidate).name}',
                    f'services/{Path(candidate).name}',
                    f'utils/{Path(candidate).name}',
                ]
                
                for path in potential_paths:
                    if os.path.exists(path):
                        return path
    
    # If we can't determine source file, try extracting from traceback
    if 'call' in test and test['call'].get('longrepr'):
        longrepr = test['call']['longrepr']
        file_pattern = r'File "([^"]+\.py)"'
        matches = re.findall(file_pattern, longrepr)
        
        for match in matches:
            file_path = Path(match)
            # Skip test files and focus on source files
            if 'test' not in file_path.name.lower() and file_path.exists():
                try:
                    return str(file_path.relative_to(Path.cwd()))
                except ValueError:
                    return str(file_path)
    
    # Fallback to test file
    return test_file


def run_tests_with_file_mapping():
    """
    Run tests and map failures to source files.
    
    This is the exact function signature requested by the user.
    
    Returns:
        Dict mapping source files to their test failures
    """
    result = subprocess.run(
        ['pytest', '--json-report', '--json-report-file=report.json'],
        capture_output=True
    )
    
    with open('report.json') as f:
        report = json.load(f)
    
    # Create deterministic mapping
    file_failures = {}
    for test in report['tests']:
        if test['outcome'] == 'failed':
            source_file = extract_source_file(test)
            if source_file not in file_failures:
                file_failures[source_file] = []
            file_failures[source_file].append({
                'test_name': test['nodeid'],
                'error': test['call']['longrepr'],
                'line': test['call']['lineno']
            })
    
    return file_failures


def run_tests_with_file_mapping_enhanced(test_args: List[str] = None, 
                                        include_passed: bool = False,
                                        report_file: str = "report.json") -> Dict[str, List[Dict[str, Any]]]:
    """
    Enhanced version with additional options.
    
    Args:
        test_args: Additional arguments to pass to pytest
        include_passed: Whether to include passed tests
        report_file: Path to the JSON report file
        
    Returns:
        Dict mapping source files to their test results
    """
    # Prepare pytest command
    cmd = ['pytest', '--json-report', f'--json-report-file={report_file}']
    if test_args:
        cmd.extend(test_args)
    
    result = subprocess.run(cmd, capture_output=True)
    
    with open(report_file) as f:
        report = json.load(f)
    
    # Create mapping
    file_results = {}
    for test in report['tests']:
        outcome = test.get('outcome', 'unknown')
        
        # Skip passed tests unless requested
        if outcome == 'passed' and not include_passed:
            continue
        
        source_file = extract_source_file(test)
        if source_file not in file_results:
            file_results[source_file] = []
        
        # Enhanced error details
        error_info = {
            'test_name': test['nodeid'],
            'outcome': outcome,
            'error': test.get('call', {}).get('longrepr'),
            'line': test.get('call', {}).get('lineno'),
            'duration': test.get('duration', 0),
        }
        
        file_results[source_file].append(error_info)
    
    # Add summary
    summary = report.get('summary', {})
    file_results['_summary'] = {
        'total': summary.get('total', 0),
        'passed': summary.get('passed', 0),
        'failed': summary.get('failed', 0),
        'error': summary.get('error', 0),
        'skipped': summary.get('skipped', 0),
        'duration': summary.get('duration', 0),
        'outcome': 'passed' if summary.get('failed', 0) == 0 and summary.get('error', 0) == 0 else 'failed'
    }
    
    return file_results


# Example usage
if __name__ == "__main__":
    print("Testing core functionality...")
    
    try:
        # Run a small test to demonstrate
        failures = run_tests_with_file_mapping_enhanced(['tests/unit_tests/', '-x'])
        
        print("Test Results Summary:")
        print(f"Found results for {len(failures)} files")
        
        if '_summary' in failures:
            summary = failures['_summary']
            print(f"Total tests: {summary['total']}")
            print(f"Failed: {summary['failed']}")
            print(f"Passed: {summary['passed']}")
        
        # Show failures
        for source_file, results in failures.items():
            if source_file == '_summary':
                continue
                
            failed_tests = [r for r in results if r['outcome'] == 'failed']
            if failed_tests:
                print(f"\n❌ {source_file}: {len(failed_tests)} failure(s)")
                for failure in failed_tests[:2]:  # Show first 2
                    print(f"   - {failure['test_name']}")
                    
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure pytest-json-report is installed: pip install pytest-json-report")