"""Unit tests for quality metrics computation.

All tests use deterministic inputs and verify exact metric computation.
No I/O, no database, no infrastructure imports.
"""

import pytest

from tests.integration.pipelines._harness.metrics import (
    brier_score,
    cosine_similarity,
    delta_set_overlap,
    jaccard_similarity,
    mean_reciprocal_rank,
    precision_recall_f1,
    ranking_metrics,
    ranking_precision_at_k,
    reciprocal_rank,
)


class TestPrecisionRecallF1:
    """Tests for triple metric computation."""

    def test_perfect_match(self):
        """All items match exactly."""
        result = precision_recall_f1(
            expected=["a", "b", "c"],
            actual=["a", "b", "c"],
        )
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_no_match(self):
        """No items match."""
        result = precision_recall_f1(
            expected=["a", "b"],
            actual=["x", "y"],
        )
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0

    def test_partial_overlap_higher_recall(self):
        """Actual has subset of expected."""
        result = precision_recall_f1(
            expected=["a", "b", "c"],
            actual=["a", "b"],
        )
        assert result.precision == 1.0
        assert result.recall == pytest.approx(0.6667, abs=0.001)
        assert result.f1 == pytest.approx(0.8, abs=0.001)

    def test_partial_overlap_higher_precision(self):
        """Actual has more items than expected (lower precision)."""
        result = precision_recall_f1(
            expected=["a", "b"],
            actual=["a", "b", "c", "d"],
        )
        assert result.precision == 0.5
        assert result.recall == 1.0
        assert result.f1 == pytest.approx(0.6667, abs=0.001)

    def test_empty_expected_empty_actual(self):
        """Both empty is perfect."""
        result = precision_recall_f1(expected=[], actual=[])
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_empty_expected_nonempty_actual(self):
        """Over-extraction when expected is empty."""
        result = precision_recall_f1(expected=[], actual=["a"])
        assert result.precision == 0.0
        assert result.recall == 0.0  # Nothing expected, so recall is 0
        assert result.f1 == 0.0

    def test_nonempty_expected_empty_actual(self):
        """Missed everything."""
        result = precision_recall_f1(expected=["a"], actual=[])
        assert result.precision == 0.0  # Produced nothing when something expected
        assert result.recall == 0.0
        assert result.f1 == 0.0


class TestJaccardSimilarity:
    """Tests for Jaccard index (set overlap)."""

    def test_perfect_overlap(self):
        """Sets are identical."""
        sim = jaccard_similarity(["a", "b", "c"], ["a", "b", "c"])
        assert sim == 1.0

    def test_no_overlap(self):
        """Disjoint sets."""
        sim = jaccard_similarity(["a", "b"], ["x", "y"])
        assert sim == 0.0

    def test_partial_overlap(self):
        """One item in common."""
        sim = jaccard_similarity(["a", "b"], ["a", "c"])
        assert sim == pytest.approx(0.3333, abs=0.001)

    def test_empty_sets(self):
        """Both empty is 1.0 (Jaccard of two empty sets)."""
        sim = jaccard_similarity([], [])
        assert sim == 1.0

    def test_one_empty(self):
        """One empty set."""
        sim = jaccard_similarity([], ["a"])
        assert sim == 0.0


class TestReciprocalRank:
    """Tests for RR (ranking quality)."""

    def test_first_position(self):
        """Correct answer is first."""
        rr = reciprocal_rank(["correct"], ["correct", "wrong1", "wrong2"])
        assert rr == 1.0

    def test_second_position(self):
        """Correct answer is second."""
        rr = reciprocal_rank(["correct"], ["wrong1", "correct", "wrong2"])
        assert rr == 0.5

    def test_third_position(self):
        """Correct answer is third."""
        rr = reciprocal_rank(["correct"], ["wrong1", "wrong2", "correct"])
        assert rr == pytest.approx(0.3333, abs=0.001)

    def test_not_found(self):
        """Correct answer not in list."""
        rr = reciprocal_rank(["correct"], ["wrong1", "wrong2"])
        assert rr == 0.0

    def test_multiple_correct_first_match_wins(self):
        """Multiple correct answers; first one is ranked."""
        rr = reciprocal_rank(["correct1", "correct2"], ["wrong", "correct1", "correct2"])
        assert rr == 0.5


class TestBrierScore:
    """Tests for Brier score (probability calibration)."""

    def test_perfect_calibration(self):
        """Probabilities match binary outcomes."""
        score = brier_score([0.0, 1.0, 0.0, 1.0], [0, 1, 0, 1])
        assert score == 0.0

    def test_worst_calibration(self):
        """Probabilities completely wrong."""
        score = brier_score([1.0, 0.0, 1.0, 0.0], [0, 1, 0, 1])
        assert score == 1.0

    def test_moderate_confidence(self):
        """All 0.5 confidence predictions."""
        score = brier_score([0.5, 0.5, 0.5], [0, 1, 0])
        assert score == 0.25

    def test_single_example_correct(self):
        """Single correct prediction."""
        score = brier_score([0.9], [1])
        assert score == 0.01

    def test_single_example_wrong(self):
        """Single wrong prediction."""
        score = brier_score([0.9], [0])
        assert score == 0.81

    def test_empty_list(self):
        """Empty probability and label lists."""
        score = brier_score([], [])
        assert score == 0.0

    def test_length_mismatch_raises(self):
        """Mismatched lengths raise ValueError."""
        with pytest.raises(ValueError, match="must have same length"):
            brier_score([0.5, 0.5], [0, 1, 0])


class TestCosineSimilarity:
    """Tests for cosine similarity between vectors."""

    def test_identical_vectors(self):
        """Same vector has cosine 1.0."""
        sim = cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert sim == 1.0

    def test_orthogonal_vectors(self):
        """Perpendicular vectors have cosine 0.0."""
        sim = cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert sim == 0.0

    def test_opposite_vectors(self):
        """Opposite vectors have cosine -1.0."""
        sim = cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert sim == -1.0

    def test_scaled_vectors(self):
        """Scaling doesn't affect cosine."""
        sim = cosine_similarity([1.0, 1.0], [2.0, 2.0])
        assert sim == 1.0

    def test_45_degree_vectors(self):
        """45-degree angle vectors."""
        sim = cosine_similarity([1.0, 0.0], [1.0, 1.0])
        assert sim == pytest.approx(0.7071, abs=0.001)

    def test_zero_vector_raises(self):
        """Zero vector causes division by zero."""
        sim = cosine_similarity([0.0, 0.0], [1.0, 1.0])
        assert sim == 0.0

    def test_empty_vectors(self):
        """Empty vectors return 1.0 (vacuous similarity)."""
        sim = cosine_similarity([], [])
        assert sim == 1.0

    def test_dimension_mismatch_raises(self):
        """Mismatched dimensions raise ValueError."""
        with pytest.raises(ValueError, match="same dimension"):
            cosine_similarity([1.0], [1.0, 2.0])


class TestDeltaSetOverlap:
    """Tests for connection refinement delta F1."""

    def test_perfect_delta(self):
        """All additions and removals are correct."""
        f1 = delta_set_overlap(
            expected_added=["a", "b"],
            actual_added=["a", "b"],
            expected_removed=["x", "y"],
            actual_removed=["x", "y"],
        )
        assert f1 == 1.0

    def test_no_delta(self):
        """No changes made, and none expected."""
        f1 = delta_set_overlap(
            expected_added=[],
            actual_added=[],
            expected_removed=[],
            actual_removed=[],
        )
        assert f1 == 1.0

    def test_partial_delta(self):
        """Some changes are correct."""
        f1 = delta_set_overlap(
            expected_added=["a", "b"],
            actual_added=["a"],
            expected_removed=["x"],
            actual_removed=["x"],
        )
        # Combined delta: expected {a, b, x}, actual {a, x}
        # Precision: 2/2 = 1.0, Recall: 2/3 = 0.667, F1 = 0.8
        assert f1 == pytest.approx(0.8, abs=0.001)

    def test_empty_expected_false_additions(self):
        """Made additions when none were expected."""
        f1 = delta_set_overlap(
            expected_added=[],
            actual_added=["a", "b"],
            expected_removed=[],
            actual_removed=[],
        )
        # Expected delta: empty, Actual delta: {a, b}
        # Precision: 0/2 = 0.0, Recall: vacuous 1.0, F1 = 0.0
        assert f1 == 0.0

    def test_missed_additions(self):
        """Missed additions."""
        f1 = delta_set_overlap(
            expected_added=["a", "b"],
            actual_added=[],
            expected_removed=[],
            actual_removed=[],
        )
        # Expected delta: {a, b}, Actual delta: empty
        # Precision: vacuous 1.0, Recall: 0.0, F1 = 0.0
        assert f1 == 0.0


class TestRankingPrecisionAtK:
    """Tests for precision@k (ranking quality)."""

    def test_perfect_top1(self):
        """All expected items are first."""
        precision = ranking_precision_at_k(["correct"], ["correct", "wrong1", "wrong2"], k=1)
        assert precision == 1.0

    def test_missed_top1(self):
        """Expected item not in top 1."""
        precision = ranking_precision_at_k(["correct"], ["wrong1", "correct", "wrong2"], k=1)
        assert precision == 0.0

    def test_perfect_top3(self):
        """All expected items in top 3."""
        precision = ranking_precision_at_k(
            ["a", "b", "c"], ["a", "b", "c", "d", "e"], k=3
        )
        assert precision == 1.0

    def test_partial_top3(self):
        """Two of three expected items in top 3."""
        precision = ranking_precision_at_k(["a", "b", "c"], ["a", "b", "x", "c"], k=3)
        # Top 3: {a, b, x}, matches: 2, precision = 2/3
        assert precision == pytest.approx(0.6667, abs=0.001)

    def test_no_matches_top3(self):
        """None of expected items in top 3."""
        precision = ranking_precision_at_k(["a", "b"], ["x", "y", "z", "a"], k=3)
        assert precision == 0.0

    def test_empty_expected(self):
        """Empty expected list returns 1.0."""
        precision = ranking_precision_at_k([], ["a", "b", "c"], k=1)
        assert precision == 1.0

    def test_single_expected_multiple_matches_top3(self):
        """Single expected item appears multiple times (treated as set)."""
        precision = ranking_precision_at_k(["a"], ["a", "a", "b"], k=3)
        # Top 3: {a, b}, matches: 1, precision = 1/3
        assert precision == pytest.approx(0.3333, abs=0.001)


class TestMeanReciprocalRank:
    """Tests for Mean Reciprocal Rank (MRR)."""

    def test_single_expected_at_rank1(self):
        """Single expected item at first position."""
        mrr = mean_reciprocal_rank(["correct"], ["correct", "wrong1", "wrong2"])
        assert mrr == 1.0

    def test_single_expected_at_rank2(self):
        """Single expected item at second position."""
        mrr = mean_reciprocal_rank(["correct"], ["wrong1", "correct", "wrong2"])
        assert mrr == 0.5

    def test_multiple_expected_all_found(self):
        """Multiple expected items, all in list."""
        mrr = mean_reciprocal_rank(["a", "b"], ["a", "wrong", "b"])
        # RR for a: 1/1 = 1.0, RR for b: 1/3 = 0.333
        # MRR = (1.0 + 0.333) / 2 = 0.667
        assert mrr == pytest.approx(0.6667, abs=0.001)

    def test_multiple_expected_one_missing(self):
        """One expected item not in list."""
        mrr = mean_reciprocal_rank(["a", "b"], ["wrong", "a", "wrong2"])
        # RR for a: 1/2 = 0.5, RR for b: 0 (not found)
        # MRR = (0.5 + 0) / 2 = 0.25
        assert mrr == 0.25

    def test_empty_expected(self):
        """Empty expected list returns 1.0."""
        mrr = mean_reciprocal_rank([], ["a", "b", "c"])
        assert mrr == 1.0

    def test_none_found(self):
        """None of expected items found in list."""
        mrr = mean_reciprocal_rank(["a", "b"], ["x", "y", "z"])
        assert mrr == 0.0


class TestRankingMetrics:
    """Tests for combined ranking metrics."""

    def test_perfect_ranking(self):
        """All expected items in top positions."""
        metrics = ranking_metrics(["a", "b", "c"], ["a", "b", "c", "d", "e"])
        # top1_precision: 1 match in top-1 / 1 = 1.0
        # top3_precision: 3 matches in top-3 / 3 = 1.0
        # MRR: a=1.0, b=0.5, c=0.333, avg ≈ 0.611
        assert metrics.top1_precision == 1.0
        assert metrics.top3_precision == 1.0
        assert metrics.mrr == pytest.approx(0.6111, abs=0.001)

    def test_one_expected_top1_only(self):
        """Single expected item only at rank 1."""
        metrics = ranking_metrics(["a"], ["a", "b", "c", "d"])
        # top1_precision: 1 match in top-1 / 1 = 1.0
        # top3_precision: 1 match in top-3 / 3 = 0.333
        # MRR: a at rank 1 = 1.0
        assert metrics.top1_precision == 1.0
        assert metrics.top3_precision == pytest.approx(0.3333, abs=0.001)
        assert metrics.mrr == 1.0

    def test_one_expected_rank2(self):
        """Single expected item at rank 2."""
        metrics = ranking_metrics(["a"], ["b", "a", "c", "d"])
        # top1_precision: 0 matches in top-1 / 1 = 0.0
        # top3_precision: 1 match in top-3 / 3 = 0.333
        # MRR: a at rank 2 = 0.5
        assert metrics.top1_precision == 0.0
        assert metrics.top3_precision == pytest.approx(0.3333, abs=0.001)
        assert metrics.mrr == 0.5

    def test_multiple_expected_mixed_positions(self):
        """Multiple expected, some in top-1, some in top-3."""
        metrics = ranking_metrics(["a", "b"], ["a", "x", "b", "c"])
        # top1_precision: 1 match in top-1 / 1 = 1.0
        # top3_precision: 2 matches in top-3 / 3 = 0.667
        # MRR: a at rank 1 (1.0), b at rank 3 (0.333), avg = 0.667
        assert metrics.top1_precision == 1.0
        assert metrics.top3_precision == pytest.approx(0.6667, abs=0.001)
        assert metrics.mrr == pytest.approx(0.6667, abs=0.001)
