"""
Integration tests for reference filter service with database interactions.

These tests validate that the filter service correctly interacts with both
the local database (for predicates) and reference database (for external
predicates and links).
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from unittest.mock import Mock  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
import json  # noqa: E402

from database.models import Base, Predicate  # noqa: E402
from reference_db.models import (
    Base as ReferenceBase,
    ReferenceNode,
    ReferenceLink,
    ExternalPredicate,
)  # noqa: E402, E501
from reference_db.manager import ReferenceManager  # noqa: E402
from services.reference_filter_service import ReferenceFilterService  # noqa: E402, E501


@pytest.fixture
def local_db_session():
    """Create an in-memory SQLite database for local predicates."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def ref_db_session():
    """Create an in-memory SQLite database for reference data."""
    engine = create_engine("sqlite:///:memory:")
    ReferenceBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_ref_manager(ref_db_session):
    """Create a mock reference manager with database session."""
    manager = Mock(spec=ReferenceManager)
    manager.session = ref_db_session
    # Mock the list_external_predicates method to query the test database

    def list_external_predicates(source=None, limit=None):
        from reference_db.models import ExternalPredicate

        query = ref_db_session.query(ExternalPredicate)
        if source:
            query = query.filter_by(source=source)
        if limit:
            query = query.limit(limit)
        return query.all()

    manager.list_external_predicates = list_external_predicates
    return manager


@pytest.fixture
def filter_service(local_db_session, mock_ref_manager):
    """Create a filter service instance."""
    return ReferenceFilterService(local_db_session, mock_ref_manager)


def test_filter_service_with_real_database_interaction(
    local_db_session, ref_db_session, mock_ref_manager
):  # noqa: E501
    """Test filter service with actual database reads."""
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
    local_db_session.add(predicate)
    local_db_session.commit()

    # Create external predicate in reference database
    from datetime import date

    ext_pred = ExternalPredicate(
        id="ext-pred-1",
        source="schema.org",
        external_id="relatedTo",
        title="Related To",
        definition="Schema.org related relationship",
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat(),
    )
    ref_db_session.add(ext_pred)
    ref_db_session.commit()

    # Create reference nodes and links
    today = date.today().isoformat()
    node1 = ReferenceNode(
        id="node-1",
        title="Concept A",
        definition="Definition of Concept A",
        source="schema.org",
        external_id="ConceptA",
        created_at=today,
        updated_at=today,
    )
    node2 = ReferenceNode(
        id="node-2",
        title="Concept B",
        definition="Definition of Concept B",
        source="schema.org",
        external_id="ConceptB",
        created_at=today,
        updated_at=today,
    )
    link = ReferenceLink(
        id="link-1",
        subject_node="node-1",
        predicate="relatedTo",
        object_node="node-2",
        created_at=today,
        updated_at=today,
    )
    ref_db_session.add_all([node1, node2, link])
    ref_db_session.commit()

    # Create filter service and test filtering
    service = ReferenceFilterService(local_db_session, mock_ref_manager)

    # Test that filtering works with database queries
    filtered_links, stats = service.filter_links([link])

    # Should include the link since its predicate is relevant
    assert len(filtered_links) == 1
    assert stats["filtering_active"] is True
    assert stats["filter_mode"] == "whitelist"


def test_filter_service_handles_database_errors_gracefully(
    local_db_session, mock_ref_manager
):  # noqa: E501
    """Test that database errors are handled gracefully."""
    from unittest.mock import patch

    service = ReferenceFilterService(local_db_session, mock_ref_manager)

    # Create a mock link
    link = Mock(spec=ReferenceLink)
    link.predicate = "testPred"

    # Mock the _build_relevance_sets method to raise an exception
    with patch.object(
        service, "_build_relevance_sets", side_effect=Exception("Database error")
    ):  # noqa: E501
        # Should handle error and return unfiltered links
        filtered_links, stats = service.filter_links([link])

        # Should return original links on error
        assert len(filtered_links) == 1
        assert "error" in stats
        assert stats["error"] == "Database error"
        assert stats["filtering_active"] is False


def test_filter_statistics_with_real_predicates(
    local_db_session, mock_ref_manager
):  # noqa: E501
    """Test filter statistics calculation with real database predicates."""
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
        local_db_session.add(pred)
    local_db_session.commit()

    service = ReferenceFilterService(local_db_session, mock_ref_manager)
    stats = service.get_filter_statistics()

    assert stats["total_predicates"] == 3
    assert stats["relevant_count"] == 1
    assert stats["irrelevant_count"] == 1
    assert stats["unmapped_count"] == 1
    assert "schema.org:rel1" in stats["relevant_external_predicates"]
    assert "dbpedia:irrel1" in stats["irrelevant_external_predicates"]


def test_cache_behavior_with_database_updates(
    local_db_session, mock_ref_manager
):  # noqa: E501
    """Test that cache is properly used and invalidated."""
    # Create initial predicate
    predicate = Predicate(
        id="pred-1",
        identifier="cached-pred",
        title="Cached Predicate",
        is_relevant=True,
        mapping=json.dumps(
            {"external_predicates": [{"source": "schema.org", "external_id": "cached"}]}
        ),
    )
    local_db_session.add(predicate)
    local_db_session.commit()

    service = ReferenceFilterService(local_db_session, mock_ref_manager)

    # First call should build cache
    relevant1 = service.get_relevant_predicates()
    assert "schema.org:cached" in relevant1

    # Second call should use cache (same result)
    relevant2 = service.get_relevant_predicates()
    assert relevant1 == relevant2

    # Invalidate cache
    service.invalidate_cache()

    # Update predicate in database
    predicate.is_relevant = False
    local_db_session.commit()

    # Next call should rebuild from database
    relevant3 = service.get_relevant_predicates(force_refresh=True)
    assert "schema.org:cached" not in relevant3


def test_batch_predicate_fetch_optimization(
    local_db_session, ref_db_session, mock_ref_manager
):  # noqa: E501
    """Test that batch fetching optimizes database queries."""
    from datetime import date

    # Create multiple external predicates
    for i in range(10):
        ext_pred = ExternalPredicate(
            id=f"ext-pred-{i}",
            source="test",
            external_id=f"pred{i}",
            title=f"Predicate {i}",
            definition=f"Test predicate {i}",
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat(),
        )
        ref_db_session.add(ext_pred)
    ref_db_session.commit()

    # Create links using subset of predicates
    links = []
    for i in range(5):
        link = Mock(spec=ReferenceLink)
        link.predicate = f"pred{i}"
        links.append(link)

    service = ReferenceFilterService(local_db_session, mock_ref_manager)

    # Batch fetch should only fetch the 5 predicates needed
    predicate_map = service._batch_fetch_predicates_for_links(links)

    # Should have entries for the 5 predicates referenced in links
    assert len(predicate_map) == 5
    for i in range(5):
        assert f"pred{i}" in predicate_map


def test_filter_mode_determination_logic(local_db_session, mock_ref_manager):
    """Test the filter mode determination logic."""
    service = ReferenceFilterService(local_db_session, mock_ref_manager)

    # Whitelist mode: when relevant predicates exist
    relevant = {"pred1", "pred2"}
    irrelevant = {"pred3"}
    mode = service._determine_filter_mode(relevant, irrelevant)
    assert mode == "whitelist"

    # Blacklist mode: when only irrelevant predicates exist
    relevant = set()
    irrelevant = {"pred3", "pred4"}
    mode = service._determine_filter_mode(relevant, irrelevant)
    assert mode == "blacklist"

    # Whitelist mode: when both exist, relevant takes precedence
    relevant = {"pred1"}
    irrelevant = {"pred3"}
    mode = service._determine_filter_mode(relevant, irrelevant)
    assert mode == "whitelist"


def test_filter_service_with_null_relevance_values(
    local_db_session, mock_ref_manager
):  # noqa: E501
    """Test that predicates with null is_relevant values don't affect filtering."""  # noqa: E501
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
        local_db_session.add(pred)
    local_db_session.commit()

    service = ReferenceFilterService(local_db_session, mock_ref_manager)

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
