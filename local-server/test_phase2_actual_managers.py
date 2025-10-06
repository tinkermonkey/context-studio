#!/usr/bin/env python3
"""
Phase 2 QA: Unit tests for actual database manager directory creation
Tests the real manager implementations, not mocks
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path to import managers
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_pipeline_manager_creates_directory():
    """Test that PipelineDatabaseManager creates /datafiles/ directory"""
    from pipeline.manager import PipelineDatabaseManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = os.path.join(tmp_dir, "datafiles", "pipeline.db")

        # Ensure datafiles directory doesn't exist yet
        datafiles_dir = os.path.join(tmp_dir, "datafiles")
        assert not os.path.exists(datafiles_dir), "Directory should not exist yet"

        # Create manager - should create directory
        manager = PipelineDatabaseManager(db_path=test_db_path)

        # Verify directory was created
        assert os.path.exists(datafiles_dir), "PipelineDatabaseManager should create /datafiles/ directory"
        assert os.path.isdir(datafiles_dir), "Should be a directory"

        print("✓ PASS: PipelineDatabaseManager creates /datafiles/ directory")
        return True

def test_reference_manager_creates_directory():
    """Test that ReferenceManager creates /datafiles/ directory"""
    from reference_db.manager import ReferenceManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = os.path.join(tmp_dir, "datafiles", "reference.db")

        # Ensure datafiles directory doesn't exist yet
        datafiles_dir = os.path.join(tmp_dir, "datafiles")
        assert not os.path.exists(datafiles_dir), "Directory should not exist yet"

        # Create manager - should create directory
        manager = ReferenceManager(db_path=test_db_path)

        # Verify directory was created
        assert os.path.exists(datafiles_dir), "ReferenceManager should create /datafiles/ directory"
        assert os.path.isdir(datafiles_dir), "Should be a directory"

        print("✓ PASS: ReferenceManager creates /datafiles/ directory")
        return True

def test_dataset_manager_creates_directory():
    """Test that DatasetManager creates datasets directory"""
    from dataset.manager import DatasetManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = os.path.join(tmp_dir, "datafiles", "datasets", "dataset.db")

        # Ensure directories don't exist yet
        datafiles_dir = os.path.join(tmp_dir, "datafiles")
        datasets_dir = os.path.join(tmp_dir, "datafiles", "datasets")
        assert not os.path.exists(datafiles_dir), "Directory should not exist yet"

        # Create manager - should create directories
        manager = DatasetManager(db_path=test_db_path)

        # Verify directories were created
        assert os.path.exists(datafiles_dir), "DatasetManager should create /datafiles/ directory"
        assert os.path.exists(datasets_dir), "DatasetManager should create /datafiles/datasets/ directory"
        assert os.path.isdir(datasets_dir), "Should be a directory"

        print("✓ PASS: DatasetManager creates /datafiles/datasets/ directory")
        return True

def test_proxy_manager_creates_directory():
    """Test that ProxyManager creates /datafiles/ directory"""
    from nlp.proxy_manager import ProxyManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = os.path.join(tmp_dir, "datafiles", "proxy.db")

        # Ensure datafiles directory doesn't exist yet
        datafiles_dir = os.path.join(tmp_dir, "datafiles")
        assert not os.path.exists(datafiles_dir), "Directory should not exist yet"

        # Create manager - should create directory
        manager = ProxyManager(db_path=test_db_path)

        # Verify directory was created
        assert os.path.exists(datafiles_dir), "ProxyManager should create /datafiles/ directory"
        assert os.path.isdir(datafiles_dir), "Should be a directory"

        print("✓ PASS: ProxyManager creates /datafiles/ directory")
        return True

def test_managers_handle_existing_directory():
    """Test that all managers handle existing directory correctly (exist_ok=True)"""
    from pipeline.manager import PipelineDatabaseManager
    from reference_db.manager import ReferenceManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        datafiles_dir = os.path.join(tmp_dir, "datafiles")

        # Pre-create the directory
        os.makedirs(datafiles_dir, exist_ok=True)
        assert os.path.exists(datafiles_dir), "Directory should exist"

        # Create managers - should not raise error
        pipeline_db = os.path.join(tmp_dir, "datafiles", "pipeline.db")
        reference_db = os.path.join(tmp_dir, "datafiles", "reference.db")

        manager1 = PipelineDatabaseManager(db_path=pipeline_db)
        manager2 = ReferenceManager(db_path=reference_db)

        # Verify directory still exists and no errors occurred
        assert os.path.exists(datafiles_dir), "Directory should still exist"

        print("✓ PASS: Managers handle existing directory correctly")
        return True

def test_fresh_installation_creates_all_directories():
    """Test that a fresh installation creates all necessary directories"""
    from pipeline.manager import PipelineDatabaseManager
    from reference_db.manager import ReferenceManager
    from dataset.manager import DatasetManager
    from nlp.proxy_manager import ProxyManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Ensure nothing exists yet
        datafiles_dir = os.path.join(tmp_dir, "datafiles")
        datasets_dir = os.path.join(tmp_dir, "datafiles", "datasets")
        assert not os.path.exists(datafiles_dir), "Directory should not exist yet"

        # Initialize all managers as in a fresh installation
        pipeline_manager = PipelineDatabaseManager(
            db_path=os.path.join(tmp_dir, "datafiles", "pipeline.db")
        )
        reference_manager = ReferenceManager(
            db_path=os.path.join(tmp_dir, "datafiles", "reference.db")
        )
        dataset_manager = DatasetManager(
            db_path=os.path.join(tmp_dir, "datafiles", "datasets", "dataset.db")
        )
        proxy_manager = ProxyManager(
            db_path=os.path.join(tmp_dir, "datafiles", "proxy.db")
        )

        # Verify all directories were created
        assert os.path.exists(datafiles_dir), "Fresh installation should create /datafiles/"
        assert os.path.exists(datasets_dir), "Fresh installation should create /datafiles/datasets/"

        print("✓ PASS: Fresh installation creates all directories")
        return True

def test_directory_creation_pattern():
    """Verify all managers use os.makedirs(dir, exist_ok=True) pattern"""

    # Read the actual source files to verify pattern
    managers_to_check = [
        ('pipeline/manager.py', 'PipelineDatabaseManager'),
        ('reference_db/manager.py', 'ReferenceManager'),
        ('dataset/manager.py', 'DatasetManager'),
        ('nlp/proxy_manager.py', 'ProxyManager'),
    ]

    pattern_found = 0
    for file_path, manager_name in managers_to_check:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        with open(full_path, 'r') as f:
            content = f.read()
            # Check for the pattern
            if 'os.makedirs' in content and 'exist_ok=True' in content:
                pattern_found += 1
                print(f"  ✓ {manager_name} uses os.makedirs with exist_ok=True")

    assert pattern_found == 4, f"Expected 4 managers with correct pattern, found {pattern_found}"
    print("✓ PASS: All managers use os.makedirs(dir, exist_ok=True) pattern")
    return True

def run_all_tests():
    """Run all tests and report results"""
    tests = [
        ("PipelineDatabaseManager creates /datafiles/ directory", test_pipeline_manager_creates_directory),
        ("ReferenceManager creates /datafiles/ directory", test_reference_manager_creates_directory),
        ("DatasetManager creates datasets directory", test_dataset_manager_creates_directory),
        ("ProxyManager creates /datafiles/ directory", test_proxy_manager_creates_directory),
        ("Managers handle existing directory correctly", test_managers_handle_existing_directory),
        ("Fresh installation creates all directories", test_fresh_installation_creates_all_directories),
        ("All managers use os.makedirs(dir, exist_ok=True) pattern", test_directory_creation_pattern),
    ]

    print("\n" + "="*80)
    print("Phase 2 QA: Testing Actual Database Manager Directory Creation")
    print("="*80 + "\n")

    passed = 0
    failed = 0
    errors = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_name, str(e)))
            print(f"✗ FAIL: {test_name}")
            print(f"  Error: {e}")

    print("\n" + "="*80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*80 + "\n")

    if errors:
        print("FAILED TESTS:")
        for test_name, error in errors:
            print(f"  - {test_name}: {error}")
        return False
    else:
        print("✅ ALL TESTS PASSED - Ready for production")
        return True

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
