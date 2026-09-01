"""
Standalone integration tests for reference filter service.

These tests run without the full app context, focusing on the core
filtering logic with database interactions.
"""

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import json
from unittest.mock import Mock

from database.models import Base, Predicate
from reference_db.models import (
    Base as ReferenceBase,
)
from reference_db.models import (
    ExternalPredicate as ReferencePredicate,
)
from services.reference_filter_service import ReferenceFilterService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_integration_filter_with_databases():
    """Integration test with real database interactions."""
    print("Testing filter service with real database interactions...")

    # Create in-memory databases
    local_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    ref_engine = create_engine("sqlite:///:memory:")
    ReferenceBase.metadata.create_all(ref_engine)
    RefSession = sessionmaker(bind=ref_engine)
    ref_db = RefSession()

    # Create external predicate
    from datetime import datetime

    ext_pred = ReferencePredicate(
        id="ext-pred-1",
        source="schema.org",
        external_id="relatedTo",
        title="Related To",
        definition="Schema.org related relationship",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    ref_db.add(ext_pred)
    ref_db.commit()

    # Create mock reference manager
    mock_manager = Mock()
    mock_manager.get_session.return_value = ref_db
    mock_manager.list_external_predicates.return_value = [ext_pred]

    # Create global predicate with mapping
    predicate = Predicate(
        id="pred-1",
        identifier="related-to",
        title="Related To",
        definition="A general relationship",
        is_relevant=True,
        mapping=json.dumps(
            {
                "external_predicates": [
                    {"source": "schema.org", "external_id": "relatedTo"}
                ]
            }
        ),
    )
    local_db.add(predicate)
    local_db.commit()

    # Create filter service
    service = ReferenceFilterService(local_db, mock_manager)

    # Create mock links
    link1 = Mock()
    link1.predicate = "relatedTo"
    link2 = Mock()
    link2.predicate = "unknownPred"

    # Test filtering
    _filtered_links, stats = service.filter_links([link1, link2])

    print(f"  Total before: {stats['total_before']}")
    print(f"  Total after: {stats['total_after']}")
    print(f"  Filter mode: {stats['filter_mode']}")
    print(f"  Predicates used: {stats['predicates_used']}")

    # Assertions
    assert stats["total_before"] == 2
    assert stats["total_after"] == 1  # Only link1 should be included
    assert stats["filter_mode"] == "whitelist"
    assert stats["filtering_active"] is True

    # Cleanup
    local_db.close()
    ref_db.close()

    print("✓ Integration test passed")


def test_filter_statistics():
    """Test filter statistics calculation."""
    print("\nTesting filter statistics...")

    # Create in-memory databases
    local_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    ref_engine = create_engine("sqlite:///:memory:")
    ReferenceBase.metadata.create_all(ref_engine)
    RefSession = sessionmaker(bind=ref_engine)
    ref_db = RefSession()

    # Create mock reference manager
    mock_manager = Mock()
    mock_manager.get_session.return_value = ref_db
    mock_manager.list_external_predicates.return_value = []

    # Create various predicates
    predicates = [
        Predicate(
            id="pred-1",
            identifier="relevant-pred",
            title="Relevant Predicate",
            is_relevant=True,
            mapping=json.dumps(
                {
                    "external_predicates": [
                        {"source": "schema.org", "external_id": "rel1"}
                    ]
                }
            ),
        ),
        Predicate(
            id="pred-2",
            identifier="irrelevant-pred",
            title="Irrelevant Predicate",
            is_relevant=False,
            mapping=json.dumps(
                {
                    "external_predicates": [
                        {"source": "dbpedia", "external_id": "irrel1"}
                    ]
                }
            ),
        ),
        Predicate(
            id="pred-3",
            identifier="unmapped-pred",
            title="Unmapped Predicate",
            is_relevant=None,
            mapping=None,
        ),
    ]

    for pred in predicates:
        local_db.add(pred)
    local_db.commit()

    service = ReferenceFilterService(local_db, mock_manager)
    stats = service.get_filter_statistics()

    print(f"  Total predicates: {stats['total_predicates']}")
    print(f"  Relevant count: {stats['relevant_count']}")
    print(f"  Irrelevant count: {stats['irrelevant_count']}")
    print(f"  Unmapped count: {stats['unmapped_count']}")

    assert stats["total_predicates"] == 3
    assert stats["relevant_count"] == 1
    assert stats["irrelevant_count"] == 1
    assert stats["unmapped_count"] == 1
    assert "schema.org:rel1" in stats["relevant_external_predicates"]
    assert "dbpedia:irrel1" in stats["irrelevant_external_predicates"]

    # Cleanup
    local_db.close()
    ref_db.close()

    print("✓ Statistics test passed")


def test_cache_invalidation():
    """Test cache invalidation logic."""
    print("\nTesting cache invalidation...")

    # Create in-memory databases
    local_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    ref_engine = create_engine("sqlite:///:memory:")
    ReferenceBase.metadata.create_all(ref_engine)
    RefSession = sessionmaker(bind=ref_engine)
    ref_db = RefSession()

    # Create mock reference manager
    mock_manager = Mock()
    mock_manager.get_session.return_value = ref_db
    mock_manager.list_external_predicates.return_value = []

    # Create predicate
    predicate = Predicate(
        id="pred-1",
        identifier="cached-pred",
        title="Cached Predicate",
        is_relevant=True,
        mapping=json.dumps(
            {"external_predicates": [{"source": "schema.org", "external_id": "cached"}]}
        ),
    )
    local_db.add(predicate)
    local_db.commit()

    service = ReferenceFilterService(local_db, mock_manager)

    # First call builds cache
    relevant1 = service.get_relevant_predicates()
    assert "schema.org:cached" in relevant1

    # Invalidate cache
    service.invalidate_cache()

    # Update predicate
    predicate.is_relevant = False
    local_db.commit()

    # Next call should rebuild from database
    relevant2 = service.get_relevant_predicates(force_refresh=True)
    assert "schema.org:cached" not in relevant2

    # Cleanup
    local_db.close()
    ref_db.close()

    print("✓ Cache invalidation test passed")


def test_error_handling():
    """Test error handling in filter service."""
    print("\nTesting error handling...")

    # Create in-memory database
    local_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    # Create mock reference manager that raises an error
    mock_manager = Mock()
    mock_manager.list_external_predicates.side_effect = Exception(
        "Database connection failed"
    )

    service = ReferenceFilterService(local_db, mock_manager)

    # Create mock link
    link = Mock()
    link.predicate = "testPred"

    # Should handle error gracefully
    filtered_links, stats = service.filter_links([link])

    # When there's an error in filter service, it should return unfiltered links
    # with filtering_active=False (no predicates marked = no filtering)
    assert len(filtered_links) == 1
    assert stats["filtering_active"] is False

    # Cleanup
    local_db.close()

    print("✓ Error handling test passed")


def test_null_relevance_handling():
    """Test that null relevance values are properly ignored."""
    print("\nTesting null relevance handling...")

    # Create in-memory databases
    local_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    ref_engine = create_engine("sqlite:///:memory:")
    ReferenceBase.metadata.create_all(ref_engine)
    RefSession = sessionmaker(bind=ref_engine)
    ref_db = RefSession()

    # Create mock reference manager
    mock_manager = Mock()
    mock_manager.get_session.return_value = ref_db
    mock_manager.list_external_predicates.return_value = []

    # Create predicates with various relevance states
    predicates = [
        Predicate(
            id="pred-1",
            identifier="null-pred",
            title="Null Predicate",
            is_relevant=None,  # Null should be ignored
            mapping=json.dumps(
                {"external_predicates": [{"source": "test", "external_id": "null1"}]}
            ),
        ),
        Predicate(
            id="pred-2",
            identifier="relevant-pred",
            title="Relevant Predicate",
            is_relevant=True,
            mapping=json.dumps(
                {"external_predicates": [{"source": "test", "external_id": "rel1"}]}
            ),
        ),
    ]

    for pred in predicates:
        local_db.add(pred)
    local_db.commit()

    service = ReferenceFilterService(local_db, mock_manager)

    # Get relevance sets
    relevant = service.get_relevant_predicates()
    irrelevant = service.get_irrelevant_predicates()

    # Null predicate should not be in either set
    assert "test:null1" not in relevant
    assert "test:null1" not in irrelevant

    # Only the relevant predicate should be in relevant set
    assert "test:rel1" in relevant
    assert len(relevant) == 1
    assert len(irrelevant) == 0

    # Cleanup
    local_db.close()
    ref_db.close()

    print("✓ Null relevance handling test passed")


if __name__ == "__main__":
    try:
        test_integration_filter_with_databases()
        test_filter_statistics()
        test_cache_invalidation()
        test_error_handling()
        test_null_relevance_handling()
        print("\n✅ All integration tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
