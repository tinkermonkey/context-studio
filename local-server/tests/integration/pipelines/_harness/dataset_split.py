"""Fixed dev/holdout scenario split for individual_extraction quality fixtures (§3.3).

The 10 hand-labeled scenarios under
`tests/integration/fixtures/pipelines/individual_extraction/` are today both the
tuning set and the eval set, which lets the closed loop overfit. This module
fixes a 7 (dev) / 3 (holdout) split by name: loops optimize on dev, holdout is
scored on every run but never used for selection (see the accept gate in
`documentation/karpathy_loop_design.md` §6).

The `basic/` fixture directory under the same parent is a minimal contract-test
fixture (input.json + expected.json only, matching the same convention used by
every other pipeline type's `basic/` scenario) and is intentionally excluded —
it is not one of the 10 hand-labeled quality-corpus scenarios and carries no
GT triples to score against.

The split is assigned alphabetically for determinism and reproducibility; the
10 scenarios do not differ enough in size or difficulty to warrant a more
elaborate stratification at this corpus size.
"""

INDIVIDUAL_EXTRACTION_DEV_SCENARIOS: list[str] = [
    "async_patterns",
    "clean_code",
    "design_patterns",
    "distributed_systems",
    "domain_driven_design",
    "microservices_architecture",
    "object_oriented_design",
]

INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS: list[str] = [
    "reactive_programming",
    "service_oriented",
    "testing_strategies",
]

# Canonical ordering: dev scenarios first, then holdout. Equivalent to the
# full 10-scenario corpus used by the quality test suites.
INDIVIDUAL_EXTRACTION_SCENARIOS: list[str] = (
    INDIVIDUAL_EXTRACTION_DEV_SCENARIOS + INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS
)


def split_for(scenario: str) -> str:
    """
    Return which split a scenario belongs to: "dev" or "holdout".

    Raises:
        ValueError: If the scenario is not part of the fixed split (e.g. a
            future promoted scenario that hasn't been assigned yet, or the
            non-quality `basic/` contract fixture).
    """
    if scenario in INDIVIDUAL_EXTRACTION_DEV_SCENARIOS:
        return "dev"
    if scenario in INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS:
        return "holdout"
    raise ValueError(f"Scenario '{scenario}' is not assigned to the dev/holdout split")
