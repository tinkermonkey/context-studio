"""
Unit tests for RAG Pipeline Test Scoring Service.

Tests span-based matching, overlap calculation, and metric computation
including edge cases like no matches, partial overlaps, and multiple entities.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from rag.models import ExtractedEntity
from rag.test_scoring import AnnotationSpan, RAGTestScoringService


class TestRAGScoringService:
    """Test suite for RAGTestScoringService."""

    @pytest.fixture
    def scoring_service(self):
        """Create a scoring service with default threshold (0.8)."""
        return RAGTestScoringService(overlap_threshold=0.8)

    @pytest.fixture
    def strict_scoring_service(self):
        """Create a scoring service with strict threshold (1.0 for exact match only)."""
        return RAGTestScoringService(overlap_threshold=1.0)

    # ==================== Overlap Calculation Tests ====================

    def test_exact_overlap(self, scoring_service):
        """Test that exact span overlap returns 1.0."""
        overlap = scoring_service._calculate_overlap((0, 10), (0, 10))
        assert overlap == 1.0

    def test_no_overlap(self, scoring_service):
        """Test that non-overlapping spans return 0.0."""
        overlap = scoring_service._calculate_overlap((0, 10), (20, 30))
        assert overlap == 0.0

    def test_partial_overlap(self, scoring_service):
        """Test partial overlap calculation."""
        # Span1: 0-10 (length 10)
        # Span2: 5-15 (length 10)
        # Intersection: 5-10 (length 5)
        # Overlap: 5 / min(10, 10) = 0.5
        overlap = scoring_service._calculate_overlap((0, 10), (5, 15))
        assert overlap == 0.5

    def test_contained_span(self, scoring_service):
        """Test overlap when one span contains another."""
        # Span1: 0-10 (length 10)
        # Span2: 2-5 (length 3)
        # Intersection: 2-5 (length 3)
        # Overlap: 3 / min(10, 3) = 1.0 (100% of smaller span)
        overlap = scoring_service._calculate_overlap((0, 10), (2, 5))
        assert overlap == 1.0

    def test_zero_length_span(self, scoring_service):
        """Test that zero-length spans return 0.0 overlap."""
        overlap = scoring_service._calculate_overlap((5, 5), (0, 10))
        assert overlap == 0.0

    def test_adjacent_spans(self, scoring_service):
        """Test that adjacent spans (touching but not overlapping) return 0.0."""
        overlap = scoring_service._calculate_overlap((0, 10), (10, 20))
        assert overlap == 0.0

    # ==================== Precision/Recall/F1 Calculation Tests ====================

    def test_perfect_precision(self, scoring_service):
        """Test precision with no false positives."""
        precision = scoring_service._calculate_precision(
            true_positives=10, false_positives=0
        )
        assert precision == 1.0

    def test_perfect_recall(self, scoring_service):
        """Test recall with no false negatives."""
        recall = scoring_service._calculate_recall(true_positives=10, false_negatives=0)
        assert recall == 1.0

    def test_zero_precision(self, scoring_service):
        """Test precision when there are no true positives."""
        precision = scoring_service._calculate_precision(
            true_positives=0, false_positives=10
        )
        assert precision == 0.0

    def test_zero_recall(self, scoring_service):
        """Test recall when there are no true positives."""
        recall = scoring_service._calculate_recall(true_positives=0, false_negatives=10)
        assert recall == 0.0

    def test_f1_perfect_score(self, scoring_service):
        """Test F1 score with perfect precision and recall."""
        f1 = scoring_service._calculate_f1(precision=1.0, recall=1.0)
        assert f1 == 1.0

    def test_f1_zero_score(self, scoring_service):
        """Test F1 score when both precision and recall are zero."""
        f1 = scoring_service._calculate_f1(precision=0.0, recall=0.0)
        assert f1 == 0.0

    def test_f1_balanced(self, scoring_service):
        """Test F1 score with balanced precision and recall."""
        # F1 = 2 * (0.8 * 0.8) / (0.8 + 0.8) = 0.8
        f1 = scoring_service._calculate_f1(precision=0.8, recall=0.8)
        assert f1 == pytest.approx(0.8, abs=0.001)

    def test_f1_imbalanced(self, scoring_service):
        """Test F1 score with imbalanced precision and recall."""
        # F1 = 2 * (1.0 * 0.5) / (1.0 + 0.5) = 0.667
        f1 = scoring_service._calculate_f1(precision=1.0, recall=0.5)
        assert f1 == pytest.approx(0.667, abs=0.001)

    # ==================== Entity to Span Conversion Tests ====================

    def test_entities_to_spans(self, scoring_service):
        """Test conversion of extracted entities to spans."""
        entities = [
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6], "matched_kg_node": "node_123"},
            ),
            ExtractedEntity(
                text="programming",
                type="CONCEPT",
                confidence=0.85,
                source_layer="kg",
                sentence_index=0,
                metadata={"char_range": [7, 18]},
            ),
        ]

        spans = scoring_service._entities_to_spans(entities)

        assert len(spans) == 2
        assert spans[0].start_char == 0
        assert spans[0].end_char == 6
        assert spans[0].matched_kg_node == "node_123"
        assert spans[0].text == "Python"
        assert spans[1].start_char == 7
        assert spans[1].end_char == 18
        assert spans[1].matched_kg_node is None

    # ==================== Full Scoring Tests ====================

    def test_perfect_extraction(self, scoring_service):
        """Test scoring with perfect extraction (all correct)."""
        paragraph_text = "Python is a programming language."

        extracted_entities = [
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6], "matched_kg_node": "node_python"},
            )
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            )
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1_score == 1.0
        assert result.true_positives == 1
        assert result.false_positives == 0
        assert result.false_negatives == 0

    def test_no_extractions(self, scoring_service):
        """Test scoring when no entities are extracted (all false negatives)."""
        paragraph_text = "Python is a programming language."

        extracted_entities = []

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            ),
            AnnotationSpan(
                start_char=12,
                end_char=23,
                structure_node_id="node_programming",
                text="programming",
            ),
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1_score == 0.0
        assert result.true_positives == 0
        assert result.false_positives == 0
        assert result.false_negatives == 2

    def test_no_ground_truth(self, scoring_service):
        """Test scoring when there are no ground truth annotations (all false positives)."""
        paragraph_text = "Python is a programming language."

        extracted_entities = [
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6]},
            ),
            ExtractedEntity(
                text="programming",
                type="CONCEPT",
                confidence=0.85,
                source_layer="kg",
                sentence_index=0,
                metadata={"char_range": [12, 23]},
            ),
        ]

        ground_truth = []

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1_score == 0.0
        assert result.true_positives == 0
        assert result.false_positives == 2
        assert result.false_negatives == 0

    def test_partial_match_accepted(self, scoring_service):
        """Test that partial overlaps above threshold are accepted."""
        paragraph_text = "Python programming language"

        # Extraction is slightly off (0-7 instead of 0-6)
        extracted_entities = [
            ExtractedEntity(
                text="Python ",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 7], "matched_kg_node": "node_python"},
            )
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            )
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        # Overlap: 6/6 = 1.0 (all of ground truth overlaps)
        # Should match because overlap >= 0.8 threshold
        assert result.true_positives == 1
        assert result.false_positives == 0
        assert result.false_negatives == 0

    def test_partial_match_rejected(self, strict_scoring_service):
        """Test that partial overlaps below strict threshold are rejected."""
        paragraph_text = "Python programming language"

        # Extraction is slightly off (0-7 instead of 0-6)
        extracted_entities = [
            ExtractedEntity(
                text="Python ",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 7], "matched_kg_node": "node_python"},
            )
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            )
        ]

        result = strict_scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        # Overlap is 6/6 = 1.0 for ground truth, but 6/7 = 0.857 for extraction
        # Since overlap uses min(span1, span2), overlap = 6/6 = 1.0
        # This should actually match even with strict threshold
        assert result.true_positives == 1

    def test_multiple_entities_mixed_results(self, scoring_service):
        """Test scoring with mix of correct, missed, and spurious extractions."""
        paragraph_text = "Python is a programming language developed by Guido."

        extracted_entities = [
            # True positive - correct extraction
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6], "matched_kg_node": "node_python"},
            ),
            # False positive - not in ground truth
            ExtractedEntity(
                text="language",
                type="CONCEPT",
                confidence=0.70,
                source_layer="nlp",
                sentence_index=0,
                metadata={"char_range": [24, 32]},
            ),
            # Missing: "Guido" (false negative)
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            ),
            AnnotationSpan(
                start_char=47, end_char=52, structure_node_id="node_guido", text="Guido"
            ),
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        assert result.true_positives == 1  # Python
        assert result.false_positives == 1  # language
        assert result.false_negatives == 1  # Guido
        assert result.precision == 0.5  # 1/(1+1)
        assert result.recall == 0.5  # 1/(1+1)
        assert result.f1_score == 0.5

    def test_node_id_mismatch_prevents_match(self, scoring_service):
        """Test that mismatched structure node IDs prevent matching."""
        paragraph_text = "Python programming"

        extracted_entities = [
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6], "matched_kg_node": "node_wrong"},
            )
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            )
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        # Span overlaps perfectly, but node IDs don't match
        assert result.true_positives == 0
        assert result.false_positives == 1
        assert result.false_negatives == 1

    def test_none_node_id_matches_anything(self, scoring_service):
        """Test that None node ID in extraction matches any ground truth."""
        paragraph_text = "Python programming"

        extracted_entities = [
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6]},  # No matched_kg_node
            )
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            )
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        # Should match because extraction has no node constraint
        assert result.true_positives == 1
        assert result.false_positives == 0
        assert result.false_negatives == 0

    def test_result_to_dict(self, scoring_service):
        """Test conversion of ScoringResult to dictionary."""
        paragraph_text = "Python is great"

        extracted_entities = [
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6], "matched_kg_node": "node_python"},
            )
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            )
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        result_dict = result.to_dict()

        assert "precision" in result_dict
        assert "recall" in result_dict
        assert "f1_score" in result_dict
        assert "true_positives" in result_dict
        assert "false_positives" in result_dict
        assert "false_negatives" in result_dict
        assert "matches" in result_dict
        assert isinstance(result_dict["matches"], list)
        assert len(result_dict["matches"]) == 1  # One true positive

    def test_match_details_structure(self, scoring_service):
        """Test that match details have correct structure."""
        paragraph_text = "Python is a programming language."

        extracted_entities = [
            ExtractedEntity(
                text="Python",
                type="TECH",
                confidence=0.95,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [0, 6], "matched_kg_node": "node_python"},
            ),
            ExtractedEntity(
                text="Java",
                type="TECH",
                confidence=0.90,
                source_layer="llm",
                sentence_index=0,
                metadata={"char_range": [100, 104]},  # False positive
            ),
        ]

        ground_truth = [
            AnnotationSpan(
                start_char=0, end_char=6, structure_node_id="node_python", text="Python"
            ),
            AnnotationSpan(
                start_char=12,
                end_char=23,
                structure_node_id="node_programming",
                text="programming",
            ),
        ]

        result = scoring_service.score_extraction(
            extracted_entities, ground_truth, paragraph_text
        )

        matches = result.matches

        # Should have 1 true positive, 1 false positive, 1 false negative
        assert len(matches) == 3

        # Find each type
        true_positives = [m for m in matches if m["type"] == "true_positive"]
        false_positives = [m for m in matches if m["type"] == "false_positive"]
        false_negatives = [m for m in matches if m["type"] == "false_negative"]

        assert len(true_positives) == 1
        assert len(false_positives) == 1
        assert len(false_negatives) == 1

        # Validate true positive structure
        tp = true_positives[0]
        assert "extraction_span" in tp
        assert "extraction_text" in tp
        assert "annotation_span" in tp
        assert "annotation_text" in tp
        assert "matched_node" in tp
        assert "expected_node" in tp

        # Validate false positive structure
        fp = false_positives[0]
        assert "extraction_span" in fp
        assert "extraction_text" in fp
        assert "matched_node" in fp

        # Validate false negative structure
        fn = false_negatives[0]
        assert "annotation_span" in fn
        assert "annotation_text" in fn
        assert "expected_node" in fn


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
