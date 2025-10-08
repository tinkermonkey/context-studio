#!/usr/bin/env python3
"""
Validation script for external predicates implementation.

This script verifies that the ExternalPredicate model and manager methods
are correctly implemented and can be imported without errors.
"""

import sys
import os
import tempfile

# Add local-server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from reference_db.models import ExternalPredicate
        from reference_db.config import ReferenceConfig, REFERENCE_SCHEMA_VERSION
        from reference_db.manager import ReferenceManager
        print("✓ All imports successful")
        print(f"✓ Schema version: {REFERENCE_SCHEMA_VERSION}")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_model_creation():
    """Test that ExternalPredicate model can be instantiated."""
    print("\nTesting model creation...")
    try:
        from reference_db.models import ExternalPredicate
        from datetime import date
        from uuid import uuid4

        predicate = ExternalPredicate(
            id=str(uuid4()),
            title="test",
            definition="test definition",
            source="test_source",
            external_id="test_id",
            attributes=None,
            title_embedding=None,
            definition_embedding=None,
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat()
        )

        assert predicate.title == "test"
        assert predicate.source == "test_source"
        print("✓ Model creation successful")
        return True
    except Exception as e:
        print(f"✗ Model creation failed: {e}")
        return False


def test_manager_methods():
    """Test that manager methods exist and are callable."""
    print("\nTesting manager methods...")
    try:
        from reference_db.manager import ReferenceManager

        # Check that all required methods exist
        required_methods = [
            'add_external_predicate',
            'get_external_predicate',
            'get_external_predicate_by_source',
            'list_external_predicates',
            'search_external_predicates_by_similarity'
        ]

        for method_name in required_methods:
            if not hasattr(ReferenceManager, method_name):
                print(f"✗ Missing method: {method_name}")
                return False
            print(f"  ✓ {method_name} exists")

        print("✓ All manager methods present")
        return True
    except Exception as e:
        print(f"✗ Manager methods check failed: {e}")
        return False


def test_database_creation():
    """Test that database with external_predicates table can be created."""
    print("\nTesting database creation...")
    try:
        from reference_db.config import ReferenceConfig
        from reference_db.manager import ReferenceManager

        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_path = tf.name

        try:
            # Create database
            with ReferenceManager(config, db_path=db_path) as manager:
                # Check that external_predicates table exists
                from sqlalchemy import text
                with manager.engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table' AND name='external_predicates'")
                    )
                    tables = [row[0] for row in result]

                    if 'external_predicates' not in tables:
                        print("✗ external_predicates table not created")
                        return False

                    print("  ✓ external_predicates table exists")

                    # Check indexes
                    result = conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='external_predicates'")
                    )
                    indexes = [row[0] for row in result]
                    print(f"  ✓ {len(indexes)} indexes created")

            print("✓ Database creation successful")
            return True
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    except Exception as e:
        print(f"✗ Database creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("External Predicates Implementation Validation")
    print("=" * 60)

    tests = [
        test_imports,
        test_model_creation,
        test_manager_methods,
        test_database_creation
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✓ All validation tests passed!")
        return 0
    else:
        print("\n✗ Some validation tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
