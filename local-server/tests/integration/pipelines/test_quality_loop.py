"""
Tests for the closed-loop optimizer logic (Phase 6).

Exercises coordinate_ascent with a synthetic (model-free) evaluator so the
regression gate, acceptance logic, and telemetry emission are validated
deterministically in milliseconds, plus the scoreboard reader.
"""

import json
import os
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.quality_loop import coordinate_ascent
from tests.integration.pipelines._harness.report import MetricsEmitter, read_scoreboard


@pytest.mark.asyncio
async def test_coordinate_ascent_picks_best_and_emits(tmp_path):
    # Synthetic objective: k=2 is best for the primary metric.
    primary_by_k = {1: 0.50, 2: 0.70, 3: 0.60}

    async def fake_evaluate(config):
        return {"f1": primary_by_k[config["k"]], "brier": 0.2}

    emitter = MetricsEmitter(tmp_path)
    config, base_m, best_m, base_p, best_p, evals = await coordinate_ascent(
        fake_evaluate,
        base_config={"k": 1},
        space={"k": [1, 2, 3]},
        primary="f1",
        emitter=emitter,
        pipeline_tag="quality_loop_test",
        passes=1,
    )

    assert base_p == 0.50
    assert best_p == 0.70  # accepted the improvement
    assert config["k"] == 2
    assert best_p >= base_p  # regression gate
    assert evals >= 2

    # Telemetry was written with baseline + candidate + tuned rows.
    rows = [
        json.loads(line)
        for line in (tmp_path / "quality_loop_test.jsonl").read_text().splitlines()
        if line.strip()
    ]
    refs = {r["config_ref"] for r in rows}
    assert {"baseline", "candidate", "tuned"} <= refs


@pytest.mark.asyncio
async def test_coordinate_ascent_multi_knob_carry_forward(tmp_path):
    # Objective rewards the k1=2 AND k2=3 combination — only reachable if
    # accepting k1=2 carries forward while sweeping k2 (the point of the algorithm).
    def score(cfg):
        if cfg["k1"] == 2 and cfg["k2"] == 3:
            return 0.9
        return 0.6 if cfg["k1"] == 2 else 0.5

    async def fake_evaluate(config):
        return {"f1": score(config), "brier": 0.2}

    emitter = MetricsEmitter(tmp_path)
    config, _, _, base_p, best_p, _ = await coordinate_ascent(
        fake_evaluate,
        base_config={"k1": 1, "k2": 1},
        space={"k1": [1, 2], "k2": [1, 2, 3]},
        primary="f1",
        emitter=emitter,
        pipeline_tag="quality_loop_multi",
        passes=2,
    )
    assert config["k1"] == 2 and config["k2"] == 3
    assert best_p == 0.9 and base_p == 0.5


@pytest.mark.asyncio
async def test_coordinate_ascent_holds_gate_when_no_improvement(tmp_path):
    async def fake_evaluate(config):
        return {"f1": 0.42, "brier": 0.2}  # flat: nothing beats baseline

    emitter = MetricsEmitter(tmp_path)
    config, _, _, base_p, best_p, _ = await coordinate_ascent(
        fake_evaluate,
        base_config={"k": 1},
        space={"k": [1, 2, 3]},
        primary="f1",
        emitter=emitter,
        pipeline_tag="quality_loop_flat",
        passes=1,
    )
    assert best_p == base_p == 0.42
    assert config["k"] == 1  # stayed on baseline


class _DeterministicRng:
    """
    Stand-in for random.Random with the two calls coordinate_ascent needs
    (`shuffle`, `choice`), pinned to fixed, reproducible choices instead of a
    magic real seed — makes the restart/jitter path exercised below exact and
    stable across Python versions.
    """

    def shuffle(self, values):
        pass  # keep declared knob order

    def choice(self, values):
        return values[-1]  # always jitter to the last (max) value per knob


@pytest.mark.asyncio
async def test_coordinate_ascent_restart_ratchet_respects_floor_gate(tmp_path):
    """
    karpathy_loop_design.md §4.1: a jittered restart start must never become
    the global best — nor contaminate best_metrics/best_config — if it
    violates the floor gate, even when its primary metric looks better in
    isolation. Regression test for the restart-ratchet floor-check gap.
    """

    def score(cfg):
        if cfg["a"] == 2:
            # Tempting on the primary metric, but fails the floor gate.
            return {"primary": 0.99, "floor": 0.1}
        return {"primary": 0.6 if cfg["b"] == 2 else 0.5, "floor": 0.5}

    async def fake_evaluate(config):
        return score(config)

    emitter = MetricsEmitter(tmp_path)
    config, base_m, best_m, base_p, best_p, evals = await coordinate_ascent(
        fake_evaluate,
        base_config={"a": 1, "b": 1},
        space={"a": [1, 2], "b": [1, 2]},
        primary="primary",
        emitter=emitter,
        pipeline_tag="quality_loop_restart_floor",
        passes=1,
        floor_key="floor",
        restarts=2,
        rng=_DeterministicRng(),
    )

    assert base_p == 0.5
    # The floor-violating jittered start (a=2, primary=0.99) must never win —
    # the accepted best only ever comes from the b=2 knob, which respects the
    # floor gate.
    assert best_p == 0.6
    assert config == {"a": 1, "b": 2}
    # best_metrics must always describe best_config, never the mismatched
    # floor-violating jittered dict.
    assert best_m["primary"] == best_p
    assert best_m["floor"] + 1e-9 >= base_m["floor"]


def test_read_scoreboard_returns_latest_per_config_ref(tmp_path):
    metrics_file = tmp_path / "scoreboard.jsonl"
    rows = [
        {"config_ref": "baseline", "config_version": 0, "metrics": {"f1": 0.5}},
        {"config_ref": "candidate", "config_version": 1, "metrics": {"f1": 0.6}},
        {"config_ref": "candidate", "config_version": 2, "metrics": {"f1": 0.55}},
        {"config_ref": "tuned", "config_version": 3, "metrics": {"f1": 0.6}},
    ]
    metrics_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    board = read_scoreboard(metrics_file)
    assert set(board) == {"baseline", "candidate", "tuned"}
    # candidate keeps the highest-version row.
    assert board["candidate"]["config_version"] == 2


def test_read_scoreboard_missing_file_returns_empty(tmp_path):
    assert read_scoreboard(tmp_path / "nope.jsonl") == {}
