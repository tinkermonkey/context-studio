"""
Tests for the A/B evaluation and promotion decision logic for grounded_v1.

Phase 4 work: validates that grounded_v1 is properly compared against the
default baseline and that promotion/rejection decisions are correctly made
based on the defined criteria.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from scripts.quality_tournament import _evaluate_grounded_v1_promotion


class TestGroundedV1PromotionDecision:
    def test_grounded_v1_not_found_returns_incomplete(self):
        results = [
            {"variant": "open_v1", "dev": {"strict_f1": 0.5, "soft_f1": 0.6}},
            {"variant": "default", "dev": {"strict_f1": 0.941, "soft_f1": 0.952}},
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["decision"] == "INCOMPLETE"
        assert decision["grounded_v1_found"] is False
        assert "cassettes" in decision["reason"].lower()

    def test_grounded_v1_meets_both_criteria_promotes(self):
        results = [
            {"variant": "grounded_v1", "dev": {"strict_f1": 0.95, "soft_f1": 0.96}},
            {"variant": "default", "dev": {"strict_f1": 0.941, "soft_f1": 0.952}},
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["decision"] == "PROMOTE"
        assert decision["grounded_v1_found"] is True
        assert decision["comparison"]["strict_f1"]["meets_threshold"] is True
        assert decision["comparison"]["soft_f1"]["meets_threshold"] is True

    def test_grounded_v1_exactly_meets_threshold_promotes(self):
        results = [
            {"variant": "grounded_v1", "dev": {"strict_f1": 0.941, "soft_f1": 0.952}},
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["decision"] == "PROMOTE"
        assert decision["comparison"]["strict_f1"]["meets_threshold"] is True
        assert decision["comparison"]["soft_f1"]["meets_threshold"] is True

    def test_grounded_v1_fails_strict_f1_threshold(self):
        results = [
            {"variant": "grounded_v1", "dev": {"strict_f1": 0.940, "soft_f1": 0.96}},
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["decision"] == "STAY"
        assert decision["comparison"]["strict_f1"]["meets_threshold"] is False
        assert decision["comparison"]["soft_f1"]["meets_threshold"] is True
        assert "strict-F1" in decision["reason"]

    def test_grounded_v1_fails_soft_f1_threshold(self):
        results = [
            {"variant": "grounded_v1", "dev": {"strict_f1": 0.95, "soft_f1": 0.951}},
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["decision"] == "STAY"
        assert decision["comparison"]["strict_f1"]["meets_threshold"] is True
        assert decision["comparison"]["soft_f1"]["meets_threshold"] is False
        assert "soft-F1" in decision["reason"]

    def test_grounded_v1_fails_both_thresholds(self):
        results = [
            {"variant": "grounded_v1", "dev": {"strict_f1": 0.93, "soft_f1": 0.94}},
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["decision"] == "STAY"
        assert decision["comparison"]["strict_f1"]["meets_threshold"] is False
        assert decision["comparison"]["soft_f1"]["meets_threshold"] is False
        assert "strict-F1" in decision["reason"]
        assert "soft-F1" in decision["reason"]

    def test_decision_includes_numeric_thresholds(self):
        results = [
            {"variant": "grounded_v1", "dev": {"strict_f1": 0.950, "soft_f1": 0.960}},
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["comparison"]["strict_f1"]["threshold"] == 0.941
        assert decision["comparison"]["soft_f1"]["threshold"] == 0.952

    def test_decision_preserves_grounded_metrics(self):
        results = [
            {
                "variant": "grounded_v1",
                "dev": {
                    "strict_f1": 0.95,
                    "soft_f1": 0.96,
                    "candidate_recall": 0.85,
                },
            }
        ]
        decision = _evaluate_grounded_v1_promotion(results)
        assert decision["grounded_v1_metrics"]["strict_f1"] == 0.95
        assert decision["grounded_v1_metrics"]["soft_f1"] == 0.96
        assert decision["grounded_v1_metrics"]["candidate_recall"] == 0.85
