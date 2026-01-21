"""
Pydantic models for RAG experiment API endpoints.

These models handle request validation and response serialization
for the RAG experimentation endpoints.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


# ==================== Request Models ====================

class CreateTestParagraphRequest(BaseModel):
    """Request model for creating a test paragraph."""

    text: str = Field(..., min_length=1, description="Text content of the test paragraph")
    notes: Optional[str] = Field(None, description="Optional notes about this test paragraph")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Apple is a technology company founded by Steve Jobs.",
                    "notes": "Test paragraph for entity extraction"
                }
            ]
        }
    }


class UpdateTestParagraphRequest(BaseModel):
    """Request model for updating a test paragraph."""

    text: Optional[str] = Field(None, min_length=1, description="Updated text content")
    notes: Optional[str] = Field(None, description="Updated notes")

    @field_validator('text', 'notes')
    @classmethod
    def at_least_one_field(cls, v, info):
        """Ensure at least one field is provided."""
        # This will be checked in the endpoint handler
        return v


class CreateAnnotationRequest(BaseModel):
    """Request model for creating an annotation on a test paragraph."""

    start_char: int = Field(..., ge=0, description="Starting character position (inclusive)")
    end_char: int = Field(..., ge=0, description="Ending character position (exclusive)")
    structure_node_id: str = Field(..., min_length=1, description="ID of the structure node in local.db")

    @field_validator('end_char')
    @classmethod
    def end_after_start(cls, v, info):
        """Validate that end_char is after start_char."""
        if 'start_char' in info.data and v <= info.data['start_char']:
            raise ValueError('end_char must be greater than start_char')
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "start_char": 0,
                    "end_char": 5,
                    "structure_node_id": "550e8400-e29b-41d4-a716-446655440000"
                }
            ]
        }
    }


class RunPipelineTestRequest(BaseModel):
    """Request model for executing pipeline tests."""

    paragraph_ids: List[str] = Field(..., min_length=1, description="List of test paragraph IDs to test")
    pipeline_names: List[str] = Field(..., min_length=1, description="List of pipeline class names to execute")
    enable_trace: bool = Field(False, description="Enable detailed trace logging")
    enable_llm_layer: bool = Field(True, description="Enable LLM extraction layer")

    @field_validator('pipeline_names')
    @classmethod
    def validate_pipeline_names(cls, v):
        """Validate that pipeline class names exist in the registry."""
        from rag.pipeline_registry import get_pipeline_registry

        registry = get_pipeline_registry()
        available_pipelines = registry.list_pipelines()

        invalid_pipelines = [name for name in v if name not in available_pipelines]
        if invalid_pipelines:
            raise ValueError(
                f"Invalid pipeline names: {', '.join(invalid_pipelines)}. "
                f"Available pipelines: {', '.join(available_pipelines)}"
            )

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "paragraph_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                    "pipeline_names": ["StandardRAGPipeline", "FastRAGPipeline"],
                    "enable_trace": False,
                    "enable_llm_layer": True
                }
            ]
        }
    }


# ==================== Response Models ====================

class AnnotationResponse(BaseModel):
    """Response model for an annotation."""

    id: str = Field(..., description="Annotation ID")
    paragraph_id: str = Field(..., description="Test paragraph ID")
    start_char: int = Field(..., description="Starting character position")
    end_char: int = Field(..., description="Ending character position")
    structure_node_id: str = Field(..., description="Structure node ID")
    text: str = Field(..., description="Annotated text span")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "paragraph_id": "660e8400-e29b-41d4-a716-446655440001",
                    "start_char": 0,
                    "end_char": 5,
                    "structure_node_id": "770e8400-e29b-41d4-a716-446655440002",
                    "text": "Apple",
                    "created_at": "2025-01-15T10:00:00Z"
                }
            ]
        }
    }


class TestParagraphResponse(BaseModel):
    """Response model for a test paragraph."""

    id: str = Field(..., description="Test paragraph ID")
    text: str = Field(..., description="Paragraph text")
    notes: Optional[str] = Field(None, description="Optional notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    annotations: List[AnnotationResponse] = Field(default_factory=list, description="List of annotations")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "text": "Apple is a technology company.",
                    "notes": "Test paragraph",
                    "created_at": "2025-01-15T10:00:00Z",
                    "annotations": []
                }
            ]
        }
    }


class TestParagraphListResponse(BaseModel):
    """Response model for list of test paragraphs."""

    paragraphs: List[TestParagraphResponse] = Field(..., description="List of test paragraphs")
    total_count: int = Field(..., description="Total count of paragraphs returned")
    limit: int = Field(..., description="Limit used for pagination")
    offset: int = Field(..., description="Offset used for pagination")


class ScoringDetailsResponse(BaseModel):
    """Response model for scoring details."""

    precision: float = Field(..., ge=0.0, le=1.0, description="Precision score (0-1)")
    recall: float = Field(..., ge=0.0, le=1.0, description="Recall score (0-1)")
    f1_score: float = Field(..., ge=0.0, le=1.0, description="F1 score (0-1)")
    true_positives: int = Field(..., ge=0, description="Number of true positives")
    false_positives: int = Field(..., ge=0, description="Number of false positives")
    false_negatives: int = Field(..., ge=0, description="Number of false negatives")


class PipelineRunResultResponse(BaseModel):
    """Response model for a single pipeline run result."""

    run_id: str = Field(..., description="Pipeline run ID")
    pipeline_name: str = Field(..., description="Pipeline class name")
    paragraph_id: str = Field(..., description="Test paragraph ID")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    entities_extracted: Optional[int] = Field(None, description="Number of entities extracted")
    scoring: Optional[ScoringDetailsResponse] = Field(None, description="Scoring details")
    executed_at: str = Field(..., description="Execution timestamp (ISO format)")
    error: Optional[str] = Field(None, description="Error message if pipeline failed")
    error_type: Optional[str] = Field(None, description="Error type if pipeline failed")


class RunPipelineTestResponse(BaseModel):
    """Response model for pipeline test execution."""

    results: List[PipelineRunResultResponse] = Field(..., description="List of pipeline run results")
    total_runs: int = Field(..., description="Total number of runs completed")
    successful_runs: int = Field(..., description="Number of successful runs")
    failed_runs: int = Field(..., description="Number of failed runs")


class PipelineComparisonItem(BaseModel):
    """Response model for a single pipeline in comparison results."""

    pipeline_name: str = Field(..., description="Pipeline class name")
    run_id: str = Field(..., description="Most recent run ID")
    f1_score: Optional[int] = Field(None, description="F1 score as percentage (0-100)")
    precision_score: Optional[int] = Field(None, description="Precision score as percentage (0-100)")
    recall_score: Optional[int] = Field(None, description="Recall score as percentage (0-100)")
    entities_extracted: int = Field(..., description="Number of entities extracted")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    executed_at: str = Field(..., description="Execution timestamp (ISO format)")


class PipelineComparisonSummary(BaseModel):
    """Summary statistics for pipeline comparison."""

    total_pipelines: int = Field(..., description="Number of pipelines compared")
    best_pipeline: Optional[str] = Field(None, description="Name of best performing pipeline")
    best_f1_score: Optional[int] = Field(None, description="Best F1 score as percentage")


class PipelineComparisonResponse(BaseModel):
    """Response model for pipeline comparison results."""

    paragraph_id: str = Field(..., description="Test paragraph ID")
    runs: List[PipelineComparisonItem] = Field(..., description="Pipeline comparison results")
    summary: PipelineComparisonSummary = Field(..., description="Comparison summary")


class PipelineRunDetailsResponse(BaseModel):
    """Response model for detailed pipeline run information."""

    run_id: str = Field(..., description="Pipeline run ID")
    paragraph_id: str = Field(..., description="Test paragraph ID")
    pipeline_class: str = Field(..., description="Pipeline class name")
    executed_at: str = Field(..., description="Execution timestamp (ISO format)")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    entities_extracted: int = Field(..., description="Number of entities extracted")
    precision_score: Optional[int] = Field(None, description="Precision score as percentage")
    recall_score: Optional[int] = Field(None, description="Recall score as percentage")
    f1_score: Optional[int] = Field(None, description="F1 score as percentage")
    result_data: Dict[str, Any] = Field(..., description="Full result data including entities and scoring details")
