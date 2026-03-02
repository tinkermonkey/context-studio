"""
RAG Observability Store

This module provides persistence for RAG pipeline observability data,
including metrics and detailed trace information.
"""
from typing import Dict, Any, Optional, List, Sequence
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text, CursorResult
import json
import uuid

from utils.logger import get_logger

logger = get_logger(__name__)


class RAGObservabilityStore:
    """
    Handles persistence of RAG pipeline observability data.

    Stores two types of data:
    - Metrics: Performance timing and entity counts per layer (30-day retention)
    - Traces: Detailed input/output data for debugging (7-day retention)
    """

    # Retention periods
    METRICS_RETENTION_DAYS = 30
    TRACES_RETENTION_DAYS = 7

    def __init__(self, db_session: Session):
        """
        Initialize RAG Observability Store.

        Args:
            db_session: Database session (should be for operations.db)
        """
        self.db_session = db_session
        logger.info("RAGObservabilityStore initialized")

    def save_metrics(
        self,
        request_id: str,
        total_time_ms: float,
        layer_0_time_ms: float,
        layer_0_count: int,
        layer_1_time_ms: float,
        layer_1_count: int,
        layer_2_time_ms: float,
        layer_2_count: int,
        layer_3_time_ms: float,
        layer_3_count: int,
        input_text: str
    ) -> str:
        """
        Save RAG processing metrics to database.

        Args:
            request_id: Unique identifier for the RAG extraction request
            total_time_ms: Total pipeline execution time in milliseconds
            layer_0_time_ms: Layer 0 (KG context) execution time in milliseconds
            layer_0_count: Number of entities/concepts found in Layer 0
            layer_1_time_ms: Layer 1 (LLM extraction) execution time in milliseconds
            layer_1_count: Number of entities found in Layer 1
            layer_2_time_ms: Layer 2 (spaCy gap detection) execution time in milliseconds
            layer_2_count: Number of gaps found in Layer 2
            layer_3_time_ms: Layer 3 (concept resolution) execution time in milliseconds
            layer_3_count: Number of concepts resolved in Layer 3
            input_text: Input paragraph text that was processed

        Returns:
            Metrics record ID
        """
        metrics_id = str(uuid.uuid4())

        try:
            # Store input text in sentence_text column for reference
            self.db_session.execute(text("""
                INSERT INTO rag_processing_metrics (
                    id, request_id, sentence_text,
                    layer_0_time_ms, layer_0_count,
                    layer_1_time_ms, layer_1_count,
                    layer_2_time_ms, layer_2_count,
                    layer_3_time_ms, layer_3_count,
                    total_time_ms, timestamp, retention_days
                ) VALUES (
                    :id, :request_id, :input_text,
                    :layer_0_time_ms, :layer_0_count,
                    :layer_1_time_ms, :layer_1_count,
                    :layer_2_time_ms, :layer_2_count,
                    :layer_3_time_ms, :layer_3_count,
                    :total_time_ms, :timestamp, :retention_days
                )
            """), {
                "id": metrics_id,
                "request_id": request_id,
                "input_text": input_text[:500],  # Truncate to first 500 chars for storage efficiency
                "layer_0_time_ms": int(layer_0_time_ms),
                "layer_0_count": layer_0_count,
                "layer_1_time_ms": int(layer_1_time_ms),
                "layer_1_count": layer_1_count,
                "layer_2_time_ms": int(layer_2_time_ms),
                "layer_2_count": layer_2_count,
                "layer_3_time_ms": int(layer_3_time_ms),
                "layer_3_count": layer_3_count,
                "total_time_ms": int(total_time_ms),
                "timestamp": datetime.now(timezone.utc),
                "retention_days": self.METRICS_RETENTION_DAYS
            })

            self.db_session.commit()
            logger.debug(f"Saved metrics for request {request_id}: {metrics_id}")
            return metrics_id

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to save metrics for request {request_id}: {e}", exc_info=True)
            raise

    def save_trace(
        self,
        request_id: str,
        sentence_index: int,
        layer_name: str,
        operation_type: str,
        trace_data: Dict[str, Any]
    ) -> str:
        """
        Save detailed trace data for a specific layer operation.

        Args:
            request_id: RAG extraction request ID
            sentence_index: Index of sentence being processed (or -1 for paragraph-level)
            layer_name: Name of layer (e.g., "kg_context", "llm_extraction", "spacy_gap", "concept_resolution")
            operation_type: Type of operation (e.g., "input", "output", "error")
            trace_data: Dictionary containing trace details

        Returns:
            Trace record ID
        """
        trace_id = str(uuid.uuid4())

        try:
            self.db_session.execute(text("""
                INSERT INTO rag_observability_trace (
                    id, request_id, sentence_index, layer_name, operation_type,
                    trace_data, timestamp, retention_days
                ) VALUES (
                    :id, :request_id, :sentence_index, :layer_name, :operation_type,
                    :trace_data, :timestamp, :retention_days
                )
            """), {
                "id": trace_id,
                "request_id": request_id,
                "sentence_index": sentence_index,
                "layer_name": layer_name,
                "operation_type": operation_type,
                "trace_data": json.dumps(trace_data),
                "timestamp": datetime.now(timezone.utc),
                "retention_days": self.TRACES_RETENTION_DAYS
            })

            self.db_session.commit()
            logger.debug(f"Saved trace for request {request_id}, layer {layer_name}: {trace_id}")
            return trace_id

        except Exception as e:
            self.db_session.rollback()
            logger.error(
                f"Failed to save trace for request {request_id}, layer {layer_name}: {e}",
                exc_info=True
            )
            raise

    def get_metrics(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metrics for a specific request.

        Args:
            request_id: RAG extraction request ID

        Returns:
            Dictionary containing metrics, or None if not found
        """
        try:
            result: Optional[Any] = self.db_session.execute(text("""
                SELECT
                    id, request_id, sentence_text,
                    layer_0_time_ms, layer_0_count,
                    layer_1_time_ms, layer_1_count,
                    layer_2_time_ms, layer_2_count,
                    layer_3_time_ms, layer_3_count,
                    total_time_ms, timestamp
                FROM rag_processing_metrics
                WHERE request_id = :request_id
            """), {"request_id": request_id}).fetchone()

            if not result:
                return None

            return {
                "id": result[0],
                "request_id": result[1],
                "input_text": result[2],
                "layer_0": {
                    "time_ms": result[3],
                    "count": result[4]
                },
                "layer_1": {
                    "time_ms": result[5],
                    "count": result[6]
                },
                "layer_2": {
                    "time_ms": result[7],
                    "count": result[8]
                },
                "layer_3": {
                    "time_ms": result[9],
                    "count": result[10]
                },
                "total_time_ms": result[11],
                "timestamp": result[12]
            }

        except Exception as e:
            logger.error(f"Failed to retrieve metrics for request {request_id}: {e}", exc_info=True)
            return None

    def get_traces(self, request_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all trace records for a specific request.

        Args:
            request_id: RAG extraction request ID

        Returns:
            List of trace dictionaries
        """
        try:
            results: Sequence[Any] = self.db_session.execute(text("""
                SELECT
                    id, request_id, sentence_index, layer_name, operation_type,
                    trace_data, timestamp
                FROM rag_observability_trace
                WHERE request_id = :request_id
                ORDER BY sentence_index, timestamp
            """), {"request_id": request_id}).fetchall()

            traces: List[Dict[str, Any]] = []
            for row in results:
                traces.append({
                    "id": row[0],
                    "request_id": row[1],
                    "sentence_index": row[2],
                    "layer_name": row[3],
                    "operation_type": row[4],
                    "trace_data": json.loads(row[5]),
                    "timestamp": row[6]
                })

            return traces

        except Exception as e:
            logger.error(f"Failed to retrieve traces for request {request_id}: {e}", exc_info=True)
            return []

    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Remove observability data that exceeds retention periods.

        Returns:
            Dictionary with counts of deleted metrics and traces
        """
        try:
            # Calculate cutoff timestamps
            metrics_cutoff: datetime = datetime.now(timezone.utc) - timedelta(days=self.METRICS_RETENTION_DAYS)
            traces_cutoff: datetime = datetime.now(timezone.utc) - timedelta(days=self.TRACES_RETENTION_DAYS)

            # Delete old metrics
            metrics_result: CursorResult[Any] = self.db_session.execute(text("""
                DELETE FROM rag_processing_metrics
                WHERE timestamp < :cutoff
            """), {"cutoff": metrics_cutoff})

            metrics_deleted: int = metrics_result.rowcount

            # Delete old traces
            traces_result: CursorResult[Any] = self.db_session.execute(text("""
                DELETE FROM rag_observability_trace
                WHERE timestamp < :cutoff
            """), {"cutoff": traces_cutoff})

            traces_deleted: int = traces_result.rowcount

            self.db_session.commit()

            logger.info(
                f"Cleaned up observability data: {metrics_deleted} metrics, "
                f"{traces_deleted} traces deleted"
            )

            return {
                "metrics_deleted": metrics_deleted,
                "traces_deleted": traces_deleted
            }

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to cleanup old observability data: {e}", exc_info=True)
            return {
                "metrics_deleted": 0,
                "traces_deleted": 0
            }
