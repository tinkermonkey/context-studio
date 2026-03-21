"""
Operations Database Models

These models are for operational data (task management, LLM traceability, etc.)
stored in the operations.db database, separate from dataset data.

Schema is automatically managed - no manual migrations needed.
SQLAlchemy's metadata.create_all() handles schema updates automatically.

Note: For change tracking, use the ChangeEvent model in database.models instead.
"""

from typing import Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship
import datetime

# Separate base for operations database
OperationsBase: Any = declarative_base()


class PipelineFlavor(OperationsBase):
    """Pipeline flavor configuration for LLM operations."""

    __tablename__ = "pipeline_flavors"

    id = Column(String, primary_key=True)
    pipeline = Column(String, nullable=False)
    title = Column(String, nullable=False)
    llm_provider = Column(String, nullable=False)
    llm_model = Column(String, nullable=False)
    llm_config = Column(Text, nullable=False)  # JSON string
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<PipelineFlavor(pipeline='{self.pipeline}', title='{self.title}')>"


class PipelineFlavorExecution(OperationsBase):
    """Execution record for pipeline flavor runs (LLM traceability)."""

    __tablename__ = "pipeline_flavor_executions"
    __table_args__ = (
        Index("idx_executions_flavor_id", "pipeline_flavor_id"),
        Index("idx_executions_pipeline_type", "pipeline_type"),
        Index("idx_executions_status", "status"),
    )

    id = Column(String, primary_key=True)
    pipeline_flavor_id = Column(String, nullable=False)
    pipeline_type = Column(String, nullable=False)
    pipeline_flavor_version = Column(Integer, nullable=False)
    request_context = Column(Text, nullable=False)  # JSON
    user_prompt = Column(Text, nullable=False)
    response_message = Column(Text, nullable=True)
    structured_output = Column(Text, nullable=True)  # JSON structured output data
    execution_time_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    status = Column(String, nullable=False)  # pending, success, error, timeout
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<PipelineFlavorExecution(id='{self.id}', status='{self.status}')>"


class PipelineFlavorSelection(OperationsBase):
    """User selection of an LLM suggestion for traceability."""

    __tablename__ = "pipeline_flavor_selections"
    __table_args__ = (
        Index("idx_selections_execution_id", "pipeline_execution_id"),
        Index("idx_selections_record", "record_type", "record_id"),
    )

    id = Column(String, primary_key=True)
    pipeline_execution_id = Column(String, nullable=False)
    record_type = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    suggestion_field = Column(String, nullable=False)
    selected_content = Column(Text, nullable=False)
    date_created = Column(DateTime, nullable=False)

    def __repr__(self):
        return (
            f"<PipelineFlavorSelection(id='{self.id}', record_id='{self.record_id}')>"
        )


class RAGProcessingMetrics(OperationsBase):
    """Performance metrics for RAG pipeline requests."""

    __tablename__ = "rag_processing_metrics"
    __table_args__ = (
        Index("idx_rag_metrics_request_id", "request_id"),
        Index("idx_rag_metrics_timestamp", "timestamp"),
    )

    id = Column(String, primary_key=True)
    request_id = Column(String, nullable=False)
    sentence_text = Column(Text, nullable=False)

    # Layer 0: Knowledge Graph Context Preparation
    layer_0_time_ms = Column(Integer, nullable=True)
    layer_0_count = Column(Integer, nullable=True)

    # Layer 1: LLM-based Entity Extraction
    layer_1_time_ms = Column(Integer, nullable=True)
    layer_1_count = Column(Integer, nullable=True)

    # Layer 2: spaCy Syntactic Gap Analysis
    layer_2_time_ms = Column(Integer, nullable=True)
    layer_2_count = Column(Integer, nullable=True)

    # Layer 3: Concept Resolution via KG and Web Search
    layer_3_time_ms = Column(Integer, nullable=True)
    layer_3_count = Column(Integer, nullable=True)

    # Total processing time
    total_time_ms = Column(Integer, nullable=False)

    # Timestamp for retention management
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    # Retention period: 30 days for metrics
    retention_days = Column(Integer, nullable=False, default=30)

    def __repr__(self):
        return f"<RAGProcessingMetrics(request_id='{self.request_id}', total_time_ms={self.total_time_ms})>"


class RAGObservabilityTrace(OperationsBase):
    """Detailed trace data for RAG pipeline debugging."""

    __tablename__ = "rag_observability_trace"
    __table_args__ = (
        Index("idx_rag_trace_request_id", "request_id"),
        Index("idx_rag_trace_layer_name", "layer_name"),
        Index("idx_rag_trace_timestamp", "timestamp"),
        Index("idx_rag_trace_request_sentence", "request_id", "sentence_index"),
    )

    id = Column(String, primary_key=True)
    request_id = Column(String, nullable=False)
    sentence_index = Column(Integer, nullable=False)
    layer_name = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)

    # JSON data containing full layer input/output
    trace_data = Column(Text, nullable=False)

    # Timestamp for retention management
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    # Retention period: 7 days for traces (more detailed, shorter retention)
    retention_days = Column(Integer, nullable=False, default=7)

    def __repr__(self):
        return f"<RAGObservabilityTrace(request_id='{self.request_id}', layer_name='{self.layer_name}')>"


class TestParagraph(OperationsBase):
    """Test paragraph for RAG pipeline experimentation."""

    __tablename__ = "test_paragraphs"

    id = Column(String, primary_key=True)
    text = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    # Relationships with cascade delete
    annotations = relationship(
        "TestAnnotation", back_populates="paragraph", cascade="all, delete-orphan"
    )
    pipeline_runs = relationship(
        "RAGPipelineRun", back_populates="paragraph", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<TestParagraph(id='{self.id}')>"


class TestAnnotation(OperationsBase):
    """Ground truth annotation for test paragraph entities."""

    __tablename__ = "test_annotations"
    __table_args__ = (
        Index("idx_test_annotation_paragraph_id", "paragraph_id"),
        Index("idx_test_annotation_structure_node_id", "structure_node_id"),
    )

    id = Column(String, primary_key=True)
    paragraph_id = Column(String, ForeignKey("test_paragraphs.id"), nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    structure_node_id = Column(
        String, nullable=False
    )  # Soft FK to structure_nodes in local.db
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    # Relationship back to paragraph
    paragraph = relationship("TestParagraph", back_populates="annotations")

    def __repr__(self):
        return f"<TestAnnotation(id='{self.id}', paragraph_id='{self.paragraph_id}')>"


class RAGPipelineRun(OperationsBase):
    """Execution result for a RAG pipeline test run."""

    __tablename__ = "rag_pipeline_runs"
    __table_args__ = (
        Index("idx_rag_run_paragraph_id", "paragraph_id"),
        Index("idx_rag_run_pipeline_class", "pipeline_class"),
        Index("idx_rag_run_executed_at", "executed_at"),
    )

    id = Column(String, primary_key=True)
    paragraph_id = Column(String, ForeignKey("test_paragraphs.id"), nullable=False)
    pipeline_class = Column(
        String, nullable=False
    )  # Pipeline class name (e.g., "StandardRAGPipeline")
    executed_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    execution_time_ms = Column(Integer, nullable=False)
    entities_extracted = Column(Integer, nullable=False)
    precision_score = Column(Integer, nullable=True)  # Stored as percentage (0-100)
    recall_score = Column(Integer, nullable=True)  # Stored as percentage (0-100)
    f1_score = Column(Integer, nullable=True)  # Stored as percentage (0-100)
    result_data = Column(Text, nullable=True)  # JSON blob with full extraction results

    # Relationship back to paragraph
    paragraph = relationship("TestParagraph", back_populates="pipeline_runs")

    def __repr__(self):
        return f"<RAGPipelineRun(id='{self.id}', pipeline_class='{self.pipeline_class}', f1_score={self.f1_score})>"
