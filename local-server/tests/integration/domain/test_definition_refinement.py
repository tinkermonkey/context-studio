"""
Integration tests for Schema Node Definition Refinement pipeline.

Tests the DefinitionRefinementOrchestrator with mock LLM provider.
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
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
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
def sample_class(ontology_service):
    """Create a sample class for testing."""
    taxonomy = ontology_service.create_taxonomy("Test", "")
    scheme = ontology_service.create_scheme(taxonomy_id=taxonomy.id, title="Test")
    return ontology_service.create_class(
        concept_scheme_id=scheme.id,
        title="Person",
        description="A human being",
    )


class TestDefinitionRefinementOrchestrator:
    """Tests for definition refinement orchestration."""

    def test_execute_with_valid_input(self, sample_class, session_factory):
        """Should execute and produce candidates."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        candidates_json = json.dumps(
            [
                {
                    "definition": "A human individual",
                    "rationale": "Aligns with parent and siblings",
                    "sources_used": ["parent", "siblings"],
                    "confidence": 0.8,
                },
                {
                    "definition": "An adult human",
                    "rationale": "Emphasizes maturity",
                    "sources_used": ["llm"],
                    "confidence": 0.6,
                },
            ]
        )

        llm = MockLLMProvider(response=candidates_json)
        config = {"model": "test-model", "temperature": 0.0}
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config=config,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": sample_class.id,
                "current_definition": "A human being",
            },
            llm_provider=llm,
        )

        result_state = orchestrator.execute(state)

        # Use pytest.mark.asyncio if needed, but we can test sync behavior here
        import asyncio

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        assert len(result_state.candidates) >= 2
        assert result_state.result is not None
        assert "candidates" in result_state.result

    def test_missing_node_id_raises_error(self, session_factory):
        """Should raise ValueError if node_id is missing."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        llm = MockLLMProvider()
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={"current_definition": "Test"},
            llm_provider=llm,
        )

        import asyncio

        with pytest.raises(ValueError, match="node_id is required"):
            asyncio.run(orchestrator.execute(state))

    def test_nonexistent_class_fails(self, session_factory):
        """Should fail when class doesn't exist."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        llm = MockLLMProvider()
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": "nonexistent",
                "current_definition": "Test",
            },
            llm_provider=llm,
        )

        import asyncio

        with pytest.raises(ValueError, match="Class not found"):
            asyncio.run(orchestrator.execute(state))

    def test_handles_llm_json_with_code_fence(self, sample_class, session_factory):
        """Should parse JSON response with code fence markers."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        candidates_json = f"""```json
[
  {{
    "definition": "A human",
    "rationale": "Concise",
    "sources_used": ["llm"],
    "confidence": 0.7
  }}
]
```"""

        llm = MockLLMProvider(response=candidates_json)
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": sample_class.id,
                "current_definition": "A human being",
            },
            llm_provider=llm,
        )

        import asyncio

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        assert len(result_state.candidates) >= 1
