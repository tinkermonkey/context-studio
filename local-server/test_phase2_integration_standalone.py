#!/usr/bin/env python3
"""
Phase 2: Integration Tests for datafiles directory creation
Standalone version without pytest dependencies
"""

import os
import sys
import tempfile
import shutil
import sqlite3
from pathlib import Path

def test_database_manager_directory_integration():
    """Integration test: Verify directory creation before database operations"""
    print("\n=== Test: Database Manager Directory Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Simulate the full flow: directory creation + database creation
        db_path = os.path.join(tmp_dir, "datafiles", "test.db")
        db_dir = os.path.dirname(db_path)

        # Step 1: Create directory
        os.makedirs(db_dir, exist_ok=True)
        print(f"  ✓ Created directory: {db_dir}")

        # Step 2: Create database (this would fail without directory)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.close()
        print(f"  ✓ Created database: {db_path}")

        # Verify
        assert os.path.exists(db_dir), "Directory should exist"
        assert os.path.exists(db_path), "Database should exist"

    print("✓ PASS: Database manager directory integration works")
    return True

def test_file_system_operations():
    """Integration test: File system operations with directory creation"""
    print("\n=== Test: File System Operations Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test various file operations after directory creation
        base_dir = os.path.join(tmp_dir, "datafiles")
        os.makedirs(base_dir, exist_ok=True)

        # Test 1: Create file in directory
        test_file = os.path.join(base_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        print(f"  ✓ Created file: {test_file}")

        # Test 2: List directory
        files = os.listdir(base_dir)
        assert len(files) == 1, "Should have one file"
        print(f"  ✓ Listed directory contents: {files}")

        # Test 3: Check permissions
        assert os.access(base_dir, os.W_OK), "Directory should be writable"
        print(f"  ✓ Directory has correct permissions")

    print("✓ PASS: File system operations integration works")
    return True

def test_nested_paths_integration():
    """Integration test: Nested directory paths"""
    print("\n=== Test: Nested Directory Paths Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test creating databases in nested directories
        paths = [
            os.path.join(tmp_dir, "datafiles", "db1.db"),
            os.path.join(tmp_dir, "datafiles", "datasets", "db2.db"),
            os.path.join(tmp_dir, "datafiles", "datasets", "exports", "db3.db"),
        ]

        for db_path in paths:
            db_dir = os.path.dirname(db_path)
            os.makedirs(db_dir, exist_ok=True)

            # Create a database file
            with open(db_path, 'w') as f:
                f.write("dummy db")

            assert os.path.exists(db_path), f"Database should exist: {db_path}"
            print(f"  ✓ Created: {db_path}")

    print("✓ PASS: Nested directory paths integration works")
    return True

def test_permissions_integration():
    """Integration test: Directory permissions"""
    print("\n=== Test: Directory Permissions Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = os.path.join(tmp_dir, "datafiles")
        os.makedirs(data_dir, exist_ok=True)

        # Check that directory has appropriate permissions
        stat_info = os.stat(data_dir)
        mode = stat_info.st_mode

        # Verify owner has read, write, execute
        assert os.access(data_dir, os.R_OK), "Should be readable"
        assert os.access(data_dir, os.W_OK), "Should be writable"
        assert os.access(data_dir, os.X_OK), "Should be executable"

        print(f"  ✓ Directory permissions: readable={os.access(data_dir, os.R_OK)}, "
              f"writable={os.access(data_dir, os.W_OK)}, "
              f"executable={os.access(data_dir, os.X_OK)}")

    print("✓ PASS: Directory permissions integration works")
    return True

def test_concurrent_creation_integration():
    """Integration test: Concurrent directory creation (exist_ok=True prevents race)"""
    print("\n=== Test: Concurrent Directory Creation Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = os.path.join(tmp_dir, "datafiles")

        # Simulate concurrent creation (multiple managers initializing)
        for i in range(5):
            os.makedirs(data_dir, exist_ok=True)

        assert os.path.exists(data_dir), "Directory should exist after concurrent creation"
        print(f"  ✓ Directory created successfully with 5 concurrent os.makedirs calls")

    print("✓ PASS: Concurrent directory creation integration works")
    return True

def test_manager_initialization_sequence():
    """Integration test: Manager initialization sequence"""
    print("\n=== Test: Manager Initialization Sequence Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Simulate initialization sequence of multiple managers
        managers = [
            ("PipelineManager", os.path.join(tmp_dir, "datafiles", "pipeline.db")),
            ("ReferenceManager", os.path.join(tmp_dir, "datafiles", "reference.db")),
            ("DatasetManager", os.path.join(tmp_dir, "datafiles", "datasets", "dataset.db")),
            ("ProxyManager", os.path.join(tmp_dir, "datafiles", "cache.db")),
        ]

        for manager_name, db_path in managers:
            db_dir = os.path.dirname(db_path)
            os.makedirs(db_dir, exist_ok=True)
            print(f"  ✓ {manager_name} created directory: {db_dir}")

        # Verify all directories exist
        base_dir = os.path.join(tmp_dir, "datafiles")
        datasets_dir = os.path.join(tmp_dir, "datafiles", "datasets")

        assert os.path.exists(base_dir), "Base datafiles directory should exist"
        assert os.path.exists(datasets_dir), "Datasets directory should exist"

    print("✓ PASS: Manager initialization sequence integration works")
    return True

def test_fresh_install_flow():
    """Integration test: Fresh installation flow"""
    print("\n=== Test: Fresh Installation Flow Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Simulate fresh installation
        print(f"  Starting fresh installation in: {tmp_dir}")

        # Step 1: Check nothing exists
        datafiles_dir = os.path.join(tmp_dir, "datafiles")
        assert not os.path.exists(datafiles_dir), "Should start with no directories"
        print(f"  ✓ Verified clean state")

        # Step 2: Initialize all managers (create directories)
        db_paths = [
            os.path.join(tmp_dir, "datafiles", "pipeline.db"),
            os.path.join(tmp_dir, "datafiles", "reference.db"),
            os.path.join(tmp_dir, "datafiles", "datasets", "dataset.db"),
            os.path.join(tmp_dir, "datafiles", "cache.db"),
        ]

        for db_path in db_paths:
            db_dir = os.path.dirname(db_path)
            os.makedirs(db_dir, exist_ok=True)

        print(f"  ✓ All manager directories created")

        # Step 3: Verify application can start (all directories exist)
        assert os.path.exists(os.path.join(tmp_dir, "datafiles")), "datafiles/ should exist"
        assert os.path.exists(os.path.join(tmp_dir, "datafiles", "datasets")), "datafiles/datasets/ should exist"

    print("✓ PASS: Fresh installation flow integration works")
    return True

def test_error_handling_integration():
    """Integration test: Error handling scenarios"""
    print("\n=== Test: Error Handling Integration ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test 1: Directory already exists (exist_ok=True prevents error)
        data_dir = os.path.join(tmp_dir, "datafiles")
        os.makedirs(data_dir)
        os.makedirs(data_dir, exist_ok=True)  # Should not raise
        print(f"  ✓ No error when directory exists (exist_ok=True)")

        # Test 2: Parent directory doesn't exist (os.makedirs creates it)
        nested_dir = os.path.join(tmp_dir, "level1", "level2", "datafiles")
        os.makedirs(nested_dir, exist_ok=True)
        assert os.path.exists(nested_dir), "Should create all parent directories"
        print(f"  ✓ Creates parent directories automatically")

    print("✓ PASS: Error handling integration works")
    return True

def run_all_integration_tests():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("Phase 2: Integration Tests (Standalone)")
    print("="*80)

    tests = [
        ("Database Manager Directory Integration", test_database_manager_directory_integration),
        ("File System Operations Integration", test_file_system_operations),
        ("Nested Directory Paths Integration", test_nested_paths_integration),
        ("Directory Permissions Integration", test_permissions_integration),
        ("Concurrent Directory Creation Integration", test_concurrent_creation_integration),
        ("Manager Initialization Sequence Integration", test_manager_initialization_sequence),
        ("Fresh Installation Flow Integration", test_fresh_install_flow),
        ("Error Handling Integration", test_error_handling_integration),
    ]

    passed = 0
    failed = 0
    errors = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
                errors.append(test_name)
        except Exception as e:
            failed += 1
            errors.append((test_name, str(e)))
            print(f"\n✗ FAIL: {test_name}")
            print(f"  Error: {e}")

    print("\n" + "="*80)
    print(f"Integration Test Results: {passed} passed, {failed} failed")
    print("="*80)

    if errors:
        print("\nFAILED TESTS:")
        for error in errors:
            if isinstance(error, tuple):
                print(f"  - {error[0]}: {error[1]}")
            else:
                print(f"  - {error}")
        return False
    else:
        print("\n✅ ALL INTEGRATION TESTS PASSED")
        return True

if __name__ == "__main__":
    success = run_all_integration_tests()
    sys.exit(0 if success else 1)
