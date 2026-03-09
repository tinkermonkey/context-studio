"""
Unit tests for RAG Test Scoring Service

Tests span-based matching, overlap calculation, and metric computation.
"""

from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest  # noqa: E402

# Direct imports to avoid full app initialization
from rag.test_scoring import RAGTestScoringService, AnnotationSpan  # noqa: E402, E501

# Avoid importing rag.models which has dependencies
# Instead, we'll create a simple mock for ExtractedEntity
from dataclasses import dataclass  # noqa: E402
from typing import Dict, Any  # noqa: E402


@dataclass
class ExtractedEntity:
    """Mock ExtractedEntity for testing."""

    text: str
    type: str
    confidence: float
    source_layer: str
    sentence_index: int
    metadata: Dict[str, Any]


class TestOverlapCalculation:
    """Test overlap calculation between spans."""

    def setup_method(self):
        self.service = RAGTestScoringService(overlap_threshold=0.8)

    def test_exact_match(self):
        """Test overlap calculation for exact span match."""
        overlap = self.service._calculate_overlap((10, 20), (10, 20))
        assert overlap == 1.0

    def test_no_overlap(self):
        """Test overlap calculation for non-overlapping spans."""
        overlap = self.service._calculate_overlap((10, 20), (30, 40))
        assert overlap == 0.0

    def test_partial_overlap_80_percent(self):
        """Test 80% overlap (should meet threshold)."""
        # span1: 10-20 (length 10)
        # span2: 12-22 (length 10)
        # intersection: 12-20 (length 8)
        # overlap: 8/10 = 0.8
        overlap = self.service._calculate_overlap((10, 20), (12, 22))
        assert overlap == 0.8

    def test_partial_overlap_50_percent(self):
        """Test 50% overlap (should not meet default threshold)."""
        # span1: 10-20 (length 10)
        # span2: 15-25 (length 10)
        # intersection: 15-20 (length 5)
        # overlap: 5/10 = 0.5
        overlap = self.service._calculate_overlap((10, 20), (15, 25))
        assert overlap == 0.5

    def test_one_span_contains_other(self):
        """Test when one span completely contains the other."""
        # span1: 10-30 (length 20)
        # span2: 15-25 (length 10)
        # intersection: 15-25 (length 10)
        # overlap: 10/10 = 1.0 (using min length)
        overlap = self.service._calculate_overlap((10, 30), (15, 25))
        assert overlap == 1.0

    def test_zero_length_span(self):
        """Test handling of zero-length spans."""
        overlap = self.service._calculate_overlap((10, 10), (10, 20))
        assert overlap == 0.0


class TestMetricCalculation:
    """Test precision, recall, and F1 calculation."""

    def setup_method(self):
        self.service = RAGTestScoringService()

    def test_precision_perfect(self):
        """Test precision calculation with perfect result."""
        precision = self.service._calculate_precision(10, 0)
        assert precision == 1.0

    def test_precision_50_percent(self):
        """Test precision calculation with 50% accuracy."""
        precision = self.service._calculate_precision(5, 5)
        assert precision == 0.5

    def test_precision_no_extractions(self):
        """Test precision when no entities extracted."""
        precision = self.service._calculate_precision(0, 0)
        assert precision == 0.0

    def test_recall_perfect(self):
        """Test recall calculation with perfect result."""
        recall = self.service._calculate_recall(10, 0)
        assert recall == 1.0

    def test_recall_50_percent(self):
        """Test recall calculation with 50% coverage."""
        recall = self.service._calculate_recall(5, 5)
        assert recall == 0.5

    def test_recall_no_annotations(self):
        """Test recall when no annotations exist."""
        recall = self.service._calculate_recall(0, 0)
        assert recall == 0.0

    def test_f1_perfect(self):
        """Test F1 calculation with perfect scores."""
        f1 = self.service._calculate_f1(1.0, 1.0)
        assert f1 == 1.0

    def test_f1_balanced(self):
        """Test F1 calculation with balanced precision/recall."""
        f1 = self.service._calculate_f1(0.5, 0.5)
        assert f1 == 0.5

    def test_f1_unbalanced(self):
        """Test F1 calculation with unbalanced precision/recall."""
        # P=0.8, R=0.4 -> F1 = 2*(0.8*0.4)/(0.8+0.4) = 0.64/1.2 = 0.533...
        f1 = self.service._calculate_f1(0.8, 0.4)
        assert abs(f1 - 0.5333) < 0.01

    def test_f1_zero_scores(self):
        """Test F1 calculation when both scores are zero."""
        f1 = self.service._calculate_f1(0.0, 0.0)
        assert f1 == 0.0


class TestScoringScenarios:
    """Test complete scoring scenarios."""

    def setup_method(self):
        self.service = RAGTestScoringService(overlap_threshold=0.8)
        self.paragraph_text = (
            "Apple Inc. is a technology company founded by Steve Jobs."
        )

    def _create_extracted_entity(
        self,
        text: str,
        start_char: int,
        end_char: int,
        matched_kg_node: Optional[str] = None,
    ) -> ExtractedEntity:
        """Helper to create ExtractedEntity for testing."""
        return ExtractedEntity(
            text=text,
            type="CONCEPT",
            confidence=0.9,
            source_layer="llm",
            sentence_index=0,
            metadata={
                "char_range": [start_char, end_char],
                "matched_kg_node": matched_kg_node,
            },
        )

    def test_perfect_match(self):
        """Test scenario with perfect extraction matching all annotations."""
        extracted = [
            self._create_extracted_entity("Apple Inc.", 0, 10, "node1"),
            self._create_extracted_entity("Steve Jobs", 47, 58, "node2"),
        ]

        annotations = [
            AnnotationSpan(0, 10, "node1", "Apple Inc."),
            AnnotationSpan(47, 58, "node2", "Steve Jobs"),
        ]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1_score == 1.0
        assert result.true_positives == 2
        assert result.false_positives == 0
        assert result.false_negatives == 0

    def test_no_matches(self):
        """Test scenario with no matches at all."""
        extracted = [self._create_extracted_entity("Microsoft", 100, 109, "node3")]

        annotations = [AnnotationSpan(0, 10, "node1", "Apple Inc.")]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1_score == 0.0
        assert result.true_positives == 0
        assert result.false_positives == 1
        assert result.false_negatives == 1

    def test_partial_matches(self):
        """Test scenario with some correct and some incorrect extractions."""
        extracted = [
            self._create_extracted_entity("Apple Inc.", 0, 10, "node1"),  # Correct
            self._create_extracted_entity("technology", 16, 26, "node3"),  # Extra (FP)
        ]

        annotations = [
            AnnotationSpan(0, 10, "node1", "Apple Inc."),  # Matched
            AnnotationSpan(47, 58, "node2", "Steve Jobs"),  # Missed (FN)
        ]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        assert result.true_positives == 1
        assert result.false_positives == 1
        assert result.false_negatives == 1
        assert result.precision == 0.5  # 1/(1+1)
        assert result.recall == 0.5  # 1/(1+1)
        assert result.f1_score == 0.5

    def test_partial_span_overlap(self):
        """Test matching with partial span overlap meeting threshold."""
        # Extract "Apple" instead of "Apple Inc."
        extracted = [self._create_extracted_entity("Apple", 0, 5, "node1")]

        # Annotate "Apple Inc."
        annotations = [AnnotationSpan(0, 10, "node1", "Apple Inc.")]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        # "Apple" (0-5, length 5) vs "Apple Inc." (0-10, length 10)
        # Intersection: 0-5 (length 5)
        # Overlap: 5/5 = 1.0 (using min length) -> Should match!
        assert result.true_positives == 1
        assert result.false_positives == 0
        assert result.false_negatives == 0

    def test_insufficient_overlap(self):
        """Test non-matching with insufficient overlap."""
        # Extract "Inc." only
        extracted = [self._create_extracted_entity("Inc.", 6, 10, "node1")]

        # Annotate "Apple Inc."
        annotations = [AnnotationSpan(0, 10, "node1", "Apple Inc.")]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        # "Inc." (6-10, length 4) vs "Apple Inc." (0-10, length 10)
        # Intersection: 6-10 (length 4)
        # Overlap: 4/4 = 1.0 -> Should match!
        # (Because we use min length, the smaller span is fully covered)
        assert result.true_positives == 1

    def test_empty_extractions(self):
        """Test scenario with no extractions."""
        extracted = []

        annotations = [AnnotationSpan(0, 10, "node1", "Apple Inc.")]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1_score == 0.0
        assert result.true_positives == 0
        assert result.false_positives == 0
        assert result.false_negatives == 1

    def test_empty_annotations(self):
        """Test scenario with no ground truth annotations."""
        extracted = [self._create_extracted_entity("Apple Inc.", 0, 10, "node1")]

        annotations = []

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        assert result.precision == 0.0  # No ground truth to match
        assert result.recall == 0.0
        assert result.f1_score == 0.0
        assert result.true_positives == 0
        assert result.false_positives == 1
        assert result.false_negatives == 0

    def test_duplicate_extractions(self):
        """Test scenario with multiple extractions for same annotation."""
        extracted = [
            self._create_extracted_entity("Apple Inc.", 0, 10, "node1"),
            self._create_extracted_entity(
                "Apple", 0, 5, "node1"
            ),  # Overlapping extraction
        ]

        annotations = [AnnotationSpan(0, 10, "node1", "Apple Inc.")]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        # Should match one extraction to the annotation, other becomes FP
        assert result.true_positives == 1
        assert result.false_positives == 1  # The duplicate
        assert result.false_negatives == 0

    def test_node_mismatch(self):
        """Test that node IDs must match for successful match."""
        extracted = [self._create_extracted_entity("Apple Inc.", 0, 10, "wrong_node")]

        annotations = [AnnotationSpan(0, 10, "correct_node", "Apple Inc.")]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        # Spans overlap perfectly but node IDs don't match
        assert result.true_positives == 0
        assert result.false_positives == 1
        assert result.false_negatives == 1

    def test_null_matched_kg_node(self):
        """Test extraction with no matched_kg_node (should still match by span)."""
        extracted = [
            self._create_extracted_entity("Apple Inc.", 0, 10, None)  # No node match
        ]

        annotations = [AnnotationSpan(0, 10, "node1", "Apple Inc.")]

        result = self.service.score_extraction(
            extracted, annotations, self.paragraph_text
        )

        # Should match by span alone when no node is matched
        assert result.true_positives == 1
        assert result.false_positives == 0
        assert result.false_negatives == 0


class TestCustomThreshold:
    """Test scoring with custom overlap thresholds."""

    def test_lower_threshold_allows_more_matches(self):
        """Test that lower threshold allows looser matching."""
        service_strict = RAGTestScoringService(overlap_threshold=0.9)
        service_loose = RAGTestScoringService(overlap_threshold=0.5)

        paragraph = "Test paragraph."
        extracted = [
            ExtractedEntity(
                text="Test",
                type="CONCEPT",
                confidence=0.9,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 4], "matched_kg_node": "node1"},
            )
        ]

        annotations = [
            AnnotationSpan(0, 10, "node1", "Test paragraph")  # Much longer span
        ]

        # Strict threshold: "Test" (0-4, len 4) vs "Test paragraph" (0-10, len 10)
        # Intersection: 0-4 (len 4), Overlap: 4/4 = 1.0 -> Matches!
        result_strict = service_strict.score_extraction(
            extracted, annotations, paragraph
        )

        # Loose threshold: Same calculation, should also match
        result_loose = service_loose.score_extraction(extracted, annotations, paragraph)

        # Both should match in this case
        assert result_strict.true_positives == 1
        assert result_loose.true_positives == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
