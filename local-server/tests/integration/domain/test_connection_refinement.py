"""
Integration tests for Schema Node Connection Refinement pipeline.

Tests the ConnectionRefinementOrchestrator with mock LLM provider.
"""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.services import OntologyService
from domain.pipeline.ports import LLMResponse
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.base import PipelineState
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
)
from domain.ports import EventPublisher


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response: str = ""):
        self.response = response
        self.calls = []

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return LLMResponse(
            content=self.response,
            tokens_in=50,
            tokens_out=50,
            duration_ms=100.0,
            finish_reason="stop",
            model=model,
        )


class DummyEventPublisher(EventPublisher):
    """Dummy event publisher for testing."""

    def publish(self, event):
        pass


class DummyEmbeddingService:
    """Dummy embedding service for testing."""

    def embed(self, text: str) -> list[float]:
        return [0.0] * 384


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def ontology_service(session_factory):
    """Create an ontology service."""
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    embedding_svc = DummyEmbeddingService()
    event_pub = DummyEventPublisher()
    return OntologyService(
        repository=repo,
        embedding_service=embedding_svc,
        event_publisher=event_pub,
    )


@pytest.fixture
def sample_classes(ontology_service):
    """Create sample classes for testing."""
    taxonomy = ontology_service.create_taxonomy("Test", "")
    scheme = ontology_service.create_scheme(taxonomy_id=taxonomy.id, title="Test")

    class1 = ontology_service.create_class(
        concept_scheme_id=scheme.id,
        title="Person",
        description="A person",
    )

    class2 = ontology_service.create_class(
        concept_scheme_id=scheme.id,
        title="Organization",
        description="An organization",
    )

    return {"class1": class1, "class2": class2}


class TestConnectionRefinementOrchestrator:
    """Tests for connection refinement orchestration."""

    def test_execute_with_valid_input(self, sample_classes, session_factory):
        """Should execute and produce deltas."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        deltas_json = json.dumps(
            [
                {
                    "operation": "add",
                    "subject": sample_classes["class1"].id,
                    "predicate": "works_for",
                    "object": sample_classes["class2"].id,
                    "rationale": "Based on sibling patterns",
                    "sources_cited": ["siblings"],
                    "confidence": 0.8,
                },
                {
                    "operation": "add",
                    "subject": sample_classes["class2"].id,
                    "predicate": "employs",
                    "object": sample_classes["class1"].id,
                    "rationale": "Inverse relationship",
                    "sources_cited": ["relationship_pattern"],
                    "confidence": 0.7,
                },
            ]
        )

        llm = MockLLMProvider(response=deltas_json)
        config = {"model": "test-model", "temperature": 0.0}
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config=config,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": sample_classes["class1"].id,
                "current_connections": [],
            },
            llm_provider=llm,
        )

        import asyncio

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        assert len(result_state.deltas) >= 1
        assert result_state.result is not None
        assert "deltas" in result_state.result

    def test_missing_scope_id_raises_error(self, session_factory):
        """Should raise ValueError if scope_id is missing."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        llm = MockLLMProvider()
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={"current_connections": []},
            llm_provider=llm,
        )

        import asyncio

        with pytest.raises(ValueError, match="scope_id is required"):
            asyncio.run(orchestrator.execute(state))

    def test_nonexistent_class_fails(self, session_factory):
        """Should fail when class doesn't exist."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        llm = MockLLMProvider()
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": "nonexistent",
                "current_connections": [],
            },
            llm_provider=llm,
        )

        import asyncio

        with pytest.raises(ValueError, match="Class not found"):
            asyncio.run(orchestrator.execute(state))

    def test_handles_empty_deltas(self, sample_classes, session_factory):
        """Should handle LLM returning empty delta list."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        llm = MockLLMProvider(response="[]")
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": sample_classes["class1"].id,
                "current_connections": [],
            },
            llm_provider=llm,
        )

        import asyncio

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        # Should have at least a default empty delta
        assert isinstance(result_state.deltas, list)

    def test_limits_deltas_to_max(self, sample_classes, session_factory):
        """Should limit deltas to max (5)."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        # Create 10 deltas
        deltas = [
            {
                "operation": "add",
                "subject": sample_classes["class1"].id,
                "predicate": f"prop{i}",
                "object": sample_classes["class2"].id,
                "rationale": f"Delta {i}",
                "sources_cited": ["test"],
                "confidence": 0.5,
            }
            for i in range(10)
        ]

        llm = MockLLMProvider(response=json.dumps(deltas))
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": sample_classes["class1"].id,
                "current_connections": [],
            },
            llm_provider=llm,
        )

        import asyncio

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        assert len(result_state.deltas) <= 5
