"""
What the tournament measures is chosen like any run (scripts/quality_tournament.py):
its benchmark pass takes an implementation and a configuration, its variants
say which implementation, configuration and model they run, its telemetry and
digest are labeled with what ran, and its stale-cassette gate and the
triple-corpus guard follow the chosen target.

Nothing here loads a model or replays a corpus.
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

import scripts.quality_tournament as quality_tournament
from scripts import benchmark_replay
from scripts.benchmark_replay import DocumentResult, resolve_target, summarize
from scripts.quality_tournament import (
    Variant,
    _amain,
    _emit_scoreboard_row,
    _guard,
    _make_default_variant,
    _render_benchmark_section,
    _render_scoreboard_digest,
    _render_stale_section,
    _stale_for_target,
    _write_benchmark_report,
    triple_corpus_target,
)
from tests.integration.pipelines._harness.report import MetricsEmitter

TWO_PASS = "default"
FIND_THEN_TYPE = "find_then_type"
_GROUPS = ("dev", "holdout", "bootstrap", "wave4", "arxiv")


def _row(variant: str, strict_f1: float = 0.93, **ran: str) -> dict:
    """A variant's result as `_run_variant` returns it, with the keys the renderers read."""
    metrics = {
        "strict_f1": strict_f1,
        "soft_f1": strict_f1 + 0.01,
        "candidate_recall": 1.0,
        "predicate_recall": 1.0,
        "label_accuracy_strict": 1.0,
        "label_accuracy_soft": 1.0,
    }
    return {
        "variant": variant,
        "implementation": ran.get("implementation", TWO_PASS),
        "configuration": ran.get("configuration", "extraction-openrouter-default"),
        "model": ran.get("model", "google/gemini-3-flash-preview"),
        "tuned_knobs": {},
        "error_report_json": "report.json",
        **{group: dict(metrics) for group in _GROUPS},
    }


def _variant(name: str, implementation: str) -> Variant:
    async def run_scenario(config, scenario):
        return []

    return Variant(
        name=name,
        base_config={},
        knob_space={},
        run_scenario=run_scenario,
        implementation=implementation,
    )


class TestWhatTheVariantsRun:
    def test_the_default_variants_run_the_registered_implementation_with_its_recorded_model(self):
        target = triple_corpus_target()
        implementations, configurations = benchmark_replay.pipeline_registries()
        registered = configurations.get_latest(
            benchmark_replay.PIPELINE_TYPE, TWO_PASS, "extraction-openrouter-default"
        )

        assert target.implementation == TWO_PASS
        assert target.configuration == "extraction-openrouter-default"
        assert target.model == registered.config["model"]
        for grounding, name in ((False, "default"), (True, "default+grounding")):
            variant = _make_default_variant(None, grounding=grounding)
            assert variant.name == name
            assert variant.implementation == TWO_PASS
            assert variant.configuration == target.configuration
            assert variant.model == target.model

    def test_no_variant_and_no_helper_of_the_removed_grounded_variant_remains(self):
        assert not [name for name in dir(quality_tournament) if "grounded" in name.lower()]
        assert not hasattr(quality_tournament, "DEFAULT_PIPELINE_MODEL")


class TestGuard:
    def test_the_guard_is_the_row_of_the_variant_that_runs_the_target(self):
        results = [_row("default+grounding", 0.5), _row("default", 0.93), _row("open_v1", 0.03)]
        guard = _guard(results, {}, resolve_target(TWO_PASS))

        assert guard["applies"] is True
        assert (guard["variant"], guard["status"]) == ("default", "scored")
        assert guard["strict_f1"] == 0.93
        assert guard["soft_f1"] == pytest.approx(0.94)
        assert guard["model"] == "google/gemini-3-flash-preview"

    def test_the_guard_does_not_apply_to_an_implementation_no_variant_runs(self):
        """The `default` row is there to be read, and is not taken for find_then_type's."""
        guard = _guard([_row("default", 0.93)], {}, resolve_target(FIND_THEN_TYPE))

        assert guard["applies"] is False
        assert "find_then_type" in guard["reason"]
        assert "strict_f1" not in guard

    def test_a_guard_that_applies_but_has_no_score_says_why(self):
        target = resolve_target(TWO_PASS)
        assert _guard([_row("open_v1")], {}, target) == {
            "applies": True,
            "variant": "default",
            "status": "not_registered",
        }
        stale = {"default": {"calls": 17, "misses": 3}}
        assert _guard([_row("default")], stale, target)["status"] == "stale"
        assert "strict_f1" not in _guard([_row("default")], stale, target)


class TestStaleGate:
    VARIANTS = {
        "default": _variant("default", TWO_PASS),
        "default+grounding": _variant("default+grounding", TWO_PASS),
        "open_v1": _variant("open_v1", "open_v1"),
    }

    def test_only_variants_that_run_the_target_gate_the_run(self):
        stale = {name: {"calls": 4, "misses": 1} for name in ("default+grounding", "open_v1")}

        assert _stale_for_target(stale, self.VARIANTS, resolve_target(TWO_PASS)) == [
            "default+grounding"
        ]
        assert _stale_for_target(stale, self.VARIANTS, resolve_target(FIND_THEN_TYPE)) == []

    def test_a_stale_benchmark_recording_is_named_with_the_command_that_records_it(self):
        target = resolve_target(FIND_THEN_TYPE)
        results = [
            DocumentResult("edit_check", "stale", calls=40, misses=12),
            DocumentResult("gitlab_architecture", "not_recorded"),
        ]
        section = _render_stale_section({}, results, target)

        assert section.startswith("## STALE CASSETTES")
        assert "`find_then_type` with `extraction-find-then-type`: 12 of 40" in section
        assert f"benchmark_replay.py --record --spend {target.flags}" in section
        assert "record_default_cassettes" not in section

    def test_nothing_stale_renders_nothing(self):
        scored = [DocumentResult("edit_check", "not_recorded")]
        assert _render_stale_section({}, scored, resolve_target(TWO_PASS)) == ""
        assert _render_stale_section({}) == ""


class TestLabels:
    def test_a_scoreboard_row_holds_the_model_and_configuration_that_ran(self, tmp_path):
        emitter = MetricsEmitter(tmp_path)
        _emit_scoreboard_row(emitter, "dev", _row("default+grounding"), {"strict_f1": 0.9})
        target = resolve_target(FIND_THEN_TYPE)
        _emit_scoreboard_row(emitter, "benchmark_dev", target.describe(), {"typed_f1": 0.46})

        (metrics_file,) = tmp_path.iterdir()
        variant_row, benchmark_row = (
            json.loads(line) for line in metrics_file.read_text().splitlines()
        )
        assert variant_row["model"] == "google/gemini-3-flash-preview"
        assert variant_row["config_ref"] == "extraction-openrouter-default"
        assert variant_row["implementation"] == TWO_PASS
        assert variant_row["variant"] == "default+grounding"
        assert variant_row["fixture_id"] == "dev"
        assert benchmark_row["model"] == target.model
        assert benchmark_row["config_ref"] == "extraction-find-then-type"
        assert benchmark_row["implementation"] == FIND_THEN_TYPE
        assert "variant" not in benchmark_row
        assert benchmark_row["metrics"] == {"typed_f1": 0.46}

    def test_a_label_never_replaces_a_field_of_the_row(self, tmp_path):
        MetricsEmitter(tmp_path).emit(
            pipeline_type="t",
            fixture_id="dev",
            model="m",
            config_ref="c",
            config_version=1,
            metrics={},
            labels={"model": "other", "variant": "v"},
        )
        (metrics_file,) = tmp_path.iterdir()
        row = json.loads(metrics_file.read_text())
        assert (row["model"], row["variant"]) == ("m", "v")

    def test_the_digest_says_what_each_variant_ran_and_decides_no_promotion(self):
        results = [_row("default"), _row("open_v1", 0.03, implementation="open_v1")]
        digest = _render_scoreboard_digest("run-1", results, {})

        assert "## What each variant ran" in digest
        assert (
            "- **default**: implementation `default`, configuration "
            "`extraction-openrouter-default`, model `google/gemini-3-flash-preview`"
        ) in digest
        assert "- **open_v1**: implementation `open_v1`" in digest
        assert "A/B Evaluation" not in digest and "grounded_v1" not in digest

    @pytest.mark.parametrize("implementation", [TWO_PASS, FIND_THEN_TYPE])
    def test_the_benchmark_section_is_headed_by_what_ran(self, implementation, tmp_path):
        target = resolve_target(implementation)
        results = [DocumentResult("edit_check", "not_recorded")]
        guard = _guard([_row("default", 0.93)], {}, target)
        section = _render_benchmark_section(
            results, summarize(results, target), tmp_path / "b.json", target, guard
        )

        assert section.startswith(
            f"## Benchmark: `{implementation}` with `{target.configuration}` ({target.model})"
        )
        assert f"benchmark_replay.py --record --spend {target.flags}" in section
        assert f"`{benchmark_replay.cassette_dir(target).name}/`" in section
        if implementation == FIND_THEN_TYPE:
            assert "Triple-corpus guard: not applicable" in section
            assert "0.930" not in section
        else:
            assert "Triple-corpus guard: the `default` variant's dev strict-F1 0.930" in section

    def test_the_benchmark_report_says_what_ran_and_carries_the_guard(self, tmp_path, monkeypatch):
        monkeypatch.setattr(quality_tournament, "_EXPERIMENTS_REPORTS_DIR", tmp_path)
        target = resolve_target(FIND_THEN_TYPE)
        results = [DocumentResult("edit_check", "not_recorded")]
        guard = _guard([_row("default")], {}, target)
        path = _write_benchmark_report("run-1", results, summarize(results, target), guard)

        report = json.loads(path.read_text())
        assert report["implementation"] == FIND_THEN_TYPE
        assert report["configuration"] == "extraction-find-then-type"
        assert report["model"] == target.model
        assert report["status"] == "not_recorded"
        assert report["guard"]["applies"] is False


class TestTargetFlags:
    @pytest.mark.parametrize(
        "implementation, configuration",
        [("no_such", None), (FIND_THEN_TYPE, "extraction-default"), ("open_v1", None)],
    )
    def test_a_target_that_cannot_run_ends_the_tournament_before_it_loads_anything(
        self, implementation, configuration, capsys
    ):
        args = argparse.Namespace(implementation=implementation, configuration=configuration)
        assert asyncio.run(_amain(args)) == 1
        assert "ERROR" in capsys.readouterr().out

    def test_the_flags_reach_the_tournament(self, monkeypatch):
        seen = {}

        async def fake_amain(args):
            seen.update(vars(args))
            return 0

        monkeypatch.setattr(quality_tournament, "_amain", fake_amain)
        monkeypatch.setattr(
            sys,
            "argv",
            ["quality_tournament.py", "--implementation", FIND_THEN_TYPE, "--configuration", "c"],
        )
        assert quality_tournament.main() == 0
        assert (seen["implementation"], seen["configuration"]) == (FIND_THEN_TYPE, "c")
        assert seen["pipeline"] == "individual"

        monkeypatch.setattr(sys, "argv", ["quality_tournament.py"])
        quality_tournament.main()
        assert (seen["implementation"], seen["configuration"]) == (None, None)
