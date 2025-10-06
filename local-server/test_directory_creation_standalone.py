#!/usr/bin/env python3
"""
Standalone test script for verifying datafiles directory creation.
This can be run independently without pytest infrastructure.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path


def test_pipeline_db_creates_datafiles_directory():
    """Test that PipelineDatabaseManager creates /datafiles/ directory if it doesn't exist."""
    print("Testing: PipelineDatabaseManager creates /datafiles/ directory...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up pipeline database path in a non-existent datafiles directory
        db_dir = os.path.join(temp_dir, "datafiles")
        db_path = os.path.join(db_dir, "pipeline.db")

        # Ensure directory does not exist initially
        assert not os.path.exists(db_dir), "Directory should not exist initially"

        # Import and initialize pipeline manager
        from pipeline.manager import PipelineDatabaseManager

        manager = PipelineDatabaseManager(pipeline_db_path=db_path)

        # Verify directory was created
        assert os.path.exists(db_dir), "Directory should have been created"
        assert os.path.isdir(db_dir), "Path should be a directory"

        # Verify database file was created
        assert os.path.exists(db_path), "Database file should have been created"

        # Clean up
        manager.engine.dispose()

    print("✓ PASS: PipelineDatabaseManager creates /datafiles/ directory")


def test_reference_db_creates_datafiles_directory():
    """Test that ReferenceManager creates /datafiles/ directory if it doesn't exist."""
    print("Testing: ReferenceManager creates /datafiles/ directory...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up reference database path in a non-existent datafiles directory
        db_dir = os.path.join(temp_dir, "datafiles")
        db_path = os.path.join(db_dir, "reference.db")

        # Ensure directory does not exist initially
        assert not os.path.exists(db_dir), "Directory should not exist initially"

        # Import and initialize reference manager
        from reference_db.manager import ReferenceManager
        from reference_db.config import ReferenceConfig

        config = ReferenceConfig()
        manager = ReferenceManager(config, db_path=db_path)

        # Verify directory was created
        assert os.path.exists(db_dir), "Directory should have been created"
        assert os.path.isdir(db_dir), "Path should be a directory"

        # Verify database file was created
        assert os.path.exists(db_path), "Database file should have been created"

        # Clean up
        manager.close()

    print("✓ PASS: ReferenceManager creates /datafiles/ directory")


def test_dataset_manager_creates_datasets_directory():
    """Test that DatasetManager creates datasets directory if it doesn't exist."""
    print("Testing: DatasetManager creates datasets directory...")

    with tempfile.TemporaryDirectory() as temp_dir:
        datasets_dir = os.path.join(temp_dir, "datasets")

        # Ensure directory does not exist initially
        assert not os.path.exists(datasets_dir), "Directory should not exist initially"

        # Import and initialize dataset manager
        from dataset.manager import DatasetManager

        config_path = os.path.join(temp_dir, "datasets.json")
        manager = DatasetManager(
            datasets_config_path=config_path,
            datasets_directory=datasets_dir
        )

        # Verify directory was created
        assert os.path.exists(datasets_dir), "Directory should have been created"
        assert os.path.isdir(datasets_dir), "Path should be a directory"

    print("✓ PASS: DatasetManager creates datasets directory")


def test_fresh_install_creates_all_directories():
    """Test that all required directories are created on fresh installation."""
    print("Testing: Fresh installation creates all directories...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Simulate fresh installation - no datafiles directory
        datafiles_dir = os.path.join(temp_dir, "datafiles")
        assert not os.path.exists(datafiles_dir), "Directory should not exist initially"

        # Initialize all managers that use datafiles
        from pipeline.manager import PipelineDatabaseManager
        from reference_db.manager import ReferenceManager
        from reference_db.config import ReferenceConfig

        # Create pipeline manager
        pipeline_db_path = os.path.join(datafiles_dir, "pipeline.db")
        pipeline_manager = PipelineDatabaseManager(pipeline_db_path=pipeline_db_path)

        # Verify datafiles directory was created
        assert os.path.exists(datafiles_dir), "Datafiles directory should have been created"

        # Create reference manager
        reference_db_path = os.path.join(datafiles_dir, "reference.db")
        reference_config = ReferenceConfig()
        reference_manager = ReferenceManager(reference_config, db_path=reference_db_path)

        # Verify all databases exist
        assert os.path.exists(pipeline_db_path), "Pipeline database should exist"
        assert os.path.exists(reference_db_path), "Reference database should exist"

        # Clean up
        pipeline_manager.engine.dispose()
        reference_manager.close()

    print("✓ PASS: Fresh installation creates all directories")


def test_handles_existing_directory():
    """Test that managers work when directory already exists."""
    print("Testing: Managers handle existing directory (exist_ok=True)...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up pipeline database path with existing datafiles directory
        db_dir = os.path.join(temp_dir, "datafiles")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "pipeline.db")

        # Import and initialize pipeline manager
        from pipeline.manager import PipelineDatabaseManager

        manager = PipelineDatabaseManager(pipeline_db_path=db_path)

        # Verify no errors occurred
        assert os.path.exists(db_dir), "Directory should exist"
        assert os.path.exists(db_path), "Database file should exist"

        # Clean up
        manager.engine.dispose()

    print("✓ PASS: Managers handle existing directory correctly")


def test_directory_creation_pattern():
    """Verify all database managers use os.makedirs(dir, exist_ok=True) pattern."""
    print("Testing: All managers use consistent directory creation pattern...")

    import inspect

    # List of manager modules to check
    tests = [
        ('pipeline.manager', 'PipelineDatabaseManager'),
        ('reference_db.manager', 'ReferenceManager'),
        ('dataset.manager', 'DatasetManager'),
    ]

    for module_name, class_name in tests:
        module = __import__(module_name, fromlist=[class_name])

        # Get source code of the module
        source = inspect.getsource(module)

        # Check for directory creation pattern
        assert 'os.makedirs' in source, f"{module_name} should use os.makedirs for directory creation"
        assert 'exist_ok=True' in source, f"{module_name} should use exist_ok=True to handle existing directories"

    print("✓ PASS: All managers use os.makedirs(dir, exist_ok=True) pattern")


def main():
    """Run all tests."""
    print("=" * 70)
    print("Phase 2: Datafiles Directory Creation Tests")
    print("=" * 70)
    print()

    tests = [
        test_pipeline_db_creates_datafiles_directory,
        test_reference_db_creates_datafiles_directory,
        test_dataset_manager_creates_datasets_directory,
        test_handles_existing_directory,
        test_fresh_install_creates_all_directories,
        test_directory_creation_pattern,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
            print()
        except AssertionError as e:
            print(f"✗ FAIL: {test_func.__name__}")
            print(f"  Error: {e}")
            print()
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {test_func.__name__}")
            print(f"  Exception: {type(e).__name__}: {e}")
            print()
            failed += 1

    print("=" * 70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
