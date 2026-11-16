"""
Integration tests for Schema Node Definition Refinement pipeline.

Tests the DefinitionRefinementOrchestrator with mock LLM provider.
"""

import asyncio
import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import PipelineState
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
)

from .mocks import MockLLMProvider


@pytest.fixture
def sample_class(ontology_service):
    """Create a sample class for testing."""
    taxonomy = ontology_service.create_taxonomy(title="Test Taxonomy", description="")
    scheme = ontology_service.create_scheme(taxonomy_id=taxonomy.id, title="Test Scheme")
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
            config={"model": "test-model"},
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={"current_definition": "Test"},
            llm_provider=llm,
        )

        with pytest.raises(PipelineInputError, match="node_id is required"):
            asyncio.run(orchestrator.execute(state))

    def test_nonexistent_class_fails(self, session_factory):
        """Should fail when class doesn't exist."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        llm = MockLLMProvider()
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config={"model": "test-model"},
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

        with pytest.raises(PipelineInputError, match="No class or property definition"):
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
            config={"model": "test-model"},
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
        assert len(result_state.candidates) == 1
        assert result_state.candidates[0]["definition"] == "A human"

    def test_handles_malformed_llm_response(self, sample_class, session_factory):
        """Should raise error when LLM response is not valid JSON."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        llm = MockLLMProvider(response="This is not JSON at all")
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config={"model": "test-model"},
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

        with pytest.raises(PipelineExecutionError, match="LLM response validation failed"):
            asyncio.run(orchestrator.execute(state))


class _RecordingLLM:
    """Answers '[]' and records the model, temperature and output limit of each call."""

    def __init__(self):
        self.calls = []

    async def complete_async(self, system_prompt, user_prompt, model, **kwargs):
        self.calls.append((model, kwargs["temperature"], kwargs["max_tokens"]))
        return Mock(content="[]", tokens_in=1, tokens_out=1, duration_ms=1.0)


class TestRunParameters:
    """The refinement's model, temperature and output limit are the run's."""

    @staticmethod
    def _run(session_factory, node_id, config, **named):
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        llm = _RecordingLLM()
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm,
            traversal=SchemaNeighborhoodTraversal(ontology_repo=repo),
            config=config,
        )
        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={"node_id": node_id, "current_definition": "A person", **named},
            llm_provider=llm,
        )
        asyncio.run(orchestrator.execute(state))
        return llm.calls

    def test_what_the_runs_input_names_wins(self, sample_class, session_factory):
        calls = self._run(
            session_factory,
            sample_class.id,
            {"model": "configured", "max_tokens": 2500},
            model="named",
            temperature=0.3,
            max_tokens=700,
        )

        assert calls == [("named", 0.3, 700)]

    def test_what_the_input_leaves_out_is_the_configurations(self, sample_class, session_factory):
        calls = self._run(
            session_factory,
            sample_class.id,
            {"model": "configured", "temperature": 0.1, "max_tokens": 2500},
        )

        assert calls == [("configured", 0.1, 2500)]
