"""Fixed dev/holdout scenario split for individual_extraction quality fixtures (§3.3).

Also assigns each scenario an `OntologyContext` (`PLACEHOLDER` or `DR_SPEC`) —
which ontology it is graded against — per the per-scenario ontology context
gap identified against `documentation/karpathy_loop_dr_ontology_design.md`.
All 18 scenarios currently run against the placeholder ontology; a scenario
graded against the imported DR spec (e.g. a future `dr_bootstrap_*` scenario)
is added to `SCENARIO_ONTOLOGY` alongside its dev/holdout assignment.

The scenarios under `tests/integration/fixtures/pipelines/individual_extraction/`
would otherwise be both the tuning set and the eval set, which lets the closed
loop overfit. This module fixes a dev/holdout split by name: loops optimize on
dev, holdout is scored on every run but never used for selection (see the
accept gate in `documentation/karpathy_loop_design.md` §6).

The `basic/` fixture directory under the same parent is a minimal contract-test
fixture (input.json + expected.json only, matching the same convention used by
every other pipeline type's `basic/` scenario) and is intentionally excluded —
it is not one of the hand-labeled quality-corpus scenarios and carries no GT
triples to score against.

The corpus has two domains: 10 hand-labeled software-architecture-concept
scenarios (the original corpus), and 8 arxiv-abstract scenarios (`arxiv_*`,
promoted per §3.3 from previously-unused fixtures; their `expected.json` is
LLM-drafted and awaits human review — see
`tests/integration/fixtures/pipelines/individual_extraction/NEEDS_HUMAN_REVIEW.md`).
The split is stratified by domain and assigned alphabetically within each
domain for determinism and reproducibility, so both domains are represented in
both dev and holdout (a holdout drawn from only one domain would not exercise
cross-domain generalization). Within a domain, scenarios do not differ enough
in size or difficulty to warrant a more elaborate stratification at this
corpus size.

- Software-architecture-concept domain (10): first 7 alphabetically -> dev,
  last 3 -> holdout.
- Arxiv domain (8): first 6 alphabetically -> dev, last 2 -> holdout.

Overall: 13 dev / 5 holdout (18 total), close to the original 70/30 ratio.
"""

from enum import Enum

INDIVIDUAL_EXTRACTION_DEV_SCENARIOS: list[str] = [
    # Software-architecture-concept domain
    "async_patterns",
    "clean_code",
    "design_patterns",
    "distributed_systems",
    "domain_driven_design",
    "microservices_architecture",
    "object_oriented_design",
    # Arxiv domain
    "arxiv_byzantine_fault_tolerance",
    "arxiv_cloud_platform_landscape",
    "arxiv_cloud_provisioning",
    "arxiv_consensus_protocol_collaboration",
    "arxiv_crdt_networks",
    "arxiv_kubernetes_energy_monitoring",
]

INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS: list[str] = [
    # Software-architecture-concept domain
    "reactive_programming",
    "service_oriented",
    "testing_strategies",
    # Arxiv domain
    "arxiv_llm_research_lab",
    "arxiv_researcher_profile",
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


class OntologyContext(Enum):
    """Which ontology a scenario's ground truth is graded against."""

    PLACEHOLDER = "placeholder"
    DR_SPEC = "dr_spec"


# Every scenario in the fixed split runs against the throwaway 3-class
# placeholder ontology today. A scenario graded against the imported DR spec
# (see documentation/karpathy_loop_dr_ontology_design.md) is added here with
# OntologyContext.DR_SPEC when it lands.
SCENARIO_ONTOLOGY: dict[str, OntologyContext] = {
    scenario: OntologyContext.PLACEHOLDER for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS
}


def ontology_context_for(scenario: str) -> OntologyContext:
    """
    Return which ontology context a scenario is graded against.

    Raises:
        ValueError: If the scenario has no ontology assignment (e.g. a
            future promoted scenario that hasn't been assigned yet).
    """
    if scenario not in SCENARIO_ONTOLOGY:
        raise ValueError(f"Scenario '{scenario}' has no assigned ontology context")
    return SCENARIO_ONTOLOGY[scenario]
