#!/usr/bin/env python
"""
Standalone test script for reference_db module.
Does not require pytest infrastructure or full app loading.
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from reference_db.models import Base, ReferenceNode, ReferenceLink
from reference_db.config import (
    ReferenceConfig,
    REFERENCE_SCHEMA_VERSION,
    EMBEDDING_MODEL_VERSION
)
from reference_db.manager import ReferenceManager


def test_reference_node_creation():
    """TC-U001.1: Verify ReferenceNode model includes all required fields."""
    print("TEST: test_reference_node_creation")

    # Test database insert generates UUID automatically
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_node.db"
        engine = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Create node - UUID is generated on insert, not on object creation
            node = ReferenceNode(
                source="dbpedia",
                external_id="http://dbpedia.org/resource/Python",
                title="Python",
                definition="A high-level programming language",
                attributes='{"type": "ProgrammingLanguage"}',
                title_embedding=b'\x00\x01\x02\x03',
                definition_embedding=b'\x04\x05\x06\x07'
            )
            session.add(node)
            session.flush()  # Trigger default value generation

            assert node.source == "dbpedia"
            assert node.external_id == "http://dbpedia.org/resource/Python"
            assert node.title == "Python"
            assert node.definition == "A high-level programming language"
            assert node.attributes == '{"type": "ProgrammingLanguage"}'
            assert node.title_embedding == b'\x00\x01\x02\x03'
            assert node.definition_embedding == b'\x04\x05\x06\x07'
            assert node.id is not None  # UUID should be generated after flush
            assert isinstance(node.created_at, datetime)

            print("✓ PASS: All required fields present and UUID auto-generated on insert")
        finally:
            session.close()
            engine.dispose()


def test_reference_node_unique_constraint():
    """TC-U001.3: Verify UNIQUE constraint on (source, external_id)."""
    print("\nTEST: test_reference_node_unique_constraint")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_unique.db"
        engine = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Create first node
            node1 = ReferenceNode(
                source="dbpedia",
                external_id="http://dbpedia.org/resource/Test",
                title="Test 1"
            )
            session.add(node1)
            session.commit()

            # Try to create duplicate
            node2 = ReferenceNode(
                source="dbpedia",
                external_id="http://dbpedia.org/resource/Test",
                title="Test 2"
            )
            session.add(node2)

            try:
                session.commit()
                print("✗ FAIL: Duplicate insertion should have failed")
                return False
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) or "unique constraint" in str(e).lower():
                    print("✓ PASS: UNIQUE constraint properly enforced")
                    return True
                else:
                    print(f"✗ FAIL: Unexpected error: {e}")
                    return False

        finally:
            session.close()
            engine.dispose()


def test_reference_config_https_validation():
    """TC-U003, TC-SEC002: Verify HTTPS-only URL validation."""
    print("\nTEST: test_reference_config_https_validation")

    # HTTP should be rejected
    try:
        ReferenceConfig(source_url="http://example.com/data")
        print("✗ FAIL: HTTP URL should be rejected")
        return False
    except ValidationError as e:
        if "HTTPS" in str(e) or "https" in str(e):
            print("✓ PASS: HTTP URLs rejected")
        else:
            print(f"✗ FAIL: Wrong validation error: {e}")
            return False

    # HTTPS should be accepted
    config = ReferenceConfig(source_url="https://example.com/data")
    assert config.source_url == "https://example.com/data"
    print("✓ PASS: HTTPS URLs accepted")

    # None should be accepted
    config = ReferenceConfig(source_url=None)
    assert config.source_url is None
    print("✓ PASS: None URLs accepted")
    return True


def test_reference_config_validation():
    """TC-U003: Verify configuration parameter validation."""
    print("\nTEST: test_reference_config_validation")

    # Valid similarity threshold
    config = ReferenceConfig(similarity_threshold=0.5)
    assert config.similarity_threshold == 0.5

    # Invalid similarity threshold
    try:
        ReferenceConfig(similarity_threshold=1.5)
        print("✗ FAIL: Invalid similarity threshold should be rejected")
        return False
    except ValidationError:
        print("✓ PASS: Invalid similarity threshold rejected")

    # Valid batch size
    config = ReferenceConfig(batch_size=100)
    assert config.batch_size == 100

    # Invalid batch size
    try:
        ReferenceConfig(batch_size=2000)
        print("✗ FAIL: Invalid batch size should be rejected")
        return False
    except ValidationError:
        print("✓ PASS: Invalid batch size rejected")

    # Valid retry count
    config = ReferenceConfig(retry_count=5)
    assert config.retry_count == 5

    # Invalid retry count
    try:
        ReferenceConfig(retry_count=20)
        print("✗ FAIL: Invalid retry count should be rejected")
        return False
    except ValidationError:
        print("✓ PASS: Invalid retry count rejected")

    return True


def test_reference_manager_initialization():
    """TC-I003: Verify basic manager initialization."""
    print("\nTEST: test_reference_manager_initialization")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_ref.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)

        result = manager.initialize()
        if not result:
            print("✗ FAIL: Manager initialization failed")
            return False

        if not db_file.exists():
            print("✗ FAIL: Database file not created")
            return False

        # Verify tables were created
        engine = manager.get_engine()
        with engine.connect() as conn:
            tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()

        table_names = [t[0] for t in tables]
        if "reference_nodes" not in table_names:
            print("✗ FAIL: reference_nodes table not created")
            return False

        if "reference_links" not in table_names:
            print("✗ FAIL: reference_links table not created")
            return False

        if "reference_db_version" not in table_names:
            print("✗ FAIL: reference_db_version table not created")
            return False

        print("✓ PASS: Manager initialized and all tables created")
        manager.cleanup()
        return True


def test_reference_manager_get_status():
    """Verify manager status reporting."""
    print("\nTEST: test_reference_manager_get_status")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_status.db"
        config = ReferenceConfig(database_path=str(db_file))
        manager = ReferenceManager(config)

        # Before initialization
        status = manager.get_status()
        if status["is_initialized"]:
            print("✗ FAIL: Should not be initialized yet")
            return False

        # After initialization
        manager.initialize()
        status = manager.get_status()
        if not status["is_initialized"]:
            print("✗ FAIL: Should be initialized")
            return False

        if status["schema_version"] != REFERENCE_SCHEMA_VERSION:
            print(f"✗ FAIL: Wrong schema version: {status['schema_version']}")
            return False

        print("✓ PASS: Status reporting works correctly")
        manager.cleanup()
        return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Reference DB Unit Tests")
    print("=" * 70)

    tests = [
        test_reference_node_creation,
        test_reference_node_unique_constraint,
        test_reference_config_https_validation,
        test_reference_config_validation,
        test_reference_manager_initialization,
        test_reference_manager_get_status,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            result = test_func()
            if result is None or result is True:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ FAIL: Test raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
