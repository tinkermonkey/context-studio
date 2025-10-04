#!/usr/bin/env python3
"""
Standalone test runner for reference database revisions.

This script tests the revised reference database implementation without requiring
the full application context.
"""

import os
import sys
import tempfile
from datetime import date
from uuid import uuid4

# Add the local-server directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reference_db.models import ReferenceNode, ReferenceLink
from reference_db.config import ReferenceConfig, REFERENCE_SCHEMA_VERSION, EMBEDDING_MODEL_VERSION
from pydantic import ValidationError


def test_models():
    """Test ReferenceNode and ReferenceLink models."""
    print("Testing models...")

    # Test ReferenceNode creation
    node = ReferenceNode(
        id=str(uuid4()),
        title="Person",
        definition="A human being",
        source="schema.org",
        external_id="Person",
        attributes=None,
        title_embedding=None,
        definition_embedding=None,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    assert node.title == "Person"
    assert node.definition == "A human being"
    assert node.source == "schema.org"
    assert node.external_id == "Person"
    print("✓ ReferenceNode creation successful")

    # Test __repr__
    repr_str = repr(node)
    assert "ReferenceNode" in repr_str
    assert "schema.org" in repr_str
    assert "Person" in repr_str
    print("✓ ReferenceNode __repr__ works")

    # Test ReferenceLink creation
    link = ReferenceLink(
        id=str(uuid4()),
        subject_node=str(uuid4()),
        predicate="subClassOf",
        object_node=str(uuid4()),
        attributes=None,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    assert link.predicate == "subClassOf"
    print("✓ ReferenceLink creation successful")

    # Test __repr__
    repr_str = repr(link)
    assert "ReferenceLink" in repr_str
    assert "subClassOf" in repr_str
    print("✓ ReferenceLink __repr__ works")


def test_config():
    """Test ReferenceConfig validation."""
    print("\nTesting configuration...")

    # Test default config
    config = ReferenceConfig()
    assert config.schema_org_api_url.startswith("https://")
    assert config.embedding_model == EMBEDDING_MODEL_VERSION
    assert 0.0 <= config.similarity_threshold <= 1.0
    assert 1 <= config.batch_size <= 1000
    assert 0 <= config.retry_count <= 10
    print("✓ Default configuration valid")

    # Test HTTPS validation
    try:
        ReferenceConfig(schema_org_api_url="https://schema.org/api")
        print("✓ HTTPS URL accepted")
    except ValidationError:
        print("✗ HTTPS URL rejected (should be accepted)")
        return False

    # Test HTTP rejection for remote hosts
    try:
        ReferenceConfig(schema_org_api_url="http://schema.org/api")
        print("✗ HTTP URL for remote host accepted (should be rejected)")
        return False
    except ValidationError as e:
        error = str(e)
        assert "HTTPS" in error or "security" in error.lower()
        print("✓ HTTP URL for remote host rejected")

    # Test localhost HTTP allowed
    try:
        ReferenceConfig(schema_org_api_url="http://localhost:8000/api")
        print("✓ HTTP URL for localhost accepted")
    except ValidationError:
        print("✗ HTTP URL for localhost rejected (should be accepted)")
        return False

    # Test 127.0.0.1 HTTP allowed
    try:
        ReferenceConfig(schema_org_api_url="http://127.0.0.1:8000/api")
        print("✓ HTTP URL for 127.0.0.1 accepted")
    except ValidationError:
        print("✗ HTTP URL for 127.0.0.1 rejected (should be accepted)")
        return False

    # Test similarity threshold validation
    try:
        ReferenceConfig(similarity_threshold=1.5)
        print("✗ Invalid similarity threshold accepted (should be rejected)")
        return False
    except ValidationError as e:
        error = str(e)
        # Accept either custom validator message or Pydantic's default message
        assert "similarity_threshold" in error.lower() or "1" in error
        print("✓ Out-of-range similarity threshold rejected")

    # Test batch size validation
    try:
        ReferenceConfig(batch_size=5000)
        print("✗ Invalid batch size accepted (should be rejected)")
        return False
    except ValidationError as e:
        error = str(e)
        # Accept either custom validator message or Pydantic's default message
        assert "batch_size" in error.lower() or "1000" in error
        print("✓ Out-of-range batch size rejected")

    # Test retry count validation
    try:
        ReferenceConfig(retry_count=20)
        print("✗ Invalid retry count accepted (should be rejected)")
        return False
    except ValidationError as e:
        error = str(e)
        # Accept either custom validator message or Pydantic's default message
        assert "retry_count" in error.lower() or "10" in error
        print("✓ Out-of-range retry count rejected")

    return True


def test_manager_core():
    """Test core ReferenceManager functionality (without vector operations)."""
    print("\nTesting manager core functionality...")

    from reference_db.manager import ReferenceManager

    config = ReferenceConfig()

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
        db_path = tf.name

    try:
        # Test initialization
        manager = ReferenceManager(config, db_path=db_path)
        assert manager.config.similarity_threshold == config.similarity_threshold
        print("✓ Manager initialization successful")

        # Test manual close
        manager.close()
        assert manager.session is None
        print("✓ Manual close works")

        # Test context manager protocol
        with ReferenceManager(config, db_path=db_path) as manager:
            assert manager is not None
            assert manager.session is not None

        assert manager.session is None
        print("✓ Context manager protocol works")

        # Test lock file cleanup
        lock_path = f"{db_path}.rebuild.lock"
        assert not os.path.exists(lock_path), "Lock file should be cleaned up"
        print("✓ Lock file cleanup successful")

        return True

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
        lock_path = f"{db_path}.rebuild.lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)


def main():
    """Run all tests."""
    print("=" * 60)
    print("Reference Database Revision Tests")
    print("=" * 60)

    try:
        test_models()

        if not test_config():
            print("\n✗ Configuration tests failed")
            return 1

        if not test_manager_core():
            print("\n✗ Manager core tests failed")
            return 1

        print("\n" + "=" * 60)
        print("✓ All revision tests passed!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
