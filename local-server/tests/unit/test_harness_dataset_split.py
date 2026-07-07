"""Unit tests for the fixed dev/holdout split and per-scenario ontology context.

No I/O, no database, no infrastructure imports.
"""

import pytest

from tests.integration.pipelines._harness.dataset_split import (
    INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    SCENARIO_DISPOSITION,
    SCENARIO_ONTOLOGY,
    OntologyContext,
    ScenarioDisposition,
    disposition_for,
    ontology_context_for,
    split_for,
)


class TestSplitFor:
    def test_dev_scenario_returns_dev(self):
        assert split_for("async_patterns") == "dev"

    def test_holdout_scenario_returns_holdout(self):
        assert split_for("reactive_programming") == "holdout"

    def test_unassigned_scenario_raises(self):
        with pytest.raises(ValueError, match="not assigned to the dev/holdout split"):
            split_for("basic")


class TestOntologyContextFor:
    def test_every_scenario_is_mapped(self):
        for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.PLACEHOLDER

    def test_dev_and_holdout_scenarios_all_mapped(self):
        for scenario in INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.PLACEHOLDER

    def test_unmapped_scenario_raises(self):
        with pytest.raises(ValueError, match="no assigned ontology context"):
            ontology_context_for("not_a_real_scenario")

    def test_scenario_ontology_keys_match_the_fixed_split(self):
        assert set(SCENARIO_ONTOLOGY.keys()) == set(INDIVIDUAL_EXTRACTION_SCENARIOS)

    def test_all_18_scenarios_currently_placeholder(self):
        assert len(SCENARIO_ONTOLOGY) == 18
        assert all(v == OntologyContext.PLACEHOLDER for v in SCENARIO_ONTOLOGY.values())


class TestDispositionFor:
    def test_every_scenario_has_a_recorded_disposition(self):
        for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS:
            disposition_for(scenario)  # raises if missing

    def test_scenario_disposition_keys_match_the_fixed_split(self):
        assert set(SCENARIO_DISPOSITION.keys()) == set(INDIVIDUAL_EXTRACTION_SCENARIOS)

    def test_all_18_legacy_scenarios_kept_as_separate_context(self):
        # Phase 3 decision: none of the 18 pre-import scenarios are retired
        # or relabeled against the DR ontology -- see
        # LEGACY_CORPUS_DISPOSITION.md for the rationale.
        assert len(SCENARIO_DISPOSITION) == 18
        assert all(v == ScenarioDisposition.SEPARATE_CONTEXT for v in SCENARIO_DISPOSITION.values())

    def test_unmapped_scenario_raises(self):
        with pytest.raises(ValueError, match="no recorded legacy-corpus disposition"):
            disposition_for("not_a_real_scenario")

    def test_disposition_and_ontology_context_agree_for_every_scenario(self):
        # A SEPARATE_CONTEXT disposition should only ever be paired with a
        # non-DR ontology context; nothing marked RELABELED should still be
        # graded against the placeholder.
        for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS:
            disposition = disposition_for(scenario)
            context = ontology_context_for(scenario)
            if disposition == ScenarioDisposition.SEPARATE_CONTEXT:
                assert context != OntologyContext.DR_SPEC
            if disposition == ScenarioDisposition.RELABELED:
                assert context == OntologyContext.DR_SPEC
