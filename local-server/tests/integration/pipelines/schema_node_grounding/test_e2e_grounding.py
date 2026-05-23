"""End-to-end tests for schema node grounding pipeline."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.pipelines.entities import PipelineType
from domain.pipelines.schema_node_grounding.orchestrator import SchemaGroundingOrchestrator
from domain.pipelines.schema_node_grounding.scoring import (
    GroundingCandidate,
    GroundingScorer,
)


class TestE2ESchemaNodeGrounding:
    """End-to-end tests for schema node grounding."""

    @pytest.fixture
    def grounding_fixtures(self):
        """Fixture data for grounding tests."""
        return {
            "class_person": {
                "node_label": "Person",
                "node_type": "Class",
                "dbpedia_candidates": [
                    {
                        "uri": "http://dbpedia.org/resource/Person",
                        "label": "Person",
                        "description": "A human being or individual",
                        "source": "DBpedia",
                        "source_score": 0.95,
                    },
                    {
                        "uri": "http://dbpedia.org/resource/Individual",
                        "label": "Individual",
                        "description": "A single thing or organism",
                        "source": "DBpedia",
                        "source_score": 0.7,
                    },
                ],
                "conceptnet_candidates": [
                    {
                        "uri": "http://conceptnet.io/c/en/person",
                        "label": "person",
                        "description": "a human being",
                        "source": "ConceptNet",
                        "source_score": 0.85,
                    },
                ],
            },
            "property_knows": {
                "node_label": "knows",
                "node_type": "PropertyDefinition",
                "dbpedia_candidates": [
                    {
                        "uri": "http://dbpedia.org/property/knows",
                        "label": "knows",
                        "description": "relationship of acquaintance",
                        "source": "DBpedia",
                        "source_score": 0.8,
                    },
                ],
                "conceptnet_candidates": [
                    {
                        "uri": "http://conceptnet.io/c/en/know",
                        "label": "know",
                        "description": "to have knowledge of",
                        "source": "ConceptNet",
                        "source_score": 0.75,
                    },
                ],
            },
        }

    @pytest.mark.asyncio
    async def test_grounding_class_node_full_workflow(self, grounding_fixtures):
        """Test full grounding workflow for a Class node."""
        fixture = grounding_fixtures["class_person"]

        # Create mock adapter
        mock_adapter = AsyncMock()
        candidates = [
            GroundingCandidate(**c) for c in fixture["dbpedia_candidates"] + fixture["conceptnet_candidates"]
        ]
        mock_adapter.query_sources = AsyncMock(return_value=candidates)

        # Create real scorer
        scorer = GroundingScorer()

        # Create real orchestrator
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=mock_adapter,
            scorer=scorer,
            config={"top_n": 10},
        )

        # Execute
        state = AsyncMock()
        state.run_id = "test-123"
        state.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
        state.input_data = {
            "node_label": fixture["node_label"],
            "node_type": fixture["node_type"],
            "sources": ["DBpedia", "ConceptNet"],
        }
        state.current_status = "pending"
        state.llm_provider = None
        state.result = None

        result = await orchestrator.execute(state)

        # Verify results
        assert result.current_status == "completed"
        assert len(result.groundings) == 3
        assert result.result is not None
        assert "groundings" in result.result

        # Verify top candidate is "Person" (exact match, highest confidence)
        top = result.groundings[0]
        assert top.label == "Person"
        assert top.match_confidence >= result.groundings[-1].match_confidence

    @pytest.mark.asyncio
    async def test_grounding_property_node_full_workflow(self, grounding_fixtures):
        """Test full grounding workflow for a PropertyDefinition node."""
        fixture = grounding_fixtures["property_knows"]

        mock_adapter = AsyncMock()
        candidates = [
            GroundingCandidate(**c) for c in fixture["dbpedia_candidates"] + fixture["conceptnet_candidates"]
        ]
        mock_adapter.query_sources = AsyncMock(return_value=candidates)

        scorer = GroundingScorer()
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=mock_adapter,
            scorer=scorer,
            config={"top_n": 5},
        )

        state = AsyncMock()
        state.run_id = "test-456"
        state.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
        state.input_data = {
            "node_label": fixture["node_label"],
            "node_type": fixture["node_type"],
            "sources": ["DBpedia", "ConceptNet"],
        }
        state.current_status = "pending"
        state.llm_provider = None
        state.result = None

        result = await orchestrator.execute(state)

        assert result.current_status == "completed"
        assert len(result.groundings) <= 5
        assert result.groundings[0].label in ["knows", "know"]

    @pytest.mark.asyncio
    async def test_grounding_confidence_scores_valid_range(self, grounding_fixtures):
        """Test that all confidence scores are in valid [0, 1] range."""
        fixture = grounding_fixtures["class_person"]

        mock_adapter = AsyncMock()
        candidates = [
            GroundingCandidate(**c) for c in fixture["dbpedia_candidates"] + fixture["conceptnet_candidates"]
        ]
        mock_adapter.query_sources = AsyncMock(return_value=candidates)

        scorer = GroundingScorer()
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=mock_adapter,
            scorer=scorer,
            config={"top_n": 10},
        )

        state = AsyncMock()
        state.run_id = "test-scores"
        state.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
        state.input_data = {
            "node_label": fixture["node_label"],
            "node_type": fixture["node_type"],
        }
        state.current_status = "pending"
        state.llm_provider = None
        state.result = None

        result = await orchestrator.execute(state)

        for grounding in result.groundings:
            assert 0.0 <= grounding.match_confidence <= 1.0
            assert grounding.match_rationale

    @pytest.mark.asyncio
    async def test_grounding_output_format(self, grounding_fixtures):
        """Test output format matches specification."""
        fixture = grounding_fixtures["class_person"]

        mock_adapter = AsyncMock()
        candidates = [
            GroundingCandidate(**c) for c in fixture["dbpedia_candidates"][:1]
        ]
        mock_adapter.query_sources = AsyncMock(return_value=candidates)

        scorer = GroundingScorer()
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=mock_adapter,
            scorer=scorer,
        )

        state = AsyncMock()
        state.run_id = "test-format"
        state.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
        state.input_data = {
            "node_label": fixture["node_label"],
            "node_type": fixture["node_type"],
        }
        state.current_status = "pending"
        state.llm_provider = None
        state.result = None

        result = await orchestrator.execute(state)

        groundings = result.result["groundings"]
        assert len(groundings) > 0

        grounding = groundings[0]
        assert "uri" in grounding
        assert "label" in grounding
        assert "description" in grounding
        assert "source" in grounding
        assert "match_confidence" in grounding
        assert "match_rationale" in grounding

    @pytest.mark.asyncio
    async def test_zero_candidates_edge_case(self):
        """Test edge case with zero matching candidates."""
        mock_adapter = AsyncMock()
        mock_adapter.query_sources = AsyncMock(return_value=[])

        scorer = GroundingScorer()
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=mock_adapter,
            scorer=scorer,
        )

        state = AsyncMock()
        state.run_id = "test-zero"
        state.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
        state.input_data = {
            "node_label": "UnknownConcept",
            "node_type": "Class",
        }
        state.current_status = "pending"
        state.llm_provider = None
        state.result = None

        result = await orchestrator.execute(state)

        assert result.current_status == "completed"
        assert result.groundings == []
        assert result.result["total_candidates_evaluated"] == 0

    @pytest.mark.asyncio
    async def test_multi_source_ranking(self, grounding_fixtures):
        """Test that candidates from different sources are properly ranked together."""
        fixture = grounding_fixtures["class_person"]

        mock_adapter = AsyncMock()
        candidates = [
            GroundingCandidate(**c) for c in fixture["dbpedia_candidates"] + fixture["conceptnet_candidates"]
        ]
        mock_adapter.query_sources = AsyncMock(return_value=candidates)

        scorer = GroundingScorer()
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=mock_adapter,
            scorer=scorer,
        )

        state = AsyncMock()
        state.run_id = "test-multi"
        state.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
        state.input_data = {
            "node_label": fixture["node_label"],
            "node_type": fixture["node_type"],
        }
        state.current_status = "pending"
        state.llm_provider = None
        state.result = None

        result = await orchestrator.execute(state)

        sources_in_result = {g.source for g in result.groundings}
        assert len(sources_in_result) > 0
        confidence_scores = [g.match_confidence for g in result.groundings]
        assert confidence_scores == sorted(confidence_scores, reverse=True)
