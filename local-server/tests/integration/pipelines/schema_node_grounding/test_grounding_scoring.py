"""Tests for grounding scoring logic."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
from unittest.mock import AsyncMock

from domain.pipelines.schema_node_grounding.scoring import (
    GroundingCandidate,
    GroundingScorer,
    NodeType,
    compute_label_match_score,
    build_match_rationale,
)


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
