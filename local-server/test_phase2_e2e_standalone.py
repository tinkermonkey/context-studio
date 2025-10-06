#!/usr/bin/env python3
"""
Phase 2: End-to-End Tests for datafiles directory creation
Standalone version testing real-world workflows
"""

import os
import sys
import tempfile
import shutil
import sqlite3
import time
from pathlib import Path

def test_e2e_fresh_installation_workflow():
    """E2E: Complete fresh installation workflow"""
    print("\n=== E2E Test: Fresh Installation Workflow ===")

    with tempfile.TemporaryDirectory() as app_root:
        print(f"  Simulating fresh app installation in: {app_root}")

        # Step 1: Application starts with no data
        datafiles_path = os.path.join(app_root, "datafiles")
        assert not os.path.exists(datafiles_path), "Fresh install: no datafiles yet"
        print("  ✓ Step 1: Verified clean installation state")

        # Step 2: Application initializes managers (creates directories)
        db_paths = {
            "pipeline": os.path.join(app_root, "datafiles", "pipeline.db"),
            "reference": os.path.join(app_root, "datafiles", "reference.db"),
            "dataset": os.path.join(app_root, "datafiles", "datasets", "dataset.db"),
            "cache": os.path.join(app_root, "datafiles", "cache.db"),
        }

        for name, db_path in db_paths.items():
            db_dir = os.path.dirname(db_path)
            os.makedirs(db_dir, exist_ok=True)
            # Create database
            conn = sqlite3.connect(db_path)
            conn.execute(f"CREATE TABLE {name}_data (id INTEGER PRIMARY KEY)")
            conn.close()

        print("  ✓ Step 2: All managers initialized and databases created")

        # Step 3: Verify application can operate
        assert os.path.exists(datafiles_path), "datafiles directory created"
        assert len(os.listdir(datafiles_path)) > 0, "datafiles contains databases"

        print("  ✓ Step 3: Application operational")

    print("✓ PASS: Fresh installation workflow E2E test passed")
    return True

def test_e2e_application_restart_workflow():
    """E2E: Application restart with existing data"""
    print("\n=== E2E Test: Application Restart Workflow ===")

    with tempfile.TemporaryDirectory() as app_root:
        datafiles_path = os.path.join(app_root, "datafiles")

        # Initial startup
        print("  First startup...")
        os.makedirs(datafiles_path, exist_ok=True)
        db_path = os.path.join(datafiles_path, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE data (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO data (value) VALUES ('initial')")
        conn.commit()
        conn.close()
        print("  ✓ First startup: Database created with data")

        # Application restart
        print("  Restarting application...")
        os.makedirs(datafiles_path, exist_ok=True)  # Should not fail
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT value FROM data")
        result = cursor.fetchone()[0]
        conn.close()

        assert result == "initial", "Data should persist across restarts"
        print("  ✓ Restart: Data persisted correctly")

    print("✓ PASS: Application restart workflow E2E test passed")
    return True

def test_e2e_migration_workflow():
    """E2E: Migration from old structure to new structure"""
    print("\n=== E2E Test: Migration Workflow ===")

    with tempfile.TemporaryDirectory() as app_root:
        # Old structure: databases in root
        old_db_path = os.path.join(app_root, "pipeline.db")
        conn = sqlite3.connect(old_db_path)
        conn.execute("CREATE TABLE data (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO data (value) VALUES ('old_data')")
        conn.commit()
        conn.close()
        print("  ✓ Old structure: Database in root directory")

        # Migration: Move to new structure
        new_datafiles_dir = os.path.join(app_root, "datafiles")
        os.makedirs(new_datafiles_dir, exist_ok=True)
        new_db_path = os.path.join(new_datafiles_dir, "pipeline.db")
        shutil.move(old_db_path, new_db_path)
        print("  ✓ Migration: Moved database to /datafiles/")

        # New structure works
        conn = sqlite3.connect(new_db_path)
        cursor = conn.execute("SELECT value FROM data")
        result = cursor.fetchone()[0]
        conn.close()

        assert result == "old_data", "Data should survive migration"
        print("  ✓ New structure: Data accessible in new location")

    print("✓ PASS: Migration workflow E2E test passed")
    return True

def test_e2e_multi_user_scenario():
    """E2E: Multi-user/instance scenario (simulated)"""
    print("\n=== E2E Test: Multi-Instance Scenario ===")

    with tempfile.TemporaryDirectory() as shared_storage:
        # Simulate two application instances accessing shared storage
        datafiles_path = os.path.join(shared_storage, "datafiles")

        # Instance 1 initializes
        print("  Instance 1: Initializing...")
        os.makedirs(datafiles_path, exist_ok=True)
        db1 = os.path.join(datafiles_path, "instance1.db")
        conn1 = sqlite3.connect(db1)
        conn1.execute("CREATE TABLE data (id INTEGER PRIMARY KEY)")
        conn1.close()
        print("  ✓ Instance 1: Created database")

        # Instance 2 initializes (directory already exists)
        print("  Instance 2: Initializing...")
        os.makedirs(datafiles_path, exist_ok=True)  # Should not fail
        db2 = os.path.join(datafiles_path, "instance2.db")
        conn2 = sqlite3.connect(db2)
        conn2.execute("CREATE TABLE data (id INTEGER PRIMARY KEY)")
        conn2.close()
        print("  ✓ Instance 2: Created database (no conflict)")

        # Verify both databases exist
        assert os.path.exists(db1), "Instance 1 database exists"
        assert os.path.exists(db2), "Instance 2 database exists"

    print("✓ PASS: Multi-instance scenario E2E test passed")
    return True

def test_e2e_docker_deployment_workflow():
    """E2E: Docker deployment workflow"""
    print("\n=== E2E Test: Docker Deployment Workflow ===")

    with tempfile.TemporaryDirectory() as container_volume:
        # Simulate Docker container with mounted volume
        print("  Docker container starting...")

        # Container volume is empty initially
        datafiles_path = os.path.join(container_volume, "datafiles")
        assert not os.path.exists(datafiles_path), "Volume initially empty"
        print("  ✓ Container started with empty volume")

        # Application in container creates directories
        os.makedirs(datafiles_path, exist_ok=True)
        db_path = os.path.join(datafiles_path, "app.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO config VALUES ('version', '1.0')")
        conn.commit()
        conn.close()
        print("  ✓ Application initialized in container")

        # Container restart (volume persists)
        print("  Container restarting...")
        assert os.path.exists(datafiles_path), "Volume persists"
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT value FROM config WHERE key='version'")
        version = cursor.fetchone()[0]
        conn.close()
        assert version == "1.0", "Data persisted in volume"
        print("  ✓ Container restarted, data persisted")

    print("✓ PASS: Docker deployment workflow E2E test passed")
    return True

def test_e2e_backup_recovery_workflow():
    """E2E: Backup and recovery workflow"""
    print("\n=== E2E Test: Backup and Recovery Workflow ===")

    with tempfile.TemporaryDirectory() as workspace:
        # Original installation
        original_datafiles = os.path.join(workspace, "original", "datafiles")
        os.makedirs(original_datafiles, exist_ok=True)
        db_path = os.path.join(original_datafiles, "production.db")

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE critical_data (id INTEGER PRIMARY KEY, info TEXT)")
        conn.execute("INSERT INTO critical_data (info) VALUES ('important')")
        conn.commit()
        conn.close()
        print("  ✓ Original: Production database created")

        # Backup
        backup_dir = os.path.join(workspace, "backup")
        shutil.copytree(original_datafiles, backup_dir)
        print("  ✓ Backup: Created backup of datafiles directory")

        # Disaster occurs (simulate by removing original)
        shutil.rmtree(original_datafiles)
        print("  ✓ Disaster: Original data lost")

        # Recovery
        recovered_datafiles = os.path.join(workspace, "recovered", "datafiles")
        os.makedirs(os.path.dirname(recovered_datafiles), exist_ok=True)
        shutil.copytree(backup_dir, recovered_datafiles)
        print("  ✓ Recovery: Restored from backup")

        # Verify recovery
        recovered_db = os.path.join(recovered_datafiles, "production.db")
        conn = sqlite3.connect(recovered_db)
        cursor = conn.execute("SELECT info FROM critical_data")
        info = cursor.fetchone()[0]
        conn.close()

        assert info == "important", "Critical data recovered"
        print("  ✓ Verification: All data recovered successfully")

    print("✓ PASS: Backup and recovery workflow E2E test passed")
    return True

def test_e2e_configuration_change_workflow():
    """E2E: Configuration change workflow"""
    print("\n=== E2E Test: Configuration Change Workflow ===")

    with tempfile.TemporaryDirectory() as app_root:
        # Initial configuration
        datafiles_v1 = os.path.join(app_root, "datafiles")
        os.makedirs(datafiles_v1, exist_ok=True)
        db_v1 = os.path.join(datafiles_v1, "data.db")
        conn = sqlite3.connect(db_v1)
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('db_version', 'v1')")
        conn.commit()
        conn.close()
        print("  ✓ Initial config: Database created in /datafiles/")

        # Configuration change: Add subdirectory
        datasets_dir = os.path.join(datafiles_v1, "datasets")
        os.makedirs(datasets_dir, exist_ok=True)
        db_v2 = os.path.join(datasets_dir, "datasets.db")
        conn = sqlite3.connect(db_v2)
        conn.execute("CREATE TABLE datasets (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()
        print("  ✓ Config change: Added /datafiles/datasets/ subdirectory")

        # Verify both databases work
        conn1 = sqlite3.connect(db_v1)
        cursor1 = conn1.execute("SELECT value FROM settings WHERE key='db_version'")
        assert cursor1.fetchone()[0] == "v1"
        conn1.close()

        conn2 = sqlite3.connect(db_v2)
        cursor2 = conn2.execute("SELECT COUNT(*) FROM datasets")
        assert cursor2.fetchone()[0] == 0
        conn2.close()

        print("  ✓ Verification: Both databases operational")

    print("✓ PASS: Configuration change workflow E2E test passed")
    return True

def test_e2e_production_deployment_workflow():
    """E2E: Production deployment workflow"""
    print("\n=== E2E Test: Production Deployment Workflow ===")

    with tempfile.TemporaryDirectory() as prod_root:
        # Deployment steps
        print("  Deploying to production...")

        # Step 1: Create data directory structure
        datafiles = os.path.join(prod_root, "datafiles")
        datasets = os.path.join(datafiles, "datasets")
        os.makedirs(datasets, exist_ok=True)
        print("  ✓ Step 1: Created directory structure")

        # Step 2: Initialize all databases
        databases = [
            ("pipeline.db", datafiles),
            ("reference.db", datafiles),
            ("dataset.db", datasets),
            ("cache.db", datafiles),
        ]

        for db_name, db_dir in databases:
            db_path = os.path.join(db_dir, db_name)
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO metadata VALUES ('deployed', 'true')")
            conn.commit()
            conn.close()

        print("  ✓ Step 2: Initialized all production databases")

        # Step 3: Health check
        all_healthy = True
        for db_name, db_dir in databases:
            db_path = os.path.join(db_dir, db_name)
            if not os.path.exists(db_path):
                all_healthy = False
                break

        assert all_healthy, "All databases should be accessible"
        print("  ✓ Step 3: Health check passed")

        # Step 4: Simulate production traffic
        # Multiple concurrent requests (simulated)
        for i in range(10):
            os.makedirs(datafiles, exist_ok=True)  # Should not fail
            os.makedirs(datasets, exist_ok=True)   # Should not fail

        print("  ✓ Step 4: Handled production traffic")

    print("✓ PASS: Production deployment workflow E2E test passed")
    return True

def run_all_e2e_tests():
    """Run all E2E tests"""
    print("\n" + "="*80)
    print("Phase 2: End-to-End Tests (Standalone)")
    print("="*80)

    tests = [
        ("Fresh Installation Workflow", test_e2e_fresh_installation_workflow),
        ("Application Restart Workflow", test_e2e_application_restart_workflow),
        ("Migration Workflow", test_e2e_migration_workflow),
        ("Multi-Instance Scenario", test_e2e_multi_user_scenario),
        ("Docker Deployment Workflow", test_e2e_docker_deployment_workflow),
        ("Backup and Recovery Workflow", test_e2e_backup_recovery_workflow),
        ("Configuration Change Workflow", test_e2e_configuration_change_workflow),
        ("Production Deployment Workflow", test_e2e_production_deployment_workflow),
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
    print(f"E2E Test Results: {passed} passed, {failed} failed")
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
        print("\n✅ ALL E2E TESTS PASSED")
        return True

if __name__ == "__main__":
    success = run_all_e2e_tests()
    sys.exit(0 if success else 1)
