"""Shared quality testing harness for pipeline quality suites.

Provides the foundational substrate for pipeline quality measurement:
- Dual-mode execution (cassette replay vs live)
- LLM-level recording/replay via cassettes
- JSONL metrics emission
- Standardized fixture loading and execution
- Per-fixture quality metric computation
"""

from .cassettes import (
    CassetteLLMProvider,
    CassetteStaleError,
    RecordingLLMProvider,
)
from .metrics import (
    PrecisionRecallF1,
    RankingMetrics,
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
from .report import ABReport, FloorGate, MetricsEmitter
from .runner import QualityRunner

__all__ = [
    "CassetteLLMProvider",
    "RecordingLLMProvider",
    "CassetteStaleError",
    "MetricsEmitter",
    "FloorGate",
    "ABReport",
    "QualityRunner",
    "precision_recall_f1",
    "PrecisionRecallF1",
    "jaccard_similarity",
    "reciprocal_rank",
    "brier_score",
    "cosine_similarity",
    "delta_set_overlap",
    "RankingMetrics",
    "ranking_metrics",
    "ranking_precision_at_k",
    "mean_reciprocal_rank",
]
