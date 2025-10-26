"""
RAG Pipeline Test Management Service

This module provides CRUD operations for test data and orchestrates
parallel pipeline execution for systematic comparison and experimentation.
"""

import uuid
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from operations.models import TestParagraph, TestAnnotation, RAGPipelineRun
from rag.pipeline_registry import get_pipeline_registry
from rag.test_scoring import RAGTestScoringService, AnnotationSpan
from rag.models import ExtractedEntity
from utils.logger import get_logger

logger = get_logger(__name__)


class RAGTestManagementService:
    """
    Service for managing RAG pipeline test data and execution.

    Provides:
    - CRUD operations for test paragraphs and annotations
    - Test execution orchestration with parallel pipeline runs
    - Results aggregation and comparison
    - Cross-database validation for structure_node_id references
    """

    # Maximum concurrent pipeline executions
    MAX_CONCURRENT_PIPELINES = 3

    def __init__(self, kg_db_session: Session, ops_db_session: Session):
        """
        Initialize test management service.

        Args:
            kg_db_session: Database session for knowledge graph (local.db)
            ops_db_session: Database session for operations (operations.db)
        """
        self.kg_db_session = kg_db_session
        self.ops_db_session = ops_db_session
        self.scoring_service = RAGTestScoringService()
        self.pipeline_registry = get_pipeline_registry()
        logger.info("RAGTestManagementService initialized")

    # ==================== Test Paragraph CRUD ====================

    def create_test_paragraph(self, text: str, notes: str = None) -> TestParagraph:
        """
        Create a new test paragraph.

        Args:
            text: The paragraph text to test with
            notes: Optional notes about this test paragraph

        Returns:
            Created TestParagraph instance
        """
        test_paragraph = TestParagraph(
            id=str(uuid.uuid4()),
            text=text,
            notes=notes,
            created_at=datetime.utcnow()
        )

        self.ops_db_session.add(test_paragraph)
        self.ops_db_session.commit()

        logger.info(f"Created test paragraph: {test_paragraph.id}")
        return test_paragraph

    def get_test_paragraph(self, paragraph_id: str) -> Optional[TestParagraph]:
        """Get a test paragraph by ID."""
        return self.ops_db_session.query(TestParagraph).filter(
            TestParagraph.id == paragraph_id
        ).first()

    def list_test_paragraphs(self, limit: int = 100, offset: int = 0) -> List[TestParagraph]:
        """
        List test paragraphs with pagination.

        Args:
            limit: Maximum number of paragraphs to return
            offset: Number of paragraphs to skip

        Returns:
            List of TestParagraph instances
        """
        return self.ops_db_session.query(TestParagraph).order_by(
            TestParagraph.created_at.desc()
        ).limit(limit).offset(offset).all()

    def update_test_paragraph(
        self,
        paragraph_id: str,
        text: str = None,
        notes: str = None
    ) -> Optional[TestParagraph]:
        """
        Update a test paragraph.

        Args:
            paragraph_id: ID of paragraph to update
            text: New text (optional)
            notes: New notes (optional)

        Returns:
            Updated TestParagraph, or None if not found
        """
        paragraph = self.get_test_paragraph(paragraph_id)
        if not paragraph:
            logger.warning(f"Test paragraph not found: {paragraph_id}")
            return None

        if text is not None:
            paragraph.text = text
        if notes is not None:
            paragraph.notes = notes

        self.ops_db_session.commit()
        logger.info(f"Updated test paragraph: {paragraph_id}")
        return paragraph

    def delete_test_paragraph(self, paragraph_id: str) -> bool:
        """
        Delete a test paragraph and all associated data.

        Args:
            paragraph_id: ID of paragraph to delete

        Returns:
            True if deleted, False if not found
        """
        paragraph = self.get_test_paragraph(paragraph_id)
        if not paragraph:
            logger.warning(f"Test paragraph not found: {paragraph_id}")
            return False

        # Delete associated annotations and runs (cascade should handle this,
        # but we'll be explicit for safety)
        self.ops_db_session.query(TestAnnotation).filter(
            TestAnnotation.paragraph_id == paragraph_id
        ).delete()

        self.ops_db_session.query(RAGPipelineRun).filter(
            RAGPipelineRun.paragraph_id == paragraph_id
        ).delete()

        self.ops_db_session.delete(paragraph)
        self.ops_db_session.commit()

        logger.info(f"Deleted test paragraph: {paragraph_id}")
        return True

    # ==================== Test Annotation CRUD ====================

    def create_test_annotation(
        self,
        paragraph_id: str,
        start_char: int,
        end_char: int,
        structure_node_id: str
    ) -> Optional[TestAnnotation]:
        """
        Create a new annotation for a test paragraph.

        Validates that:
        - The paragraph exists
        - The structure_node_id exists in local.db

        Args:
            paragraph_id: ID of the test paragraph
            start_char: Starting character position
            end_char: Ending character position
            structure_node_id: ID of the structure node in local.db

        Returns:
            Created TestAnnotation, or None if validation fails
        """
        # Validate paragraph exists
        paragraph = self.get_test_paragraph(paragraph_id)
        if not paragraph:
            logger.error(f"Cannot create annotation: paragraph {paragraph_id} not found")
            return None

        # Validate structure_node_id exists in local.db
        if not self._validate_structure_node_id(structure_node_id):
            logger.error(
                f"Cannot create annotation: structure_node {structure_node_id} not found in local.db"
            )
            return None

        # Validate character positions
        if start_char < 0 or end_char > len(paragraph.text) or start_char >= end_char:
            logger.error(
                f"Invalid character positions: start={start_char}, end={end_char}, "
                f"text_length={len(paragraph.text)}"
            )
            return None

        annotation = TestAnnotation(
            id=str(uuid.uuid4()),
            paragraph_id=paragraph_id,
            start_char=start_char,
            end_char=end_char,
            structure_node_id=structure_node_id,
            created_at=datetime.utcnow()
        )

        self.ops_db_session.add(annotation)
        self.ops_db_session.commit()

        logger.info(f"Created test annotation: {annotation.id} for paragraph {paragraph_id}")
        return annotation

    def get_annotations_for_paragraph(self, paragraph_id: str) -> List[TestAnnotation]:
        """Get all annotations for a test paragraph."""
        return self.ops_db_session.query(TestAnnotation).filter(
            TestAnnotation.paragraph_id == paragraph_id
        ).order_by(TestAnnotation.start_char).all()

    def delete_test_annotation(self, annotation_id: str) -> bool:
        """
        Delete a test annotation.

        Args:
            annotation_id: ID of annotation to delete

        Returns:
            True if deleted, False if not found
        """
        annotation = self.ops_db_session.query(TestAnnotation).filter(
            TestAnnotation.id == annotation_id
        ).first()

        if not annotation:
            logger.warning(f"Test annotation not found: {annotation_id}")
            return False

        self.ops_db_session.delete(annotation)
        self.ops_db_session.commit()

        logger.info(f"Deleted test annotation: {annotation_id}")
        return True

    def _validate_structure_node_id(self, structure_node_id: str) -> bool:
        """
        Validate that a structure_node_id exists in local.db.

        Args:
            structure_node_id: ID to validate

        Returns:
            True if exists, False otherwise
        """
        try:
            result = self.kg_db_session.execute(
                text("SELECT COUNT(*) FROM structure_nodes WHERE id = :id"),
                {"id": structure_node_id}
            ).scalar()
            return result > 0
        except Exception as e:
            logger.error(f"Error validating structure_node_id: {e}", exc_info=True)
            return False

    # ==================== Pipeline Execution ====================

    async def run_pipeline_test(
        self,
        paragraph_id: str,
        pipeline_names: List[str],
        enable_trace: bool = False,
        enable_llm_layer: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Run one or more pipelines against a test paragraph and score the results.

        Args:
            paragraph_id: ID of the test paragraph
            pipeline_names: List of pipeline class names to run
            enable_trace: Enable detailed tracing
            enable_llm_layer: Enable LLM layer

        Returns:
            List of dictionaries containing run results and scores
        """
        # Get paragraph and annotations
        paragraph = self.get_test_paragraph(paragraph_id)
        if not paragraph:
            logger.error(f"Test paragraph not found: {paragraph_id}")
            return []

        annotations = self.get_annotations_for_paragraph(paragraph_id)
        if not annotations:
            logger.warning(f"No annotations found for paragraph {paragraph_id}")

        # Convert annotations to AnnotationSpan objects
        annotation_spans = [
            AnnotationSpan(
                start_char=ann.start_char,
                end_char=ann.end_char,
                structure_node_id=ann.structure_node_id,
                text=paragraph.text[ann.start_char:ann.end_char]
            )
            for ann in annotations
        ]

        # Run pipelines in parallel with controlled concurrency
        logger.info(
            f"Running {len(pipeline_names)} pipelines against paragraph {paragraph_id}"
        )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PIPELINES)

        # Create tasks for parallel execution
        tasks = [
            self._run_single_pipeline(
                pipeline_name,
                paragraph,
                annotation_spans,
                enable_trace,
                enable_llm_layer,
                semaphore
            )
            for pipeline_name in pipeline_names
        ]

        # Execute all tasks and gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Pipeline {pipeline_names[i]} failed: {result}",
                    exc_info=result
                )
            else:
                valid_results.append(result)

        logger.info(
            f"Completed {len(valid_results)}/{len(pipeline_names)} pipeline runs "
            f"for paragraph {paragraph_id}"
        )

        return valid_results

    async def _run_single_pipeline(
        self,
        pipeline_name: str,
        paragraph: TestParagraph,
        annotation_spans: List[AnnotationSpan],
        enable_trace: bool,
        enable_llm_layer: bool,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """
        Run a single pipeline and score the results.

        Args:
            pipeline_name: Name of pipeline to run
            paragraph: Test paragraph
            annotation_spans: Ground truth annotations
            enable_trace: Enable tracing
            enable_llm_layer: Enable LLM layer
            semaphore: Semaphore for concurrency control

        Returns:
            Dictionary with run results and scores
        """
        async with semaphore:
            logger.info(f"Starting pipeline {pipeline_name} for paragraph {paragraph.id}")
            start_time = datetime.utcnow()

            # Create pipeline instance
            pipeline = self.pipeline_registry.create_pipeline(
                pipeline_name=pipeline_name,
                kg_db_session=self.kg_db_session,
                ops_db_session=self.ops_db_session,
                config={}
            )

            if not pipeline:
                raise ValueError(f"Pipeline {pipeline_name} not found in registry")

            # Execute extraction
            extraction_start = datetime.utcnow()
            extraction_response = await pipeline.extract_entities(
                text=paragraph.text,
                enable_trace=enable_trace,
                enable_llm_layer=enable_llm_layer
            )
            execution_time_ms = int((datetime.utcnow() - extraction_start).total_seconds() * 1000)

            # Score the results
            scoring_result = self.scoring_service.score_extraction(
                extracted_entities=extraction_response.entities,
                ground_truth_annotations=annotation_spans,
                paragraph_text=paragraph.text
            )

            # Save pipeline run to database
            run_id = str(uuid.uuid4())
            pipeline_run = RAGPipelineRun(
                id=run_id,
                paragraph_id=paragraph.id,
                pipeline_class=pipeline_name,
                executed_at=start_time,
                execution_time_ms=execution_time_ms,
                entities_extracted=len(extraction_response.entities),
                precision_score=int(scoring_result.precision * 100),  # Store as percentage
                recall_score=int(scoring_result.recall * 100),
                f1_score=int(scoring_result.f1_score * 100),
                result_data=json.dumps({
                    "entities": [
                        {
                            "text": e.text,
                            "type": e.type,
                            "confidence": e.confidence,
                            "source_layer": e.source_layer,
                            "metadata": e.metadata
                        }
                        for e in extraction_response.entities
                    ],
                    "scoring_details": scoring_result.to_dict()
                })
            )

            self.ops_db_session.add(pipeline_run)
            self.ops_db_session.commit()

            logger.info(
                f"Pipeline {pipeline_name} completed: "
                f"F1={scoring_result.f1_score:.2f}, "
                f"P={scoring_result.precision:.2f}, "
                f"R={scoring_result.recall:.2f}, "
                f"time={execution_time_ms}ms"
            )

            return {
                "run_id": run_id,
                "pipeline_name": pipeline_name,
                "paragraph_id": paragraph.id,
                "execution_time_ms": execution_time_ms,
                "entities_extracted": len(extraction_response.entities),
                "scoring": scoring_result.to_dict(),
                "executed_at": start_time.isoformat()
            }

    # ==================== Results Retrieval ====================

    def get_pipeline_runs_for_paragraph(
        self,
        paragraph_id: str,
        limit: int = 100
    ) -> List[RAGPipelineRun]:
        """Get all pipeline runs for a specific test paragraph."""
        return self.ops_db_session.query(RAGPipelineRun).filter(
            RAGPipelineRun.paragraph_id == paragraph_id
        ).order_by(RAGPipelineRun.executed_at.desc()).limit(limit).all()

    def get_pipeline_run_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed results for a specific pipeline run.

        Args:
            run_id: ID of the pipeline run

        Returns:
            Dictionary with run details and full result data
        """
        run = self.ops_db_session.query(RAGPipelineRun).filter(
            RAGPipelineRun.id == run_id
        ).first()

        if not run:
            return None

        result_data = json.loads(run.result_data) if run.result_data else {}

        return {
            "run_id": run.id,
            "paragraph_id": run.paragraph_id,
            "pipeline_class": run.pipeline_class,
            "executed_at": run.executed_at.isoformat(),
            "execution_time_ms": run.execution_time_ms,
            "entities_extracted": run.entities_extracted,
            "precision_score": run.precision_score,
            "recall_score": run.recall_score,
            "f1_score": run.f1_score,
            "result_data": result_data
        }

    def compare_pipeline_runs(
        self,
        paragraph_id: str,
        pipeline_names: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare results across multiple pipeline runs for a paragraph.

        Args:
            paragraph_id: ID of the test paragraph
            pipeline_names: Optional list of pipeline names to filter by

        Returns:
            Dictionary with comparison results
        """
        runs = self.get_pipeline_runs_for_paragraph(paragraph_id)

        if pipeline_names:
            runs = [r for r in runs if r.pipeline_class in pipeline_names]

        if not runs:
            return {
                "paragraph_id": paragraph_id,
                "runs": [],
                "summary": {}
            }

        # Group runs by pipeline class (use most recent run for each)
        pipeline_runs = {}
        for run in runs:
            if run.pipeline_class not in pipeline_runs:
                pipeline_runs[run.pipeline_class] = run

        # Build comparison
        comparison = []
        for pipeline_class, run in pipeline_runs.items():
            comparison.append({
                "pipeline_name": pipeline_class,
                "run_id": run.id,
                "f1_score": run.f1_score,
                "precision_score": run.precision_score,
                "recall_score": run.recall_score,
                "entities_extracted": run.entities_extracted,
                "execution_time_ms": run.execution_time_ms,
                "executed_at": run.executed_at.isoformat()
            })

        # Sort by F1 score descending
        comparison.sort(key=lambda x: x["f1_score"] or 0, reverse=True)

        return {
            "paragraph_id": paragraph_id,
            "runs": comparison,
            "summary": {
                "total_pipelines": len(comparison),
                "best_pipeline": comparison[0]["pipeline_name"] if comparison else None,
                "best_f1_score": comparison[0]["f1_score"] if comparison else None
            }
        }
