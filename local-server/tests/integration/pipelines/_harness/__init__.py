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
    brier_score,
    cosine_similarity,
    delta_set_overlap,
    jaccard_similarity,
    precision_recall_f1,
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
]
