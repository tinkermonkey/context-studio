"""A normal test run must not rewrite the committed _metrics history (#1632).

The quality suites emit metrics rows through the session's quality_metrics_dir.
Without --record-metrics that is a temporary directory, so the committed
tests/integration/fixtures/pipelines/_metrics/*.jsonl files only change through
a deliberate recording run.
"""

import json
import re
from pathlib import Path

import pytest

from tests.integration.pipelines._harness.report import (
    COMMITTED_METRICS_DIR,
    MetricsEmitter,
    metrics_dir_for_run,
    metrics_file_to_aggregate,
)

PIPELINES_TEST_DIR = Path(__file__).resolve().parent


def _committed_history() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(COMMITTED_METRICS_DIR.glob("*.jsonl"))}


def test_committed_history_exists():
    """The guard below is only meaningful while there is a committed history to protect."""
    assert (COMMITTED_METRICS_DIR / "schema_extraction.jsonl").exists()


def test_normal_run_leaves_committed_metrics_unchanged(request, quality_metrics_dir):
    """Emitting through the session's metrics dir leaves every committed file as it was."""
    if request.config.getoption("--record-metrics"):
        pytest.skip("--record-metrics appends to the committed history on purpose")

    assert quality_metrics_dir.resolve() != COMMITTED_METRICS_DIR.resolve()
    before = _committed_history()

    MetricsEmitter(quality_metrics_dir).emit(
        pipeline_type="schema_extraction",
        fixture_id="metrics_location_guard",
        model="test-model",
        config_ref="default",
        config_version=1,
        metrics={"class_jaccard": 1.0},
    )

    assert _committed_history() == before
    rows = (quality_metrics_dir / "schema_extraction.jsonl").read_text().splitlines()
    assert json.loads(rows[-1])["fixture_id"] == "metrics_location_guard"


def test_only_recording_targets_the_committed_history(tmp_path):
    """--record-metrics selects the committed directory; otherwise the scratch directory."""
    assert metrics_dir_for_run(record=False, scratch_dir=tmp_path) == tmp_path
    assert metrics_dir_for_run(record=True, scratch_dir=tmp_path) == COMMITTED_METRICS_DIR


def test_aggregate_reads_this_runs_rows_else_the_committed_history(tmp_path):
    """Aggregate gates read this run's rows when it emitted any, else the committed history."""
    committed = COMMITTED_METRICS_DIR / "definition_refinement.jsonl"
    assert metrics_file_to_aggregate(tmp_path, "definition_refinement") == committed

    run_file = tmp_path / "definition_refinement.jsonl"
    run_file.write_text("{}\n")
    assert metrics_file_to_aggregate(tmp_path, "definition_refinement") == run_file


def test_no_pipeline_test_writes_to_the_committed_metrics_dir_directly():
    """Suites take their metrics dir from the quality_metrics_dir fixture, never a fixed path."""
    hard_coded = re.compile(r"""["']_metrics["']""")
    offenders = [
        str(path.relative_to(PIPELINES_TEST_DIR))
        for path in PIPELINES_TEST_DIR.rglob("*.py")
        if path.name != "report.py" and hard_coded.search(path.read_text())
    ]
    assert offenders == []
