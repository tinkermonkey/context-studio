"""
Integration tests for vector search functionality with real embeddings.

Tests search_by_similarity with real sentence-transformers model to validate
known-query accuracy requirements (TC-I002).
"""

import os
import tempfile
import time
from typing import cast

import pytest
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager

# Skip if embeddings not available
pytest.importorskip(
    "embeddings.generate_embeddings", reason="embeddings module not available"
)


@pytest.fixture(scope="module")
def manager_with_schema_org_data():
    """
    Create a manager with Schema.org test data and real embeddings.

    This fixture creates a realistic dataset for integration testing.
    """
    from embeddings.generate_embeddings import generate_embedding

    config = ReferenceConfig()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    manager = ReferenceManager(config, db_path=db_path)

    # Add Schema.org entities with real embeddings
    test_entities = [
        {
            "title": "Person",
            "definition": "A person (alive, dead, undead, or fictional).",
            "external_id": "Person",
        },
        {
            "title": "Organization",
            "definition": "An organization such as a school, NGO, corporation, club, etc.",
            "external_id": "Organization",
        },
        {
            "title": "CreativeWork",
            "definition": "The most generic kind of creative work, including books, movies, photographs, software programs, etc.",
            "external_id": "CreativeWork",
        },
        {
            "title": "Event",
            "definition": "An event happening at a certain time and location, such as a concert, lecture, or festival.",
            "external_id": "Event",
        },
        {
            "title": "Place",
            "definition": "Entities that have a somewhat fixed, physical extension.",
            "external_id": "Place",
        },
        {
            "title": "Product",
            "definition": "Any offered product or service. For example: a pair of shoes; a concert ticket; the rental of a car.",
            "external_id": "Product",
        },
        {"title": "Book", "definition": "A book.", "external_id": "Book"},
        {"title": "Movie", "definition": "A movie.", "external_id": "Movie"},
        {
            "title": "MusicRecording",
            "definition": "A music recording (track), usually a single song.",
            "external_id": "MusicRecording",
        },
        {
            "title": "Restaurant",
            "definition": "A restaurant.",
            "external_id": "Restaurant",
        },
        {
            "title": "Hotel",
            "definition": "A hotel is an establishment that provides paid lodging.",
            "external_id": "Hotel",
        },
        {
            "title": "LocalBusiness",
            "definition": "A particular physical business or branch of an organization.",
            "external_id": "LocalBusiness",
        },
        {
            "title": "Article",
            "definition": "An article, such as a news article or piece of investigative report.",
            "external_id": "Article",
        },
        {
            "title": "SoftwareApplication",
            "definition": "A software application.",
            "external_id": "SoftwareApplication",
        },
        {
            "title": "WebPage",
            "definition": "A web page. Every web page is implicitly assumed to be declared to be of type WebPage.",
            "external_id": "WebPage",
        },
    ]

    for entity in test_entities:
        title_emb = generate_embedding(entity["title"])
        def_emb = generate_embedding(entity["definition"])

        manager.add_reference_node(
            title=entity["title"],
            definition=entity["definition"],
            source="schema.org",
            external_id=entity["external_id"],
            title_embedding=title_emb,
            definition_embedding=def_emb,
            embedding_dims=384,  # sentence-transformers default
        )

    yield manager, db_path

    manager.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestVectorSearchAccuracy:
    """
    Test suite for vector search accuracy with real embeddings.

    Validates TC-I002 requirement: known-query accuracy ≥90% success rate.
    """

    def test_known_queries_accuracy(self, manager_with_schema_org_data):
        """
        Test that known queries achieve ≥90% accuracy.

        This test uses 15-20 known queries and validates that the correct
        entity appears in the top-3 results for at least 90% of queries.

        Validates TC-I002 requirement with REAL sentence-transformers model.
        """
        from embeddings.generate_embeddings import generate_embedding

        manager, _db_path = manager_with_schema_org_data

        def embedding_gen(text: str) -> bytes:
            return cast(bytes, generate_embedding(text))

        # Define known queries and expected results (entity should be in top-3)
        test_queries = [
            ("human being", "Person"),
            ("individual person", "Person"),
            ("company or institution", "Organization"),
            ("business entity", "Organization"),
            ("creative content", "CreativeWork"),
            ("artistic work", "CreativeWork"),
            ("happening or occasion", "Event"),
            ("scheduled activity", "Event"),
            ("location or venue", "Place"),
            ("physical location", "Place"),
            ("item for sale", "Product"),
            ("merchandise", "Product"),
            ("written publication", "Book"),
            ("film or cinema", "Movie"),
            ("song recording", "MusicRecording"),
            ("dining establishment", "Restaurant"),
            ("lodging accommodation", "Hotel"),
            ("local shop or store", "LocalBusiness"),
            ("news story", "Article"),
            ("computer program", "SoftwareApplication"),
        ]

        successful_queries = 0
        total_queries = len(test_queries)
        failed_queries = []

        for query, expected_entity in test_queries:
            results = manager.search_by_similarity(
                query_text=query,
                source="schema.org",
                limit=3,  # Check top-3 results
                threshold=0.0,  # No threshold filtering for accuracy test
                embedding_generator=embedding_gen,
            )

            # Check if expected entity is in top-3
            top_3_titles = [node.title for node, score in results[:3]]

            if expected_entity in top_3_titles:
                successful_queries += 1
            else:
                failed_queries.append(
                    {
                        "query": query,
                        "expected": expected_entity,
                        "got_top_3": top_3_titles,
                    }
                )

        # Calculate accuracy
        accuracy = (successful_queries / total_queries) * 100

        # Report results
        print("\nVector Search Accuracy Test Results:")
        print(f"Total queries: {total_queries}")
        print(f"Successful: {successful_queries}")
        print(f"Accuracy: {accuracy:.1f}%")

        if failed_queries:
            print(f"\nFailed queries ({len(failed_queries)}):")
            for failure in failed_queries:
                print(f"  Query: '{failure['query']}'")
                print(f"    Expected: {failure['expected']}")
                print(f"    Got top-3: {failure['got_top_3']}")

        # Validate TC-I002: ≥90% accuracy (allows 2-3 failures out of 15-20 queries)
        assert (
            accuracy >= 90.0
        ), f"Vector search accuracy {accuracy:.1f}% is below required 90% (TC-I002)"

    def test_threshold_filtering_accuracy(self, manager_with_schema_org_data):
        """
        Test that threshold filtering works correctly with real embeddings.

        Validates that similarity threshold correctly filters results.
        """
        from embeddings.generate_embeddings import generate_embedding

        manager, _db_path = manager_with_schema_org_data

        def embedding_gen(text: str) -> bytes:
            return cast(bytes, generate_embedding(text))

        # Search with high threshold
        results_high = manager.search_by_similarity(
            query_text="human being",
            source="schema.org",
            limit=20,
            threshold=0.8,
            embedding_generator=embedding_gen,
        )

        # Search with low threshold
        results_low = manager.search_by_similarity(
            query_text="human being",
            source="schema.org",
            limit=20,
            threshold=0.3,
            embedding_generator=embedding_gen,
        )

        # High threshold should return fewer or equal results
        assert len(results_high) <= len(
            results_low
        ), "Higher threshold should return fewer or equal results"

        # All results from high threshold search should have score >= 0.8
        for node, score in results_high:
            assert (
                score >= 0.8
            ), f"Result {node.title} has score {score} < threshold 0.8"

        # All results from low threshold search should have score >= 0.3
        for node, score in results_low:
            assert (
                score >= 0.3
            ), f"Result {node.title} has score {score} < threshold 0.3"


class TestVectorSearchPerformance:
    """
    Test suite for vector search performance.

    Validates TC-P002 and TC-S003: search latency requirements.
    """

    def test_search_performance_under_50ms(self, manager_with_schema_org_data):
        """
        Test that vector search returns top-20 results in <50ms.

        Validates TC-P002 and TC-S003 performance requirements.
        """
        from embeddings.generate_embeddings import generate_embedding

        manager, _db_path = manager_with_schema_org_data

        def embedding_gen(text: str) -> bytes:
            return cast(bytes, generate_embedding(text))

        # Warm up the search (first query may be slower due to caching)
        manager.search_by_similarity(
            query_text="test warmup",
            limit=20,
            threshold=0.0,
            embedding_generator=embedding_gen,
        )

        # Measure search performance
        test_queries = [
            "human being",
            "organization",
            "creative work",
            "event",
            "place",
        ]

        search_times = []

        for query in test_queries:
            start_time = time.perf_counter()

            manager.search_by_similarity(
                query_text=query,
                limit=20,
                threshold=0.0,
                embedding_generator=embedding_gen,
            )

            end_time = time.perf_counter()
            search_time_ms = (end_time - start_time) * 1000

            search_times.append(search_time_ms)

        # Calculate average search time
        avg_search_time = sum(search_times) / len(search_times)
        max_search_time = max(search_times)

        print("\nVector Search Performance Results:")
        print(f"Average search time: {avg_search_time:.2f}ms")
        print(f"Max search time: {max_search_time:.2f}ms")
        print(f"Individual times: {[f'{t:.2f}ms' for t in search_times]}")

        # Validate TC-P002 and TC-S003: <50ms for top-20 queries
        # Note: This is for the search operation only, not including embedding generation
        # In production, embedding generation would be done once and cached
        assert (
            avg_search_time < 50.0
        ), f"Average search time {avg_search_time:.2f}ms exceeds 50ms requirement (TC-P002, TC-S003)"

    def test_search_fails_fast_on_error(self, manager_with_schema_org_data):
        """
        Test that search fails fast with HTTP 500 on vector search errors.

        Validates that errors are not silently converted to empty results.
        """
        manager, _db_path = manager_with_schema_org_data

        # Test with invalid embedding generator that returns wrong size
        def bad_embedding_gen(text: str) -> bytes:
            import numpy as np

            # Return wrong size embedding
            return np.array([0.1, 0.2], dtype=np.float32).tobytes()

        # Should raise RuntimeError, not return empty results
        with pytest.raises(RuntimeError, match="Vector search failed"):
            manager.search_by_similarity(
                query_text="test",
                limit=20,
                threshold=0.0,
                embedding_generator=bad_embedding_gen,
            )
