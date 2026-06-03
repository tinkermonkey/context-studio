"""Shared quality testing harness for pipeline quality suites.

This module provides the foundational substrate for all quality measurement in Phase B:
- Dual-mode execution (cassette replay vs live)
- LLM-level recording/replay via cassettes
- JSONL metrics emission
- Standardized fixture loading and execution
- Per-fixture quality metric computation
"""

from .cassettes import (
    CassetteLLMProvider,
    CassetteStaleError,
    RecordingHTTPTransport,
    RecordingLLMProvider,
)
from .metrics import (
    brier_score,
    cosine_similarity,
    delta_set_overlap,
    jaccard_similarity,
    mean_reciprocal_rank,
    precision_recall_f1,
)
from .report import MetricsEmitter
from .runner import QualityRunner

__all__ = [
    "CassetteLLMProvider",
    "RecordingLLMProvider",
    "RecordingHTTPTransport",
    "CassetteStaleError",
    "MetricsEmitter",
    "QualityRunner",
    "precision_recall_f1",
    "jaccard_similarity",
    "mean_reciprocal_rank",
    "brier_score",
    "cosine_similarity",
    "delta_set_overlap",
]
