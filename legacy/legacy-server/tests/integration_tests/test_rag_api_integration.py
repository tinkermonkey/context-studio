"""
Integration tests for RAG Pipeline API endpoints.

These tests verify all RAG API endpoints with the FastAPI test client.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from uuid import uuid4

import numpy as np
import pytest
from database.custom_types import NodeType
from database.models import Base, StructureNode
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import create_app


@pytest.fixture
def test_kg_db():
    """Create a temporary test database for knowledge graph."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Add some test structure nodes with embeddings
    session = SessionLocal()
    try:
        # Create embedding model to generate test embeddings
        from embeddings.generate_embeddings import get_model

        model = get_model()

        # Add test terms with embeddings
        terms_data = [
            (
                "Machine Learning",
                "A field of artificial intelligence focused on algorithms that learn from data",
            ),
            (
                "Neural Networks",
                "Computing systems inspired by biological neural networks",
            ),
            (
                "Artificial Intelligence",
                "The simulation of human intelligence by machines",
            ),
        ]

        for title, definition in terms_data:
            # Generate embedding
            embedding = model.encode([title])[0]
            embedding_blob = np.array(embedding, dtype=np.float32).tobytes()

            node = StructureNode(
                node_type=NodeType.TERM,
                title=title,
                definition=definition,
                title_embedding=embedding_blob,
                parent_node_id=None,
            )
            session.add(node)

        session.commit()
    finally:
        session.close()

    yield engine, SessionLocal

    # Cleanup
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def test_ops_db():
    """Create a temporary test database for operations/observability."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine)

    # Create observability tables
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_processing_metrics (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_text TEXT NOT NULL,
                layer_0_time_ms INTEGER,
                layer_0_count INTEGER,
                layer_1_time_ms INTEGER,
                layer_1_count INTEGER,
                layer_2_time_ms INTEGER,
                layer_2_count INTEGER,
                layer_3_time_ms INTEGER,
                layer_3_count INTEGER,
                total_time_ms INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                retention_days INTEGER DEFAULT 30 NOT NULL
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_observability_trace (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                layer_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                trace_data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                retention_days INTEGER DEFAULT 7 NOT NULL
            )
        """))
        conn.commit()

    yield engine, SessionLocal

    # Cleanup
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def test_client(test_kg_db, test_ops_db):
    """Create test client for API integration tests."""
    _kg_engine, kg_session_maker = test_kg_db
    _ops_engine, ops_session_maker = test_ops_db

    # Create app with test database sessions
    app = create_app(session_local=kg_session_maker)

    # Override operations DB dependency
    from api.dependencies.rag_services import get_operations_db

    def override_ops_db():
        session = ops_session_maker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_operations_db] = override_ops_db

    with TestClient(app) as client:
        yield client


class TestRAGPipelineAPIEndpoints:
    """Integration tests for RAG Pipeline API endpoints."""

    def test_extract_entities_success(self, test_client):
        """Test POST /api/rag/extract with valid request."""
        response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "Machine learning and neural networks are key technologies.",
                "enable_trace": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "request_id" in data
        assert "entities" in data
        assert "metrics" in data
        assert "trace_available" in data

        # Verify metrics structure
        metrics = data["metrics"]
        assert "kg_layer" in metrics
        assert "nlp_layer" in metrics
        assert "llm_layer" in metrics
        assert "web_layer" in metrics
        assert "total_execution_time_ms" in metrics
        assert "total_entities" in metrics
        assert "total_sentences" in metrics

        # Verify entities are a list
        assert isinstance(data["entities"], list)

    def test_extract_entities_with_trace(self, test_client):
        """Test POST /api/rag/extract with trace enabled."""
        response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "Artificial intelligence is transforming technology.",
                "enable_trace": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify trace is available
        assert data["trace_available"] is True
        assert "request_id" in data

    def test_extract_entities_empty_text(self, test_client):
        """Test POST /api/rag/extract with empty text."""
        response = test_client.post(
            "/api/rag/extract", json={"text": "", "enable_trace": False}
        )

        # Should return 400 or validation error (422)
        assert response.status_code in [400, 422]

    def test_extract_entities_whitespace_only(self, test_client):
        """Test POST /api/rag/extract with whitespace-only text."""
        response = test_client.post(
            "/api/rag/extract", json={"text": "   \n\t  ", "enable_trace": False}
        )

        # Should return validation error
        assert response.status_code == 422

    def test_extract_entities_missing_text(self, test_client):
        """Test POST /api/rag/extract without text field."""
        response = test_client.post("/api/rag/extract", json={"enable_trace": False})

        # Should return validation error
        assert response.status_code == 422

    def test_get_metrics_success(self, test_client):
        """Test GET /api/rag/metrics/{request_id} with valid request_id."""
        # First, create an extraction request
        extract_response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "Neural networks enable deep learning.",
                "enable_trace": False,
            },
        )
        assert extract_response.status_code == 200
        request_id = extract_response.json()["request_id"]

        # Now get metrics for that request
        metrics_response = test_client.get(f"/api/rag/metrics/{request_id}")

        assert metrics_response.status_code == 200
        metrics_data = metrics_response.json()

        # Verify metrics structure
        assert "request_id" in metrics_data
        assert metrics_data["request_id"] == request_id
        assert "layer_0" in metrics_data
        assert "layer_1" in metrics_data
        assert "layer_2" in metrics_data
        assert "layer_3" in metrics_data
        assert "total_time_ms" in metrics_data

    def test_get_metrics_not_found(self, test_client):
        """Test GET /api/rag/metrics/{request_id} with non-existent request_id."""
        fake_request_id = str(uuid4())
        response = test_client.get(f"/api/rag/metrics/{fake_request_id}")

        assert response.status_code == 404
        detail = response.json()["detail"].lower()
        assert "not found" in detail or "no metrics" in detail

    def test_get_trace_success(self, test_client):
        """Test GET /api/rag/trace/{request_id} with trace enabled."""
        # Create extraction with trace enabled
        extract_response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "Machine learning algorithms process data efficiently.",
                "enable_trace": True,
            },
        )
        assert extract_response.status_code == 200
        request_id = extract_response.json()["request_id"]

        # Get trace data
        trace_response = test_client.get(f"/api/rag/trace/{request_id}")

        assert trace_response.status_code == 200
        trace_data = trace_response.json()

        assert "request_id" in trace_data
        assert "traces" in trace_data
        assert isinstance(trace_data["traces"], list)
        assert len(trace_data["traces"]) > 0

    def test_get_trace_not_enabled(self, test_client):
        """Test GET /api/rag/trace/{request_id} when trace was not enabled."""
        # Create extraction WITHOUT trace
        extract_response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "Artificial intelligence transforms industries.",
                "enable_trace": False,
            },
        )
        assert extract_response.status_code == 200
        request_id = extract_response.json()["request_id"]

        # Try to get trace data
        trace_response = test_client.get(f"/api/rag/trace/{request_id}")

        # Should return 404 because no trace data exists
        assert trace_response.status_code == 404

    def test_get_trace_by_layer_success(self, test_client):
        """Test GET /api/rag/trace/{request_id}/layer/{layer_name} with valid layer."""
        # Create extraction with trace enabled
        extract_response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "Deep learning uses neural network architectures.",
                "enable_trace": True,
            },
        )
        assert extract_response.status_code == 200
        request_id = extract_response.json()["request_id"]

        # Get trace for specific layer - using concept_resolution which reliably completes
        # (kg_context may timeout in test environment due to embedding model loading)
        layer_name = "concept_resolution"
        trace_response = test_client.get(
            f"/api/rag/trace/{request_id}/layer/{layer_name}"
        )

        assert trace_response.status_code == 200
        trace_data = trace_response.json()

        assert "request_id" in trace_data
        assert "layer_name" in trace_data
        assert trace_data["layer_name"] == layer_name
        assert "traces" in trace_data

    def test_get_trace_by_layer_invalid_layer(self, test_client):
        """Test GET /api/rag/trace/{request_id}/layer/{layer_name} with invalid layer."""
        # Create extraction with trace enabled
        extract_response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "AI systems use machine learning techniques.",
                "enable_trace": True,
            },
        )
        assert extract_response.status_code == 200
        request_id = extract_response.json()["request_id"]

        # Try to get trace for invalid layer
        invalid_layer = "invalid_layer_name"
        trace_response = test_client.get(
            f"/api/rag/trace/{request_id}/layer/{invalid_layer}"
        )

        assert trace_response.status_code == 400
        assert "invalid layer name" in trace_response.json()["detail"].lower()

    def test_delete_trace_success(self, test_client):
        """Test DELETE /api/rag/trace/{request_id} to remove trace data."""
        # Create extraction with trace enabled
        extract_response = test_client.post(
            "/api/rag/extract",
            json={
                "text": "Machine learning enables predictive analytics.",
                "enable_trace": True,
            },
        )
        assert extract_response.status_code == 200
        request_id = extract_response.json()["request_id"]

        # Verify trace exists
        trace_response = test_client.get(f"/api/rag/trace/{request_id}")
        assert trace_response.status_code == 200

        # Delete trace
        delete_response = test_client.delete(f"/api/rag/trace/{request_id}")

        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert "message" in delete_data
        assert "traces_deleted" in delete_data
        assert delete_data["traces_deleted"] > 0

        # Verify trace no longer exists
        trace_response_after = test_client.get(f"/api/rag/trace/{request_id}")
        assert trace_response_after.status_code == 404

    def test_delete_trace_not_found(self, test_client):
        """Test DELETE /api/rag/trace/{request_id} with non-existent request_id."""
        fake_request_id = str(uuid4())
        response = test_client.delete(f"/api/rag/trace/{fake_request_id}")

        assert response.status_code == 404
        detail = response.json()["detail"].lower()
        assert "not found" in detail or "no trace" in detail

    def test_update_config_timeout_settings(self, test_client):
        """Test POST /api/rag/config/update to modify timeout settings."""
        response = test_client.post(
            "/api/rag/config/update",
            json={
                "timeout_layer_0": 1.0,
                "timeout_layer_1": 40.0,
                "timeout_layer_2": 1.5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "updated_config" in data
        assert "current_config" in data

        # Verify updated values
        current_config = data["current_config"]
        assert current_config["timeout_layer_0"] == 1.0
        assert current_config["timeout_layer_1"] == 40.0
        assert current_config["timeout_layer_2"] == 1.5

    def test_update_config_dedup_threshold(self, test_client):
        """Test POST /api/rag/config/update to modify deduplication threshold."""
        response = test_client.post(
            "/api/rag/config/update", json={"dedup_similarity_threshold": 0.85}
        )

        assert response.status_code == 200
        data = response.json()

        current_config = data["current_config"]
        assert current_config["dedup_similarity_threshold"] == 0.85

    def test_update_config_kg_top_k(self, test_client):
        """Test POST /api/rag/config/update to modify KG top-k parameter."""
        response = test_client.post("/api/rag/config/update", json={"kg_top_k": 100})

        assert response.status_code == 200
        data = response.json()

        current_config = data["current_config"]
        assert current_config["kg_top_k"] == 100

    def test_update_config_invalid_timeout(self, test_client):
        """Test POST /api/rag/config/update with invalid timeout value."""
        response = test_client.post(
            "/api/rag/config/update",
            json={"timeout_layer_0": -1.0},  # Invalid: negative timeout
        )

        assert response.status_code == 400
        assert "positive number" in response.json()["detail"].lower()

    def test_update_config_invalid_dedup_threshold(self, test_client):
        """Test POST /api/rag/config/update with out-of-range dedup threshold."""
        response = test_client.post(
            "/api/rag/config/update",
            json={"dedup_similarity_threshold": 1.5},  # Invalid: > 1.0
        )

        assert response.status_code == 400
        assert "between 0.0 and 1.0" in response.json()["detail"].lower()

    def test_update_config_invalid_key(self, test_client):
        """Test POST /api/rag/config/update with invalid configuration key."""
        response = test_client.post(
            "/api/rag/config/update", json={"invalid_config_key": 123}
        )

        assert response.status_code == 400
        assert (
            "invalid configuration keys" in response.json()["detail"].lower()
        )

    def test_update_config_multiple_settings(self, test_client):
        """Test POST /api/rag/config/update with multiple settings at once."""
        response = test_client.post(
            "/api/rag/config/update",
            json={
                "timeout_layer_1": 50.0,
                "dedup_similarity_threshold": 0.95,
                "kg_top_k": 75,
            },
        )

        assert response.status_code == 200
        data = response.json()

        current_config = data["current_config"]
        assert current_config["timeout_layer_1"] == 50.0
        assert current_config["dedup_similarity_threshold"] == 0.95
        assert current_config["kg_top_k"] == 75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
