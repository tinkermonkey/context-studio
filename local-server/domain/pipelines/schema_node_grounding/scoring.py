"""
Scoring and candidate normalization for schema node grounding.

Provides domain-neutral candidate representation and scoring strategies
for combining source-native scores with cross-source heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class NodeType(str, Enum):
    """Types of schema nodes that can be grounded."""

    CLASS = "Class"
    PROPERTY_DEFINITION = "PropertyDefinition"


@dataclass(frozen=True)
class GroundingCandidate:
    """
    Domain-neutral candidate external grounding from any source.

    Attributes:
        uri: External identifier (e.g., DBpedia URI, ConceptNet ID)
        label: Human-readable label from the source
        description: Definition or description snippet from source
        source: Source name (e.g., "DBpedia", "ConceptNet")
        source_score: Source-native confidence in [0.0, 1.0]
        types: Optional type information from source (e.g., rdf:type values)
    """

    uri: str
    label: str
    description: str | None
    source: str
    source_score: float
    types: list[str] | None = None


@dataclass(frozen=True)
class ScoredCandidate:
    """
    Grounding candidate with combined cross-source confidence score.

    Attributes:
        uri: External identifier
        label: Human-readable label
        description: Definition snippet
        source: Source name
        source_score: Source-native score
        label_match_score: Score from exact/fuzzy label matching [0.0, 1.0]
        semantic_similarity_score: Score from embedding-based similarity [0.0, 1.0]
        match_confidence: Final combined confidence score in [0.0, 1.0]
        match_rationale: Human-readable explanation of score components
    """

    uri: str
    label: str
    description: str | None
    source: str
    source_score: float
    label_match_score: float
    semantic_similarity_score: float
    match_confidence: float
    match_rationale: str


def compute_label_match_score(candidate_label: str, node_label: str) -> float:
    """
    Score label match between candidate and schema node.

    Exact match (case-insensitive) scores 1.0. Substring and fuzzy matches
    receive lower scores. No match scores 0.0.

    Args:
        candidate_label: Label from external source
        node_label: Label from schema node being grounded

    Returns:
        Score in [0.0, 1.0]
    """
    if not candidate_label or not node_label:
        return 0.0

    c_lower = candidate_label.lower()
    n_lower = node_label.lower()

    # Exact match
    if c_lower == n_lower:
        return 1.0

    # Substring match
    if c_lower in n_lower or n_lower in c_lower:
        return 0.8

    # Word overlap (simple heuristic)
    c_words = set(c_lower.split())
    n_words = set(n_lower.split())
    if c_words and n_words:
        overlap = len(c_words & n_words) / max(len(c_words), len(n_words))
        if overlap > 0.0:
            return 0.5 + (overlap * 0.3)

    return 0.0


def build_match_rationale(
    label_match: float,
    semantic_sim: float,
    source_score: float,
) -> str:
    """
    Build human-readable rationale for scoring decision.

    Args:
        label_match: Label match score component
        semantic_sim: Semantic similarity score component
        source_score: Source-native score component

    Returns:
        Multi-component explanation
    """
    parts = []
    if label_match >= 0.8:
        parts.append("strong label match")
    elif label_match >= 0.5:
        parts.append("moderate label match")
    elif label_match > 0.0:
        parts.append("weak label match")

    if semantic_sim >= 0.8:
        parts.append("high semantic similarity")
    elif semantic_sim >= 0.5:
        parts.append("moderate semantic similarity")
    elif semantic_sim > 0.0:
        parts.append("low semantic similarity")

    if source_score >= 0.8:
        parts.append("high source confidence")
    elif source_score >= 0.5:
        parts.append("moderate source confidence")

    return "; ".join(parts) if parts else "low confidence across all dimensions"


class GroundingScorer:
    """
    Scorer for grounding candidates using configurable weights.

    Combines source-native scores with cross-source heuristics
    (label matching, semantic similarity, type compatibility).
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        embedding_service: Any = None,
        error_callback: Callable[[str, str, Exception], None] | None = None,
    ) -> None:
        """
        Initialize the scorer.

        Args:
            weights: Score component weights. Expected keys:
                - source_score: Weight for source-native score (default 0.3)
                - label_match: Weight for label matching (default 0.3)
                - semantic_similarity: Weight for semantic similarity (default 0.4)
            embedding_service: Optional service for computing embedding similarity
            error_callback: Optional synchronous callable(node_label, candidate_label, error)
                for error reporting when embedding similarity fails. Must be synchronous.
        """
        default_weights = {
            "source_score": 0.3,
            "label_match": 0.3,
            "semantic_similarity": 0.4,
        }
        self._weights = {**default_weights, **(weights or {})}
        self._embedding_service = embedding_service
        self._error_callback = error_callback

    async def score_candidates(
        self,
        candidates: list[GroundingCandidate],
        node_label: str,
        node_type: NodeType | None = None,
    ) -> list[ScoredCandidate]:
        """
        Score a list of candidates and return ranked results.

        Args:
            candidates: List of grounding candidates from sources
            node_label: Label of the schema node being grounded
            node_type: Type of node (Class or PropertyDefinition)

        Returns:
            List of ScoredCandidate objects sorted by match_confidence (descending)
        """
        scored = []

        for candidate in candidates:
            label_match = compute_label_match_score(candidate.label, node_label)

            semantic_sim = 0.0
            if self._embedding_service:
                try:
                    semantic_sim = await self._embedding_service.similarity(
                        node_label, candidate.description or candidate.label
                    )
                except Exception as e:
                    if self._error_callback:
                        self._error_callback(node_label, candidate.label, e)
                    semantic_sim = 0.0

            combined_score = (
                self._weights["source_score"] * candidate.source_score
                + self._weights["label_match"] * label_match
                + self._weights["semantic_similarity"] * semantic_sim
            )

            rationale = build_match_rationale(label_match, semantic_sim, candidate.source_score)

            scored.append(
                ScoredCandidate(
                    uri=candidate.uri,
                    label=candidate.label,
                    description=candidate.description,
                    source=candidate.source,
                    source_score=candidate.source_score,
                    label_match_score=label_match,
                    semantic_similarity_score=semantic_sim,
                    match_confidence=min(1.0, combined_score),
                    match_rationale=rationale,
                )
            )

        return sorted(scored, key=lambda c: c.match_confidence, reverse=True)
