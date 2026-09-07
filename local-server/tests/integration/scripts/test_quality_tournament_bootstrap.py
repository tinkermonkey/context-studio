"""
Tests for the Wave 1 DR bootstrap-scenario diagnostic pass in
scripts/quality_tournament.py (#1109 Phase 5).

Uses a fake `Variant.run_scenario` (no spaCy/embedding models required) over
the real `dr_bootstrap_*` fixtures, so these run fast and offline like
test_quality_loop.py's synthetic-evaluator tests.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from scripts.quality_tournament import (
    Variant,
    _aggregate,
    _build_bootstrap_reports,
    _build_scenario_reports,
)
from tests.fixtures.pipeline_fixtures import load_expected_output
from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
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
class TestBuildBootstrapReports:
    async def test_covers_every_bootstrap_scenario_tagged_with_the_bootstrap_split(
        self,
    ):
        reports = await _build_bootstrap_reports(_perfect_variant(), {}, embed_fn=None)
        assert {r.scenario for r in reports} == set(DR_BOOTSTRAP_SCENARIOS)
        assert all(r.split == "bootstrap" for r in reports)

    async def test_perfect_variant_scores_bootstrap_strict_f1_of_one(self):
        reports = await _build_bootstrap_reports(_perfect_variant(), {}, embed_fn=None)
        metrics = _aggregate(reports, "bootstrap")
        assert metrics["strict_f1"] == 1.0
        assert metrics["soft_f1"] == 1.0

    async def test_empty_variant_scores_bootstrap_strict_f1_of_zero(self):
        reports = await _build_bootstrap_reports(_empty_variant(), {}, embed_fn=None)
        metrics = _aggregate(reports, "bootstrap")
        assert metrics["strict_f1"] == 0.0


@pytest.mark.asyncio
class TestBootstrapExclusionFromDevHoldout:
    async def test_bootstrap_scenarios_never_appear_in_the_full_corpus_scenario_reports(
        self,
    ):
        """
        Phase 5 requirement: Loop B continues passing only the dev/holdout
        scenario lists to the aggregation that feeds the Loop C accept gate.
        `_build_scenario_reports` (the source of `dev`/`holdout` in
        `_run_variant`'s return value) must never include a bootstrap scenario.
        """
        reports = await _build_scenario_reports(_perfect_variant(), {}, embed_fn=None)
        scenarios = {r.scenario for r in reports}
        assert scenarios == set(INDIVIDUAL_EXTRACTION_SCENARIOS)
        assert scenarios.isdisjoint(DR_BOOTSTRAP_SCENARIOS)
        assert all(r.split in ("dev", "holdout") for r in reports)

    async def test_changing_bootstrap_scores_does_not_change_dev_holdout_aggregation(
        self,
    ):
        """
        A candidate that is perfect on dev/holdout but empty on bootstrap (or
        vice versa) must score identically on dev/holdout either way -- the
        two evaluation passes are fully independent.
        """
        dev_holdout_reports = await _build_scenario_reports(_perfect_variant(), {}, embed_fn=None)
        dev_metrics = _aggregate(dev_holdout_reports, "dev")
        holdout_metrics = _aggregate(dev_holdout_reports, "holdout")

        bootstrap_reports_empty = await _build_bootstrap_reports(
            _empty_variant(), {}, embed_fn=None
        )
        bootstrap_reports_perfect = await _build_bootstrap_reports(
            _perfect_variant(), {}, embed_fn=None
        )
        assert _aggregate(bootstrap_reports_empty, "bootstrap")["strict_f1"] == 0.0
        assert _aggregate(bootstrap_reports_perfect, "bootstrap")["strict_f1"] == 1.0

        # dev/holdout metrics themselves came from a wholly separate corpus walk
        # and are unaffected by either bootstrap outcome above.
        assert dev_metrics["strict_f1"] == 1.0
        assert holdout_metrics["strict_f1"] == 1.0
