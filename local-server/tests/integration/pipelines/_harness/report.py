"""JSONL metrics artifact emission and floor gating.

Writes versioned JSONL rows to _metrics/ directory for queryable
metric history and A/B comparison aggregation.
"""

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MetricsEmitter:
    """Emits versioned JSONL rows to _metrics/ directory."""

    def __init__(self, metrics_dir: Path | str) -> None:
        """
        Initialize the metrics emitter.

        Args:
            metrics_dir: Directory where JSONL files will be written
        """
        self._metrics_dir = Path(metrics_dir)
        self._metrics_dir.mkdir(parents=True, exist_ok=True)
        self._run_id = str(uuid.uuid4())

    def emit(
        self,
        pipeline_type: str,
        scenario: str,
        model: str,
        config_ref: str,
        config_version: int,
        metrics: dict[str, float],
        mode: str = "cassette",
        source: str = "automated",
        duration_ms: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """
        Emit a single metrics row to JSONL.

        Args:
            pipeline_type: Pipeline type identifier
            scenario: Scenario name
            model: Model identifier
            config_ref: Configuration reference
            config_version: Configuration version number
            metrics: Dict of metric_name → metric_value pairs
            mode: Execution mode ("cassette" or "live")
            source: Source of metrics ("automated" or "human_eval")
            duration_ms: Execution duration in milliseconds
            tokens_in: Input token count
            tokens_out: Output token count
        """
        row = {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self._run_id,
            "pipeline_type": pipeline_type,
            "scenario": scenario,
            "model": model,
            "config_ref": config_ref,
            "config_version": config_version,
            "mode": mode,
            "source": source,
            "duration_ms": duration_ms,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "metrics": metrics,
        }

        # Append to JSONL file (one row per line, no outer array)
        metrics_file = self._metrics_dir / f"{pipeline_type}.jsonl"
        with open(metrics_file, "a") as f:
            f.write(json.dumps(row) + "\n")


class FloorGate:
    """Asserts pipeline quality metrics against configurable floors."""

    def __init__(self, floors: dict[str, float]) -> None:
        """
        Initialize the floor gate.

        Args:
            floors: Dict mapping metric_name → minimum_acceptable_value
        """
        self._floors = floors

    def assert_metrics(
        self, metrics: dict[str, float], pipeline_type: str = "unknown"
    ) -> None:
        """
        Assert that all metrics meet their floor values.

        Args:
            metrics: Dict of metric_name → metric_value
            pipeline_type: Pipeline type for error context

        Raises:
            AssertionError: If any metric falls below its floor
        """
        failures = []

        for metric_name, floor_value in self._floors.items():
            if metric_name not in metrics:
                failures.append(f"Missing metric: {metric_name}")
                continue

            actual_value = metrics[metric_name]

            # Higher is better for most metrics, but Brier score is lower-is-better
            if metric_name == "brier":
                if actual_value > floor_value:
                    failures.append(
                        f"{metric_name}={actual_value:.4f} exceeds "
                        f"floor {floor_value:.4f} (lower is better)"
                    )
            else:
                if actual_value < floor_value:
                    failures.append(
                        f"{metric_name}={actual_value:.4f} below "
                        f"floor {floor_value:.4f}"
                    )

        if failures:
            error_msg = (
                f"Quality gate failed for {pipeline_type}:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )
            raise AssertionError(error_msg)


class ABReport:
    """Formats side-by-side A/B comparison output."""

    @staticmethod
    def format_comparison(
        config_a: str,
        config_b: str,
        metrics_a: dict[str, float],
        metrics_b: dict[str, float],
    ) -> str:
        """
        Format an A/B comparison as human-readable text.

        Args:
            config_a: Name of configuration A
            config_b: Name of configuration B
            metrics_a: Metrics dict for config A
            metrics_b: Metrics dict for config B

        Returns:
            Formatted comparison string
        """
        lines = [f"\nA/B Comparison: {config_a} vs {config_b}\n"]
        lines.append("Metric".ljust(20) + config_a.ljust(15) + config_b.ljust(15) + "Delta")
        lines.append("-" * 65)

        all_metrics = sorted(set(metrics_a.keys()) | set(metrics_b.keys()))

        for metric_name in all_metrics:
            value_a = metrics_a.get(metric_name, float("nan"))
            value_b = metrics_b.get(metric_name, float("nan"))

            has_nan = math.isnan(value_a) or math.isnan(value_b)
            delta = value_b - value_a if not has_nan else float("nan")
            delta_str = f"{delta:+.4f}" if not has_nan else "N/A"

            value_a_str = f"{value_a:.4f}" if not math.isnan(value_a) else "N/A"
            value_b_str = f"{value_b:.4f}" if not math.isnan(value_b) else "N/A"

            lines.append(
                f"{metric_name.ljust(20)}"
                f"{value_a_str:<15}"
                f"{value_b_str:<15}"
                f"{delta_str}"
            )

        return "\n".join(lines)
