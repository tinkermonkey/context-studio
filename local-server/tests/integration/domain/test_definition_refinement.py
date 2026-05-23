"""
Integration tests for Schema Node Definition Refinement pipeline.

Tests the DefinitionRefinementOrchestrator with mock LLM provider.
"""

import asyncio
import json
from uuid import uuid4

import pytest

from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.base import PipelineState
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
)

from .mocks import MockLLMProvider


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

        with pytest.raises(ValueError, match="Class not found"):
            asyncio.run(orchestrator.execute(state))

    def test_handles_llm_json_with_code_fence(self, sample_class, session_factory):
        """Should parse JSON response with code fence markers."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        candidates_json = """```json
[
  {
    "definition": "A human",
    "rationale": "Concise",
    "sources_used": ["llm"],
    "confidence": 0.7
  }
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

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        assert len(result_state.candidates) >= 1

    def test_handles_malformed_llm_response(self, sample_class, session_factory):
        """Should fallback gracefully when LLM response is not valid JSON."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        llm = MockLLMProvider(response="This is not JSON at all")
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

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        # Should have at least a fallback candidate with the raw response
        assert len(result_state.candidates) >= 1
        assert result_state.candidates[0]["confidence"] <= 0.5
