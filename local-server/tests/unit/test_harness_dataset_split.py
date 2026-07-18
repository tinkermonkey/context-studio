"""Unit tests for the fixed dev/holdout split and per-scenario ontology context.

No I/O, no database, no infrastructure imports.
"""

import pytest

from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS,
    RELABELED_ARXIV_DEV_SCENARIOS,
    RETIRED_ARXIV_SCENARIOS,
    SCENARIO_DISPOSITION,
    SCENARIO_ONTOLOGY,
    WAVE2_SME_HOLDOUT_SCENARIOS,
    WAVE2_SME_SCENARIOS,
    WAVE3_SME_HOLDOUT_SCENARIOS,
    WAVE3_SME_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
    OntologyContext,
    ScenarioDisposition,
    disposition_for,
    ontology_context_for,
    split_for,
)


class TestSplitFor:
    def test_dev_scenario_returns_dev(self):
        assert split_for("sme_waypoint_product_vision") == "dev"

    def test_holdout_scenario_returns_holdout(self):
        assert split_for("sme_waypoint_technician_ux") == "holdout"

    def test_unassigned_scenario_raises(self):
        with pytest.raises(ValueError, match="not assigned to the dev/holdout split"):
            split_for("basic")

    def test_placeholder_legacy_scenarios_are_eliminated_from_the_scored_split(self):
        # The software-arch legacy scenarios run against the throwaway placeholder
        # ontology (free-form concept extraction, not grounded identification) and
        # are eliminated from the scored corpus — the split is DR-grounded only.
        for scenario in ("async_patterns", "clean_code", "design_patterns", "reactive_programming"):
            assert scenario not in INDIVIDUAL_EXTRACTION_SCENARIOS
            with pytest.raises(ValueError, match="not assigned to the dev/holdout split"):
                split_for(scenario)

    def test_every_scored_scenario_is_dr_grounded(self):
        # The whole point of the elimination: nothing in the scored split is
        # graded against the placeholder ontology anymore.
        for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.DR_SPEC


class TestOntologyContextFor:
    def test_legacy_scenario_ontology_contexts(self):
        # Software-arch + retired arxiv keep the placeholder context; the 3
        # DR-relabeled arxiv scenarios are graded against the DR spec.
        for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS:
            expected = (
                OntologyContext.DR_SPEC
                if scenario in RELABELED_ARXIV_DEV_SCENARIOS
                else OntologyContext.PLACEHOLDER
            )
            assert ontology_context_for(scenario) == expected

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
        # SCENARIO_ONTOLOGY records every legacy scenario for the disposition
        # record, including the placeholder software-arch scenarios and the
        # retired arxiv scenarios that are NOT in the scored split. Only the
        # relabeled arxiv scenarios (of the legacy set) are scored.
        assert set(SCENARIO_ONTOLOGY.keys()) == (
            set(INDIVIDUAL_EXTRACTION_SCENARIOS)
            | set(LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS)
            | set(DR_BOOTSTRAP_SCENARIOS)
            | set(WAVE4_INFORMAL_SCENARIOS)
        )

    def test_all_18_legacy_scenarios_recorded_with_context(self):
        legacy_ontology = {
            scenario: SCENARIO_ONTOLOGY[scenario]
            for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS
        }
        assert len(legacy_ontology) == 18
        # 15 placeholder (10 software-arch + 5 retired arxiv), 3 DR_SPEC (relabeled).
        dr = {s for s, v in legacy_ontology.items() if v == OntologyContext.DR_SPEC}
        assert dr == set(RELABELED_ARXIV_DEV_SCENARIOS)
        assert all(
            legacy_ontology[s] == OntologyContext.PLACEHOLDER
            for s in legacy_ontology
            if s not in RELABELED_ARXIV_DEV_SCENARIOS
        )


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


class TestWave3SmeScenarios:
    def test_wave3_scenarios_are_graded_against_dr_spec_not_placeholder(self):
        for scenario in WAVE3_SME_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.DR_SPEC

    def test_wave3_scenarios_are_included_in_the_dev_holdout_split(self):
        # Same as Wave 2: Wave 3 scenarios ARE folded into the fixed
        # dev/holdout split (design doc §7, #1109 Phase 7 acceptance
        # criteria).
        for scenario in WAVE3_SME_SCENARIOS:
            assert scenario in INDIVIDUAL_EXTRACTION_SCENARIOS
            split_for(scenario)  # raises if not assigned

    def test_wave3_holdout_scenarios_land_in_holdout(self):
        for scenario in WAVE3_SME_HOLDOUT_SCENARIOS:
            assert split_for(scenario) == "holdout"

    def test_wave3_scenarios_disjoint_from_bootstrap_scenarios(self):
        assert set(WAVE3_SME_SCENARIOS).isdisjoint(DR_BOOTSTRAP_SCENARIOS)

    def test_wave3_scenarios_disjoint_from_wave2_scenarios(self):
        assert set(WAVE3_SME_SCENARIOS).isdisjoint(WAVE2_SME_SCENARIOS)


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


class TestWave4InformalScenarios:
    def test_wave4_scenarios_are_graded_against_dr_spec_not_placeholder(self):
        for scenario in WAVE4_INFORMAL_SCENARIOS:
            assert ontology_context_for(scenario) == OntologyContext.DR_SPEC

    def test_wave4_scenarios_are_excluded_from_the_dev_holdout_split(self):
        # Wave 4 scenarios are a distinct diagnostic group, like Wave 1's
        # bootstrap scenarios, not folded into the fixed dev/holdout split
        # (design doc §8, #1109 Phase 8 acceptance criteria: Wave 4 must
        # never gate a Wave 0-3 accept/reject decision).
        for scenario in WAVE4_INFORMAL_SCENARIOS:
            assert scenario not in INDIVIDUAL_EXTRACTION_SCENARIOS
            with pytest.raises(ValueError, match="not assigned to the dev/holdout split"):
                split_for(scenario)

    def test_wave4_scenarios_disjoint_from_bootstrap_scenarios(self):
        assert set(WAVE4_INFORMAL_SCENARIOS).isdisjoint(DR_BOOTSTRAP_SCENARIOS)

    def test_wave4_scenarios_disjoint_from_wave2_and_wave3_scenarios(self):
        assert set(WAVE4_INFORMAL_SCENARIOS).isdisjoint(WAVE2_SME_SCENARIOS)
        assert set(WAVE4_INFORMAL_SCENARIOS).isdisjoint(WAVE3_SME_SCENARIOS)


class TestDispositionFor:
    def test_every_legacy_scenario_has_a_recorded_disposition(self):
        for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS:
            disposition_for(scenario)  # raises if missing

    def test_scenario_disposition_keys_match_the_legacy_split(self):
        assert set(SCENARIO_DISPOSITION.keys()) == set(LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS)

    def test_legacy_dispositions_reflect_the_arxiv_review(self):
        # After the NEEDS_HUMAN_REVIEW.md disposition pass: all 18 legacy
        # scenarios are recorded — the 5 reviewed arxiv scenarios are RETIRED, the
        # 3 relabeled arxiv scenarios are RELABELED (DR-native GT), and the 10
        # software-arch scenarios stay SEPARATE_CONTEXT. See
        # LEGACY_CORPUS_DISPOSITION.md.
        assert len(SCENARIO_DISPOSITION) == 18
        retired = {s for s, d in SCENARIO_DISPOSITION.items() if d == ScenarioDisposition.RETIRED}
        relabeled = {s for s, d in SCENARIO_DISPOSITION.items() if d == ScenarioDisposition.RELABELED}
        assert retired == set(RETIRED_ARXIV_SCENARIOS)
        assert relabeled == set(RELABELED_ARXIV_DEV_SCENARIOS)
        assert all(
            SCENARIO_DISPOSITION[s] == ScenarioDisposition.SEPARATE_CONTEXT
            for s in SCENARIO_DISPOSITION
            if s not in RETIRED_ARXIV_SCENARIOS and s not in RELABELED_ARXIV_DEV_SCENARIOS
        )

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

    def test_wave3_scenario_has_no_legacy_disposition(self):
        # Same rationale as Wave 2 -- Wave 3 scenarios are new, DR-native
        # ground truth, not legacy scenarios subject to a disposition.
        for scenario in WAVE3_SME_SCENARIOS:
            with pytest.raises(ValueError, match="no recorded legacy-corpus disposition"):
                disposition_for(scenario)

    def test_wave4_scenario_has_no_legacy_disposition(self):
        # Same rationale as Wave 2/3 -- Wave 4 scenarios are new, DR-native
        # ground truth, not legacy scenarios subject to a disposition.
        for scenario in WAVE4_INFORMAL_SCENARIOS:
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
