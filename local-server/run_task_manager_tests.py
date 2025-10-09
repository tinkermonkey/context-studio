"""
Standalone test runner for TaskManager tests.
Bypasses conftest to avoid import issues.
"""

import sys
import os
import asyncio
import subprocess

# Change to local-server directory
os.chdir('/workspace/local-server')
sys.path.insert(0, '/workspace/local-server')

def run_tests():
    """Run all TaskManager tests."""

    print("=" * 80)
    print("Running TaskManager Test Suite")
    print("=" * 80)

    test_files = [
        ('Unit Tests', 'tests/unit_tests/test_task_manager.py'),
        ('Integration Tests', 'tests/integration_tests/test_background_tasks_api.py'),
        ('E2E Tests', 'tests/e2e/test_task_manager_e2e.py'),
        ('Performance Tests', 'tests/performance_tests/test_task_manager_performance.py'),
    ]

    results = {}

    for test_name, test_file in test_files:
        print(f"\n{'=' * 80}")
        print(f"Running {test_name}: {test_file}")
        print(f"{'=' * 80}\n")

        # Run pytest without conftest
        cmd = [
            sys.executable, '-m', 'pytest',
            test_file,
            '-v',
            '--tb=short',
            '--no-header',
            '-p', 'no:cacheprovider',
            '--override-ini=addopts=',  # Override addopts to disable conftest loading
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
            )

            # Print output
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)

            results[test_name] = {
                'returncode': result.returncode,
                'passed': result.returncode == 0
            }

        except subprocess.TimeoutExpired:
            print(f"TIMEOUT: {test_name} exceeded 5 minute timeout")
            results[test_name] = {'returncode': 1, 'passed': False, 'timeout': True}
        except Exception as e:
            print(f"ERROR running {test_name}: {e}")
            results[test_name] = {'returncode': 1, 'passed': False, 'error': str(e)}

    # Print summary
    print(f"\n{'=' * 80}")
    print("TEST SUMMARY")
    print(f"{'=' * 80}\n")

    for test_name, result in results.items():
        status = "✅ PASSED" if result['passed'] else "❌ FAILED"
        print(f"{test_name}: {status}")
        if 'timeout' in result:
            print(f"  └─ Timed out")
        elif 'error' in result:
            print(f"  └─ Error: {result['error']}")

    total = len(results)
    passed = sum(1 for r in results.values() if r['passed'])

    print(f"\nTotal: {passed}/{total} test suites passed")

    return all(r['passed'] for r in results.values())

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
