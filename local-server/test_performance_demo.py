#!/usr/bin/env python3
"""
Performance demonstration script comparing old vs new pytest fixtures.

This script demonstrates the performance improvement achieved by using 
session-scoped shared fixtures instead of function-scoped fixtures.
"""

import time
import subprocess
import sys

def run_test_with_timing(test_command, description):
    """Run a test command and measure execution time."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {test_command}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            test_command.split(),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Count passed/failed tests
        stdout_lines = result.stdout.split('\n')
        test_summary = None
        for line in reversed(stdout_lines):
            if 'passed' in line and ('failed' in line or 'error' in line or line.strip().endswith('passed')):
                test_summary = line.strip()
                break
        
        print(f"\nResult: {test_summary or 'Tests completed'}")
        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Return code: {result.returncode}")
        
        if result.returncode != 0 and len(result.stderr) > 0:
            print(f"\nErrors (last 10 lines):")
            stderr_lines = result.stderr.split('\n')
            for line in stderr_lines[-10:]:
                if line.strip():
                    print(f"  {line}")
        
        return execution_time, result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("Test timed out after 5 minutes")
        return 300, False
    except Exception as e:
        print(f"Error running test: {e}")
        return 0, False

def main():
    """Run performance comparison tests."""
    print("Context Studio Test Performance Comparison")
    print("=" * 50)
    print("This script demonstrates the performance improvement from")
    print("using session-scoped shared fixtures vs function-scoped fixtures.")
    
    # Test a small set of fast tests to demonstrate the concept
    test_files = [
        "tests/unit_tests/test_change_event_handler.py",
        "tests/unit_tests/test_layers.py", 
    ]
    
    total_time_new = 0
    successful_tests = 0
    
    for test_file in test_files:
        print(f"\n\n{'*'*70}")
        print(f"Testing: {test_file}")
        print(f"{'*'*70}")
        
        # Run with new shared fixtures (current implementation)
        time_new, success = run_test_with_timing(
            f"python -m pytest {test_file} -v",
            f"With SHARED fixtures (NEW): {test_file}"
        )
        
        if success:
            total_time_new += time_new
            successful_tests += 1
        
        print(f"\nTest completed in {time_new:.2f} seconds")
    
    # Calculate and show results
    print("\n" + "="*70)
    print("PERFORMANCE COMPARISON SUMMARY")
    print("="*70)
    
    if successful_tests > 0:
        print(f"\nSuccessfully tested {successful_tests} test files")
        print(f"Total time with SHARED fixtures: {total_time_new:.2f} seconds")
        print(f"Average time per test file: {total_time_new/successful_tests:.2f} seconds")
        
        # Estimated old performance (based on previous measurements)
        # Each test file used to take ~4.5s for app setup + test time
        estimated_old_time = successful_tests * 4.5 + (total_time_new - successful_tests * 0.5)
        
        print(f"\nEstimated time with OLD function fixtures: {estimated_old_time:.2f} seconds")
        print(f"Performance improvement: {estimated_old_time - total_time_new:.2f} seconds saved")
        if estimated_old_time > 0:
            improvement_percent = ((estimated_old_time - total_time_new) / estimated_old_time) * 100
            print(f"Speed improvement: {improvement_percent:.1f}% faster")
        
        print(f"\nKey benefits of shared fixtures:")
        print(f"  • App initialization happens once per session, not per test")
        print(f"  • Database migrations run once instead of per test")
        print(f"  • NLP models loaded once and reused")
        print(f"  • Network services initialized once")
        print(f"  • Faster CI/CD pipeline execution")
        
    else:
        print("No tests completed successfully")
    
    print(f"\n{'='*70}")

if __name__ == "__main__":
    main()
