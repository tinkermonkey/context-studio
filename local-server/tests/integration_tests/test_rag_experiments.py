"""
Integration tests for RAG Experiments API endpoints.

These tests verify end-to-end functionality for managing test paragraphs,
annotations, and executing parallel pipeline tests with scoring.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from app import create_app
from database.models import Base, StructureNode
from database.custom_types import NodeType
from operations.models import OperationsBase, TestParagraph, TestAnnotation, RAGPipelineRun
from rag.test_scoring import ScoringResult
from rag.models import RAGExtractionResponse, ExtractedEntity


@pytest.fixture
def test_kg_db():
    """Create a temporary test database for knowledge graph."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Add test structure nodes
    session = SessionLocal()
    try:
        nodes = [
            StructureNode(
                id=str(uuid4()),
                node_type=NodeType.TERM,
                title="Apple Inc.",
                definition="Technology company",
                parent_node_id=None
            ),
            StructureNode(
                id=str(uuid4()),
                node_type=NodeType.TERM,
                title="Steve Jobs",
                definition="Co-founder of Apple",
                parent_node_id=None
            ),
            StructureNode(
                id=str(uuid4()),
                node_type=NodeType.TERM,
                title="iPhone",
                definition="Smartphone product",
                parent_node_id=None
            ),
        ]

        for node in nodes:
            session.add(node)

        session.commit()

        # Return nodes for use in tests
        node_ids = [node.id for node in nodes]

    finally:
        session.close()

    yield engine, SessionLocal, node_ids

    # Cleanup
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def test_ops_db():
    """Create a temporary test database for operations."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    OperationsBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    yield engine, SessionLocal

    # Cleanup
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def test_client(test_kg_db, test_ops_db):
    """Create test client for API integration tests."""
    kg_engine, kg_session_maker, node_ids = test_kg_db
    ops_engine, ops_session_maker = test_ops_db

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
        # Attach node_ids for test access
        client.node_ids = node_ids
        yield client


class TestParagraphCRUD:
    """Integration tests for test paragraph CRUD operations."""

    def test_create_paragraph_success(self, test_client):
        """Test POST /api/rag-experiments/paragraphs creates a paragraph."""
        response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={
                "text": "Apple is a technology company founded by Steve Jobs.",
                "notes": "Test paragraph for entity extraction"
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["text"] == "Apple is a technology company founded by Steve Jobs."
        assert data["notes"] == "Test paragraph for entity extraction"
        assert "created_at" in data
        assert data["annotations"] == []

    def test_create_paragraph_without_notes(self, test_client):
        """Test creating a paragraph without optional notes."""
        response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={
                "text": "iPhone is a popular smartphone product."
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["text"] == "iPhone is a popular smartphone product."
        assert data["notes"] is None

    def test_create_paragraph_empty_text(self, test_client):
        """Test creating a paragraph with empty text fails validation."""
        response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={
                "text": "",
                "notes": "Empty text"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_list_paragraphs_empty(self, test_client):
        """Test GET /api/rag-experiments/paragraphs with no paragraphs."""
        response = test_client.get("/api/rag-experiments/paragraphs")

        assert response.status_code == 200
        data = response.json()

        assert data["paragraphs"] == []
        assert data["total_count"] == 0
        assert data["limit"] == 100
        assert data["offset"] == 0

    def test_list_paragraphs_with_data(self, test_client):
        """Test listing paragraphs after creating some."""
        # Create test paragraphs
        paragraph_1 = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "First test paragraph."}
        ).json()

        paragraph_2 = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Second test paragraph."}
        ).json()

        # List paragraphs
        response = test_client.get("/api/rag-experiments/paragraphs")

        assert response.status_code == 200
        data = response.json()

        assert data["total_count"] == 2
        assert len(data["paragraphs"]) == 2

        # Verify paragraphs are ordered by created_at desc
        assert data["paragraphs"][0]["id"] == paragraph_2["id"]
        assert data["paragraphs"][1]["id"] == paragraph_1["id"]

    def test_list_paragraphs_pagination(self, test_client):
        """Test pagination parameters for listing paragraphs."""
        # Create 5 test paragraphs
        for i in range(5):
            test_client.post(
                "/api/rag-experiments/paragraphs",
                json={"text": f"Test paragraph {i}"}
            )

        # Test limit
        response = test_client.get("/api/rag-experiments/paragraphs?limit=2")
        assert response.status_code == 200
        assert len(response.json()["paragraphs"]) == 2

        # Test offset
        response = test_client.get("/api/rag-experiments/paragraphs?offset=3")
        assert response.status_code == 200
        assert len(response.json()["paragraphs"]) == 2

        # Test limit + offset
        response = test_client.get("/api/rag-experiments/paragraphs?limit=2&offset=2")
        assert response.status_code == 200
        assert len(response.json()["paragraphs"]) == 2

    def test_get_paragraph_by_id_success(self, test_client):
        """Test GET /api/rag-experiments/paragraphs/{id} with valid ID."""
        # Create paragraph
        create_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test paragraph for retrieval."}
        )
        paragraph_id = create_response.json()["id"]

        # Get paragraph
        response = test_client.get(f"/api/rag-experiments/paragraphs/{paragraph_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == paragraph_id
        assert data["text"] == "Test paragraph for retrieval."

    def test_get_paragraph_not_found(self, test_client):
        """Test getting a non-existent paragraph returns 404."""
        fake_id = str(uuid4())
        response = test_client.get(f"/api/rag-experiments/paragraphs/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_paragraph_text(self, test_client):
        """Test PUT /api/rag-experiments/paragraphs/{id} to update text."""
        # Create paragraph
        create_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Original text."}
        )
        paragraph_id = create_response.json()["id"]

        # Update text
        response = test_client.put(
            f"/api/rag-experiments/paragraphs/{paragraph_id}",
            json={"text": "Updated text."}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Updated text."

    def test_update_paragraph_notes(self, test_client):
        """Test updating only the notes field."""
        create_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test text."}
        )
        paragraph_id = create_response.json()["id"]

        response = test_client.put(
            f"/api/rag-experiments/paragraphs/{paragraph_id}",
            json={"notes": "New notes"}
        )

        assert response.status_code == 200
        assert response.json()["notes"] == "New notes"

    def test_update_paragraph_no_fields(self, test_client):
        """Test updating with no fields fails."""
        create_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test text."}
        )
        paragraph_id = create_response.json()["id"]

        response = test_client.put(
            f"/api/rag-experiments/paragraphs/{paragraph_id}",
            json={}
        )

        assert response.status_code == 400
        assert "at least one field" in response.json()["detail"].lower()

    def test_delete_paragraph_success(self, test_client):
        """Test DELETE /api/rag-experiments/paragraphs/{id}."""
        # Create paragraph
        create_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "To be deleted."}
        )
        paragraph_id = create_response.json()["id"]

        # Delete paragraph
        response = test_client.delete(f"/api/rag-experiments/paragraphs/{paragraph_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = test_client.get(f"/api/rag-experiments/paragraphs/{paragraph_id}")
        assert get_response.status_code == 404

    def test_delete_paragraph_not_found(self, test_client):
        """Test deleting a non-existent paragraph returns 404."""
        fake_id = str(uuid4())
        response = test_client.delete(f"/api/rag-experiments/paragraphs/{fake_id}")

        assert response.status_code == 404


class TestAnnotationCRUD:
    """Integration tests for annotation CRUD operations."""

    def test_create_annotation_success(self, test_client):
        """Test POST /api/rag-experiments/paragraphs/{id}/annotations."""
        # Create paragraph
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Apple is a technology company."}
        )
        paragraph_id = paragraph_response.json()["id"]

        # Get a valid structure node ID
        structure_node_id = test_client.node_ids[0]

        # Create annotation
        response = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 5,
                "structure_node_id": structure_node_id
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["paragraph_id"] == paragraph_id
        assert data["start_char"] == 0
        assert data["end_char"] == 5
        assert data["structure_node_id"] == structure_node_id
        assert data["text"] == "Apple"

    def test_create_annotation_invalid_structure_node(self, test_client):
        """Test creating annotation with non-existent structure_node_id fails."""
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test text."}
        )
        paragraph_id = paragraph_response.json()["id"]

        fake_node_id = str(uuid4())

        response = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 4,
                "structure_node_id": fake_node_id
            }
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_create_annotation_invalid_char_positions(self, test_client):
        """Test creating annotation with invalid character positions fails."""
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Short text."}
        )
        paragraph_id = paragraph_response.json()["id"]
        structure_node_id = test_client.node_ids[0]

        # Test end_char beyond text length
        response = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 1000,
                "structure_node_id": structure_node_id
            }
        )

        assert response.status_code == 400

    def test_create_annotation_end_before_start(self, test_client):
        """Test that end_char must be after start_char."""
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test text."}
        )
        paragraph_id = paragraph_response.json()["id"]
        structure_node_id = test_client.node_ids[0]

        response = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 5,
                "end_char": 2,  # Before start
                "structure_node_id": structure_node_id
            }
        )

        assert response.status_code == 422  # Validation error

    def test_create_annotation_paragraph_not_found(self, test_client):
        """Test creating annotation for non-existent paragraph fails."""
        fake_paragraph_id = str(uuid4())
        structure_node_id = test_client.node_ids[0]

        response = test_client.post(
            f"/api/rag-experiments/paragraphs/{fake_paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 5,
                "structure_node_id": structure_node_id
            }
        )

        assert response.status_code == 404

    def test_list_paragraphs_includes_annotations(self, test_client):
        """Test that listing paragraphs includes their annotations."""
        # Create paragraph
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Apple and iPhone are products."}
        )
        paragraph_id = paragraph_response.json()["id"]

        # Create annotations
        annotation_1 = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 5,
                "structure_node_id": test_client.node_ids[0]
            }
        ).json()

        annotation_2 = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 10,
                "end_char": 16,
                "structure_node_id": test_client.node_ids[2]
            }
        ).json()

        # List paragraphs
        response = test_client.get("/api/rag-experiments/paragraphs")
        data = response.json()

        assert len(data["paragraphs"]) == 1
        paragraph = data["paragraphs"][0]
        assert len(paragraph["annotations"]) == 2

    def test_delete_annotation_success(self, test_client):
        """Test DELETE /api/rag-experiments/annotations/{id}."""
        # Create paragraph with annotation
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test text for deletion."}
        )
        paragraph_id = paragraph_response.json()["id"]

        annotation_response = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 4,
                "structure_node_id": test_client.node_ids[0]
            }
        )
        annotation_id = annotation_response.json()["id"]

        # Delete annotation
        response = test_client.delete(f"/api/rag-experiments/annotations/{annotation_id}")
        assert response.status_code == 204

        # Verify annotation deleted
        paragraph = test_client.get(f"/api/rag-experiments/paragraphs/{paragraph_id}").json()
        assert len(paragraph["annotations"]) == 0

    def test_delete_annotation_not_found(self, test_client):
        """Test deleting non-existent annotation returns 404."""
        fake_id = str(uuid4())
        response = test_client.delete(f"/api/rag-experiments/annotations/{fake_id}")
        assert response.status_code == 404


class TestPipelineExecution:
    """Integration tests for pipeline execution and scoring."""

    @patch('rag.test_service.RAGTestManagementService.run_pipeline_test')
    async def test_run_pipeline_test_success(self, mock_run, test_client):
        """Test POST /api/rag-experiments/run executes pipelines."""
        # Create paragraph with annotation
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Apple is a technology company."}
        )
        paragraph_id = paragraph_response.json()["id"]

        test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 5,
                "structure_node_id": test_client.node_ids[0]
            }
        )

        # Mock pipeline results
        mock_run.return_value = [
            {
                "run_id": str(uuid4()),
                "pipeline_name": "StandardRAGPipeline",
                "paragraph_id": paragraph_id,
                "execution_time_ms": 1500,
                "entities_extracted": 2,
                "scoring": {
                    "precision": 0.85,
                    "recall": 0.90,
                    "f1_score": 0.87,
                    "true_positives": 1,
                    "false_positives": 0,
                    "false_negatives": 0
                },
                "executed_at": "2025-01-15T10:00:00Z"
            }
        ]

        # Execute pipeline test
        response = test_client.post(
            "/api/rag-experiments/run",
            json={
                "paragraph_ids": [paragraph_id],
                "pipeline_names": ["StandardRAGPipeline"],
                "enable_trace": False,
                "enable_llm_layer": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 1
        assert data["successful_runs"] == 1
        assert data["failed_runs"] == 0
        assert len(data["results"]) == 1

        result = data["results"][0]
        assert result["pipeline_name"] == "StandardRAGPipeline"
        assert result["entities_extracted"] == 2
        assert result["scoring"]["f1_score"] == 0.87

    @patch('rag.test_service.RAGTestManagementService.run_pipeline_test')
    async def test_run_pipeline_test_multiple_pipelines(self, mock_run, test_client):
        """Test running multiple pipelines in parallel."""
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test text for multiple pipelines."}
        )
        paragraph_id = paragraph_response.json()["id"]

        # Mock results for 3 pipelines
        mock_run.return_value = [
            {
                "run_id": str(uuid4()),
                "pipeline_name": f"Pipeline{i}",
                "paragraph_id": paragraph_id,
                "execution_time_ms": 1000 + i * 100,
                "entities_extracted": i + 1,
                "scoring": {
                    "precision": 0.8 + i * 0.05,
                    "recall": 0.85 + i * 0.03,
                    "f1_score": 0.82 + i * 0.04,
                    "true_positives": i,
                    "false_positives": 0,
                    "false_negatives": 0
                },
                "executed_at": "2025-01-15T10:00:00Z"
            }
            for i in range(3)
        ]

        response = test_client.post(
            "/api/rag-experiments/run",
            json={
                "paragraph_ids": [paragraph_id],
                "pipeline_names": ["Pipeline0", "Pipeline1", "Pipeline2"],
                "enable_trace": False,
                "enable_llm_layer": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 3
        assert data["successful_runs"] == 3
        assert len(data["results"]) == 3

    @patch('rag.test_service.RAGTestManagementService.run_pipeline_test')
    async def test_run_pipeline_test_with_errors(self, mock_run, test_client):
        """Test handling pipeline errors during execution."""
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test text."}
        )
        paragraph_id = paragraph_response.json()["id"]

        # Mock one success, one error
        mock_run.return_value = [
            {
                "run_id": str(uuid4()),
                "pipeline_name": "GoodPipeline",
                "paragraph_id": paragraph_id,
                "execution_time_ms": 1000,
                "entities_extracted": 2,
                "scoring": {
                    "precision": 0.9,
                    "recall": 0.85,
                    "f1_score": 0.87,
                    "true_positives": 1,
                    "false_positives": 0,
                    "false_negatives": 0
                },
                "executed_at": "2025-01-15T10:00:00Z"
            },
            {
                "run_id": str(uuid4()),
                "pipeline_name": "FailingPipeline",
                "paragraph_id": paragraph_id,
                "error": "Pipeline execution timeout",
                "error_type": "TimeoutError",
                "executed_at": "2025-01-15T10:00:00Z"
            }
        ]

        response = test_client.post(
            "/api/rag-experiments/run",
            json={
                "paragraph_ids": [paragraph_id],
                "pipeline_names": ["GoodPipeline", "FailingPipeline"],
                "enable_trace": False,
                "enable_llm_layer": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 2
        assert data["successful_runs"] == 1
        assert data["failed_runs"] == 1

        # Find the failed result
        failed_result = next(r for r in data["results"] if r["pipeline_name"] == "FailingPipeline")
        assert failed_result["error"] == "Pipeline execution timeout"

    def test_run_pipeline_test_invalid_paragraph(self, test_client):
        """Test running pipeline with non-existent paragraph skips it."""
        fake_paragraph_id = str(uuid4())

        response = test_client.post(
            "/api/rag-experiments/run",
            json={
                "paragraph_ids": [fake_paragraph_id],
                "pipeline_names": ["StandardRAGPipeline"],
                "enable_trace": False,
                "enable_llm_layer": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        # Should complete but with no results
        assert data["total_runs"] == 0

    def test_run_pipeline_test_validation_errors(self, test_client):
        """Test validation errors for run endpoint."""
        # Empty paragraph_ids
        response = test_client.post(
            "/api/rag-experiments/run",
            json={
                "paragraph_ids": [],
                "pipeline_names": ["Pipeline1"],
                "enable_trace": False,
                "enable_llm_layer": True
            }
        )
        assert response.status_code == 422

        # Empty pipeline_names
        response = test_client.post(
            "/api/rag-experiments/run",
            json={
                "paragraph_ids": [str(uuid4())],
                "pipeline_names": [],
                "enable_trace": False,
                "enable_llm_layer": True
            }
        )
        assert response.status_code == 422


class TestResultsQuery:
    """Integration tests for querying and comparing pipeline results."""

    def test_get_pipeline_comparison_empty(self, test_client):
        """Test GET /api/rag-experiments/results/paragraphs/{id} with no runs."""
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Test paragraph."}
        )
        paragraph_id = paragraph_response.json()["id"]

        response = test_client.get(
            f"/api/rag-experiments/results/paragraphs/{paragraph_id}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["paragraph_id"] == paragraph_id
        assert data["runs"] == []
        assert data["summary"]["total_pipelines"] == 0
        assert data["summary"]["best_pipeline"] is None

    def test_get_pipeline_comparison_not_found(self, test_client):
        """Test comparison for non-existent paragraph returns 404."""
        fake_id = str(uuid4())
        response = test_client.get(
            f"/api/rag-experiments/results/paragraphs/{fake_id}"
        )

        assert response.status_code == 404

    def test_get_pipeline_run_details_not_found(self, test_client):
        """Test GET /api/rag-experiments/results/runs/{id} for non-existent run."""
        fake_run_id = str(uuid4())
        response = test_client.get(
            f"/api/rag-experiments/results/runs/{fake_run_id}"
        )

        assert response.status_code == 404


class TestCascadeDelete:
    """Test that deleting paragraphs cascades to annotations and runs."""

    def test_delete_paragraph_cascades_to_annotations(self, test_client):
        """Test that deleting a paragraph deletes its annotations."""
        # Create paragraph with annotations
        paragraph_response = test_client.post(
            "/api/rag-experiments/paragraphs",
            json={"text": "Apple iPhone test."}
        )
        paragraph_id = paragraph_response.json()["id"]

        annotation_response = test_client.post(
            f"/api/rag-experiments/paragraphs/{paragraph_id}/annotations",
            json={
                "start_char": 0,
                "end_char": 5,
                "structure_node_id": test_client.node_ids[0]
            }
        )
        annotation_id = annotation_response.json()["id"]

        # Delete paragraph
        delete_response = test_client.delete(
            f"/api/rag-experiments/paragraphs/{paragraph_id}"
        )
        assert delete_response.status_code == 204

        # Verify annotation is also deleted
        ann_delete_response = test_client.delete(
            f"/api/rag-experiments/annotations/{annotation_id}"
        )
        assert ann_delete_response.status_code == 404  # Already deleted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
