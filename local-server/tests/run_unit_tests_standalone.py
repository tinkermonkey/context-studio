"""
Standalone test runner for unit tests that bypasses conftest dependencies.
"""
import sys
import os

# Add local-server to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Run tests directly
import pytest

if __name__ == '__main__':
    # Run without conftest
    sys.exit(pytest.main([
        'tests/unit_tests/test_predicate_discovery.py',
        '-v',
        '--tb=short',
        '-p', 'no:cacheprovider',
        '--override-ini=python_files=test_*.py',
        '--override-ini=python_classes=Test*',
        '--override-ini=python_functions=test_*'
    ]))
