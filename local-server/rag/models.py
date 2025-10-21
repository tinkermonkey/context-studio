"""
Pydantic models for RAG (Retrieval-Augmented Generation) pipeline requests and responses.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from uuid import UUID, uuid4


class RAGExtractionRequest(BaseModel):
    """
    Request model for RAG entity extraction.

    This model represents a request to extract entities from text using the
    RAG pipeline, which processes text through multiple layers (KG, NLP, LLM, Web)
    to identify and enrich entities with context.
    """
    text: str = Field(..., description="Text to analyze and extract entities from.", min_length=1)
    enable_trace: bool = Field(default=False, description="Enable detailed tracing for observability. Defaults to false per architect requirement.")
    enable_llm_layer: Optional[bool] = Field(default=None, description="Enable Layer 1 LLM extraction. If None, uses config default.")

    @field_validator('text')
    @classmethod
    def validate_text_not_empty(cls, v: str) -> str:
        """Validate that text is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Text cannot be empty or whitespace only")
        return v


class ExtractedEntity(BaseModel):
    """
    Represents a single entity extracted from text.

    Entities are extracted through one or more layers of the RAG pipeline,
    with each entity containing metadata about its source, position, and confidence.
    """
    text: str = Field(..., description="The entity text as it appears in the source.", min_length=1)
    type: str = Field(..., description="The entity type (e.g., 'PERSON', 'ORG', 'LOCATION', 'CONCEPT').")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for this entity extraction (0.0 to 1.0).")
    source_layer: str = Field(..., description="The pipeline layer that extracted this entity ('kg', 'nlp', 'llm', 'web').")
    sentence_index: int = Field(..., ge=0, description="Index of the sentence containing this entity (0-based).")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the entity (e.g., KB IDs, relations, context).")

    @field_validator('source_layer')
    @classmethod
    def validate_source_layer(cls, v: str) -> str:
        """Validate that source_layer is one of the expected pipeline layers."""
        valid_layers = {'kg', 'nlp', 'llm', 'web'}
        if v not in valid_layers:
            raise ValueError(f"source_layer must be one of {valid_layers}, got '{v}'")
        return v


class LayerMetrics(BaseModel):
    """
    Performance metrics for a single pipeline layer.

    Tracks timing, entity counts, and operation counts for each layer of the RAG pipeline.
    """
    execution_time_ms: float = Field(..., ge=0.0, description="Execution time for this layer in milliseconds.")
    entities_found: int = Field(..., ge=0, description="Number of entities found by this layer.")
    entities_deduplicated: int = Field(default=0, ge=0, description="Number of entities removed as duplicates in this layer.")
    operations_performed: int = Field(default=0, ge=0, description="Number of operations/searches performed (e.g., vector searches, web searches).")


class ProcessingMetrics(BaseModel):
    """
    Comprehensive metrics for RAG pipeline execution.

    Captures timing and entity counts for all four layers of the pipeline,
    plus overall execution metrics.
    """
    kg_layer: LayerMetrics = Field(..., description="Metrics for knowledge graph layer.")
    nlp_layer: LayerMetrics = Field(..., description="Metrics for NLP processing layer.")
    llm_layer: LayerMetrics = Field(..., description="Metrics for LLM enrichment layer.")
    web_layer: LayerMetrics = Field(..., description="Metrics for web search layer.")

    total_execution_time_ms: float = Field(..., ge=0.0, description="Total pipeline execution time in milliseconds.")
    total_entities: int = Field(..., ge=0, description="Total number of unique entities after deduplication.")
    total_sentences: int = Field(..., ge=0, description="Total number of sentences processed.")


class RAGExtractionResponse(BaseModel):
    """
    Response model for RAG entity extraction.

    Contains extracted entities, processing metrics, and trace availability information.
    """
    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for this extraction request.")
    entities: List[ExtractedEntity] = Field(default_factory=list, description="List of extracted entities with enrichment data.")
    metrics: ProcessingMetrics = Field(..., description="Performance metrics for the extraction pipeline.")
    trace_available: bool = Field(default=False, description="Indicates whether detailed trace data is available for this request.")

    @field_validator('request_id')
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate that request_id is a valid UUID string."""
        try:
            UUID(v)
        except ValueError:
            raise ValueError(f"request_id must be a valid UUID string, got '{v}'")
        return v
