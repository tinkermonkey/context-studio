#!/usr/bin/env python3
"""
Standalone Phase 4 Validation Script

This script validates Phase 4 implementation without requiring full application dependencies.
Tests health check functionality, performance, and core requirements.
"""

import os
import sys
import time
import sqlite3
from pathlib import Path

# Add local-server to path
sys.path.insert(0, str(Path(__file__).parent))

def test_health_check_performance():
    """Test TC-S002: Health check performance (<200ms)"""
    from reference_db.manager import ReferenceManager
    import tempfile

    print("\n=== TC-S002: Health Check Performance Test ===")

    # Create a test database
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tf:
        db_path = tf.name

    try:
        manager = ReferenceManager(db_path)

        # Add some test data
        for i in range(10):
            manager.add_reference_node(
                title=f"TestNode{i}",
                definition=f"Test definition {i}",
                source="test",
                external_id=f"test-{i}"
            )

        # Measure health check performance
        start_time = time.time()
        status = manager.get_status()
        elapsed_ms = (time.time() - start_time) * 1000

        print(f"✓ Health check completed in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 200, f"Health check took {elapsed_ms:.2f}ms, should be <200ms"
        print(f"✓ Performance requirement met (<200ms)")

        # Validate response structure
        assert "status" in status, "Response must include 'status' field"
        assert "node_count" in status, "Response must include 'node_count' field"
        assert "vec_count" in status, "Response must include 'vec_count' field"
        assert "schema_version" in status, "Response must include 'schema_version' field"
        assert "model_version" in status, "Response must include 'model_version' field"
        assert "database_size" in status, "Response must include 'database_size' field"
        assert "connection_healthy" in status, "Response must include 'connection_healthy' field"
        assert "checked_at" in status, "Response must include 'checked_at' field"
        print("✓ Response schema validated")

        # Validate status logic
        assert status["node_count"] == 10, f"Expected 10 nodes, got {status['node_count']}"
        assert status["connection_healthy"] == True, "Connection should be healthy"
        print("✓ Status logic validated")

        print(f"\n✓ TC-S002 PASSED")
        return True
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_health_check_missing_database():
    """Test health check with missing database"""
    from reference_db.manager import ReferenceManager
    import tempfile

    print("\n=== Test: Health Check - Missing Database ===")

    # Use non-existent database path
    db_path = "/tmp/nonexistent_test_db_12345.db"

    if os.path.exists(db_path):
        os.remove(db_path)

    manager = ReferenceManager(db_path)
    status = manager.get_status()

    assert status["status"] == "missing", f"Expected 'missing' status, got '{status['status']}'"
    assert status["node_count"] == 0, "Node count should be 0 for missing database"
    assert "remediation" in status, "Missing database should include remediation"
    print(f"✓ Status: {status['status']}")
    print(f"✓ Remediation: {status['remediation']}")
    print("✓ Test PASSED")

    return True

def test_health_check_degraded():
    """Test health check with degraded database (embedding mismatch)"""
    from reference_db.manager import ReferenceManager
    import tempfile

    print("\n=== Test: Health Check - Degraded Database ===")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tf:
        db_path = tf.name

    try:
        manager = ReferenceManager(db_path)

        # Add nodes with embeddings
        for i in range(5):
            manager.add_reference_node(
                title=f"NodeWithEmbedding{i}",
                definition=f"Definition {i}",
                source="test",
                external_id=f"emb-{i}",
                title_embedding=b"\\x00" * (1536 * 4)  # Fake embedding
            )

        # Add nodes without embeddings
        for i in range(5):
            manager.add_reference_node(
                title=f"NodeWithoutEmbedding{i}",
                definition=f"Definition {i}",
                source="test",
                external_id=f"no-emb-{i}"
            )

        status = manager.get_status()

        assert status["status"] == "degraded", f"Expected 'degraded' status, got '{status['status']}'"
        assert status["node_count"] == 10, f"Expected 10 nodes, got {status['node_count']}"
        assert status["vec_count"] == 5, f"Expected 5 nodes with embeddings, got {status['vec_count']}"
        assert "degraded_reason" in status, "Degraded status should include reason"
        assert status["degraded_reason"] == "embedding_count_mismatch", \
            f"Expected 'embedding_count_mismatch', got '{status['degraded_reason']}'"
        assert "remediation" in status, "Degraded status should include remediation"
        assert "embedding_coverage_pct" in status, "Should include embedding coverage percentage"

        print(f"✓ Status: {status['status']}")
        print(f"✓ Degraded reason: {status['degraded_reason']}")
        print(f"✓ Coverage: {status['embedding_coverage_pct']}%")
        print(f"✓ Remediation: {status['remediation']}")
        print("✓ Test PASSED")

        return True
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_error_handling():
    """Test error handling in health check"""
    from reference_db.manager import ReferenceManager
    import tempfile

    print("\n=== Test: Error Handling ===")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tf:
        db_path = tf.name

    try:
        manager = ReferenceManager(db_path)
        manager.add_reference_node(
            title="TestNode",
            definition="Test",
            source="test",
            external_id="test-1"
        )

        # Close the database connection to simulate error
        manager.engine.dispose()

        # Try to get status with disposed connection
        status = manager.get_status()

        # Should return error status gracefully, not crash
        assert "status" in status, "Should return status even on error"
        print(f"✓ Status on error: {status['status']}")
        print(f"✓ Connection healthy: {status['connection_healthy']}")
        print("✓ Error handling works gracefully")
        print("✓ Test PASSED")

        return True
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_typescript_schema_compatibility():
    """Validate TypeScript type definition matches Python implementation"""
    print("\n=== Test: TypeScript Schema Compatibility ===")

    # Read TypeScript type definition
    ts_types_path = Path(__file__).parent.parent / "ux" / "src" / "api" / "types" / "referenceHealth.ts"

    if not ts_types_path.exists():
        print(f"⚠ TypeScript types file not found at {ts_types_path}")
        print("  Skipping compatibility test")
        return True

    with open(ts_types_path, "r") as f:
        ts_content = f.read()

    # Verify required fields are documented
    required_fields = [
        "status",
        "node_count",
        "vec_count",
        "schema_version",
        "model_version",
        "database_size",
        "database_path",
        "connection_healthy",
        "checked_at"
    ]

    for field in required_fields:
        assert field in ts_content, f"TypeScript types must include '{field}' field"
        print(f"✓ Field '{field}' documented in TypeScript")

    # Verify status values are documented
    status_values = ["healthy", "degraded", "missing", "error"]
    for status_val in status_values:
        assert status_val in ts_content, f"TypeScript types must include '{status_val}' status"
        print(f"✓ Status '{status_val}' documented in TypeScript")

    print("✓ TypeScript schema compatibility verified")
    print("✓ Test PASSED")

    return True

def main():
    """Run all Phase 4 validation tests"""
    print("=" * 60)
    print("Phase 4: API Contract Validation - Standalone Test Suite")
    print("=" * 60)

    tests = [
        ("Health Check Performance (TC-S002)", test_health_check_performance),
        ("Health Check - Missing Database", test_health_check_missing_database),
        ("Health Check - Degraded Database", test_health_check_degraded),
        ("Error Handling", test_error_handling),
        ("TypeScript Schema Compatibility", test_typescript_schema_compatibility),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n✗ {test_name} FAILED:")
            print(f"  {str(e)}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✓ ALL TESTS PASSED")
        print("✓ Phase 4 implementation validated successfully")
        return 0
    else:
        print(f"\n✗ {failed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
