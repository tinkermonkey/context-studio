"""
Unit tests for RAG Observability Store.

Tests persistence, retrieval, and cleanup of RAG observability data.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json

from rag.observability_store import RAGObservabilityStore


@pytest.fixture
def test_db():
    """Create a temporary test database with observability tables."""
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


class TestRAGObservabilityStore:
    """Test suite for RAG Observability Store."""

    def test_initialization(self, test_db):
        """Test observability store initializes correctly."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)
            assert store.db_session == session
            assert store.METRICS_RETENTION_DAYS == 30
            assert store.TRACES_RETENTION_DAYS == 7
        finally:
            session.close()

    def test_save_metrics(self, test_db):
        """Test saving processing metrics."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            request_id = "test-request-123"
            metrics_id = store.save_metrics(
                request_id=request_id,
                total_time_ms=1000.5,
                layer_0_time_ms=100.2,
                layer_0_count=5,
                layer_1_time_ms=300.7,
                layer_1_count=3,
                layer_2_time_ms=200.1,
                layer_2_count=2,
                layer_3_time_ms=400.5,
                layer_3_count=4,
                input_text="Test input paragraph"
            )

            # Verify metrics were saved
            assert metrics_id is not None

            # Query database directly to verify
            result = session.execute(text("""
                SELECT request_id, total_time_ms, layer_0_count, layer_1_count,
                       layer_2_count, layer_3_count, sentence_text
                FROM rag_processing_metrics
                WHERE id = :id
            """), {"id": metrics_id}).fetchone()

            assert result is not None
            assert result[0] == request_id
            assert result[1] == 1000  # Should be rounded to int
            assert result[2] == 5
            assert result[3] == 3
            assert result[4] == 2
            assert result[5] == 4
            assert result[6] == "Test input paragraph"

        finally:
            session.close()

    def test_save_metrics_truncates_long_text(self, test_db):
        """Test that long input text is truncated to 500 chars."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            # Create a very long input text (> 500 chars)
            long_text = "A" * 1000

            metrics_id = store.save_metrics(
                request_id="test-request",
                total_time_ms=100.0,
                layer_0_time_ms=10.0,
                layer_0_count=0,
                layer_1_time_ms=20.0,
                layer_1_count=0,
                layer_2_time_ms=30.0,
                layer_2_count=0,
                layer_3_time_ms=40.0,
                layer_3_count=0,
                input_text=long_text
            )

            # Query database to verify truncation
            result = session.execute(text("""
                SELECT sentence_text
                FROM rag_processing_metrics
                WHERE id = :id
            """), {"id": metrics_id}).fetchone()

            saved_text = result[0]
            assert len(saved_text) == 500
            assert saved_text == "A" * 500

        finally:
            session.close()

    def test_save_trace(self, test_db):
        """Test saving trace data."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            request_id = "test-request-456"
            trace_data = {
                "input_phrases": ["machine learning", "neural networks"],
                "kg_nodes_found": 3,
                "similarity_scores": [0.95, 0.88, 0.82]
            }

            trace_id = store.save_trace(
                request_id=request_id,
                sentence_index=0,
                layer_name="kg_context",
                operation_type="output",
                trace_data=trace_data
            )

            # Verify trace was saved
            assert trace_id is not None

            # Query database directly to verify
            result = session.execute(text("""
                SELECT request_id, sentence_index, layer_name, operation_type, trace_data
                FROM rag_observability_trace
                WHERE id = :id
            """), {"id": trace_id}).fetchone()

            assert result is not None
            assert result[0] == request_id
            assert result[1] == 0
            assert result[2] == "kg_context"
            assert result[3] == "output"

            # Verify trace data JSON
            saved_data = json.loads(result[4])
            assert saved_data == trace_data

        finally:
            session.close()

    def test_save_multiple_traces(self, test_db):
        """Test saving multiple trace records for different layers."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            request_id = "test-request-multi"

            # Save traces for all 4 layers
            layers = [
                ("kg_context", "output", {"kg_nodes": 5}),
                ("llm_extraction", "output", {"entities": 3}),
                ("spacy_gap", "output", {"gaps": 2}),
                ("concept_resolution", "output", {"resolved": 2})
            ]

            trace_ids = []
            for layer_name, op_type, data in layers:
                trace_id = store.save_trace(
                    request_id=request_id,
                    sentence_index=0,
                    layer_name=layer_name,
                    operation_type=op_type,
                    trace_data=data
                )
                trace_ids.append(trace_id)

            # Verify all 4 traces were saved
            assert len(trace_ids) == 4
            assert len(set(trace_ids)) == 4  # All unique

            # Query database to verify all traces
            result = session.execute(text("""
                SELECT COUNT(*)
                FROM rag_observability_trace
                WHERE request_id = :request_id
            """), {"request_id": request_id}).scalar()

            assert result == 4

        finally:
            session.close()

    def test_get_metrics(self, test_db):
        """Test retrieving metrics by request ID."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            request_id = "test-request-get"
            store.save_metrics(
                request_id=request_id,
                total_time_ms=500.0,
                layer_0_time_ms=100.0,
                layer_0_count=5,
                layer_1_time_ms=150.0,
                layer_1_count=3,
                layer_2_time_ms=100.0,
                layer_2_count=2,
                layer_3_time_ms=150.0,
                layer_3_count=4,
                input_text="Test input"
            )

            # Retrieve metrics
            metrics = store.get_metrics(request_id)

            assert metrics is not None
            assert metrics["request_id"] == request_id
            assert metrics["total_time_ms"] == 500
            assert metrics["layer_0"]["time_ms"] == 100
            assert metrics["layer_0"]["count"] == 5
            assert metrics["layer_1"]["time_ms"] == 150
            assert metrics["layer_1"]["count"] == 3
            assert metrics["layer_2"]["time_ms"] == 100
            assert metrics["layer_2"]["count"] == 2
            assert metrics["layer_3"]["time_ms"] == 150
            assert metrics["layer_3"]["count"] == 4
            assert metrics["input_text"] == "Test input"

        finally:
            session.close()

    def test_get_metrics_not_found(self, test_db):
        """Test retrieving metrics for non-existent request returns None."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            metrics = store.get_metrics("non-existent-request")
            assert metrics is None

        finally:
            session.close()

    def test_get_traces(self, test_db):
        """Test retrieving all traces for a request."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            request_id = "test-request-traces"

            # Save multiple traces
            trace_data_1 = {"data": "layer 0"}
            trace_data_2 = {"data": "layer 1"}

            store.save_trace(
                request_id=request_id,
                sentence_index=0,
                layer_name="kg_context",
                operation_type="output",
                trace_data=trace_data_1
            )

            store.save_trace(
                request_id=request_id,
                sentence_index=0,
                layer_name="llm_extraction",
                operation_type="output",
                trace_data=trace_data_2
            )

            # Retrieve traces
            traces = store.get_traces(request_id)

            assert len(traces) == 2
            assert traces[0]["layer_name"] == "kg_context"
            assert traces[0]["trace_data"] == trace_data_1
            assert traces[1]["layer_name"] == "llm_extraction"
            assert traces[1]["trace_data"] == trace_data_2

        finally:
            session.close()

    def test_get_traces_empty(self, test_db):
        """Test retrieving traces for non-existent request returns empty list."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            traces = store.get_traces("non-existent-request")
            assert traces == []

        finally:
            session.close()

    def test_get_traces_ordered(self, test_db):
        """Test that traces are returned ordered by sentence index and timestamp."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            request_id = "test-request-order"

            # Save traces out of order
            store.save_trace(
                request_id=request_id,
                sentence_index=1,
                layer_name="kg_context",
                operation_type="output",
                trace_data={"sentence": 1}
            )

            store.save_trace(
                request_id=request_id,
                sentence_index=0,
                layer_name="kg_context",
                operation_type="output",
                trace_data={"sentence": 0}
            )

            # Retrieve traces
            traces = store.get_traces(request_id)

            # Should be ordered by sentence_index
            assert len(traces) == 2
            assert traces[0]["sentence_index"] == 0
            assert traces[1]["sentence_index"] == 1

        finally:
            session.close()

    def test_cleanup_old_data(self, test_db):
        """Test cleanup of old metrics and traces."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            # Insert old metrics (40 days old)
            old_timestamp = datetime.now(timezone.utc) - timedelta(days=40)
            session.execute(text("""
                INSERT INTO rag_processing_metrics (
                    id, request_id, sentence_text, layer_0_time_ms, layer_0_count,
                    layer_1_time_ms, layer_1_count, layer_2_time_ms, layer_2_count,
                    layer_3_time_ms, layer_3_count, total_time_ms, timestamp, retention_days
                ) VALUES (
                    'old-metric-1', 'old-request', 'old text', 10, 0, 20, 0, 30, 0, 40, 0, 100, :timestamp, 30
                )
            """), {"timestamp": old_timestamp})

            # Insert recent metrics (10 days old)
            recent_timestamp = datetime.now(timezone.utc) - timedelta(days=10)
            session.execute(text("""
                INSERT INTO rag_processing_metrics (
                    id, request_id, sentence_text, layer_0_time_ms, layer_0_count,
                    layer_1_time_ms, layer_1_count, layer_2_time_ms, layer_2_count,
                    layer_3_time_ms, layer_3_count, total_time_ms, timestamp, retention_days
                ) VALUES (
                    'recent-metric-1', 'recent-request', 'recent text', 10, 0, 20, 0, 30, 0, 40, 0, 100, :timestamp, 30
                )
            """), {"timestamp": recent_timestamp})

            # Insert old traces (10 days old, should be deleted with 7-day retention)
            old_trace_timestamp = datetime.now(timezone.utc) - timedelta(days=10)
            session.execute(text("""
                INSERT INTO rag_observability_trace (
                    id, request_id, sentence_index, layer_name, operation_type,
                    trace_data, timestamp, retention_days
                ) VALUES (
                    'old-trace-1', 'old-request', 0, 'kg_context', 'output',
                    '{}', :timestamp, 7
                )
            """), {"timestamp": old_trace_timestamp})

            # Insert recent traces (2 days old)
            recent_trace_timestamp = datetime.now(timezone.utc) - timedelta(days=2)
            session.execute(text("""
                INSERT INTO rag_observability_trace (
                    id, request_id, sentence_index, layer_name, operation_type,
                    trace_data, timestamp, retention_days
                ) VALUES (
                    'recent-trace-1', 'recent-request', 0, 'kg_context', 'output',
                    '{}', :timestamp, 7
                )
            """), {"timestamp": recent_trace_timestamp})

            session.commit()

            # Perform cleanup
            result = store.cleanup_old_data()

            # Verify cleanup results
            assert result["metrics_deleted"] == 1  # Old metric deleted
            assert result["traces_deleted"] == 1  # Old trace deleted

            # Verify recent data still exists
            metrics_count = session.execute(text("""
                SELECT COUNT(*) FROM rag_processing_metrics
            """)).scalar()
            assert metrics_count == 1  # Only recent metric remains

            traces_count = session.execute(text("""
                SELECT COUNT(*) FROM rag_observability_trace
            """)).scalar()
            assert traces_count == 1  # Only recent trace remains

        finally:
            session.close()

    def test_cleanup_with_no_old_data(self, test_db):
        """Test cleanup when there's no old data to remove."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            # Perform cleanup on empty database
            result = store.cleanup_old_data()

            assert result["metrics_deleted"] == 0
            assert result["traces_deleted"] == 0

        finally:
            session.close()

    def test_save_metrics_rollback_on_error(self, test_db):
        """Test that save_metrics rolls back on error."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            # Drop the table to cause an error
            session.execute(text("DROP TABLE rag_processing_metrics"))
            session.commit()

            # Attempt to save metrics should raise exception
            with pytest.raises(Exception):
                store.save_metrics(
                    request_id="test",
                    total_time_ms=100.0,
                    layer_0_time_ms=10.0,
                    layer_0_count=0,
                    layer_1_time_ms=20.0,
                    layer_1_count=0,
                    layer_2_time_ms=30.0,
                    layer_2_count=0,
                    layer_3_time_ms=40.0,
                    layer_3_count=0,
                    input_text="test"
                )

        finally:
            session.close()

    def test_save_trace_rollback_on_error(self, test_db):
        """Test that save_trace rolls back on error."""
        engine, SessionLocal = test_db
        session = SessionLocal()

        try:
            store = RAGObservabilityStore(session)

            # Drop the table to cause an error
            session.execute(text("DROP TABLE rag_observability_trace"))
            session.commit()

            # Attempt to save trace should raise exception
            with pytest.raises(Exception):
                store.save_trace(
                    request_id="test",
                    sentence_index=0,
                    layer_name="kg_context",
                    operation_type="output",
                    trace_data={}
                )

        finally:
            session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
