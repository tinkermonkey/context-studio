"""
Performance tests for vector search functionality.

Tests that vector search meets performance requirements (TC-P002, TC-S003).
"""

import os
import statistics
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
def large_dataset_manager():
    """
    Create a manager with a larger dataset for performance testing.

    This dataset is larger than the integration test dataset to better
    simulate production conditions.
    """
    from embeddings.generate_embeddings import generate_embedding

    config = ReferenceConfig()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    manager = ReferenceManager(config, db_path=db_path)

    # Add 100+ entities with real embeddings
    base_entities = [
        "Person",
        "Organization",
        "CreativeWork",
        "Event",
        "Place",
        "Product",
        "Book",
        "Movie",
        "MusicRecording",
        "Restaurant",
        "Hotel",
        "LocalBusiness",
        "Article",
        "SoftwareApplication",
        "WebPage",
        "VideoObject",
        "ImageObject",
        "AudioObject",
        "MediaObject",
        "Dataset",
        "Action",
        "Thing",
        "Intangible",
        "Service",
        "Offer",
        "Review",
        "Rating",
        "Comment",
        "Question",
        "Answer",
        "Course",
        "EducationalOrganization",
        "School",
        "College",
        "University",
        "MedicalEntity",
        "Drug",
        "MedicalCondition",
        "Hospital",
        "Physician",
        "Recipe",
        "NutritionInformation",
        "Diet",
        "ExercisePlan",
        "PhysicalActivity",
        "Vehicle",
        "Car",
        "Motorcycle",
        "BusOrCoach",
        "Airplane",
        "TVSeries",
        "TVEpisode",
        "RadioSeries",
        "RadioEpisode",
        "PodcastSeries",
        "JobPosting",
        "Occupation",
        "EducationalOccupationalCredential",
        "WorkersUnion",
        "ProfessionalService",
        "GovernmentOrganization",
        "NGO",
        "Corporation",
        "LegalService",
        "PerformingGroup",
        "MusicGroup",
        "DanceGroup",
        "TheaterGroup",
        "SportsTeam",
        "SportsOrganization",
        "Airline",
        "Consortium",
        "FundingScheme",
        "Project",
        "ResearchProject",
        "Brand",
        "ContactPoint",
        "PostalAddress",
        "GeoCoordinates",
        "GeoShape",
        "Country",
        "State",
        "City",
        "AdministrativeArea",
        "LandmarksOrHistoricalBuildings",
        "Park",
        "Beach",
        "Mountain",
        "BodyOfWater",
        "Continent",
        "Cemetery",
        "Crematorium",
        "EventVenue",
        "CivicStructure",
        "Bridge",
        "BusStation",
        "Airport",
        "SubwayStation",
        "TrainStation",
        "TaxiStand",
    ]

    for i, entity in enumerate(base_entities):
        definition = f"A {entity.lower()} entity in the schema.org vocabulary."

        title_emb = generate_embedding(entity)
        def_emb = generate_embedding(definition)

        manager.add_reference_node(
            title=entity,
            definition=definition,
            source="schema.org",
            external_id=entity,
            title_embedding=title_emb,
            definition_embedding=def_emb,
            embedding_dims=384,
        )

    yield manager, db_path

    manager.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestVectorSearchLatency:
    """
    Performance tests for vector search latency.

    Validates TC-P002 and TC-S003 requirements.
    """

    def test_top_20_query_latency(self, large_dataset_manager):
        """
        Test that vector search returns top-20 results in <50ms.

        This test performs multiple queries and validates that the
        search operation (not including embedding generation) completes
        within 50ms.

        Validates TC-P002 and TC-S003.
        """
        from embeddings.generate_embeddings import generate_embedding

        manager, _db_path = large_dataset_manager

        def embedding_gen(text: str) -> bytes:
            return cast(bytes, generate_embedding(text))

        # Warm up queries
        for _ in range(3):
            manager.search_by_similarity(
                query_text="warmup query",
                limit=20,
                threshold=0.0,
                embedding_generator=embedding_gen,
            )

        # Test queries
        test_queries = [
            "person",
            "organization",
            "creative work",
            "event",
            "place",
            "product",
            "book",
            "movie",
            "restaurant",
            "hotel",
            "article",
            "software",
            "vehicle",
            "recipe",
            "job posting",
        ]

        search_times = []

        for query in test_queries:
            # Generate embedding once (would be cached in production)
            query_embedding = embedding_gen(query)

            # Measure search time only
            start_time = time.perf_counter()

            # Use a lambda that returns the pre-generated embedding
            _ = manager.search_by_similarity(
                query_text=query,
                limit=20,
                threshold=0.0,
                embedding_generator=lambda _: query_embedding,
            )

            end_time = time.perf_counter()
            search_time_ms = (end_time - start_time) * 1000

            search_times.append(search_time_ms)

        # Calculate statistics
        avg_time = statistics.mean(search_times)
        median_time = statistics.median(search_times)
        max_time = max(search_times)
        min_time = min(search_times)
        p95_time = statistics.quantiles(search_times, n=20)[
            18
        ]  # 95th percentile

        print(f"\n{'='*60}")
        print("Vector Search Performance Test Results (TC-P002, TC-S003)")
        print(f"{'='*60}")
        print(
            f"Dataset size: {len(test_queries)} queries against {90}+ entities"
        )
        print("Search limit: 20 results")
        print("\nLatency Statistics:")
        print(f"  Average:    {avg_time:6.2f} ms")
        print(f"  Median:     {median_time:6.2f} ms")
        print(f"  Min:        {min_time:6.2f} ms")
        print(f"  Max:        {max_time:6.2f} ms")
        print(f"  P95:        {p95_time:6.2f} ms")
        print("\nRequirement: <50ms for top-20 queries")
        print(f"Status: {'PASS' if avg_time < 50.0 else 'FAIL'}")
        print(f"{'='*60}\n")

        # Validate TC-P002 and TC-S003
        assert (
            avg_time < 50.0
        ), f"Average search latency {avg_time:.2f}ms exceeds 50ms requirement"

        assert (
            p95_time < 50.0
        ), f"P95 search latency {p95_time:.2f}ms exceeds 50ms requirement"

    def test_search_scales_linearly(self, large_dataset_manager):
        """
        Test that search time scales linearly with result limit.

        This helps validate that the implementation is efficient.
        """
        from embeddings.generate_embeddings import generate_embedding

        manager, _db_path = large_dataset_manager

        query_embedding: bytes = cast(bytes, generate_embedding("test query"))

        def embedding_gen(_: str) -> bytes:
            return query_embedding

        # Test with different limits
        limits = [10, 20, 50, 100]
        times = {}

        for limit in limits:
            measurements = []

            for _ in range(5):  # Multiple measurements for stability
                start_time = time.perf_counter()

                _ = manager.search_by_similarity(
                    query_text="test",
                    limit=limit,
                    threshold=0.0,
                    embedding_generator=embedding_gen,
                )

                end_time = time.perf_counter()
                measurements.append((end_time - start_time) * 1000)

            times[limit] = statistics.mean(measurements)

        print("\nSearch Scaling Test:")
        for limit, avg_time in times.items():
            print(f"  Limit {limit:3d}: {avg_time:6.2f} ms")

        # Verify that doubling the limit doesn't more than double the time
        # (indicates efficient implementation)
        time_ratio = times[100] / times[10]
        limit_ratio = 100 / 10

        print(
            f"\nScaling factor: {time_ratio:.2f}x time for {limit_ratio:.0f}x limit"
        )
        print(f"Efficiency: {'GOOD' if time_ratio < limit_ratio else 'POOR'}")

        # Time should not scale worse than linearly
        assert (
            time_ratio < limit_ratio * 1.5
        ), f"Search scaling is suboptimal: {time_ratio:.2f}x time for {limit_ratio:.0f}x limit"

    def test_threshold_filtering_performance(self, large_dataset_manager):
        """
        Test that threshold filtering doesn't significantly impact performance.

        The HAVING clause should be efficient.
        """
        from embeddings.generate_embeddings import generate_embedding

        manager, _db_path = large_dataset_manager

        query_embedding: bytes = cast(bytes, generate_embedding("test query"))

        def embedding_gen(_: str) -> bytes:
            return query_embedding

        # Measure with no threshold
        no_threshold_times = []
        for _ in range(10):
            start = time.perf_counter()
            _ = manager.search_by_similarity(
                query_text="test",
                limit=20,
                threshold=0.0,
                embedding_generator=embedding_gen,
            )
            no_threshold_times.append((time.perf_counter() - start) * 1000)

        # Measure with high threshold
        with_threshold_times = []
        for _ in range(10):
            start = time.perf_counter()
            _ = manager.search_by_similarity(
                query_text="test",
                limit=20,
                threshold=0.8,
                embedding_generator=embedding_gen,
            )
            with_threshold_times.append((time.perf_counter() - start) * 1000)

        avg_no_threshold = statistics.mean(no_threshold_times)
        avg_with_threshold = statistics.mean(with_threshold_times)

        print("\nThreshold Filtering Performance:")
        print(f"  No threshold (0.0):   {avg_no_threshold:6.2f} ms")
        print(f"  With threshold (0.8): {avg_with_threshold:6.2f} ms")
        print(
            f"  Overhead:             {avg_with_threshold - avg_no_threshold:6.2f} ms"
        )

        # Threshold filtering should not add significant overhead
        overhead_pct = (
            (avg_with_threshold - avg_no_threshold) / avg_no_threshold
        ) * 100

        print(f"  Overhead %:           {overhead_pct:6.2f}%")

        assert (
            overhead_pct < 20.0
        ), f"Threshold filtering adds {overhead_pct:.1f}% overhead (should be <20%)"
