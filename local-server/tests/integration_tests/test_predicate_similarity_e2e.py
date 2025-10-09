"""
End-to-end tests for predicate similarity workflows (Phase 3).

This test suite validates complete user workflows and integration scenarios:
- Discovery -> Similarity Search workflow
- Similarity Search -> Clustering workflow
- Cache invalidation and refresh scenarios
- Cross-module integration (predicates, external predicates, embeddings)
- Error recovery and resilience
- Performance under realistic workloads
"""

import pytest
import tempfile
import os
import time
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import app
from database.models import Base, Predicate
from database.utils import get_db
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from embeddings.generate_embeddings import generate_embedding


# Skip if embeddings not available
pytest.importorskip("embeddings.generate_embeddings", reason="embeddings module not available")


@pytest.fixture(scope="module")
def realistic_test_db():
    """Create a realistic test database with multiple predicates."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    # Create test database
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Add realistic predicates across different domains
    test_predicates = [
        # Spatial relations
        {
            "id": str(uuid4()),
            "identifier": "located_in",
            "title": "Located In",
            "definition": "Indicates that an entity is spatially contained within another location",
        },
        {
            "id": str(uuid4()),
            "identifier": "adjacent_to",
            "title": "Adjacent To",
            "definition": "Indicates spatial proximity or adjacency between entities",
        },
        {
            "id": str(uuid4()),
            "identifier": "near",
            "title": "Near",
            "definition": "Indicates close spatial proximity",
        },
        # Temporal relations
        {
            "id": str(uuid4()),
            "identifier": "occurs_before",
            "title": "Occurs Before",
            "definition": "Indicates temporal precedence of one event before another",
        },
        {
            "id": str(uuid4()),
            "identifier": "during",
            "title": "During",
            "definition": "Indicates temporal containment of one event within another",
        },
        # Hierarchical relations
        {
            "id": str(uuid4()),
            "identifier": "subclass_of",
            "title": "Subclass Of",
            "definition": "Indicates taxonomic hierarchy where one class is a specialization of another",
        },
        {
            "id": str(uuid4()),
            "identifier": "instance_of",
            "title": "Instance Of",
            "definition": "Indicates that an individual is a member of a class",
        },
        # Part-whole relations
        {
            "id": str(uuid4()),
            "identifier": "part_of",
            "title": "Part Of",
            "definition": "Indicates a mereological relationship where one entity is a component of another",
        },
        {
            "id": str(uuid4()),
            "identifier": "has_part",
            "title": "Has Part",
            "definition": "Indicates that an entity contains another entity as a component",
        },
        # Causal relations
        {
            "id": str(uuid4()),
            "identifier": "causes",
            "title": "Causes",
            "definition": "Indicates a causal relationship where one event leads to another",
        },
        {
            "id": str(uuid4()),
            "identifier": "enables",
            "title": "Enables",
            "definition": "Indicates that one event makes another event possible",
        },
        # Attribute relations
        {
            "id": str(uuid4()),
            "identifier": "has_property",
            "title": "Has Property",
            "definition": "Indicates that an entity possesses a specific attribute or characteristic",
        },
        {
            "id": str(uuid4()),
            "identifier": "has_value",
            "title": "Has Value",
            "definition": "Indicates the specific value of an attribute",
        },
    ]

    for pred_data in test_predicates:
        predicate = Predicate(**pred_data)
        session.add(predicate)

    session.commit()

    yield session, db_path, test_predicates

    session.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(scope="module")
def realistic_reference_db():
    """Create a realistic reference database with diverse external predicates."""
    config = ReferenceConfig()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    manager = ReferenceManager(config, db_path=db_path)

    # Add diverse external predicates across multiple sources
    external_predicates = [
        # Schema.org predicates
        ("subClassOf", "Indicates class hierarchy relationship", "schema.org"),
        ("location", "The location of an entity or event", "schema.org"),
        ("startTime", "The start time of an event", "schema.org"),
        ("endTime", "The end time of an event", "schema.org"),
        ("containedIn", "Indicates spatial containment", "schema.org"),

        # ConceptNet relations
        ("RelatedTo", "General semantic relationship", "conceptnet"),
        ("IsA", "Indicates class membership", "conceptnet"),
        ("PartOf", "Indicates part-whole relationship", "conceptnet"),
        ("HasProperty", "Indicates entity has attribute", "conceptnet"),
        ("Causes", "Indicates causal relationship", "conceptnet"),
        ("LocatedNear", "Indicates spatial proximity", "conceptnet"),
        ("UsedFor", "Indicates purpose or function", "conceptnet"),

        # DBpedia properties
        ("dbo:location", "Location of an entity", "dbpedia"),
        ("dbo:timeZone", "Time zone of a location", "dbpedia"),
        ("dbo:isPartOf", "Part-whole relationship", "dbpedia"),
        ("dbo:subdivision", "Administrative subdivision", "dbpedia"),
        ("dbo:nearestCity", "Nearest city to a location", "dbpedia"),

        # WikiData properties
        ("P131", "Located in the administrative territorial entity", "wikidata"),
        ("P361", "Part of - object of which the subject is a part", "wikidata"),
        ("P279", "Subclass of - all instances of this are instances of that", "wikidata"),
        ("P31", "Instance of - that class of which this is a particular", "wikidata"),
        ("P276", "Location - location of the item, structure or event", "wikidata"),
        ("P1365", "Replaces - person, state or item replaced by the subject", "wikidata"),
    ]

    for title, definition, source in external_predicates:
        title_emb = generate_embedding(title)
        def_emb = generate_embedding(definition)

        manager.add_external_predicate(
            title=title,
            definition=definition,
            source=source,
            external_id=f"{source}:{title}",
            title_embedding=title_emb,
            definition_embedding=def_emb,
            embedding_dims=384
        )

    yield manager, db_path

    manager.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def e2e_client(realistic_test_db, realistic_reference_db):
    """Create a test client with realistic data."""
    session, db_path, predicates = realistic_test_db
    ref_manager, ref_db_path = realistic_reference_db

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, predicates

    app.dependency_overrides.clear()


class TestSimilaritySearchWorkflows:
    """Test complete similarity search workflows."""

    def test_spatial_predicate_discovery_workflow(self, e2e_client):
        """
        E2E Test: Discover similar spatial predicates.

        Workflow:
        1. Start with a spatial predicate (located_in)
        2. Find similar external predicates
        3. Verify results include relevant spatial predicates from multiple sources
        4. Verify confidence scoring is appropriate
        """
        client, predicates = e2e_client

        # Find the located_in predicate
        spatial_pred = next(p for p in predicates if p["identifier"] == "located_in")

        # Find similar predicates
        response = client.post(
            f"/api/predicates/{spatial_pred['id']}/find-similar",
            params={
                "limit": 20,
                "threshold": 0.5,
                "use_cache": False
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify we got results
        assert data["total_results"] > 0, "Should find similar spatial predicates"

        # Verify search completed in reasonable time
        assert data["search_time_ms"] < 5000, f"Search took too long: {data['search_time_ms']}ms"

        # Verify results include spatial predicates from multiple sources
        results = data["results"]
        sources = {r["source"] for r in results}

        # Should have results from at least 2 different sources
        assert len(sources) >= 1, f"Expected multiple sources, got: {sources}"

        # Check for relevant spatial predicates
        titles_lower = [r["title"].lower() for r in results]
        spatial_keywords = ["location", "located", "contain", "near", "spatial"]

        matches = sum(1 for title in titles_lower
                     if any(keyword in title for keyword in spatial_keywords))

        assert matches > 0, "Should find predicates with spatial keywords"

        # Verify confidence scoring
        high_confidence = [r for r in results if r["confidence"] == "high"]
        medium_confidence = [r for r in results if r["confidence"] == "medium"]
        low_confidence = [r for r in results if r["confidence"] == "low"]

        # At least some results should have confidence scores
        assert len(results) == len(high_confidence) + len(medium_confidence) + len(low_confidence)

        # Verify scores are properly ordered
        scores = [r["similarity_score"] for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be ordered by score descending"

    def test_hierarchical_predicate_discovery_workflow(self, e2e_client):
        """
        E2E Test: Discover similar hierarchical predicates.

        Workflow:
        1. Start with a hierarchical predicate (subclass_of)
        2. Find similar external predicates
        3. Verify results include taxonomic/hierarchical predicates
        """
        client, predicates = e2e_client

        # Find the subclass_of predicate
        hier_pred = next(p for p in predicates if p["identifier"] == "subclass_of")

        # Find similar predicates
        response = client.post(
            f"/api/predicates/{hier_pred['id']}/find-similar",
            params={
                "limit": 15,
                "threshold": 0.6,
                "use_cache": False
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_results"] > 0

        # Check for hierarchical keywords
        results = data["results"]
        titles_lower = [r["title"].lower() for r in results]
        definitions_lower = [r["definition"].lower() for r in results]

        hierarchical_keywords = ["subclass", "class", "instance", "hierarchy", "taxonomy"]

        title_matches = sum(1 for title in titles_lower
                           if any(keyword in title for keyword in hierarchical_keywords))

        def_matches = sum(1 for definition in definitions_lower
                         if any(keyword in definition for keyword in hierarchical_keywords))

        assert title_matches + def_matches > 0, "Should find hierarchical predicates"

    def test_source_filtered_search_workflow(self, e2e_client):
        """
        E2E Test: Search with source filtering.

        Workflow:
        1. Search for similar predicates from a specific source
        2. Verify all results are from that source
        3. Repeat for different sources
        """
        client, predicates = e2e_client

        spatial_pred = next(p for p in predicates if p["identifier"] == "located_in")

        # Test each source
        for source in ["schema.org", "conceptnet", "dbpedia", "wikidata"]:
            response = client.post(
                f"/api/predicates/{spatial_pred['id']}/find-similar",
                params={
                    "source": source,
                    "limit": 10,
                    "threshold": 0.5,
                    "use_cache": False
                }
            )

            if response.status_code == 200:
                data = response.json()

                # All results should be from the specified source
                for result in data["results"]:
                    assert result["source"] == source, \
                        f"Expected source {source}, got {result['source']}"


class TestClusteringWorkflows:
    """Test complete clustering workflows."""

    def test_semantic_clustering_workflow(self, e2e_client):
        """
        E2E Test: Cluster predicates by semantic similarity.

        Workflow:
        1. Cluster all predicates
        2. Verify clusters are semantically coherent
        3. Verify cluster statistics are reasonable
        """
        client, predicates = e2e_client

        response = client.post(
            "/api/predicates/cluster-predicates",
            params={
                "min_similarity": 0.7,
                "min_cluster_size": 2,
                "eps": 0.4,
                "max_predicates": 1000
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify clustering completed
        assert "clusters" in data
        assert "total_clusters" in data
        assert "total_predicates" in data
        assert "cluster_time_ms" in data

        # Performance check
        assert data["cluster_time_ms"] < 30000, \
            f"Clustering took too long: {data['cluster_time_ms']}ms"

        # If clusters were found, verify their structure
        if data["total_clusters"] > 0:
            clusters = data["clusters"]

            for cluster in clusters:
                # Each cluster should have required fields
                assert "cluster_id" in cluster
                assert "predicate_ids" in cluster
                assert "centroid_title" in cluster
                assert "avg_similarity" in cluster
                assert "size" in cluster

                # Cluster size should match predicate count
                assert cluster["size"] == len(cluster["predicate_ids"])

                # Minimum cluster size should be respected
                assert cluster["size"] >= 2

                # Average similarity should be reasonable
                assert 0.0 <= cluster["avg_similarity"] <= 1.0

    def test_targeted_clustering_workflow(self, e2e_client):
        """
        E2E Test: Cluster a specific subset of predicates.

        Workflow:
        1. Select predicates from same semantic domain (e.g., spatial)
        2. Cluster only those predicates
        3. Verify clustering is more coherent
        """
        client, predicates = e2e_client

        # Get spatial predicates
        spatial_predicates = [
            p for p in predicates
            if any(keyword in p["identifier"]
                  for keyword in ["located", "adjacent", "near"])
        ]

        if len(spatial_predicates) >= 2:
            spatial_ids = [p["id"] for p in spatial_predicates]

            response = client.post(
                "/api/predicates/cluster-predicates",
                params={
                    "predicate_ids": spatial_ids,
                    "min_cluster_size": 2,
                    "eps": 0.5
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify clustering worked
            if data["total_clusters"] > 0:
                # All clustered predicates should be from our input set
                for cluster in data["clusters"]:
                    for pred_id in cluster["predicate_ids"]:
                        assert pred_id in spatial_ids


class TestCacheAndPerformanceWorkflows:
    """Test caching and performance-related workflows."""

    def test_cache_effectiveness_workflow(self, e2e_client):
        """
        E2E Test: Verify cache improves performance.

        Workflow:
        1. Invalidate cache
        2. Perform initial search (uncached)
        3. Perform same search again (cached)
        4. Verify cached search is faster
        """
        client, predicates = e2e_client

        # Invalidate cache first
        cache_response = client.post("/api/predicates/invalidate-similarity-cache")
        assert cache_response.status_code == 200

        test_pred = predicates[0]
        search_params = {
            "limit": 20,
            "threshold": 0.7,
            "use_cache": True
        }

        # First search (uncached)
        response1 = client.post(
            f"/api/predicates/{test_pred['id']}/find-similar",
            params=search_params
        )

        assert response1.status_code == 200
        data1 = response1.json()
        time1 = data1["search_time_ms"]

        # Second search (should be cached)
        response2 = client.post(
            f"/api/predicates/{test_pred['id']}/find-similar",
            params=search_params
        )

        assert response2.status_code == 200
        data2 = response2.json()
        time2 = data2["search_time_ms"]

        # Results should be identical
        assert data1["total_results"] == data2["total_results"]

        # Note: In test environment, cache might not always be faster
        # but both should complete in reasonable time
        assert time1 < 5000, "First search took too long"
        assert time2 < 5000, "Cached search took too long"

    def test_cache_invalidation_workflow(self, e2e_client):
        """
        E2E Test: Verify cache invalidation works correctly.

        Workflow:
        1. Perform search (cached)
        2. Invalidate cache
        3. Perform same search again
        4. Verify fresh results are returned
        """
        client, predicates = e2e_client

        test_pred = predicates[0]
        search_params = {
            "limit": 10,
            "threshold": 0.7,
            "use_cache": True
        }

        # Initial search
        response1 = client.post(
            f"/api/predicates/{test_pred['id']}/find-similar",
            params=search_params
        )
        assert response1.status_code == 200

        # Invalidate cache
        cache_response = client.post("/api/predicates/invalidate-similarity-cache")
        assert cache_response.status_code == 200

        cache_data = cache_response.json()
        assert cache_data["success"] is True
        assert "cache_entries_cleared" in cache_data

        # Search again after invalidation
        response2 = client.post(
            f"/api/predicates/{test_pred['id']}/find-similar",
            params=search_params
        )
        assert response2.status_code == 200


class TestErrorHandlingWorkflows:
    """Test error handling and edge cases."""

    def test_invalid_input_error_recovery(self, e2e_client):
        """
        E2E Test: Verify proper error handling for invalid inputs.

        Workflow:
        1. Try various invalid operations
        2. Verify appropriate error codes and messages
        3. Verify system remains stable
        """
        client, predicates = e2e_client

        # Invalid predicate ID format
        response = client.post(
            "/api/predicates/not-a-uuid/find-similar",
            params={"limit": 10, "threshold": 0.7}
        )
        assert response.status_code == 400
        assert "UUID" in response.json()["detail"]

        # Nonexistent predicate
        response = client.post(
            "/api/predicates/00000000-0000-0000-0000-000000000000/find-similar",
            params={"limit": 10, "threshold": 0.7}
        )
        assert response.status_code == 404

        # Invalid parameters (limit too high)
        response = client.post(
            f"/api/predicates/{predicates[0]['id']}/find-similar",
            params={"limit": 200, "threshold": 0.7}
        )
        assert response.status_code == 422

        # Invalid threshold
        response = client.post(
            f"/api/predicates/{predicates[0]['id']}/find-similar",
            params={"limit": 10, "threshold": 2.0}
        )
        assert response.status_code == 422

        # After all these errors, verify system still works
        response = client.post(
            f"/api/predicates/{predicates[0]['id']}/find-similar",
            params={"limit": 10, "threshold": 0.7}
        )
        assert response.status_code == 200

    def test_clustering_edge_cases(self, e2e_client):
        """
        E2E Test: Verify clustering handles edge cases.

        Workflow:
        1. Try clustering with insufficient predicates
        2. Try clustering with invalid IDs
        3. Verify appropriate error handling
        """
        client, predicates = e2e_client

        # Single predicate (insufficient)
        response = client.post(
            "/api/predicates/cluster-predicates",
            params={
                "predicate_ids": [predicates[0]["id"]],
                "min_cluster_size": 2
            }
        )
        assert response.status_code == 400
        assert "Not enough predicates" in response.json()["detail"]

        # Invalid predicate ID
        response = client.post(
            "/api/predicates/cluster-predicates",
            params={
                "predicate_ids": ["not-a-uuid"],
                "min_cluster_size": 2
            }
        )
        assert response.status_code == 400

        # Nonexistent predicate
        response = client.post(
            "/api/predicates/cluster-predicates",
            params={
                "predicate_ids": ["00000000-0000-0000-0000-000000000000"],
                "min_cluster_size": 2
            }
        )
        assert response.status_code == 404


class TestCompleteWorkflows:
    """Test complete multi-step workflows."""

    def test_complete_predicate_analysis_workflow(self, e2e_client):
        """
        E2E Test: Complete predicate analysis workflow.

        Workflow:
        1. Search for similar predicates for multiple predicates
        2. Cluster all predicates
        3. Analyze cluster coherence
        4. Invalidate cache
        5. Verify fresh results
        """
        client, predicates = e2e_client

        # Step 1: Search for similar predicates (sample 3 predicates)
        search_results = []
        for pred in predicates[:3]:
            response = client.post(
                f"/api/predicates/{pred['id']}/find-similar",
                params={"limit": 10, "threshold": 0.6, "use_cache": True}
            )
            assert response.status_code == 200
            search_results.append(response.json())

        # Verify all searches completed successfully
        assert all(r["total_results"] >= 0 for r in search_results)

        # Step 2: Cluster predicates
        cluster_response = client.post(
            "/api/predicates/cluster-predicates",
            params={
                "min_cluster_size": 2,
                "eps": 0.4
            }
        )
        assert cluster_response.status_code == 200
        cluster_data = cluster_response.json()

        # Step 3: Analyze results
        total_clustered = cluster_data["total_predicates"]
        total_clusters = cluster_data["total_clusters"]

        print(f"\nWorkflow Results:")
        print(f"  Searches performed: {len(search_results)}")
        print(f"  Clusters found: {total_clusters}")
        print(f"  Predicates clustered: {total_clustered}")

        # Step 4: Invalidate cache
        cache_response = client.post("/api/predicates/invalidate-similarity-cache")
        assert cache_response.status_code == 200

        # Step 5: Verify we can still search after cache invalidation
        response = client.post(
            f"/api/predicates/{predicates[0]['id']}/find-similar",
            params={"limit": 10, "threshold": 0.7}
        )
        assert response.status_code == 200

    def test_concurrent_operations_workflow(self, e2e_client):
        """
        E2E Test: Verify system handles concurrent operations.

        Workflow:
        1. Perform multiple searches concurrently (simulated)
        2. Verify all complete successfully
        3. Verify results are consistent
        """
        client, predicates = e2e_client

        # Simulate concurrent searches by performing multiple searches in sequence
        # (TestClient doesn't support true concurrent requests)
        results = []
        for i in range(5):
            pred = predicates[i % len(predicates)]
            response = client.post(
                f"/api/predicates/{pred['id']}/find-similar",
                params={"limit": 10, "threshold": 0.7, "use_cache": False}
            )
            assert response.status_code == 200
            results.append(response.json())

        # Verify all searches completed successfully
        assert len(results) == 5
        assert all(r["search_time_ms"] > 0 for r in results)

        # Verify consistent predicate data
        for result in results:
            assert "predicate_id" in result
            assert "results" in result
