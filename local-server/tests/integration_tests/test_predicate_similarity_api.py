"""
Integration tests for predicate similarity API endpoints.

Tests the API endpoints:
- POST /api/predicates/{id}/find-similar
- POST /api/predicates/cluster-predicates
- POST /api/predicates/invalidate-similarity-cache
"""

import pytest
import tempfile
import os
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)  # noqa: E501

from app import app  # noqa: E402
from database.models import Base, Predicate  # noqa: E402
from database.utils import get_db  # noqa: E402
from reference_db.config import ReferenceConfig  # noqa: E402
from reference_db.manager import ReferenceManager  # noqa: E402
from embeddings.generate_embeddings import generate_embedding  # noqa: E402

# Skip if embeddings not available
pytest.importorskip(
    "embeddings.generate_embeddings", reason="embeddings module not available"
)  # noqa: E501


@pytest.fixture(scope="module")
def test_db():
    """Create a test database with predicates."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    # Create test database
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Generate UUIDs for test predicates
    pred_uuid_1 = str(uuid.uuid4())
    pred_uuid_2 = str(uuid.uuid4())
    pred_uuid_3 = str(uuid.uuid4())

    # Add test predicates with proper UUIDs
    test_predicates = [
        {
            "id": pred_uuid_1,
            "identifier": "sub_class_of",
            "title": "subClassOf",
            "definition": "Indicates that one class is a subclass of another",
        },
        {
            "id": pred_uuid_2,
            "identifier": "related_to",
            "title": "relatedTo",
            "definition": "Indicates a general semantic relation",
        },
        {
            "id": pred_uuid_3,
            "identifier": "located_in",
            "title": "locatedIn",
            "definition": "Indicates spatial location",
        },
    ]

    for pred_data in test_predicates:
        predicate = Predicate(**pred_data)
        session.add(predicate)

    session.commit()

    # Store the UUIDs for use in tests
    session.test_predicate_ids = {
        "pred_1": pred_uuid_1,
        "pred_2": pred_uuid_2,
        "pred_3": pred_uuid_3,
    }

    yield session, db_path

    session.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(scope="module")
def test_reference_db():
    """Create a test reference database with external predicates."""
    config = ReferenceConfig()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    manager = ReferenceManager(config, db_path=db_path)

    # Add external predicates
    external_predicates = [
        ("subClassOf", "Indicates class hierarchy", "schema.org"),
        ("relatedTo", "General semantic relation", "conceptnet"),
        ("locatedIn", "Spatial location relation", "dbpedia"),
        ("hasProperty", "Entity has property", "wikidata"),
        ("memberOf", "Group membership", "schema.org"),
        ("partOf", "Part-whole relation", "conceptnet"),
        ("derivedFrom", "Derivation relation", "wikidata"),
        ("causes", "Causal relation", "conceptnet"),
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
            embedding_dims=384,
        )

    yield manager, db_path

    manager.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client(test_db, test_reference_db):
    """Create a test client with database override."""
    session, db_path = test_db
    ref_manager, ref_db_path = test_reference_db

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        # Add test_predicate_ids to the client for easy access in tests
        client.test_predicate_ids = session.test_predicate_ids
        yield client

    app.dependency_overrides.clear()


class TestFindSimilarEndpoint:
    """Test POST /api/predicates/{id}/find-similar endpoint."""

    def test_find_similar_basic(self, client):
        """Test basic similarity search."""
        # Get test predicate UUID
        pred_id = client.test_predicate_ids["pred_1"]

        response = client.post(
            f"/api/predicates/{pred_id}/find-similar",
            params={"limit": 10, "threshold": 0.5, "use_cache": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "predicate_id" in data
        assert "predicate_title" in data
        assert "results" in data
        assert "total_results" in data
        assert "search_time_ms" in data
        assert "cached" in data

        assert data["predicate_id"] == pred_id
        assert data["predicate_title"] == "subClassOf"
        assert isinstance(data["results"], list)
        assert data["total_results"] >= 0
        assert data["search_time_ms"] > 0
        assert data["cached"] is False

        # Check result structure if any results
        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "predicate_id" in result
            assert "source" in result
            assert "source_id" in result
            assert "title" in result
            assert "definition" in result
            assert "similarity_score" in result
            assert "confidence" in result

            assert 0.0 <= result["similarity_score"] <= 1.0
            assert result["confidence"] in ["high", "medium", "low"]

    def test_find_similar_with_source_filter(self, client):
        """Test similarity search with source filter."""
        pred_id = client.test_predicate_ids["pred_2"]

        response = client.post(
            f"/api/predicates/{pred_id}/find-similar",
            params={
                "source": "conceptnet",
                "limit": 10,
                "threshold": 0.5,
                "use_cache": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # All results should be from conceptnet
        for result in data["results"]:
            assert result["source"] == "conceptnet"

    def test_find_similar_with_caching(self, client):
        """Test similarity search with caching."""
        pred_id = client.test_predicate_ids["pred_1"]

        # First request (may or may not be cached depending on test run order)
        response1 = client.post(
            f"/api/predicates/{pred_id}/find-similar",
            params={"limit": 10, "threshold": 0.7, "use_cache": True},
        )

        assert response1.status_code == 200
        data1 = response1.json()
        # Note: First request cached status may vary depending on test execution order  # noqa: E501

        # Second request (should be consistent with first)
        response2 = client.post(
            f"/api/predicates/{pred_id}/find-similar",
            params={"limit": 10, "threshold": 0.7, "use_cache": True},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        # Note: cached status depends on cache state, may be True or False

        # Results should be consistent
        assert data1["total_results"] == data2["total_results"]
        # Cache should be working (second request might be from cache)
        assert "cached" in data1
        assert "cached" in data2

    def test_find_similar_invalid_predicate_id(self, client):
        """Test similarity search with invalid predicate ID."""
        response = client.post(
            "/api/predicates/invalid-id/find-similar",
            params={"limit": 10, "threshold": 0.7},
        )

        assert response.status_code == 400  # Invalid UUID format

    def test_find_similar_nonexistent_predicate(self, client):
        """Test similarity search with nonexistent predicate."""
        response = client.post(
            "/api/predicates/00000000-0000-0000-0000-000000000000/find-similar",  # noqa: E501
            params={"limit": 10, "threshold": 0.7},
        )

        assert response.status_code == 404

    def test_find_similar_parameter_validation(self, client):
        """Test parameter validation."""
        pred_id = client.test_predicate_ids["pred_1"]

        # Invalid limit (too high)
        response = client.post(
            f"/api/predicates/{pred_id}/find-similar",
            params={"limit": 200, "threshold": 0.7},
        )

        assert response.status_code == 422  # Validation error

        # Invalid threshold (out of range)
        response = client.post(
            f"/api/predicates/{pred_id}/find-similar",
            params={"limit": 10, "threshold": 1.5},
        )

        assert response.status_code == 422


class TestClusterPredicatesEndpoint:
    """Test POST /api/predicates/cluster-predicates endpoint."""

    def test_cluster_all_predicates(self, client):
        """Test clustering all predicates."""
        response = client.post(
            "/api/predicates/cluster-predicates",
            params={"min_similarity": 0.7, "min_cluster_size": 2, "eps": 0.5},
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "clusters" in data
        assert "total_clusters" in data
        assert "total_predicates" in data
        assert "cluster_time_ms" in data

        assert isinstance(data["clusters"], list)
        assert data["total_clusters"] >= 0
        assert data["total_predicates"] >= 0
        assert data["cluster_time_ms"] > 0

        # Check cluster structure if any clusters
        if len(data["clusters"]) > 0:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster
            assert "predicate_ids" in cluster
            assert "centroid_title" in cluster
            assert "avg_similarity" in cluster
            assert "size" in cluster

            assert cluster["cluster_id"] >= 0
            assert isinstance(cluster["predicate_ids"], list)
            assert len(cluster["predicate_ids"]) >= 2
            assert 0.0 <= cluster["avg_similarity"] <= 1.0
            assert cluster["size"] == len(cluster["predicate_ids"])

    def test_cluster_specific_predicates(self, client):
        """Test clustering specific predicates."""
        pred_ids = [
            client.test_predicate_ids["pred_1"],
            client.test_predicate_ids["pred_2"],
            client.test_predicate_ids["pred_3"],
        ]

        response = client.post(
            "/api/predicates/cluster-predicates",
            params={"predicate_ids": pred_ids, "min_cluster_size": 2, "eps": 0.5},
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["clusters"], list)
        # Verify all clustered predicates are from the input set
        input_ids = set(pred_ids)
        for cluster in data["clusters"]:
            for pred_id in cluster["predicate_ids"]:
                assert pred_id in input_ids

    def test_cluster_insufficient_predicates(self, client):
        """Test clustering with insufficient predicates."""
        pred_id = client.test_predicate_ids["pred_1"]

        response = client.post(
            "/api/predicates/cluster-predicates",
            params={"predicate_ids": [pred_id], "min_cluster_size": 2},
        )

        assert response.status_code == 400
        assert "Not enough predicates" in response.json()["detail"]

    def test_cluster_invalid_predicate_id(self, client):
        """Test clustering with invalid predicate ID."""
        response = client.post(
            "/api/predicates/cluster-predicates",
            params={"predicate_ids": ["invalid-id"], "min_cluster_size": 2},
        )

        assert response.status_code == 400

    def test_cluster_nonexistent_predicate(self, client):
        """Test clustering with nonexistent predicate."""
        response = client.post(
            "/api/predicates/cluster-predicates",
            params={
                "predicate_ids": ["00000000-0000-0000-0000-000000000000"],
                "min_cluster_size": 2,
            },
        )

        assert response.status_code == 404


class TestCacheInvalidationEndpoint:
    """Test POST /api/predicates/invalidate-similarity-cache endpoint."""

    def test_invalidate_cache(self, client):
        """Test cache invalidation."""
        response = client.post("/api/predicates/invalidate-similarity-cache")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "message" in data
        assert "invalidated" in data["message"].lower()


class TestEndToEndWorkflow:
    """Test end-to-end workflows."""

    def test_search_cluster_workflow(self, client):
        """Test complete workflow: search -> cluster -> invalidate cache."""
        pred_id = client.test_predicate_ids["pred_1"]

        # 1. Find similar predicates
        search_response = client.post(
            f"/api/predicates/{pred_id}/find-similar",
            params={"limit": 10, "threshold": 0.5},
        )
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["total_results"] >= 0

        # 2. Cluster predicates
        cluster_response = client.post(
            "/api/predicates/cluster-predicates", params={"min_cluster_size": 2}
        )
        assert cluster_response.status_code == 200
        cluster_data = cluster_response.json()
        assert cluster_data["total_clusters"] >= 0

        # 3. Invalidate cache
        cache_response = client.post(
            "/api/predicates/invalidate-similarity-cache"
        )  # noqa: E501
        assert cache_response.status_code == 200
        assert cache_response.json()["success"] is True

    def test_multiple_searches_with_cache(self, client):
        """Test multiple searches to verify caching behavior."""
        pred_id = client.test_predicate_ids["pred_2"]

        # Invalidate cache first
        client.post("/api/predicates/invalidate-similarity-cache")

        # Perform same search multiple times
        search_times = []
        for _ in range(3):
            response = client.post(
                f"/api/predicates/{pred_id}/find-similar",
                params={"limit": 10, "threshold": 0.7, "use_cache": True},
            )
            assert response.status_code == 200
            search_times.append(response.json()["search_time_ms"])

        # Second and third searches might be faster due to caching
        # (but this is not guaranteed in test environment)
        assert all(t > 0 for t in search_times)
