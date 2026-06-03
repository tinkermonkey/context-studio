"""Pure metric computation module for pipeline quality evaluation.

This module contains no infrastructure imports — only Python stdlib (math, collections).
All metrics are deterministic functions of input lists/sets.
"""

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class PrecisionRecallF1:
    """Triple metric: precision, recall, F1 score."""

    precision: float
    recall: float
    f1: float


def precision_recall_f1(expected: list[Any], actual: list[Any]) -> PrecisionRecallF1:
    """
    Compute precision, recall, and F1 score.

    Args:
        expected: List of expected items
        actual: List of actual items

    Returns:
        PrecisionRecallF1 with precision, recall, and f1 scores in [0, 1]
    """
    expected_set = set(expected)
    actual_set = set(actual)

    if len(actual_set) == 0:
        precision = 1.0 if len(expected_set) == 0 else 0.0
    else:
        precision = len(expected_set & actual_set) / len(actual_set)

    if len(expected_set) == 0:
        recall = 1.0 if len(actual_set) == 0 else 0.0
    else:
        recall = len(expected_set & actual_set) / len(expected_set)

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * (precision * recall) / (precision + recall)

    return PrecisionRecallF1(
        precision=round(precision, 4), recall=round(recall, 4), f1=round(f1, 4)
    )


def jaccard_similarity(expected: list[Any], actual: list[Any]) -> float:
    """
    Compute Jaccard similarity (set overlap).

    Args:
        expected: List of expected items
        actual: List of actual items

    Returns:
        Jaccard index in [0, 1]
    """
    expected_set = set(expected)
    actual_set = set(actual)

    intersection = len(expected_set & actual_set)
    union = len(expected_set | actual_set)

    if union == 0:
        return 1.0

    return round(intersection / union, 4)


def reciprocal_rank(expected: list[str], ranked_list: list[str]) -> float:
    """
    Compute reciprocal rank (RR) for a single query.

    Finds the rank position of the first match from expected in ranked_list.
    For ranking quality of individual queries; not averaged across queries.

    Args:
        expected: List of correct item identifiers
        ranked_list: List of candidates in rank order

    Returns:
        RR in [0, 1], or 0.0 if no match found
    """
    expected_set = set(expected)

    for rank, item in enumerate(ranked_list, start=1):
        if item in expected_set:
            return round(1.0 / rank, 4)

    return 0.0


def brier_score(expected_probs: list[float], actual_labels: list[int]) -> float:
    """
    Compute Brier score (mean squared error of probabilities).

    Args:
        expected_probs: List of predicted probabilities in [0, 1]
        actual_labels: List of binary labels {0, 1}

    Returns:
        Brier score in [0, 1], lower is better
    """
    if len(expected_probs) != len(actual_labels):
        raise ValueError("Probability and label lists must have same length")

    if len(expected_probs) == 0:
        return 0.0

    squared_errors = [(prob - label) ** 2 for prob, label in zip(expected_probs, actual_labels)]

    return round(sum(squared_errors) / len(squared_errors), 4)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector (embedding)
        vec_b: Second vector (embedding)

    Returns:
        Cosine similarity in [-1, 1], typically [0, 1] for embeddings
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have same dimension")

    if len(vec_a) == 0:
        return 1.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return round(dot_product / (norm_a * norm_b), 4)


def delta_set_overlap(
    expected_added: list[Any],
    actual_added: list[Any],
    expected_removed: list[Any],
    actual_removed: list[Any],
) -> float:
    """
    Compute set overlap for additions and removals combined (delta F1).

    For connection refinement: measures correctness of add/remove operations.
    Computes F1 over the union of added and removed items.

    Args:
        expected_added: Items that should have been added
        actual_added: Items actually added
        expected_removed: Items that should have been removed
        actual_removed: Items actually removed

    Returns:
        F1 score of the combined delta operation in [0, 1]
    """
    expected_delta = set(expected_added) | set(expected_removed)
    actual_delta = set(actual_added) | set(actual_removed)

    metrics = precision_recall_f1(list(expected_delta), list(actual_delta))
    return metrics.f1


@dataclass
class RankingMetrics:
    """Ranking metrics: top-1, top-3, MRR."""

    top1_precision: float
    top3_precision: float
    mrr: float


def mean_reciprocal_rank(
    expected_list: list[str], ranked_list: list[str]
) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) across a set of expected items.

    Averages the reciprocal rank of the first match for each expected item
    in the ranked list. Used for evaluating ranking quality.

    Args:
        expected_list: List of correct item identifiers
        ranked_list: List of candidates in rank order

    Returns:
        MRR in [0, 1], averaged across all expected items
    """
    if not expected_list:
        return 1.0

    expected_set = set(expected_list)
    rr_sum = 0.0

    for expected_item in expected_list:
        found = False
        for rank, item in enumerate(ranked_list, start=1):
            if item == expected_item:
                rr_sum += 1.0 / rank
                found = True
                break
        if not found:
            # No match found; this expected item contributes 0 to RR sum
            pass

    return round(rr_sum / len(expected_list), 4)


def ranking_precision_at_k(expected: list[str], ranked_list: list[str], k: int) -> float:
    """
    Compute precision@k: fraction of expected items in top k.

    Args:
        expected: List of correct item identifiers
        ranked_list: List of candidates in rank order (full list)
        k: Cutoff rank (1 for top-1, 3 for top-3)

    Returns:
        Precision@k in [0, 1]
    """
    if not expected:
        return 1.0

    expected_set = set(expected)
    top_k = set(ranked_list[:k])

    matches = len(expected_set & top_k)
    return round(matches / len(expected), 4)


def ranking_metrics(
    expected: list[str], ranked_list: list[str]
) -> RankingMetrics:
    """
    Compute complete ranking metrics (top-1, top-3, MRR).

    Args:
        expected: List of correct URIs or identifiers
        ranked_list: List of candidate URIs in rank order

    Returns:
        RankingMetrics dataclass with all three metrics
    """
    top1 = ranking_precision_at_k(expected, ranked_list, 1)
    top3 = ranking_precision_at_k(expected, ranked_list, 3)
    mrr = mean_reciprocal_rank(expected, ranked_list)

    return RankingMetrics(top1_precision=top1, top3_precision=top3, mrr=mrr)
