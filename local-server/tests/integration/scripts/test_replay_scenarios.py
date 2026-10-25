"""Tests that every replay-scenario call site uses the single `REPLAY_SCENARIOS` list (issue #1259).

The cassette recorders and the tournament's replay guards must agree exactly:
a recorder that skips a scenario the guard requires leaves the variant
permanently unregistered in the tournament.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts import record_default_cassettes, record_grounded_cassettes
from scripts.quality_tournament import _DEFAULT_REPLAY_SCENARIOS, _GROUNDED_REPLAY_SCENARIOS
from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    RELABELED_ARXIV_SCENARIOS,
    REPLAY_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
)


def test_replay_scenarios_is_the_ordered_union_of_the_four_groups():
    """`REPLAY_SCENARIOS` keeps the order and membership of the old hand-written union."""
    expected = (
        INDIVIDUAL_EXTRACTION_SCENARIOS
        + DR_BOOTSTRAP_SCENARIOS
        + WAVE4_INFORMAL_SCENARIOS
        + RELABELED_ARXIV_SCENARIOS
    )
    assert REPLAY_SCENARIOS == list(dict.fromkeys(expected))
    assert len(REPLAY_SCENARIOS) == len(set(REPLAY_SCENARIOS))


def test_all_call_sites_see_replay_scenarios():
    """Both recorders and both tournament replay guards use exactly `REPLAY_SCENARIOS`."""
    assert record_default_cassettes.union_scenarios() == REPLAY_SCENARIOS
    assert record_grounded_cassettes.union_scenarios() == REPLAY_SCENARIOS
    assert _DEFAULT_REPLAY_SCENARIOS == REPLAY_SCENARIOS
    assert _GROUNDED_REPLAY_SCENARIOS == REPLAY_SCENARIOS
