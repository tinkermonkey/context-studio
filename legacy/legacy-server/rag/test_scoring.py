"""
RAG Pipeline Test Scoring Service

This module provides scoring functionality for RAG pipeline test runs,
comparing extracted entities against ground truth annotations using
span-based matching with configurable overlap thresholds.
"""

from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger

from rag.models import ExtractedEntity

logger = get_logger(__name__)


@dataclass
class AnnotationSpan:
    """Represents a ground truth annotation span."""

    start_char: int
    end_char: int
    structure_node_id: str
    text: str = ""

    def __repr__(self):
        return f"AnnotationSpan({self.start_char}-{self.end_char}, node={self.structure_node_id})"


@dataclass
class ExtractionSpan:
    """Represents an extracted entity span."""

    start_char: int
    end_char: int
    matched_kg_node: str | None = None
    text: str = ""

    def __repr__(self):
        return f"ExtractionSpan({self.start_char}-{self.end_char}, node={self.matched_kg_node})"


@dataclass
class ScoringResult:
    """Result of scoring a pipeline run against ground truth."""

    precision: float  # 0.0 to 1.0
    recall: float  # 0.0 to 1.0
    f1_score: float  # 0.0 to 1.0
    true_positives: int
    false_positives: int
    false_negatives: int
    matches: list[dict[str, Any]]  # Details of matched spans

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "matches": self.matches,
        }


class RAGTestScoringService:
    """
    Service for scoring RAG pipeline extractions against ground truth.

    Implements span-based matching with:
    - Exact span matching (100% overlap)
    - Partial span matching (configurable overlap threshold, default 80%)
    - Precision, recall, and F1 score calculation
    """

    def __init__(self, overlap_threshold: float = 0.8):
        """
        Initialize the scoring service.

        Args:
            overlap_threshold: Minimum overlap ratio for partial matches (default: 0.8 = 80%)
        """
        self.overlap_threshold = overlap_threshold
        logger.info(
            f"RAGTestScoringService initialized with overlap_threshold={overlap_threshold}"
        )

    def score_extraction(
        self,
        extracted_entities: list[ExtractedEntity],
        ground_truth_annotations: list[AnnotationSpan],
        paragraph_text: str,
    ) -> ScoringResult:
        """
        Score an extraction result against ground truth annotations.

        Args:
            extracted_entities: List of entities extracted by the pipeline
            ground_truth_annotations: List of ground truth annotation spans
            paragraph_text: The original paragraph text

        Returns:
            ScoringResult with precision, recall, F1, and match details
        """
        logger.debug(
            f"Scoring extraction: {len(extracted_entities)} extracted, "
            f"{len(ground_truth_annotations)} ground truth"
        )

        # Convert extracted entities to spans
        extraction_spans = self._entities_to_spans(extracted_entities)

        # Find matches using span overlap
        matches, unmatched_extractions, unmatched_annotations = self._match_spans(
            extraction_spans, ground_truth_annotations
        )

        # Calculate metrics
        true_positives = len(matches)
        false_positives = len(unmatched_extractions)
        false_negatives = len(unmatched_annotations)

        precision = self._calculate_precision(true_positives, false_positives)
        recall = self._calculate_recall(true_positives, false_negatives)
        f1_score = self._calculate_f1(precision, recall)

        # Build match details
        match_details = self._build_match_details(
            matches, unmatched_extractions, unmatched_annotations, paragraph_text
        )

        result = ScoringResult(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            matches=match_details,
        )

        logger.info(
            f"Scoring complete: P={precision:.2f}, R={recall:.2f}, F1={f1_score:.2f}, "
            f"TP={true_positives}, FP={false_positives}, FN={false_negatives}"
        )

        return result

    def _entities_to_spans(
        self, entities: list[ExtractedEntity]
    ) -> list[ExtractionSpan]:
        """Convert extracted entities to span objects."""
        spans = []
        for entity in entities:
            # Extract char_range from metadata
            char_range = entity.metadata.get("char_range", [0, 0])
            matched_kg_node = entity.metadata.get("matched_kg_node")

            span = ExtractionSpan(
                start_char=char_range[0],
                end_char=char_range[1],
                matched_kg_node=matched_kg_node,
                text=entity.text,
            )
            spans.append(span)

        return spans

    def _match_spans(
        self,
        extraction_spans: list[ExtractionSpan],
        annotation_spans: list[AnnotationSpan],
    ) -> tuple[
        list[tuple[ExtractionSpan, AnnotationSpan]],
        list[ExtractionSpan],
        list[AnnotationSpan],
    ]:
        """
        Match extraction spans against annotation spans using overlap threshold.

        Uses a greedy matching algorithm where each annotation is matched to the best
        overlapping extraction. Time complexity: O(n*m) where n=annotations, m=extractions.
        For large-scale testing with many spans, could be optimized using interval trees,
        but current approach is simple and sufficient for typical RAG extraction sizes.

        Returns:
            Tuple of (matches, unmatched_extractions, unmatched_annotations)
        """
        matches = []
        matched_extraction_indices = set()
        matched_annotation_indices = set()

        # Sort spans by start position for potential early exit optimization
        sorted_extractions = sorted(
            enumerate(extraction_spans), key=lambda x: x[1].start_char
        )

        # For each annotation, find best matching extraction
        for ann_idx, annotation in enumerate(annotation_spans):
            best_match = None
            best_overlap = 0.0
            best_ext_idx = None

            for ext_idx, extraction in sorted_extractions:
                if ext_idx in matched_extraction_indices:
                    continue

                # Early exit if extraction starts after annotation ends (since sorted)
                if extraction.start_char >= annotation.end_char:
                    break

                # Calculate overlap
                overlap = self._calculate_overlap(
                    (extraction.start_char, extraction.end_char),
                    (annotation.start_char, annotation.end_char),
                )

                # Check if this is the best match so far
                if overlap >= self.overlap_threshold and overlap > best_overlap:
                    # Also check if structure nodes match (when available)
                    nodes_match = (
                        extraction.matched_kg_node is None
                        or extraction.matched_kg_node == annotation.structure_node_id
                    )

                    if nodes_match:
                        best_match = extraction
                        best_overlap = overlap
                        best_ext_idx = ext_idx

            # If we found a match, record it
            if best_match is not None:
                matches.append((best_match, annotation))
                matched_extraction_indices.add(best_ext_idx)
                matched_annotation_indices.add(ann_idx)

        # Collect unmatched spans
        unmatched_extractions = [
            span
            for idx, span in enumerate(extraction_spans)
            if idx not in matched_extraction_indices
        ]
        unmatched_annotations = [
            span
            for idx, span in enumerate(annotation_spans)
            if idx not in matched_annotation_indices
        ]

        return matches, unmatched_extractions, unmatched_annotations

    def _calculate_overlap(
        self, span1: tuple[int, int], span2: tuple[int, int]
    ) -> float:
        """
        Calculate overlap ratio between two spans.

        Overlap is defined as: intersection_length / min(span1_length, span2_length)

        Args:
            span1: (start, end) tuple for first span
            span2: (start, end) tuple for second span

        Returns:
            Overlap ratio from 0.0 to 1.0
        """
        start1, end1 = span1
        start2, end2 = span2

        # Calculate intersection
        intersection_start = max(start1, start2)
        intersection_end = min(end1, end2)

        if intersection_start >= intersection_end:
            # No overlap
            return 0.0

        intersection_length = intersection_end - intersection_start

        # Calculate lengths
        span1_length = end1 - start1
        span2_length = end2 - start2

        # Use the smaller span as denominator
        min_length = min(span1_length, span2_length)

        if min_length == 0:
            return 0.0

        overlap_ratio = intersection_length / min_length
        return overlap_ratio

    def _calculate_precision(self, true_positives: int, false_positives: int) -> float:
        """Calculate precision: TP / (TP + FP)"""
        total = true_positives + false_positives
        if total == 0:
            return 0.0
        return true_positives / total

    def _calculate_recall(self, true_positives: int, false_negatives: int) -> float:
        """Calculate recall: TP / (TP + FN)"""
        total = true_positives + false_negatives
        if total == 0:
            return 0.0
        return true_positives / total

    def _calculate_f1(self, precision: float, recall: float) -> float:
        """Calculate F1 score: 2 * (P * R) / (P + R)"""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    def _build_match_details(
        self,
        matches: list[tuple[ExtractionSpan, AnnotationSpan]],
        unmatched_extractions: list[ExtractionSpan],
        unmatched_annotations: list[AnnotationSpan],
        paragraph_text: str,
    ) -> list[dict[str, Any]]:
        """Build detailed match information for debugging."""
        details = []

        # True positives
        for extraction, annotation in matches:
            details.append(
                {
                    "type": "true_positive",
                    "extraction_span": [extraction.start_char, extraction.end_char],
                    "extraction_text": extraction.text
                    or paragraph_text[extraction.start_char : extraction.end_char],
                    "annotation_span": [annotation.start_char, annotation.end_char],
                    "annotation_text": annotation.text
                    or paragraph_text[annotation.start_char : annotation.end_char],
                    "matched_node": extraction.matched_kg_node,
                    "expected_node": annotation.structure_node_id,
                }
            )

        # False positives
        for extraction in unmatched_extractions:
            details.append(
                {
                    "type": "false_positive",
                    "extraction_span": [extraction.start_char, extraction.end_char],
                    "extraction_text": extraction.text
                    or paragraph_text[extraction.start_char : extraction.end_char],
                    "matched_node": extraction.matched_kg_node,
                }
            )

        # False negatives
        for annotation in unmatched_annotations:
            details.append(
                {
                    "type": "false_negative",
                    "annotation_span": [annotation.start_char, annotation.end_char],
                    "annotation_text": annotation.text
                    or paragraph_text[annotation.start_char : annotation.end_char],
                    "expected_node": annotation.structure_node_id,
                }
            )

        return details
