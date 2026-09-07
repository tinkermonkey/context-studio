"""
Tests for the Wave 4 informal-prose diagnostic pass in
scripts/quality_tournament.py (#1109 Phase 8).

Uses a fake `Variant.run_scenario` (no spaCy/embedding models required) over
the real `informal_*` fixtures, so these run fast and offline like
test_quality_tournament_bootstrap.py's synthetic-evaluator tests.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from scripts.quality_tournament import (
    Variant,
    _aggregate,
    _build_scenario_reports,
    _build_wave4_reports,
)
from tests.fixtures.pipeline_fixtures import load_expected_output
from tests.integration.pipelines._harness.dataset_split import (
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
)


def _perfect_variant() -> Variant:
    """A fake variant that always returns exactly the expected triples (perfect score)."""

    async def run_scenario(config, scenario):
        expected = load_expected_output("individual_extraction", scenario)
        return expected.get("result", {}).get("triples", [])

    return Variant(name="fake_perfect", base_config={}, knob_space={}, run_scenario=run_scenario)


def _empty_variant() -> Variant:
    """A fake variant that never returns any triples (zero score)."""

    async def run_scenario(config, scenario):
        return []

    return Variant(name="fake_empty", base_config={}, knob_space={}, run_scenario=run_scenario)


@pytest.mark.asyncio
class TestBuildWave4Reports:
    async def test_covers_every_wave4_scenario_tagged_with_the_wave4_split(self):
        reports = await _build_wave4_reports(_perfect_variant(), {}, embed_fn=None)
        assert {r.scenario for r in reports} == set(WAVE4_INFORMAL_SCENARIOS)
        assert all(r.split == "wave4" for r in reports)

    async def test_perfect_variant_scores_wave4_strict_f1_of_one(self):
        reports = await _build_wave4_reports(_perfect_variant(), {}, embed_fn=None)
        metrics = _aggregate(reports, "wave4")
        assert metrics["strict_f1"] == 1.0
        assert metrics["soft_f1"] == 1.0

    async def test_empty_variant_scores_wave4_strict_f1_of_zero(self):
        reports = await _build_wave4_reports(_empty_variant(), {}, embed_fn=None)
        metrics = _aggregate(reports, "wave4")
        assert metrics["strict_f1"] == 0.0


@pytest.mark.asyncio
class TestWave4ExclusionFromDevHoldout:
    async def test_wave4_scenarios_never_appear_in_the_full_corpus_scenario_reports(
        self,
    ):
        """
        Phase 8 requirement: Loop B continues passing only the dev/holdout
        scenario lists to the aggregation that feeds the Loop C accept gate.
        `_build_scenario_reports` (the source of `dev`/`holdout` in
        `_run_variant`'s return value) must never include a Wave 4 scenario.
        """
        reports = await _build_scenario_reports(_perfect_variant(), {}, embed_fn=None)
        scenarios = {r.scenario for r in reports}
        assert scenarios == set(INDIVIDUAL_EXTRACTION_SCENARIOS)
        assert scenarios.isdisjoint(WAVE4_INFORMAL_SCENARIOS)
        assert all(r.split in ("dev", "holdout") for r in reports)

    async def test_changing_wave4_scores_does_not_change_dev_holdout_aggregation(self):
        """
        A candidate that is perfect on dev/holdout but empty on Wave 4 (or
        vice versa) must score identically on dev/holdout either way -- the
        two evaluation passes are fully independent.
        """
        dev_holdout_reports = await _build_scenario_reports(_perfect_variant(), {}, embed_fn=None)
        dev_metrics = _aggregate(dev_holdout_reports, "dev")
        holdout_metrics = _aggregate(dev_holdout_reports, "holdout")

        wave4_reports_empty = await _build_wave4_reports(_empty_variant(), {}, embed_fn=None)
        wave4_reports_perfect = await _build_wave4_reports(_perfect_variant(), {}, embed_fn=None)
        assert _aggregate(wave4_reports_empty, "wave4")["strict_f1"] == 0.0
        assert _aggregate(wave4_reports_perfect, "wave4")["strict_f1"] == 1.0

        # dev/holdout metrics themselves came from a wholly separate corpus walk
        # and are unaffected by either wave4 outcome above.
        assert dev_metrics["strict_f1"] == 1.0
        assert holdout_metrics["strict_f1"] == 1.0
