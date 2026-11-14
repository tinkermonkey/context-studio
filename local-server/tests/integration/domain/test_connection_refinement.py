"""
Integration tests for Schema Node Connection Refinement pipeline.

Tests the ConnectionRefinementOrchestrator with mock LLM provider.
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
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
)

from .mocks import MockLLMProvider


@pytest.fixture
def sample_classes(ontology_service):
    """Create sample classes for testing."""
    taxonomy = ontology_service.create_taxonomy(title="Test Taxonomy", description="")
    scheme = ontology_service.create_scheme(taxonomy_id=taxonomy.id, title="Test Scheme")

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
            config={"model": "test-model"},
        )

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={"current_connections": []},
            llm_provider=llm,
        )

        with pytest.raises(PipelineInputError, match="scope_id is required"):
            asyncio.run(orchestrator.execute(state))

    def test_nonexistent_class_fails(self, session_factory):
        """Should fail when class doesn't exist."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        llm = MockLLMProvider()
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config={"model": "test-model"},
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

        with pytest.raises(PipelineInputError, match="Scope with id"):
            asyncio.run(orchestrator.execute(state))

    def test_handles_empty_deltas(self, sample_classes, session_factory):
        """Should handle LLM returning empty delta list."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        llm = MockLLMProvider(response="[]")
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config={"model": "test-model"},
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

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        # Should have no deltas (no fabrication)
        assert result_state.deltas == []
        assert result_state.result["total_deltas"] == 0

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
            config={"model": "test-model"},
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

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        assert len(result_state.deltas) <= 5

    def test_handles_llm_json_with_code_fence(self, sample_classes, session_factory):
        """Should parse JSON response with code fence markers."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        deltas_json = f"""```json
[
  {{
    "operation": "add",
    "subject": "{sample_classes['class1'].id}",
    "predicate": "related_to",
    "object": "{sample_classes['class2'].id}",
    "rationale": "Test delta",
    "sources_cited": ["test"],
    "confidence": 0.7
  }}
]
```"""

        llm = MockLLMProvider(response=deltas_json)
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config={"model": "test-model"},
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

        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == "completed"
        assert len(result_state.deltas) >= 1

    def test_handles_malformed_llm_response(self, sample_classes, session_factory):
        """Should raise error when LLM response is not valid JSON."""
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)

        llm = MockLLMProvider(response="This is not JSON at all")
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=traversal,
            config={"model": "test-model"},
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
    def _run(session_factory, scope_id, config, **named):
        repo = SQLiteOntologyRepository(session_factory=session_factory)
        llm = _RecordingLLM()
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm,
            traversal=SchemaNeighborhoodTraversal(ontology_repo=repo),
            config=config,
        )
        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={"scope_id": scope_id, "current_connections": [], **named},
            llm_provider=llm,
        )
        asyncio.run(orchestrator.execute(state))
        return llm.calls

    def test_what_the_runs_input_names_wins(self, sample_classes, session_factory):
        calls = self._run(
            session_factory,
            sample_classes["class1"].id,
            {"model": "configured", "max_tokens": 2500},
            model="named",
            temperature=0.3,
            max_tokens=700,
        )

        assert calls == [("named", 0.3, 700)]

    def test_what_the_input_leaves_out_is_the_configurations(
        self, sample_classes, session_factory
    ):
        calls = self._run(
            session_factory,
            sample_classes["class1"].id,
            {"model": "configured", "temperature": 0.1, "max_tokens": 2500},
        )

        assert calls == [("configured", 0.1, 2500)]
