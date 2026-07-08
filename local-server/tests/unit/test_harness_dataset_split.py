"""Unit tests for the fixed dev/holdout split and per-scenario ontology context.

No I/O, no database, no infrastructure imports.
"""

import pytest

from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS,
    SCENARIO_DISPOSITION,
    SCENARIO_ONTOLOGY,
    WAVE2_SME_HOLDOUT_SCENARIOS,
    WAVE2_SME_SCENARIOS,
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
    def test_every_legacy_scenario_is_mapped_to_placeholder(self):
        for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.PLACEHOLDER

    def test_dev_and_holdout_legacy_scenarios_all_mapped(self):
        for scenario in INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS:
            if scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS:
                assert ontology_context_for(scenario) == OntologyContext.PLACEHOLDER
            else:
                assert ontology_context_for(scenario) == OntologyContext.DR_SPEC

    def test_unmapped_scenario_raises(self):
        with pytest.raises(ValueError, match="no assigned ontology context"):
            ontology_context_for("not_a_real_scenario")

    def test_scenario_ontology_keys_match_the_fixed_split_plus_bootstrap_scenarios(self):
        assert set(SCENARIO_ONTOLOGY.keys()) == set(INDIVIDUAL_EXTRACTION_SCENARIOS) | set(
            DR_BOOTSTRAP_SCENARIOS
        )

    def test_all_18_legacy_scenarios_currently_placeholder(self):
        legacy_ontology = {
            scenario: SCENARIO_ONTOLOGY[scenario]
            for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS
        }
        assert len(legacy_ontology) == 18
        assert all(v == OntologyContext.PLACEHOLDER for v in legacy_ontology.values())


class TestWave2SmeScenarios:
    def test_wave2_scenarios_are_graded_against_dr_spec_not_placeholder(self):
        for scenario in WAVE2_SME_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.DR_SPEC

    def test_wave2_scenarios_are_included_in_the_dev_holdout_split(self):
        # Unlike Wave 1's bootstrap scenarios, Wave 2 scenarios ARE folded
        # into the fixed dev/holdout split (design doc §6, #1109 Phase 6
        # acceptance criteria).
        for scenario in WAVE2_SME_SCENARIOS:
            assert scenario in INDIVIDUAL_EXTRACTION_SCENARIOS
            split_for(scenario)  # raises if not assigned

    def test_wave2_holdout_scenarios_land_in_holdout(self):
        for scenario in WAVE2_SME_HOLDOUT_SCENARIOS:
            assert split_for(scenario) == "holdout"

    def test_wave2_scenarios_disjoint_from_bootstrap_scenarios(self):
        assert set(WAVE2_SME_SCENARIOS).isdisjoint(DR_BOOTSTRAP_SCENARIOS)


class TestDrBootstrapScenarios:
    def test_bootstrap_scenarios_are_graded_against_dr_spec_not_placeholder(self):
        for scenario in DR_BOOTSTRAP_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.DR_SPEC

    def test_bootstrap_scenarios_are_excluded_from_the_dev_holdout_split(self):
        # Wave 1 scenarios are a distinct diagnostic group, not folded into
        # the fixed dev/holdout split (design doc §5).
        for scenario in DR_BOOTSTRAP_SCENARIOS:
            assert scenario not in INDIVIDUAL_EXTRACTION_SCENARIOS
            with pytest.raises(ValueError, match="not assigned to the dev/holdout split"):
                split_for(scenario)


class TestDispositionFor:
    def test_every_legacy_scenario_has_a_recorded_disposition(self):
        for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS:
            disposition_for(scenario)  # raises if missing

    def test_scenario_disposition_keys_match_the_legacy_split(self):
        assert set(SCENARIO_DISPOSITION.keys()) == set(LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS)

    def test_all_18_legacy_scenarios_kept_as_separate_context(self):
        # Phase 3 decision: none of the 18 pre-import scenarios are retired
        # or relabeled against the DR ontology -- see
        # LEGACY_CORPUS_DISPOSITION.md for the rationale.
        assert len(SCENARIO_DISPOSITION) == 18
        assert all(v == ScenarioDisposition.SEPARATE_CONTEXT for v in SCENARIO_DISPOSITION.values())

    def test_unmapped_scenario_raises(self):
        with pytest.raises(ValueError, match="no recorded legacy-corpus disposition"):
            disposition_for("not_a_real_scenario")

    def test_wave2_scenario_has_no_legacy_disposition(self):
        # Wave 2 scenarios are new, DR-native ground truth -- not legacy
        # scenarios carrying a re-labeling/retirement/separate-context
        # decision, so disposition_for must raise for them too.
        for scenario in WAVE2_SME_SCENARIOS:
            with pytest.raises(ValueError, match="no recorded legacy-corpus disposition"):
                disposition_for(scenario)

    def test_disposition_and_ontology_context_agree_for_every_legacy_scenario(self):
        # A SEPARATE_CONTEXT disposition should only ever be paired with a
        # non-DR ontology context; nothing marked RELABELED should still be
        # graded against the placeholder.
        for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS:
            disposition = disposition_for(scenario)
            context = ontology_context_for(scenario)
            if disposition == ScenarioDisposition.SEPARATE_CONTEXT:
                assert context != OntologyContext.DR_SPEC
            if disposition == ScenarioDisposition.RELABELED:
                assert context == OntologyContext.DR_SPEC
