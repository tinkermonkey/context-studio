"""Tests for grounding scoring logic."""

import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

from domain.pipelines.schema_node_grounding.scoring import (
    GroundingCandidate,
    GroundingScorer,
    NodeType,
    build_match_rationale,
    compute_label_match_score,
)

_test_file = os.path.abspath(__file__)
_test_dir = os.path.dirname(_test_file)
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_test_dir))))
sys.path.insert(0, _root_dir)


class TestLabelMatchScore:
    """Tests for label matching."""

    def test_exact_match(self):
        """Test exact label match."""
        score = compute_label_match_score("Person", "person")
        assert score == 1.0

    def test_exact_match_case_insensitive(self):
        """Test exact match is case-insensitive."""
        score = compute_label_match_score("PERSON", "person")
        assert score == 1.0

    def test_substring_match(self):
        """Test substring match."""
        score = compute_label_match_score("Person", "persons")
        assert score == 0.8

    def test_word_overlap(self):
        """Test partial word overlap."""
        score = compute_label_match_score("Human Person", "Person Class")
        assert 0.5 < score < 0.8

    def test_no_match(self):
        """Test no match."""
        score = compute_label_match_score("Person", "Building")
        assert score == 0.0

    def test_empty_strings(self):
        """Test with empty strings."""
        assert compute_label_match_score("", "Person") == 0.0
        assert compute_label_match_score("Person", "") == 0.0
        assert compute_label_match_score("", "") == 0.0


class TestMatchRationale:
    """Tests for match rationale generation."""

    def test_strong_match(self):
        """Test strong match rationale."""
        rationale = build_match_rationale(
            label_match=0.9, semantic_sim=0.85, source_score=0.9
        )
        assert "strong label match" in rationale
        assert "high semantic similarity" in rationale
        assert "high source confidence" in rationale

    def test_weak_match(self):
        """Test weak match rationale."""
        rationale = build_match_rationale(
            label_match=0.2, semantic_sim=0.3, source_score=0.3
        )
        assert "weak" in rationale or "low" in rationale

    def test_empty_rationale(self):
        """Test zero scores produce low confidence message."""
        rationale = build_match_rationale(
            label_match=0.0, semantic_sim=0.0, source_score=0.0
        )
        assert "low confidence" in rationale


class TestGroundingScorer:
    """Tests for GroundingScorer."""

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        mock = AsyncMock()
        mock.similarity = AsyncMock(return_value=0.8)
        return mock

    @pytest.mark.asyncio
    async def test_score_candidates_with_embedding(self, mock_embedding_service):
        """Test scoring with embedding service."""
        scorer = GroundingScorer(embedding_service=mock_embedding_service)
        candidates = [
            GroundingCandidate(
                uri="http://example.com/person",
                label="Person",
                description="A human being",
                source="DBpedia",
                source_score=0.8,
            ),
            GroundingCandidate(
                uri="http://example.com/building",
                label="Building",
                description="A structure",
                source="DBpedia",
                source_score=0.5,
            ),
        ]

        scored = await scorer.score_candidates(candidates, "person", NodeType.CLASS)

        assert len(scored) == 2
        assert scored[0].uri == "http://example.com/person"
        assert scored[0].match_confidence >= 0.0
        assert scored[0].match_confidence <= 1.0
        assert scored[0].match_rationale

    @pytest.mark.asyncio
    async def test_score_candidates_sorting(self):
        """Test candidates are sorted by confidence."""
        scorer = GroundingScorer()
        candidates = [
            GroundingCandidate(
                uri="http://example.com/1",
                label="Weak Match",
                description="Description",
                source="DBpedia",
                source_score=0.2,
            ),
            GroundingCandidate(
                uri="http://example.com/2",
                label="Person",
                description="A human being",
                source="DBpedia",
                source_score=0.9,
            ),
        ]

        scored = await scorer.score_candidates(candidates, "person", NodeType.CLASS)

        assert scored[0].uri == "http://example.com/2"
        assert scored[0].match_confidence > scored[1].match_confidence

    @pytest.mark.asyncio
    async def test_score_candidates_custom_weights(self):
        """Test custom weighting."""
        scorer = GroundingScorer(
            weights={
                "source_score": 0.8,
                "label_match": 0.1,
                "semantic_similarity": 0.1,
            }
        )
        candidates = [
            GroundingCandidate(
                uri="http://example.com/1",
                label="Person",
                description="A human",
                source="Source1",
                source_score=0.9,
            ),
        ]

        scored = await scorer.score_candidates(candidates, "person")

        assert scored[0].match_confidence >= 0.7

    @pytest.mark.asyncio
    async def test_error_callback_invoked_on_embedding_service_error(self):
        """Test error_callback is called when embedding service raises."""
        # Create embedding service that raises
        mock_embedding_service = AsyncMock()
        test_error = ValueError("Embedding service failed")
        mock_embedding_service.similarity = AsyncMock(side_effect=test_error)

        # Create mock error callback
        error_callback = Mock()

        scorer = GroundingScorer(
            embedding_service=mock_embedding_service,
            error_callback=error_callback,
        )

        candidates = [
            GroundingCandidate(
                uri="http://example.com/person",
                label="Person",
                description="A human being",
                source="DBpedia",
                source_score=0.8,
            ),
        ]

        # Score candidates with embedding service error
        scored = await scorer.score_candidates(candidates, "person", NodeType.CLASS)

        # Verify error_callback was invoked with correct arguments
        error_callback.assert_called_once()
        call_args = error_callback.call_args[0]
        assert call_args[0] == "person"  # node_label
        assert call_args[1] == "Person"  # candidate_label
        assert call_args[2] is test_error  # exception

        # Verify scoring proceeded with has_embedding_score=False
        assert len(scored) == 1
        assert scored[0].has_embedding_score is False
        assert scored[0].semantic_similarity_score == 0.0
        assert "semantic similarity unavailable" in scored[0].match_rationale

    async def test_weights_normalized_when_embedding_unavailable(self):
        """Test that weights are normalized when embedding service fails."""
        mock_embedding_service = AsyncMock()
        mock_embedding_service.similarity = AsyncMock(side_effect=ValueError("Service down"))

        scorer = GroundingScorer(
            weights={
                "source_score": 0.3,
                "label_match": 0.3,
                "semantic_similarity": 0.4,
            },
            embedding_service=mock_embedding_service,
            error_callback=Mock(),
        )

        # Create candidate with perfect label match
        candidates = [
            GroundingCandidate(
                uri="http://example.com/person",
                label="person",
                description="A human being",
                source="DBpedia",
                source_score=0.8,
            ),
        ]

        scored = await scorer.score_candidates(candidates, "person", NodeType.CLASS)

        # With normalized weights (0.5 each for source_score and label_match):
        # score = 0.5*0.8 + 0.5*1.0 = 0.4 + 0.5 = 0.9
        # If weights were NOT normalized (0.3 + 0.3 + 0.4*0):
        # score = 0.3*0.8 + 0.3*1.0 = 0.24 + 0.3 = 0.54
        assert scored[0].match_confidence > 0.8
        assert scored[0].has_embedding_score is False
