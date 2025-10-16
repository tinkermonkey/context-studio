"""Migration 016: Add RAG observability tables for metrics and trace capture"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration016(Migration):
    """Add RAG processing metrics and observability trace tables."""

    version = 16
    description = "Add RAG observability tables"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Creating RAG observability tables...")

        # Create rag_processing_metrics table
        # This table stores metrics for each RAG request with layer-by-layer timing and counts
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_processing_metrics (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_text TEXT NOT NULL,

                -- Layer 0: Knowledge Graph Context Preparation (vector search for relevant KG concepts)
                layer_0_time_ms INTEGER,
                layer_0_count INTEGER,

                -- Layer 1: LLM-based Entity Extraction (primary concept extraction using LLM)
                layer_1_time_ms INTEGER,
                layer_1_count INTEGER,

                -- Layer 2: spaCy Syntactic Gap Analysis (grammatical analysis for unrecognized spans)
                layer_2_time_ms INTEGER,
                layer_2_count INTEGER,

                -- Layer 3: Concept Resolution via KG and Web Search (resolve unrecognized concepts)
                layer_3_time_ms INTEGER,
                layer_3_count INTEGER,

                -- Total processing time
                total_time_ms INTEGER NOT NULL,

                -- Timestamp for retention management
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

                -- Retention period: 30 days for metrics
                retention_days INTEGER DEFAULT 30 NOT NULL
            )
        """))

        # Create index on request_id for efficient querying
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rag_metrics_request_id
            ON rag_processing_metrics(request_id)
        """))

        # Create index on timestamp for efficient retention cleanup
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rag_metrics_timestamp
            ON rag_processing_metrics(timestamp)
        """))

        logger.info("Created rag_processing_metrics table")

        # Create rag_observability_trace table
        # This table stores detailed layer input/output traces (optional, controlled by API parameter)
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_observability_trace (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                layer_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,

                -- JSON data containing full layer input/output
                trace_data TEXT NOT NULL,

                -- Timestamp for retention management
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

                -- Retention period: 7 days for traces (more detailed, shorter retention)
                retention_days INTEGER DEFAULT 7 NOT NULL,

                -- Note: No foreign key constraint to allow independent trace storage
            )
        """))

        # Create composite index on request_id for efficient trace queries
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rag_trace_request_id
            ON rag_observability_trace(request_id)
        """))

        # Create composite index on layer_name for layer-specific queries
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rag_trace_layer_name
            ON rag_observability_trace(layer_name)
        """))

        # Create index on timestamp for efficient retention cleanup
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rag_trace_timestamp
            ON rag_observability_trace(timestamp)
        """))

        # Create composite index for efficient filtering by request_id and sentence_index
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rag_trace_request_sentence
            ON rag_observability_trace(request_id, sentence_index)
        """))

        logger.info("Created rag_observability_trace table")
        logger.info("Successfully created RAG observability tables with indexes")

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Dropping RAG observability tables...")

        # Drop trace table first (has foreign key to metrics table)
        connection.execute(text("DROP INDEX IF EXISTS idx_rag_trace_request_sentence"))
        connection.execute(text("DROP INDEX IF EXISTS idx_rag_trace_timestamp"))
        connection.execute(text("DROP INDEX IF EXISTS idx_rag_trace_layer_name"))
        connection.execute(text("DROP INDEX IF EXISTS idx_rag_trace_request_id"))
        connection.execute(text("DROP TABLE IF EXISTS rag_observability_trace"))

        # Drop metrics table
        connection.execute(text("DROP INDEX IF EXISTS idx_rag_metrics_timestamp"))
        connection.execute(text("DROP INDEX IF EXISTS idx_rag_metrics_request_id"))
        connection.execute(text("DROP TABLE IF EXISTS rag_processing_metrics"))

        logger.info("Successfully dropped RAG observability tables and indexes")
