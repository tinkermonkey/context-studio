"""Tests for grounding orchestrator."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.schema_node_grounding.orchestrator import (
    SchemaGroundingOrchestrator,
    SchemaGroundingState,
)
from domain.pipelines.schema_node_grounding.scoring import (
    GroundingCandidate,
    ScoredCandidate,
)

_test_file = os.path.abspath(__file__)
_test_dir = os.path.dirname(_test_file)
_root_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(_test_dir)))
)
sys.path.insert(0, _root_dir)


class TestSchemaGroundingOrchestrator:
    """Tests for SchemaGroundingOrchestrator."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock grounding adapter."""
        mock = AsyncMock()
        mock.query_sources = AsyncMock(
            return_value=[
                GroundingCandidate(
                    uri="http://dbpedia.org/resource/Person",
                    label="Person",
                    description="A human being",
                    source="DBpedia",
                    source_score=0.8,
                ),
                GroundingCandidate(
                    uri="http://conceptnet.io/c/en/person",
                    label="person",
                    description="a human being",
                    source="ConceptNet",
                    source_score=0.7,
                ),
            ]
        )
        return mock

    @pytest.fixture
    def mock_scorer(self):
        """Create mock scorer."""

        async def score_fn(candidates, node_label, node_type=None):
            return [
                ScoredCandidate(
                    uri=c.uri,
                    label=c.label,
                    description=c.description,
                    source=c.source,
                    source_score=c.source_score,
                    label_match_score=0.9,
                    semantic_similarity_score=0.85,
                    match_confidence=0.88,
                    match_rationale="strong label match; high semantic similarity",
                )
                for c in candidates
            ]

        mock = MagicMock()
        mock.score_candidates = AsyncMock(side_effect=score_fn)
        return mock

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_adapter, mock_scorer, mock_llm_provider):
        """Test successful execution."""
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=mock_llm_provider,
            grounding_adapter=mock_adapter,
            scorer=mock_scorer,
            config={"top_n": 10},
        )

        state = SchemaGroundingState(
            run_id="run-123",
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data={
                "node_label": "Person",
                "node_type": "Class",
                "sources": ["DBpedia", "ConceptNet"],
            },
        )

        result = await orchestrator.execute(state)

        assert result.current_status == "completed"
        assert len(result.groundings) == 2
        assert result.result is not None
        assert len(result.result["groundings"]) == 2

    @pytest.mark.asyncio
    async def test_execute_no_candidates(
        self, mock_adapter, mock_scorer, mock_llm_provider
    ):
        """Test execution with no candidates found."""
        mock_adapter.query_sources = AsyncMock(return_value=[])
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=mock_llm_provider,
            grounding_adapter=mock_adapter,
            scorer=mock_scorer,
            config={"top_n": 10},
        )

        state = SchemaGroundingState(
            run_id="run-123",
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data={"node_label": "UnknownThing", "node_type": "Class"},
        )

        result = await orchestrator.execute(state)

        assert result.current_status == "completed"
        assert result.groundings == []
        assert len(result.result["groundings"]) == 0

    @pytest.mark.asyncio
    async def test_execute_missing_label(
        self, mock_adapter, mock_scorer, mock_llm_provider
    ):
        """Test execution with missing node_label."""
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=mock_llm_provider,
            grounding_adapter=mock_adapter,
            scorer=mock_scorer,
        )

        state = SchemaGroundingState(
            run_id="run-123",
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data={"node_type": "Class"},
        )

        with pytest.raises(PipelineInputError, match="node_label is required"):
            await orchestrator.execute(state)

    @pytest.mark.asyncio
    async def test_execute_invalid_node_type(
        self, mock_adapter, mock_scorer, mock_llm_provider
    ):
        """Test execution with invalid node_type raises PipelineInputError."""
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=mock_llm_provider,
            grounding_adapter=mock_adapter,
            scorer=mock_scorer,
        )

        state = SchemaGroundingState(
            run_id="run-123",
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data={
                "node_label": "Person",
                "node_type": "InvalidType",
            },
        )

        with pytest.raises(PipelineInputError, match="Invalid node_type"):
            await orchestrator.execute(state)

    @pytest.mark.asyncio
    async def test_execute_truncates_to_top_n(
        self, mock_adapter, mock_scorer, mock_llm_provider
    ):
        """Test that results are truncated to top_n."""
        candidates = [
            GroundingCandidate(
                uri=f"http://example.com/{i}",
                label=f"Result {i}",
                description="Description",
                source="DBpedia",
                source_score=0.8,
            )
            for i in range(15)
        ]
        mock_adapter.query_sources = AsyncMock(return_value=candidates)

        async def score_fn(cands, node_label, node_type=None):
            return [
                ScoredCandidate(
                    uri=c.uri,
                    label=c.label,
                    description=c.description,
                    source=c.source,
                    source_score=c.source_score,
                    label_match_score=0.5,
                    semantic_similarity_score=0.5,
                    match_confidence=0.5,
                    match_rationale="test",
                )
                for c in cands
            ]

        mock_scorer.score_candidates = AsyncMock(side_effect=score_fn)

        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=mock_llm_provider,
            grounding_adapter=mock_adapter,
            scorer=mock_scorer,
            config={"top_n": 5},
        )

        state = SchemaGroundingState(
            run_id="run-123",
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data={"node_label": "Person", "node_type": "Class"},
        )

        result = await orchestrator.execute(state)

        assert len(result.groundings) == 5

    @pytest.mark.asyncio
    async def test_build_graph_returns_none(
        self, mock_adapter, mock_scorer, mock_llm_provider
    ):
        """Test that build_graph returns None (single-node implementation)."""
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=mock_llm_provider,
            grounding_adapter=mock_adapter,
            scorer=mock_scorer,
        )

        graph = orchestrator.build_graph()

        assert graph is None
