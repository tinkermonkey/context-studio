"""
Integration tests for Phase 4: API Contract Validation.

Test Cases:
- TC-I001: Vector similarity search accuracy
- TC-I002: Link retrieval and traversal
- TC-I003: Multi-hop relationship queries
- TC-I004: Query performance benchmarks
- TC-I005: Known queries validation
"""

import pytest
import tempfile
import os
import json
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.models import ReferenceNode, ReferenceLink
from uuid import uuid4
from datetime import date


@pytest.fixture(scope="module")
def known_queries():
    """Load known queries from fixture file."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), '..', 'fixtures', 'known_queries.json'
    )

    with open(fixture_path, 'r') as f:
        return json.load(f)


@pytest.fixture(scope="module")
def integration_test_database():
    """Create a comprehensive test database for integration testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path=db_path)

    # Create embeddings helper - uses text content for deterministic results
    def create_embedding(text: str) -> bytes:
        """Create embedding based on text content."""
        # Use text hash for reproducible embeddings
        hash_val = abs(hash(text)) % 1000 / 1000.0
        vec = np.full(384, hash_val, dtype=np.float32)
        # Add some variation based on text length
        for i, char in enumerate(text[:20]):
            vec[i % 384] += ord(char) / 1000.0
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    # Create nodes based on Schema.org sample
    nodes = {}

    # Entities
    entities = [
        ("Person", "A person (alive, dead, undead, or fictional).", "Person"),
        ("Thing", "The most generic type of item.", "Thing"),
        ("Organization", "An organization such as a school, NGO, corporation, club, etc.", "Organization"),
        ("Place", "Entities that have a somewhat fixed, physical extension.", "Place"),
        ("CreativeWork", "The most generic kind of creative work, including books, movies, photographs, software programs, etc.", "CreativeWork"),
        ("Book", "A book.", "Book"),
        ("Event", "An event happening at a certain time and location.", "Event"),
        ("Product", "Any offered product or service.", "Product"),
    ]

    for title, definition, ext_id in entities:
        node = manager.add_reference_node(
            title=title,
            definition=definition,
            source="schema.org",
            external_id=ext_id,
            attributes=json.dumps({"@type": "entity"}),
            title_embedding=create_embedding(title),
            definition_embedding=create_embedding(definition),
            embedding_dims=384
        )
        nodes[ext_id.lower()] = node

    # Properties
    properties = [
        ("author", "The author of this content or rating.", "author"),
        ("name", "The name of the item.", "name"),
        ("givenName", "Given name. In the U.S., the first name of a Person.", "givenName"),
        ("familyName", "Family name. In the U.S., the last name of a Person.", "familyName"),
        ("publisher", "The publisher of the creative work.", "publisher"),
        ("organizer", "An organizer of an Event.", "organizer"),
        ("location", "The location of for example where the event is happening.", "location"),
        ("employee", "Someone working for this organization.", "employee"),
        ("founder", "A person who founded this organization.", "founder"),
    ]

    for title, definition, ext_id in properties:
        node = manager.add_reference_node(
            title=title,
            definition=definition,
            source="schema.org",
            external_id=ext_id,
            attributes=json.dumps({"@type": "property"}),
            title_embedding=create_embedding(title),
            definition_embedding=create_embedding(definition),
            embedding_dims=384
        )
        nodes[ext_id.lower()] = node

    # Rollback any pending transactions
    if manager.session.in_transaction():
        manager.session.rollback()

    # Create relationships
    links = []

    # SubClassOf relationships
    subclass_relations = [
        ("person", "thing"),
        ("organization", "thing"),
        ("place", "thing"),
        ("creativework", "thing"),
        ("book", "creativework"),
        ("event", "thing"),
        ("product", "thing"),
    ]

    for subject_key, object_key in subclass_relations:
        link = ReferenceLink(
            id=str(uuid4()),
            subject_node=nodes[subject_key].id,
            predicate="subClassOf",
            object_node=nodes[object_key].id,
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat()
        )
        links.append(link)

    # DomainIncludes relationships (property -> entity)
    domain_relations = [
        ("author", "creativework"),
        ("author", "book"),
        ("name", "thing"),
        ("givenname", "person"),
        ("familyname", "person"),
        ("publisher", "creativework"),
        ("organizer", "event"),
        ("location", "event"),
        ("location", "organization"),
        ("employee", "organization"),
        ("founder", "organization"),
    ]

    for property_key, entity_key in domain_relations:
        link = ReferenceLink(
            id=str(uuid4()),
            subject_node=nodes[property_key].id,
            predicate="domainIncludes",
            object_node=nodes[entity_key].id,
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat()
        )
        links.append(link)

    # RangeIncludes relationships (property -> entity)
    range_relations = [
        ("author", "person"),
        ("author", "organization"),
        ("publisher", "person"),
        ("publisher", "organization"),
        ("organizer", "person"),
        ("organizer", "organization"),
        ("location", "place"),
        ("employee", "person"),
        ("founder", "person"),
    ]

    for property_key, entity_key in range_relations:
        link = ReferenceLink(
            id=str(uuid4()),
            subject_node=nodes[property_key].id,
            predicate="rangeIncludes",
            object_node=nodes[entity_key].id,
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat()
        )
        links.append(link)

    manager.session.add_all(links)
    manager.session.commit()
    manager.close()

    yield db_path, nodes

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


class TestTC_I001_VectorSimilaritySearchAccuracy:
    """
    TC-I001: Vector similarity search accuracy test.

    Target: >95% accuracy on known queries
    """

    def test_known_queries_accuracy(self, integration_test_database, known_queries):
        """Test search accuracy against known queries."""
        db_path, nodes = integration_test_database

        # Mock embedding to match our test data
        def mock_embedding(text: str) -> bytes:
            hash_val = abs(hash(text)) % 1000 / 1000.0
            vec = np.full(384, hash_val, dtype=np.float32)
            for i, char in enumerate(text[:20]):
                vec[i % 384] += ord(char) / 1000.0
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        config = ReferenceConfig()
        total_queries = 0
        successful_queries = 0

        for query_spec in known_queries["queries"]:
            total_queries += 1
            query_text = query_spec["query"]
            expected_results = query_spec.get("expected_results", [])

            # Execute search
            with ReferenceManager(config, db_path=db_path) as manager:
                results = manager.search_by_similarity(
                    query_text=query_text,
                    limit=10,
                    threshold=0.6,
                    embedding_generator=mock_embedding
                )

                # Check if expected results are found
                found_identifiers = [r[0].external_id for r in results]

                for expected in expected_results:
                    if expected["identifier"] in found_identifiers:
                        # Verify similarity threshold if specified
                        result = [r for r in results if r[0].external_id == expected["identifier"]][0]
                        if result[1] >= expected.get("min_similarity", 0.0):
                            successful_queries += 1
                            break

        accuracy = (successful_queries / total_queries) * 100 if total_queries > 0 else 0
        assert accuracy >= 95, f"Search accuracy {accuracy:.1f}% is below 95% target"


class TestTC_I002_LinkRetrievalAndTraversal:
    """
    TC-I002: Link retrieval and traversal validation.

    Tests ability to retrieve and navigate relationship links.
    """

    def test_retrieve_domain_includes_links(self, integration_test_database):
        """Test retrieval of domainIncludes links."""
        db_path, nodes = integration_test_database

        config = ReferenceConfig()
        with ReferenceManager(config, db_path=db_path) as manager:
            # Get author property
            author_node = nodes.get("author")
            assert author_node is not None

            # Get links
            links = manager.get_node_links(
                node_id=author_node.id,
                direction="outbound",
                predicate="domainIncludes"
            )

            assert len(links) > 0, "No domainIncludes links found for author property"

            # Verify links point to expected entities
            target_ids = [link.object_node for link in links]
            target_nodes = [manager.get_reference_node(tid) for tid in target_ids]
            target_identifiers = [n.external_id for n in target_nodes if n]

            assert "CreativeWork" in target_identifiers or "Book" in target_identifiers

    def test_traverse_subclass_hierarchy(self, integration_test_database):
        """Test traversing subClassOf hierarchy."""
        db_path, nodes = integration_test_database

        config = ReferenceConfig()
        with ReferenceManager(config, db_path=db_path) as manager:
            # Start with Book, traverse to Thing
            book_node = nodes.get("book")
            assert book_node is not None

            # Get subClassOf links
            links = manager.get_node_links(
                node_id=book_node.id,
                direction="outbound",
                predicate="subClassOf"
            )

            assert len(links) > 0, "No subClassOf links found for Book"

            # Verify hierarchy
            parent_id = links[0].object_node
            parent_node = manager.get_reference_node(parent_id)

            # Book -> CreativeWork or Book -> Thing
            assert parent_node.external_id in ["CreativeWork", "Thing"]


class TestTC_I003_MultiHopRelationshipQueries:
    """
    TC-I003: Multi-hop relationship query validation.

    Tests complex queries that span multiple relationships.
    """

    def test_find_properties_for_entity(self, integration_test_database):
        """Find all properties that apply to an entity via domainIncludes."""
        db_path, nodes = integration_test_database

        config = ReferenceConfig()
        with ReferenceManager(config, db_path=db_path) as manager:
            person_node = nodes.get("person")
            assert person_node is not None

            # Get all properties that have Person in domainIncludes
            links = manager.get_node_links(
                node_id=person_node.id,
                direction="inbound",
                predicate="domainIncludes"
            )

            assert len(links) > 0, "No properties found for Person entity"

            # Get property nodes
            property_ids = [link.subject_node for link in links]
            properties = [manager.get_reference_node(pid) for pid in property_ids]
            property_names = [p.external_id for p in properties if p]

            # Verify expected properties
            assert "givenName" in property_names
            assert "familyName" in property_names

    def test_find_valid_types_for_property(self, integration_test_database):
        """Find valid entity types for a property via rangeIncludes."""
        db_path, nodes = integration_test_database

        config = ReferenceConfig()
        with ReferenceManager(config, db_path=db_path) as manager:
            author_prop = nodes.get("author")
            assert author_prop is not None

            # Get rangeIncludes links
            links = manager.get_node_links(
                node_id=author_prop.id,
                direction="outbound",
                predicate="rangeIncludes"
            )

            assert len(links) > 0, "No rangeIncludes found for author property"

            # Get entity types
            type_ids = [link.object_node for link in links]
            types = [manager.get_reference_node(tid) for tid in type_ids]
            type_names = [t.external_id for t in types if t]

            # Author can be Person or Organization
            assert "Person" in type_names or "Organization" in type_names


class TestTC_I004_QueryPerformanceBenchmarks:
    """
    TC-I004: Query performance benchmarks.

    Validates query performance meets targets.
    """

    def test_search_performance(self, integration_test_database):
        """Verify search executes within performance target."""
        import time
        db_path, nodes = integration_test_database

        def mock_embedding(text: str) -> bytes:
            vec = np.full(384, 0.5, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        config = ReferenceConfig()
        with ReferenceManager(config, db_path=db_path) as manager:
            start_time = time.time()

            results = manager.search_by_similarity(
                query_text="person",
                limit=20,
                threshold=0.5,
                embedding_generator=mock_embedding
            )

            execution_time_ms = (time.time() - start_time) * 1000

            # Search should complete in <100ms for small dataset
            assert execution_time_ms < 100, \
                f"Search took {execution_time_ms:.2f}ms, expected <100ms"

    def test_link_retrieval_performance(self, integration_test_database):
        """Verify link retrieval performance."""
        import time
        db_path, nodes = integration_test_database

        config = ReferenceConfig()
        with ReferenceManager(config, db_path=db_path) as manager:
            person_node = nodes.get("person")

            start_time = time.time()

            links = manager.get_node_links(
                node_id=person_node.id,
                direction="both"
            )

            execution_time_ms = (time.time() - start_time) * 1000

            # Link retrieval should complete in <50ms
            assert execution_time_ms < 50, \
                f"Link retrieval took {execution_time_ms:.2f}ms, expected <50ms"


class TestTC_I005_KnownQueriesValidation:
    """
    TC-I005: Known queries validation with expected results.

    Validates that known queries return expected results with expected links.
    """

    def test_person_who_writes_books_query(self, integration_test_database):
        """Validate 'person who writes books' query (Q001)."""
        db_path, nodes = integration_test_database

        def mock_embedding(text: str) -> bytes:
            hash_val = abs(hash(text)) % 1000 / 1000.0
            vec = np.full(384, hash_val, dtype=np.float32)
            for i, char in enumerate(text[:20]):
                vec[i % 384] += ord(char) / 1000.0
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        config = ReferenceConfig()
        with ReferenceManager(config, db_path=db_path) as manager:
            # Search for "person who writes books"
            results = manager.search_by_similarity(
                query_text="person who writes books",
                limit=10,
                threshold=0.5,
                embedding_generator=mock_embedding
            )

            # Should find Person entity
            person_results = [r for r in results if r[0].external_id == "Person"]
            assert len(person_results) > 0, "Person not found for 'person who writes books' query"

            person_node = person_results[0][0]

            # Get properties via domainIncludes
            links = manager.get_node_links(
                node_id=person_node.id,
                direction="inbound",
                predicate="domainIncludes"
            )

            property_ids = [link.subject_node for link in links]
            properties = [manager.get_reference_node(pid) for pid in property_ids]
            property_names = [p.external_id for p in properties if p]

            # Should include name and givenName
            assert "name" in property_names, "name property not found"
            assert "givenName" in property_names, "givenName property not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
