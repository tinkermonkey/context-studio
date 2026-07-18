"""Unit tests for quality metrics computation.

All tests use deterministic inputs and verify exact metric computation.
No I/O, no database, no infrastructure imports.
"""

import pytest

from tests.integration.pipelines._harness.metrics import (
    brier_score,
    candidate_recall,
    cosine_similarity,
    delta_set_overlap,
    jaccard_similarity,
    label_accuracy,
    label_match_tier,
    mean_reciprocal_rank,
    normalize_label,
    precision_recall_f1,
    predicate_recall,
    ranking_metrics,
    ranking_precision_at_k,
    reciprocal_rank,
    soft_precision_recall_f1,
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


class TestNormalizeLabel:
    """Tests for lemma/stem-normalization of triple-slot labels (§3.1, §3.3)."""

    def test_third_person_verb_matches_base_form(self):
        """'ensures'/'ensure' normalize to the same value (the motivating example)."""
        assert normalize_label("ensures") == normalize_label("ensure")

    def test_another_third_person_verb(self):
        assert normalize_label("improves") == normalize_label("improve")

    def test_multi_word_snake_case_label(self):
        """Each underscore-separated token is stemmed independently."""
        assert normalize_label("runs_in") == normalize_label("run_in")

    def test_empty_label_returns_empty(self):
        assert normalize_label("") == ""

    def test_distinct_words_stay_distinct(self):
        assert normalize_label("causes") != normalize_label("prevents")


class TestLabelMatchTier:
    """Tests for the four-tier label match classification."""

    def test_exact_match_is_tier_one(self):
        assert label_match_tier("consensus_algorithm", "consensus_algorithm") == 1.0

    def test_normalized_match_is_tier_point_nine(self):
        assert label_match_tier("ensures", "ensure") == 0.9

    def test_fallback_embedding_proxy_is_tier_point_seven(self):
        """Bag-of-stems cosine >= 0.85 without a normalized match falls to tier 0.7."""
        tier = label_match_tier("quick_brown_fox", "quick_brown_fox_jumps")
        assert tier == 0.7

    def test_no_match_is_tier_zero(self):
        assert label_match_tier("foo", "bar") == 0.0

    def test_embed_fn_is_used_when_supplied(self):
        """An injected embed_fn overrides the stdlib fallback proxy."""
        vectors = {"a": [1.0, 0.0], "b": [1.0, 0.0]}
        tier = label_match_tier("a", "b", embed_fn=lambda label: vectors[label])
        assert tier == 0.7


class TestSoftPrecisionRecallF1:
    """Tests for tiered soft triple matching (§3.1)."""

    def test_perfect_match(self):
        result = soft_precision_recall_f1(
            expected=[("a", "causes", "b")], actual=[("a", "causes", "b")]
        )
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_normalized_predicate_variant_scores_point_nine(self):
        result = soft_precision_recall_f1(
            expected=[("a", "ensures", "b")], actual=[("a", "ensure", "b")]
        )
        assert result.precision == 0.9
        assert result.recall == 0.9
        assert result.f1 == 0.9

    def test_embedding_tier_scores_point_seven(self):
        result = soft_precision_recall_f1(
            expected=[("quick_brown_fox", "causes", "target")],
            actual=[("quick_brown_fox_jumps", "causes", "target")],
        )
        assert result.precision == 0.7
        assert result.recall == 0.7
        assert result.f1 == 0.7

    def test_no_match_scores_zero(self):
        result = soft_precision_recall_f1(expected=[("a", "p", "b")], actual=[("x", "q", "y")])
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0

    def test_empty_expected_empty_actual(self):
        result = soft_precision_recall_f1(expected=[], actual=[])
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_never_scores_below_strict_f1(self):
        """Every strict match is also a tier-1.0 soft match."""
        expected = [("a", "p", "b"), ("c", "q", "d")]
        actual = [("a", "p", "b")]
        strict = precision_recall_f1(expected, actual)
        soft = soft_precision_recall_f1(expected, actual)
        assert soft.f1 >= strict.f1

    def test_one_to_one_matching_no_double_counting(self):
        """A single actual triple cannot satisfy two expected triples."""
        result = soft_precision_recall_f1(
            expected=[("a", "p", "b"), ("a", "p", "b")], actual=[("a", "p", "b")]
        )
        # Only one of the two identical expected triples can be matched.
        assert result.recall == 0.5


class TestCandidateRecall:
    """Tests for candidate_recall (§3.1: coverage diagnostic)."""

    def test_all_labels_present(self):
        assert candidate_recall(expected=[("a", "p", "b")], actual=[("a", "q", "b")]) == 1.0

    def test_no_actual_triples(self):
        assert candidate_recall(expected=[("a", "p", "b")], actual=[]) == 0.0

    def test_empty_expected_is_vacuous(self):
        assert candidate_recall(expected=[], actual=[("a", "q", "b")]) == 1.0

    def test_partial_coverage(self):
        result = candidate_recall(
            expected=[("a", "p", "b"), ("c", "p", "d")], actual=[("a", "q", "x")]
        )
        # GT labels {a, b, c, d}; only "a" appears among actual's {a, x}.
        assert result == 0.25


class TestPredicateRecall:
    """Tests for predicate_recall (§3.1: relation-derivation diagnostic)."""

    def test_relation_derived_regardless_of_predicate(self):
        assert predicate_recall(expected=[("a", "p", "b")], actual=[("a", "q", "b")]) == 1.0

    def test_relation_not_derived(self):
        assert predicate_recall(expected=[("a", "p", "b")], actual=[("a", "q", "c")]) == 0.0

    def test_empty_expected_is_vacuous(self):
        assert predicate_recall(expected=[], actual=[("a", "q", "b")]) == 1.0

    def test_empty_actual_with_nonempty_expected(self):
        assert predicate_recall(expected=[("a", "p", "b")], actual=[]) == 0.0


class TestLabelAccuracy:
    """Tests for label_accuracy (§3.1: normalization diagnostic)."""

    def test_exact_labels_on_derived_pair(self):
        result = label_accuracy(expected=[("a", "p", "b")], actual=[("a", "q", "b")])
        assert result == {"strict": 1.0, "soft": 1.0, "derived_count": 1}

    def test_normalized_only_match_is_soft_but_not_strict(self):
        result = label_accuracy(expected=[("player", "p", "runs")], actual=[("player", "q", "run")])
        assert result["strict"] == 0.0
        assert result["soft"] == 1.0
        assert result["derived_count"] == 1

    def test_no_derived_pairs_is_vacuously_accurate(self):
        result = label_accuracy(expected=[("a", "p", "b")], actual=[])
        assert result == {"strict": 1.0, "soft": 1.0, "derived_count": 0}


class TestRecognitionMetrics:
    """Pairwise coreference metrics for cross-document recognition (#1142)."""

    def _m(self, entity, node, title="X", canonical="X"):
        return {"entity_key": entity, "canonical_title": canonical, "node_id": node, "title": title}

    def test_perfect_clustering(self):
        from tests.integration.pipelines._harness.metrics import recognition_metrics

        r = recognition_metrics([self._m("K", "k")] * 3 + [self._m("N", "n")] * 2)
        assert r.dedup_precision == 1.0 and r.dedup_recall == 1.0 and r.dedup_f1 == 1.0
        assert r.node_count_ratio == 1.0

    def test_false_merge_tanks_precision_not_recall(self):
        from tests.integration.pipelines._harness.metrics import recognition_metrics

        # N's mentions wrongly land on K's node
        r = recognition_metrics([self._m("K", "k")] * 3 + [self._m("N", "k")] * 2)
        assert r.dedup_precision < 1.0
        assert r.dedup_recall == 1.0
        assert r.node_count_ratio < 1.0  # over-merged

    def test_missed_merge_tanks_recall_not_precision(self):
        from tests.integration.pipelines._harness.metrics import recognition_metrics

        # K's mentions split across two nodes
        r = recognition_metrics([self._m("K", "k1")] * 2 + [self._m("K", "k2")])
        assert r.dedup_precision == 1.0
        assert r.dedup_recall < 1.0
        assert r.node_count_ratio > 1.0  # duplicates

    def test_canonical_label_accuracy(self):
        from tests.integration.pipelines._harness.metrics import recognition_metrics

        # correctly resolved, but node titled with a variant, not the canonical
        r = recognition_metrics(
            [self._m("K", "k", title="Kubernetes", canonical="Kubernetes"),
             self._m("K", "k", title="K8s", canonical="Kubernetes")]
        )
        assert r.dedup_precision == 1.0
        assert r.canonical_label_accuracy == 0.5

    def test_empty_is_perfect(self):
        from tests.integration.pipelines._harness.metrics import recognition_metrics

        r = recognition_metrics([])
        assert r.dedup_f1 == 1.0 and r.gt_entity_count == 0
