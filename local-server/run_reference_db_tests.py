#!/usr/bin/env python3
"""
Standalone test runner for reference_db unit tests.
Bypasses conftest.py to avoid dependency issues.
"""

import sys
import os
import tempfile
import traceback
from pathlib import Path

# Add local-server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import test functions
from tests.unit_tests.test_reference_db import (
    test_reference_node_creation,
    test_reference_node_unique_constraint,
    test_reference_node_different_sources,
    test_reference_link_creation,
    test_reference_link_cascade_delete,
    test_reference_config_defaults,
    test_reference_config_https_validation,
    test_reference_config_similarity_threshold_validation,
    test_reference_config_batch_size_validation,
    test_reference_config_retry_count_validation,
    test_reference_manager_initialization,
    test_reference_manager_schema_version_detection,
    test_reference_manager_rebuild_creates_backup,
    test_reference_manager_atomic_lock_prevents_race_condition,
    test_reference_manager_get_status,
    test_reference_manager_cleanup,
    test_sqlite_vec_extension_loading,
)


def run_test(test_func, test_name, *args):
    """Run a single test function and report results."""
    try:
        test_func(*args)
        print(f"✓ PASS: {test_name}")
        return True
    except Exception as e:
        print(f"✗ FAIL: {test_name}")
        print(f"  Error: {str(e)}")
        traceback.print_exc()
        print()
        return False


def main():
    """Run all reference_db unit tests."""
    print("="*70)
    print("Running Reference DB Unit Tests")
    print("="*70)
    print()

    passed = 0
    failed = 0
    skipped = 0

    # Create temp directory for tests
    temp_dir = Path(tempfile.mkdtemp(prefix="ref_db_test_"))

    tests = [
        ("test_reference_node_creation", test_reference_node_creation, []),
        ("test_reference_node_unique_constraint", test_reference_node_unique_constraint, [temp_dir]),
        ("test_reference_node_different_sources", test_reference_node_different_sources, [temp_dir]),
        ("test_reference_link_creation", test_reference_link_creation, []),
        ("test_reference_link_cascade_delete", test_reference_link_cascade_delete, [temp_dir]),
        ("test_reference_config_defaults", test_reference_config_defaults, []),
        ("test_reference_config_https_validation", test_reference_config_https_validation, []),
        ("test_reference_config_similarity_threshold_validation", test_reference_config_similarity_threshold_validation, []),
        ("test_reference_config_batch_size_validation", test_reference_config_batch_size_validation, []),
        ("test_reference_config_retry_count_validation", test_reference_config_retry_count_validation, []),
        ("test_reference_manager_initialization", test_reference_manager_initialization, [temp_dir]),
        ("test_reference_manager_schema_version_detection", test_reference_manager_schema_version_detection, [temp_dir]),
        ("test_reference_manager_rebuild_creates_backup", test_reference_manager_rebuild_creates_backup, [temp_dir]),
        ("test_reference_manager_atomic_lock_prevents_race_condition", test_reference_manager_atomic_lock_prevents_race_condition, [temp_dir]),
        ("test_reference_manager_get_status", test_reference_manager_get_status, [temp_dir]),
        ("test_reference_manager_cleanup", test_reference_manager_cleanup, [temp_dir]),
        ("test_sqlite_vec_extension_loading", test_sqlite_vec_extension_loading, [temp_dir]),
    ]

    for test_name, test_func, args in tests:
        if run_test(test_func, test_name, *args):
            passed += 1
        else:
            failed += 1

    print()
    print("="*70)
    print("Test Summary")
    print("="*70)
    print(f"Total:   {passed + failed + skipped}")
    print(f"Passed:  {passed}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    print()

    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
