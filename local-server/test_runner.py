#!/usr/bin/env python3
"""
Test runner script for agents that maps test failures to source files.

This script runs pytest with JSON reporting and creates a deterministic mapping
of test failures to their corresponding source files for easier debugging and
analysis by automated agents.
"""

import subprocess
import json
import os
import sys
import re
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import argparse


class TestFailureMapper:
    """Maps test failures to source files for automated analysis."""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.report_file = self.project_root / "test_report.json"
        
    def extract_source_file(self, test_info: Dict[str, Any]) -> str:
        """
        Extract the primary source file being tested from test information.
        
        Args:
            test_info: Test information from pytest JSON report
            
        Returns:
            Relative path to the source file being tested
        """
        # Get the test file path
        test_file = test_info.get('nodeid', '').split('::')[0]
        
        # Try to map test file to source file
        source_file = self._map_test_to_source(test_file)
        
        # If we can't determine source file, try extracting from traceback
        if not source_file and 'call' in test_info and test_info['call'].get('longrepr'):
            source_file = self._extract_from_traceback(test_info['call']['longrepr'])
        
        return source_file or test_file
    
    def _map_test_to_source(self, test_file: str) -> Optional[str]:
        """
        Map a test file to its corresponding source file.
        
        Args:
            test_file: Path to the test file
            
        Returns:
            Relative path to the corresponding source file, if determinable
        """
        if not test_file:
            return None
            
        test_path = Path(test_file)
        
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
        
        for pattern, replacement in patterns:
            if match := re.match(pattern, str(test_path)):
                candidate = re.sub(pattern, replacement, str(test_path))
                
                # Check if the source file exists
                potential_paths = [
                    self.project_root / candidate,
                    self.project_root / 'api' / Path(candidate).name,
                    self.project_root / 'llm' / Path(candidate).name,
                    self.project_root / 'database' / Path(candidate).name,
                    self.project_root / 'services' / Path(candidate).name,
                    self.project_root / 'utils' / Path(candidate).name,
                ]
                
                for path in potential_paths:
                    if path.exists():
                        return str(path.relative_to(self.project_root))
        
        return None
    
    def _extract_from_traceback(self, longrepr: str) -> Optional[str]:
        """
        Extract source file from error traceback.
        
        Args:
            longrepr: Long representation of the error from pytest
            
        Returns:
            Relative path to source file mentioned in traceback
        """
        if not longrepr:
            return None
            
        # Look for file paths in traceback
        file_pattern = r'File "([^"]+\.py)"'
        matches = re.findall(file_pattern, longrepr)
        
        for match in matches:
            file_path = Path(match)
            
            # Skip test files and focus on source files
            if 'test' not in file_path.name.lower():
                try:
                    # Try to make it relative to project root
                    if file_path.is_absolute():
                        rel_path = file_path.relative_to(self.project_root)
                    else:
                        rel_path = file_path
                    
                    if (self.project_root / rel_path).exists():
                        return str(rel_path)
                except (ValueError, OSError):
                    continue
        
        return None
    
    def extract_error_details(self, test_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract detailed error information from test failure.
        
        Args:
            test_info: Test information from pytest JSON report
            
        Returns:
            Dictionary containing error details
        """
        error_details = {
            'test_name': test_info.get('nodeid', 'Unknown'),
            'outcome': test_info.get('outcome', 'Unknown'),
            'error': None,
            'line': None,
            'duration': test_info.get('duration', 0),
            'keywords': test_info.get('keywords', []),
        }
        
        # Extract call information
        if 'call' in test_info:
            call_info = test_info['call']
            error_details['error'] = call_info.get('longrepr', 'No error message')
            error_details['line'] = call_info.get('lineno')
            
        # Extract setup/teardown failures
        if test_info.get('outcome') == 'error':
            if 'setup' in test_info and test_info['setup'].get('outcome') == 'failed':
                error_details['error'] = test_info['setup'].get('longrepr', 'Setup failed')
                error_details['phase'] = 'setup'
            elif 'teardown' in test_info and test_info['teardown'].get('outcome') == 'failed':
                error_details['error'] = test_info['teardown'].get('longrepr', 'Teardown failed')
                error_details['phase'] = 'teardown'
        
        return error_details
    
    def run_tests_with_file_mapping(self, 
                                  test_args: Optional[List[str]] = None,
                                  include_passed: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run tests and map failures to source files.
        
        Args:
            test_args: Additional arguments to pass to pytest
            include_passed: Whether to include passed tests in the output
            
        Returns:
            Dictionary mapping source files to their test results
        """
        # Prepare pytest command
        cmd = [
            'pytest',
            '--json-report',
            f'--json-report-file={self.report_file}',
            '-v'  # Verbose output
        ]
        
        if test_args:
            cmd.extend(test_args)
        
        print(f"Running: {' '.join(cmd)}")
        
        # Run pytest
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            print(f"Pytest exit code: {result.returncode}")
            if result.stdout:
                print("STDOUT:", result.stdout[-1000:])  # Last 1000 chars
            if result.stderr:
                print("STDERR:", result.stderr[-1000:])  # Last 1000 chars
                
        except Exception as e:
            print(f"Error running pytest: {e}")
            return {}
        
        # Load and parse report
        if not self.report_file.exists():
            print(f"Report file {self.report_file} not found")
            return {}
        
        try:
            with open(self.report_file) as f:
                report = json.load(f)
        except Exception as e:
            print(f"Error loading report file: {e}")
            return {}
        
        # Create deterministic mapping
        file_results = {}
        
        for test in report.get('tests', []):
            outcome = test.get('outcome', 'unknown')
            
            # Skip passed tests unless requested
            if outcome == 'passed' and not include_passed:
                continue
            
            # Extract source file
            source_file = self.extract_source_file(test)
            
            # Initialize file entry if needed
            if source_file not in file_results:
                file_results[source_file] = []
            
            # Extract error details
            error_details = self.extract_error_details(test)
            
            file_results[source_file].append(error_details)
        
        # Add summary information
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
    
    def format_results(self, file_results: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format test results for human-readable output.
        
        Args:
            file_results: Results from run_tests_with_file_mapping
            
        Returns:
            Formatted string representation
        """
        output = []
        
        # Summary
        if '_summary' in file_results:
            summary = file_results['_summary']
            output.append("=" * 60)
            output.append("TEST RESULTS SUMMARY")
            output.append("=" * 60)
            output.append(f"Total: {summary['total']}")
            output.append(f"Passed: {summary['passed']}")
            output.append(f"Failed: {summary['failed']}")
            output.append(f"Errors: {summary['error']}")
            output.append(f"Skipped: {summary['skipped']}")
            output.append(f"Duration: {summary['duration']:.2f}s")
            output.append(f"Overall: {summary['outcome'].upper()}")
            output.append("")
        
        # File-by-file results
        for source_file, tests in file_results.items():
            if source_file == '_summary':
                continue
                
            failed_tests = [t for t in tests if t['outcome'] in ['failed', 'error']]
            if not failed_tests:
                continue
                
            output.append(f"Source File: {source_file}")
            output.append("-" * 60)
            
            for test in failed_tests:
                output.append(f"  ❌ {test['test_name']}")
                if test['line']:
                    output.append(f"     Line: {test['line']}")
                if test['error']:
                    # Truncate long error messages
                    error_msg = str(test['error'])
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200] + "..."
                    output.append(f"     Error: {error_msg}")
                output.append("")
        
        return "\n".join(output)


def main():
    """Main entry point for the test runner script."""
    parser = argparse.ArgumentParser(description="Run tests and map failures to source files")
    parser.add_argument("test_args", nargs="*", help="Additional arguments to pass to pytest")
    parser.add_argument("--include-passed", action="store_true", help="Include passed tests in output")
    parser.add_argument("--output", "-o", help="Output file for results (JSON format)")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--project-root", help="Project root directory")
    
    args = parser.parse_args()
    
    # Initialize mapper
    mapper = TestFailureMapper(args.project_root)
    
    # Run tests and get results
    try:
        results = mapper.run_tests_with_file_mapping(
            test_args=args.test_args,
            include_passed=args.include_passed
        )
        
        # Output results
        if args.format == "json":
            output_data = json.dumps(results, indent=2)
        else:
            output_data = mapper.format_results(results)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_data)
            print(f"Results written to {args.output}")
        else:
            print(output_data)
        
        # Exit with appropriate code
        summary = results.get('_summary', {})
        if summary.get('outcome') == 'failed':
            sys.exit(1)
            
    except Exception as e:
        print(f"Error running test mapper: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()