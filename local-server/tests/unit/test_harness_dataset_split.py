"""Unit tests for the fixed dev/holdout split and per-scenario ontology context.

No I/O, no database, no infrastructure imports.
"""

import pytest

from tests.integration.pipelines._harness.dataset_split import (
    INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    SCENARIO_ONTOLOGY,
    OntologyContext,
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
