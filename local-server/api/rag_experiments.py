"""
API endpoints for RAG pipeline experimentation.

This module provides RESTful endpoints for managing test paragraphs,
annotations, and executing parallel pipeline tests for systematic comparison.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.exc import DatabaseError, IntegrityError

from api.dependencies.rag_services import get_operations_db
from database.utils import get_db
from sqlalchemy.orm import Session
from rag.test_service import RAGTestManagementService
from rag.test_models import (
    CreateTestParagraphRequest,
    UpdateTestParagraphRequest,
    CreateAnnotationRequest,
    RunPipelineTestRequest,
    TestParagraphResponse,
    TestParagraphListResponse,
    AnnotationResponse,
    RunPipelineTestResponse,
    PipelineRunResultResponse,
    PipelineComparisonResponse,
    PipelineRunDetailsResponse,
    ScoringDetailsResponse,
    PipelineComparisonItem,
    PipelineComparisonSummary
)
from utils.logger import get_logger

router = APIRouter(prefix="/api/rag-experiments", tags=["RAG Experiments"])
logger = get_logger(__name__)


def get_test_service(
    kg_db: Session = Depends(get_db),
    ops_db: Session = Depends(get_operations_db)
) -> RAGTestManagementService:
    """
    Dependency injection for RAGTestManagementService.

    Args:
        kg_db: Database session for knowledge graph (local.db)
        ops_db: Database session for operations (operations.db)

    Returns:
        RAGTestManagementService instance
    """
    return RAGTestManagementService(kg_db_session=kg_db, ops_db_session=ops_db)


# ==================== Test Paragraph Endpoints ====================

@router.post("/paragraphs", response_model=TestParagraphResponse, status_code=status.HTTP_201_CREATED)
async def create_test_paragraph(
    request: CreateTestParagraphRequest,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Create a new test paragraph.

    Creates a test paragraph that can be annotated with ground truth entities
    and used for pipeline testing.
    """
    try:
        logger.info(f"Creating test paragraph with text length: {len(request.text)}")
        paragraph = test_service.create_test_paragraph(
            text=request.text,
            notes=request.notes
        )

        # Get annotations (will be empty for new paragraph)
        annotations = test_service.get_annotations_for_paragraph(paragraph.id)

        logger.info(f"Successfully created test paragraph: {paragraph.id}")
        return TestParagraphResponse(
            id=paragraph.id,
            text=paragraph.text,
            notes=paragraph.notes,
            created_at=paragraph.created_at,
            annotations=[]
        )

    except DatabaseError as e:
        logger.error(f"Database error creating test paragraph: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating test paragraph"
        )
    except ValueError as e:
        logger.error(f"Validation error creating test paragraph: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating test paragraph: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create test paragraph"
        )


@router.get("/paragraphs", response_model=TestParagraphListResponse)
async def list_test_paragraphs(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of paragraphs to return"),
    offset: int = Query(0, ge=0, description="Number of paragraphs to skip"),
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    List test paragraphs with pagination.

    Returns a paginated list of test paragraphs, each with its annotations.
    """
    try:
        logger.info(f"Listing test paragraphs with limit={limit}, offset={offset}")
        paragraphs, total_count = test_service.list_test_paragraphs(limit=limit, offset=offset)

        # Build response with annotations
        paragraph_responses = []
        for paragraph in paragraphs:
            annotations = test_service.get_annotations_for_paragraph(paragraph.id)
            annotation_responses = [
                AnnotationResponse(
                    id=ann.id,
                    paragraph_id=ann.paragraph_id,
                    start_char=ann.start_char,
                    end_char=ann.end_char,
                    structure_node_id=ann.structure_node_id,
                    text=paragraph.text[ann.start_char:ann.end_char],
                    created_at=ann.created_at
                )
                for ann in annotations
            ]

            paragraph_responses.append(
                TestParagraphResponse(
                    id=paragraph.id,
                    text=paragraph.text,
                    notes=paragraph.notes,
                    created_at=paragraph.created_at,
                    annotations=annotation_responses
                )
            )

        logger.info(f"Successfully retrieved {len(paragraph_responses)} of {total_count} test paragraphs")
        return TestParagraphListResponse(
            paragraphs=paragraph_responses,
            total_count=total_count,
            limit=limit,
            offset=offset
        )

    except DatabaseError as e:
        logger.error(f"Database error listing test paragraphs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while listing test paragraphs"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing test paragraphs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list test paragraphs"
        )


@router.get("/paragraphs/{paragraph_id}", response_model=TestParagraphResponse)
async def get_test_paragraph(
    paragraph_id: str,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Get a specific test paragraph by ID.

    Returns the paragraph with all its annotations.
    """
    try:
        logger.info(f"Getting test paragraph: {paragraph_id}")
        paragraph = test_service.get_test_paragraph(paragraph_id)

        if not paragraph:
            logger.warning(f"Test paragraph not found: {paragraph_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test paragraph not found: {paragraph_id}"
            )

        # Get annotations
        annotations = test_service.get_annotations_for_paragraph(paragraph.id)
        annotation_responses = [
            AnnotationResponse(
                id=ann.id,
                paragraph_id=ann.paragraph_id,
                start_char=ann.start_char,
                end_char=ann.end_char,
                structure_node_id=ann.structure_node_id,
                text=paragraph.text[ann.start_char:ann.end_char],
                created_at=ann.created_at
            )
            for ann in annotations
        ]

        return TestParagraphResponse(
            id=paragraph.id,
            text=paragraph.text,
            notes=paragraph.notes,
            created_at=paragraph.created_at,
            annotations=annotation_responses
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test paragraph {paragraph_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get test paragraph"
        )


@router.put("/paragraphs/{paragraph_id}", response_model=TestParagraphResponse)
async def update_test_paragraph(
    paragraph_id: str,
    request: UpdateTestParagraphRequest,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Update a test paragraph.

    Can update the text content and/or notes. At least one field must be provided.
    """
    try:
        # Validate at least one field is provided
        if request.text is None and request.notes is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field (text or notes) must be provided"
            )

        logger.info(f"Updating test paragraph: {paragraph_id}")
        paragraph = test_service.update_test_paragraph(
            paragraph_id=paragraph_id,
            text=request.text,
            notes=request.notes
        )

        if not paragraph:
            logger.warning(f"Test paragraph not found: {paragraph_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test paragraph not found: {paragraph_id}"
            )

        # Get annotations
        annotations = test_service.get_annotations_for_paragraph(paragraph.id)
        annotation_responses = [
            AnnotationResponse(
                id=ann.id,
                paragraph_id=ann.paragraph_id,
                start_char=ann.start_char,
                end_char=ann.end_char,
                structure_node_id=ann.structure_node_id,
                text=paragraph.text[ann.start_char:ann.end_char],
                created_at=ann.created_at
            )
            for ann in annotations
        ]

        logger.info(f"Successfully updated test paragraph: {paragraph_id}")
        return TestParagraphResponse(
            id=paragraph.id,
            text=paragraph.text,
            notes=paragraph.notes,
            created_at=paragraph.created_at,
            annotations=annotation_responses
        )

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error updating test paragraph {paragraph_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while updating test paragraph"
        )
    except ValueError as e:
        logger.error(f"Validation error updating test paragraph {paragraph_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error updating test paragraph {paragraph_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update test paragraph"
        )


@router.delete("/paragraphs/{paragraph_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_paragraph(
    paragraph_id: str,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Delete a test paragraph.

    Deletes the paragraph and all associated annotations and pipeline runs
    (cascade delete handled by database relationships).
    """
    try:
        logger.info(f"Deleting test paragraph: {paragraph_id}")
        success = test_service.delete_test_paragraph(paragraph_id)

        if not success:
            logger.warning(f"Test paragraph not found: {paragraph_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test paragraph not found: {paragraph_id}"
            )

        logger.info(f"Successfully deleted test paragraph: {paragraph_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting test paragraph {paragraph_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete test paragraph"
        )


# ==================== Annotation Endpoints ====================

@router.post(
    "/paragraphs/{paragraph_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_annotation(
    paragraph_id: str,
    request: CreateAnnotationRequest,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Create a new annotation for a test paragraph.

    Annotations define ground truth entity spans for testing pipeline accuracy.
    Validates that:
    - The paragraph exists
    - The structure_node_id exists in local.db
    - The character positions are valid
    """
    try:
        logger.info(
            f"Creating annotation for paragraph {paragraph_id}: "
            f"[{request.start_char}:{request.end_char}] -> {request.structure_node_id}"
        )

        # Create annotation with proper transaction handling
        annotation = test_service.create_test_annotation(
            paragraph_id=paragraph_id,
            start_char=request.start_char,
            end_char=request.end_char,
            structure_node_id=request.structure_node_id
        )

        if not annotation:
            # Determine specific error reason
            paragraph = test_service.get_test_paragraph(paragraph_id)
            if not paragraph:
                logger.warning(f"Paragraph not found: {paragraph_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Test paragraph not found: {paragraph_id}"
                )
            else:
                logger.error(
                    "Failed to create annotation: invalid structure_node_id or character positions"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid structure_node_id or character positions"
                )

        # Get paragraph to extract text
        paragraph = test_service.get_test_paragraph(paragraph_id)
        text = paragraph.text[annotation.start_char:annotation.end_char]

        logger.info(f"Successfully created annotation: {annotation.id}")
        return AnnotationResponse(
            id=annotation.id,
            paragraph_id=annotation.paragraph_id,
            start_char=annotation.start_char,
            end_char=annotation.end_char,
            structure_node_id=annotation.structure_node_id,
            text=text,
            created_at=annotation.created_at
        )

    except HTTPException:
        raise
    except IntegrityError as e:
        logger.error(f"Integrity error creating annotation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid structure_node_id or annotation violates database constraints"
        )
    except DatabaseError as e:
        logger.error(f"Database error creating annotation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating annotation"
        )
    except ValueError as e:
        logger.error(f"Validation error creating annotation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating annotation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create annotation"
        )


@router.delete(
    "/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_annotation(
    annotation_id: str,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Delete a specific annotation.
    """
    try:
        logger.info(f"Deleting annotation: {annotation_id}")
        success = test_service.delete_test_annotation(annotation_id)

        if not success:
            logger.warning(f"Annotation not found: {annotation_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Annotation not found: {annotation_id}"
            )

        logger.info(f"Successfully deleted annotation: {annotation_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting annotation {annotation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete annotation"
        )


# ==================== Pipeline Execution Endpoints ====================

@router.post("/run", response_model=RunPipelineTestResponse)
async def run_pipeline_test(
    request: RunPipelineTestRequest,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Execute multiple pipelines against test paragraphs.

    Runs the specified pipelines in parallel (with controlled concurrency)
    against each test paragraph, scores the results against ground truth
    annotations, and returns execution metrics.

    Supports testing multiple pipeline variants simultaneously for comparison.
    """
    try:
        logger.info(
            f"Running pipeline test: {len(request.paragraph_ids)} paragraphs, "
            f"{len(request.pipeline_names)} pipelines"
        )

        all_results = []

        # Run tests for each paragraph
        for paragraph_id in request.paragraph_ids:
            logger.info(f"Testing paragraph: {paragraph_id}")

            # Validate paragraph exists
            paragraph = test_service.get_test_paragraph(paragraph_id)
            if not paragraph:
                logger.warning(f"Skipping non-existent paragraph: {paragraph_id}")
                continue

            # Run pipelines
            results = await test_service.run_pipeline_test(
                paragraph_id=paragraph_id,
                pipeline_names=request.pipeline_names,
                enable_trace=request.enable_trace,
                enable_llm_layer=request.enable_llm_layer
            )

            # Convert results to response models
            for result in results:
                if "error" in result:
                    # Error result
                    all_results.append(
                        PipelineRunResultResponse(
                            run_id=result["run_id"],
                            pipeline_name=result["pipeline_name"],
                            paragraph_id=result["paragraph_id"],
                            executed_at=result["executed_at"],
                            error=result["error"],
                            error_type=result.get("error_type")
                        )
                    )
                else:
                    # Success result
                    scoring_data = result["scoring"]
                    all_results.append(
                        PipelineRunResultResponse(
                            run_id=result["run_id"],
                            pipeline_name=result["pipeline_name"],
                            paragraph_id=result["paragraph_id"],
                            execution_time_ms=result["execution_time_ms"],
                            entities_extracted=result["entities_extracted"],
                            scoring=ScoringDetailsResponse(
                                precision=scoring_data["precision"],
                                recall=scoring_data["recall"],
                                f1_score=scoring_data["f1_score"],
                                true_positives=scoring_data["true_positives"],
                                false_positives=scoring_data["false_positives"],
                                false_negatives=scoring_data["false_negatives"]
                            ),
                            executed_at=result["executed_at"]
                        )
                    )

        # Calculate summary statistics
        successful_runs = len([r for r in all_results if r.error is None])
        failed_runs = len([r for r in all_results if r.error is not None])

        logger.info(
            f"Pipeline test completed: {successful_runs} successful, {failed_runs} failed"
        )

        return RunPipelineTestResponse(
            results=all_results,
            total_runs=len(all_results),
            successful_runs=successful_runs,
            failed_runs=failed_runs
        )

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error running pipeline test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while running pipeline test"
        )
    except ValueError as e:
        logger.error(f"Validation error running pipeline test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except TimeoutError as e:
        logger.error(f"Pipeline execution timeout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Pipeline execution timed out"
        )
    except Exception as e:
        logger.error(f"Unexpected error running pipeline test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run pipeline test: {str(e)}"
        )


# ==================== Results Query Endpoints ====================

@router.get("/results/paragraphs/{paragraph_id}", response_model=PipelineComparisonResponse)
async def get_pipeline_comparison(
    paragraph_id: str,
    pipeline_names: Optional[List[str]] = Query(None, description="Filter by pipeline names"),
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Compare pipeline results for a specific test paragraph.

    Returns the most recent run for each pipeline, sorted by F1 score.
    Optionally filter by specific pipeline names.
    """
    try:
        logger.info(f"Getting pipeline comparison for paragraph: {paragraph_id}")

        # Validate paragraph exists
        paragraph = test_service.get_test_paragraph(paragraph_id)
        if not paragraph:
            logger.warning(f"Test paragraph not found: {paragraph_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test paragraph not found: {paragraph_id}"
            )

        # Get comparison results
        comparison = test_service.compare_pipeline_runs(
            paragraph_id=paragraph_id,
            pipeline_names=pipeline_names
        )

        # Convert to response model
        runs = [
            PipelineComparisonItem(
                pipeline_name=run["pipeline_name"],
                run_id=run["run_id"],
                f1_score=run["f1_score"],
                precision_score=run["precision_score"],
                recall_score=run["recall_score"],
                entities_extracted=run["entities_extracted"],
                execution_time_ms=run["execution_time_ms"],
                executed_at=run["executed_at"]
            )
            for run in comparison["runs"]
        ]

        summary = PipelineComparisonSummary(
            total_pipelines=comparison["summary"]["total_pipelines"],
            best_pipeline=comparison["summary"]["best_pipeline"],
            best_f1_score=comparison["summary"]["best_f1_score"]
        )

        logger.info(f"Successfully retrieved comparison for {len(runs)} pipelines")
        return PipelineComparisonResponse(
            paragraph_id=paragraph_id,
            runs=runs,
            summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pipeline comparison: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline comparison"
        )


@router.get("/results/runs/{run_id}", response_model=PipelineRunDetailsResponse)
async def get_pipeline_run_details(
    run_id: str,
    test_service: RAGTestManagementService = Depends(get_test_service)
):
    """
    Get detailed results for a specific pipeline run.

    Returns full extraction results, entities, and scoring details.
    """
    try:
        logger.info(f"Getting pipeline run details: {run_id}")

        details = test_service.get_pipeline_run_details(run_id)
        if not details:
            logger.warning(f"Pipeline run not found: {run_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline run not found: {run_id}"
            )

        logger.info(f"Successfully retrieved run details: {run_id}")
        return PipelineRunDetailsResponse(
            run_id=details["run_id"],
            paragraph_id=details["paragraph_id"],
            pipeline_class=details["pipeline_class"],
            executed_at=details["executed_at"],
            execution_time_ms=details["execution_time_ms"],
            entities_extracted=details["entities_extracted"],
            precision_score=details["precision_score"],
            recall_score=details["recall_score"],
            f1_score=details["f1_score"],
            result_data=details["result_data"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pipeline run details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline run details"
        )
