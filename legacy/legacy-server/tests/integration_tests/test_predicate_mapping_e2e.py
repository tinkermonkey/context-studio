"""
End-to-end tests for predicate mapping and reference filtering (Phase 6).

This test file covers the complete workflow from marking predicates as relevant
to filtering reference query results based on those mappings.
"""

import json
import os
import sys
import tempfile
from datetime import datetime

import pytest

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import Base as LocalBase
from database.models import Predicate
from database.utils import get_engine
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from services.reference_filter_service import ReferenceFilterService
from sqlalchemy.orm import sessionmaker


class TestPredicateMappingE2E:
    """
    End-to-end tests for Phase 6: Predicate mapping and reference filtering.
    """

    @pytest.fixture(autouse=True)
    def check_sqlite_vec(self):
        """Check if sqlite-vec is available, skip tests if not."""
        try:
            import sqlite_vec as _  # noqa: F401 # type: ignore[import-untyped]
        except ImportError:
            pytest.skip(
                "sqlite-vec not available (expected in Docker environment)"
            )

    @pytest.fixture
    def temp_ref_db(self):
        """Create a temporary reference database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def temp_local_db(self):
        """Create a temporary local database for predicates."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        # Initialize the local database
        engine = get_engine(f"sqlite:///{db_path}")

        # Create all tables from the LocalBase metadata
        LocalBase.metadata.create_all(engine)

        SessionLocal = sessionmaker(bind=engine)

        yield db_path, SessionLocal

        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_scenario_1_no_filtering_when_no_relevance_set(
        self, temp_ref_db, temp_local_db
    ):
        """
        Scenario 1: No filtering when no predicates marked relevant.

        Steps:
        1. Create reference links
        2. Query without any predicates marked relevant
        3. Verify all links are returned
        """
        _local_db_path, SessionLocal = temp_local_db
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_ref_db) as ref_manager:
            # Create external predicates
            ref_manager.add_external_predicate(
                title="subClassOf",
                definition="Class hierarchy relationship",
                source="schema.org",
                external_id="subClassOf",
            )

            ref_manager.add_external_predicate(
                title="property",
                definition="Property relationship",
                source="schema.org",
                external_id="property",
            )

            # Create reference nodes
            node1 = ref_manager.add_reference_node(
                title="Person",
                definition="A human being",
                source="schema.org",
                external_id="Person",
            )

            node2 = ref_manager.add_reference_node(
                title="Thing",
                definition="The most generic type",
                source="schema.org",
                external_id="Thing",
            )

            # Create reference links
            ref_manager.add_reference_link(
                subject_node=node1.id, predicate="subClassOf", object_node=node2.id
            )

            ref_manager.add_reference_link(
                subject_node=node1.id, predicate="property", object_node=node2.id
            )

            # Create filter service with empty local DB (no predicates marked)
            local_session = SessionLocal()
            try:
                filter_service = ReferenceFilterService(
                    local_session, ref_manager
                )

                # Get all links
                all_links = ref_manager.get_node_links(
                    node1.id, direction="outbound"
                )

                # Apply filter
                filtered_links, stats = filter_service.filter_links(all_links)

                # Should return all links when no filtering configured
                assert len(filtered_links) == 2
                assert stats["filtering_active"] is False
                assert stats["filtered_count"] == 0
            finally:
                local_session.close()

    def test_scenario_2_filtering_with_relevant_predicates(
        self, temp_ref_db, temp_local_db
    ):
        """
        Scenario 2: Filter links based on relevant predicates.

        Steps:
        1. Create reference links with different predicates
        2. Mark one predicate as relevant in local DB
        3. Apply filtering
        4. Verify only relevant predicate links are returned
        """
        _local_db_path, SessionLocal = temp_local_db
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_ref_db) as ref_manager:
            # Create external predicates
            ref_manager.add_external_predicate(
                title="subClassOf",
                definition="Class hierarchy relationship",
                source="schema.org",
                external_id="subClassOf",
            )

            ref_manager.add_external_predicate(
                title="property",
                definition="Property relationship",
                source="schema.org",
                external_id="property",
            )

            ref_manager.add_external_predicate(
                title="relatedTo",
                definition="Related entity",
                source="schema.org",
                external_id="relatedTo",
            )

            # Create reference nodes and links
            node1 = ref_manager.add_reference_node(
                title="Person",
                definition="A human",
                source="schema.org",
                external_id="Person",
            )
            node2 = ref_manager.add_reference_node(
                title="Thing",
                definition="Generic type",
                source="schema.org",
                external_id="Thing",
            )

            ref_manager.add_reference_link(node1.id, "subClassOf", node2.id)
            ref_manager.add_reference_link(node1.id, "property", node2.id)
            ref_manager.add_reference_link(node1.id, "relatedTo", node2.id)

            # Create local predicate and mark as relevant
            local_session = SessionLocal()
            try:
                # Create predicate with mapping
                mapping_data = [{"source": "schema.org", "external_id": "subClassOf"}]

                predicate = Predicate(
                    id="pred1",
                    identifier="hierarchy",
                    title="Hierarchy Relationship",
                    definition="Represents hierarchical relationships",
                    mapping=json.dumps(mapping_data),
                    is_relevant=True,  # Mark as relevant
                    date_created=datetime.utcnow(),
                    date_modified=datetime.utcnow(),
                )
                local_session.add(predicate)
                local_session.commit()

                # Apply filtering
                filter_service = ReferenceFilterService(
                    local_session, ref_manager
                )
                all_links = ref_manager.get_node_links(
                    node1.id, direction="outbound"
                )

                filtered_links, stats = filter_service.filter_links(all_links)

                # Should only return subClassOf link
                assert len(filtered_links) == 1
                assert filtered_links[0].predicate == "subClassOf"
                assert stats["filtering_active"] is True
                assert stats["filtered_count"] == 2
                assert stats["total_before"] == 3
                assert stats["total_after"] == 1
                assert "schema.org:subClassOf" in stats["predicates_used"]

            finally:
                local_session.close()

    def test_scenario_3_exclude_irrelevant_predicates(
        self, temp_ref_db, temp_local_db
    ):
        """
        Scenario 3: Exclude links using irrelevant predicates.

        Steps:
        1. Create reference links
        2. Mark predicates as irrelevant
        3. Verify those links are filtered out
        4. Check statistics
        """
        _local_db_path, SessionLocal = temp_local_db
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_ref_db) as ref_manager:
            # Create external predicates
            ref_manager.add_external_predicate(
                title="subClassOf",
                definition="Hierarchy",
                source="schema.org",
                external_id="subClassOf",
            )
            ref_manager.add_external_predicate(
                title="deprecated",
                definition="Deprecated property",
                source="schema.org",
                external_id="deprecated",
            )

            # Create nodes and links
            node1 = ref_manager.add_reference_node(
                title="Person",
                definition="Human",
                source="schema.org",
                external_id="Person",
            )
            node2 = ref_manager.add_reference_node(
                title="Thing",
                definition="Generic",
                source="schema.org",
                external_id="Thing",
            )

            ref_manager.add_reference_link(node1.id, "subClassOf", node2.id)
            ref_manager.add_reference_link(node1.id, "deprecated", node2.id)

            # Mark deprecated as irrelevant
            local_session = SessionLocal()
            try:
                predicate = Predicate(
                    id="pred1",
                    identifier="deprecated_rel",
                    title="Deprecated Relationship",
                    definition="Old relationships",
                    mapping=json.dumps(
                        [{"source": "schema.org", "external_id": "deprecated"}]
                    ),
                    is_relevant=False,  # Mark as irrelevant
                    date_created=datetime.utcnow(),
                    date_modified=datetime.utcnow(),
                )
                local_session.add(predicate)
                local_session.commit()

                # Apply filtering
                filter_service = ReferenceFilterService(
                    local_session, ref_manager
                )
                all_links = ref_manager.get_node_links(
                    node1.id, direction="outbound"
                )

                filtered_links, stats = filter_service.filter_links(all_links)

                # Should exclude deprecated, include others
                assert len(filtered_links) == 1
                assert filtered_links[0].predicate == "subClassOf"
                assert stats["filtered_count"] == 1

            finally:
                local_session.close()

    def test_scenario_4_null_relevance_no_effect(
        self, temp_ref_db, temp_local_db
    ):
        """
        Scenario 4: Predicates with is_relevant=null don't affect filtering.

        Steps:
        1. Create predicates with null relevance
        2. Apply filtering
        3. Verify null predicates don't affect results
        """
        _local_db_path, SessionLocal = temp_local_db
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_ref_db) as ref_manager:
            # Create external predicates
            ref_manager.add_external_predicate(
                title="test1",
                definition="Test",
                source="test",
                external_id="test1",
            )

            # Create nodes and links
            node1 = ref_manager.add_reference_node(
                title="Node1",
                definition="Test node",
                source="test",
                external_id="n1",
            )
            node2 = ref_manager.add_reference_node(
                title="Node2",
                definition="Test node",
                source="test",
                external_id="n2",
            )

            ref_manager.add_reference_link(node1.id, "test1", node2.id)

            # Create predicate with null relevance
            local_session = SessionLocal()
            try:
                predicate = Predicate(
                    id="pred1",
                    identifier="test",
                    title="Test",
                    definition="Test",
                    mapping=json.dumps(
                        [{"source": "test", "external_id": "test1"}]
                    ),
                    is_relevant=None,  # Not evaluated
                    date_created=datetime.utcnow(),
                    date_modified=datetime.utcnow(),
                )
                local_session.add(predicate)
                local_session.commit()

                # Apply filtering
                filter_service = ReferenceFilterService(
                    local_session, ref_manager
                )
                all_links = ref_manager.get_node_links(
                    node1.id, direction="outbound"
                )

                filtered_links, stats = filter_service.filter_links(all_links)

                # Null predicates should not affect filtering - returns all
                assert len(filtered_links) == 1
                assert stats["filtering_active"] is False

            finally:
                local_session.close()

    def test_scenario_5_multiple_sources_filtering(
        self, temp_ref_db, temp_local_db
    ):
        """
        Scenario 5: Filter across multiple reference sources.

        Steps:
        1. Create predicates from schema.org and wikidata
        2. Mark some as relevant
        3. Verify filtering works across sources
        """
        _local_db_path, SessionLocal = temp_local_db
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_ref_db) as ref_manager:
            # Create external predicates from different sources
            ref_manager.add_external_predicate(
                title="subClassOf",
                definition="Schema hierarchy",
                source="schema.org",
                external_id="subClassOf",
            )
            ref_manager.add_external_predicate(
                title="subclass of",
                definition="Wikidata hierarchy",
                source="wikidata",
                external_id="P279",
            )
            ref_manager.add_external_predicate(
                title="property",
                definition="Schema property",
                source="schema.org",
                external_id="property",
            )

            # Create nodes and links
            node1 = ref_manager.add_reference_node(
                title="Person",
                definition="Human",
                source="schema.org",
                external_id="Person",
            )
            node2 = ref_manager.add_reference_node(
                title="Thing",
                definition="Generic",
                source="schema.org",
                external_id="Thing",
            )

            ref_manager.add_reference_link(node1.id, "subClassOf", node2.id)
            ref_manager.add_reference_link(node1.id, "P279", node2.id)
            ref_manager.add_reference_link(node1.id, "property", node2.id)

            # Mark both hierarchy predicates as relevant
            local_session = SessionLocal()
            try:
                predicate = Predicate(
                    id="pred1",
                    identifier="hierarchy",
                    title="Hierarchy",
                    definition="All hierarchy relationships",
                    mapping=json.dumps(
                        [
                            {"source": "schema.org", "external_id": "subClassOf"},
                            {"source": "wikidata", "external_id": "P279"},
                        ]
                    ),
                    is_relevant=True,
                    date_created=datetime.utcnow(),
                    date_modified=datetime.utcnow(),
                )
                local_session.add(predicate)
                local_session.commit()

                # Apply filtering
                filter_service = ReferenceFilterService(
                    local_session, ref_manager
                )
                all_links = ref_manager.get_node_links(
                    node1.id, direction="outbound"
                )

                filtered_links, stats = filter_service.filter_links(all_links)

                # Should include both hierarchy predicates
                assert len(filtered_links) == 2
                predicates_in_results = {
                    link.predicate for link in filtered_links
                }
                assert "subClassOf" in predicates_in_results
                assert "P279" in predicates_in_results
                assert "property" not in predicates_in_results
                assert len(stats["predicates_used"]) == 2

            finally:
                local_session.close()

    def test_scenario_6_filter_statistics_endpoint(
        self, temp_ref_db, temp_local_db
    ):
        """
        Scenario 6: Get filter statistics.

        Steps:
        1. Create and mark various predicates
        2. Get statistics
        3. Verify counts are correct
        """
        _local_db_path, SessionLocal = temp_local_db
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_ref_db) as ref_manager:
            # Create local predicates with various states
            local_session = SessionLocal()
            try:
                predicates = [
                    Predicate(
                        id="pred1",
                        identifier="rel1",
                        title="Relevant 1",
                        definition="Test",
                        mapping=json.dumps(
                            [{"source": "schema.org", "external_id": "test1"}]
                        ),
                        is_relevant=True,
                        date_created=datetime.utcnow(),
                        date_modified=datetime.utcnow(),
                    ),
                    Predicate(
                        id="pred2",
                        identifier="rel2",
                        title="Relevant 2",
                        definition="Test",
                        mapping=json.dumps(
                            [{"source": "schema.org", "external_id": "test2"}]
                        ),
                        is_relevant=True,
                        date_created=datetime.utcnow(),
                        date_modified=datetime.utcnow(),
                    ),
                    Predicate(
                        id="pred3",
                        identifier="irrel1",
                        title="Irrelevant 1",
                        definition="Test",
                        mapping=json.dumps(
                            [{"source": "schema.org", "external_id": "test3"}]
                        ),
                        is_relevant=False,
                        date_created=datetime.utcnow(),
                        date_modified=datetime.utcnow(),
                    ),
                    Predicate(
                        id="pred4",
                        identifier="null1",
                        title="Null 1",
                        definition="Test",
                        mapping=json.dumps(
                            [{"source": "schema.org", "external_id": "test4"}]
                        ),
                        is_relevant=None,
                        date_created=datetime.utcnow(),
                        date_modified=datetime.utcnow(),
                    ),
                ]

                for pred in predicates:
                    local_session.add(pred)
                local_session.commit()

                # Get statistics
                filter_service = ReferenceFilterService(
                    local_session, ref_manager
                )
                stats = filter_service.get_filter_statistics()

                # Verify counts
                assert stats["total_predicates"] == 4
                assert stats["relevant_count"] == 2
                assert stats["irrelevant_count"] == 1
                assert stats["unmapped_count"] == 1
                assert len(stats["relevant_external_predicates"]) == 2
                assert len(stats["irrelevant_external_predicates"]) == 1

            finally:
                local_session.close()

    def test_scenario_7_performance_minimal_overhead(
        self, temp_ref_db, temp_local_db
    ):
        """
        Scenario 7: Verify filtering performance is acceptable.

        Steps:
        1. Create many links
        2. Apply filtering
        3. Verify overhead is < 10ms
        """
        import time

        _local_db_path, SessionLocal = temp_local_db
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_ref_db) as ref_manager:
            # Create reference predicates and nodes
            ref_manager.add_external_predicate(
                title="test",
                definition="Test",
                source="test",
                external_id="test",
            )

            nodes = []
            for i in range(10):
                node = ref_manager.add_reference_node(
                    title=f"Node{i}",
                    definition="Test",
                    source="test",
                    external_id=f"n{i}",
                )
                nodes.append(node)

            # Create many links
            links = []
            for i in range(len(nodes) - 1):
                link = ref_manager.add_reference_link(
                    nodes[i].id, "test", nodes[i + 1].id
                )
                links.append(link)

            # Mark predicate as relevant
            local_session = SessionLocal()
            try:
                predicate = Predicate(
                    id="pred1",
                    identifier="test",
                    title="Test",
                    definition="Test",
                    mapping=json.dumps(
                        [{"source": "test", "external_id": "test"}]
                    ),
                    is_relevant=True,
                    date_created=datetime.utcnow(),
                    date_modified=datetime.utcnow(),
                )
                local_session.add(predicate)
                local_session.commit()

                # Measure filtering time
                filter_service = ReferenceFilterService(
                    local_session, ref_manager
                )
                all_links = ref_manager.get_node_links(
                    nodes[0].id, direction="outbound"
                )

                start_time = time.time()
                filtered_links, _stats = filter_service.filter_links(all_links)
                elapsed_ms = (time.time() - start_time) * 1000

                # Verify performance (should be < 10ms for small dataset)
                assert (
                    elapsed_ms < 10.0
                ), f"Filtering took {elapsed_ms:.2f}ms, expected < 10ms"
                assert len(filtered_links) > 0

            finally:
                local_session.close()
