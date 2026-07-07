"""Fixed dev/holdout scenario split for individual_extraction quality fixtures (§3.3).

Also assigns each scenario an `OntologyContext` (`PLACEHOLDER` or `DR_SPEC`) —
which ontology it is graded against — per the per-scenario ontology context
gap identified against `documentation/karpathy_loop_dr_ontology_design.md`.
All 18 legacy scenarios run against the placeholder ontology. The
`dr_bootstrap_*` scenarios (Wave 1, §5) are graded against the imported DR
spec and are added to `SCENARIO_ONTOLOGY` via `DR_BOOTSTRAP_SCENARIOS`, but
deliberately outside the dev/holdout split -- see that constant's docstring.

`SCENARIO_DISPOSITION` records the explicit, one-time decision made for each
of these 18 scenarios when the DR ontology import happened (#1109 Phase 3):
re-labeled against the DR ontology, retired, or kept as a separate,
non-DR-ontology context. See `ScenarioDisposition` and
`tests/integration/fixtures/pipelines/individual_extraction/LEGACY_CORPUS_DISPOSITION.md`.

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

# Wave 1 bootstrap scenarios (documentation/karpathy_loop_dr_ontology_design.md
# §5): one per qualifying prose source file discovered in
# documentation_robotics_viewer's dogfooded model by
# scripts/generate_dr_bootstrap_corpus.py. Graded against the Wave 0 DR spec
# import, never the placeholder. These are a distinct, always-reported
# diagnostic group -- deliberately NOT added to
# INDIVIDUAL_EXTRACTION_SCENARIOS / the dev-holdout split (too thin, several
# with single-digit or zero GT triples, to holdout-split meaningfully; see
# design doc §5). Only scenarios that currently exist on disk are listed
# here; a discovered-but-currently-missing source file (upstream drift) has
# no fixture directory and is therefore not registered until it reappears
# and the corpus is regenerated.
DR_BOOTSTRAP_SCENARIOS: list[str] = [
    "dr_bootstrap_claude",
    "dr_bootstrap_readme",
]

SCENARIO_ONTOLOGY.update({scenario: OntologyContext.DR_SPEC for scenario in DR_BOOTSTRAP_SCENARIOS})


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


class ScenarioDisposition(Enum):
    """
    The explicit, recorded decision made for a legacy corpus scenario at
    DR-ontology-import time (documentation/karpathy_loop_dr_ontology_design.md
    §9; #1109 Phase 3 / discussion #1111). Every scenario in the fixed split
    must have exactly one — none may be left silently carrying stale
    individual/property/entity-based ground truth after the placeholder
    ontology is retired.
    """

    RELABELED = "relabeled"  # ground truth rewritten against the DR ontology
    RETIRED = "retired"  # dropped from the active corpus
    SEPARATE_CONTEXT = "separate_context"  # kept, permanently scoped to its own (non-DR) ontology


# Disposition recorded for every scenario when the DR ontology import landed.
# All 18 pre-import scenarios keep their existing individual/property/entity
# ground truth and continue running against the placeholder ontology
# (OntologyContext.PLACEHOLDER) as a distinct, permanently-scoped evaluation
# context — none are retired (the corpus remains a working measurement of
# the extraction pipeline on its original domain) or relabeled (relabeling
# against the DR ontology's 186 classes is Wave 2-4 authoring work, not a
# mechanical Phase 3 change). Full rationale:
# tests/integration/fixtures/pipelines/individual_extraction/LEGACY_CORPUS_DISPOSITION.md
SCENARIO_DISPOSITION: dict[str, ScenarioDisposition] = {
    scenario: ScenarioDisposition.SEPARATE_CONTEXT for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS
}


def disposition_for(scenario: str) -> ScenarioDisposition:
    """
    Return the recorded legacy-corpus disposition for `scenario`.

    Raises:
        ValueError: If the scenario has no recorded disposition — every
            scenario in the fixed split must have one (see
            `SCENARIO_DISPOSITION`'s module-level comment).
    """
    if scenario not in SCENARIO_DISPOSITION:
        raise ValueError(f"Scenario '{scenario}' has no recorded legacy-corpus disposition")
    return SCENARIO_DISPOSITION[scenario]
