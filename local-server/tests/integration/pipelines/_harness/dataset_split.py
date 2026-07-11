"""Fixed dev/holdout scenario split for individual_extraction quality fixtures (§3.3).

Also assigns each scenario an `OntologyContext` (`PLACEHOLDER` or `DR_SPEC`) —
which ontology it is graded against — per the per-scenario ontology context
gap identified against `documentation/karpathy_loop_dr_ontology_design.md`.
All 18 legacy scenarios run against the placeholder ontology. The
`dr_bootstrap_*` scenarios (Wave 1, §5) are graded against the imported DR
spec and are added to `SCENARIO_ONTOLOGY` via `DR_BOOTSTRAP_SCENARIOS`, but
deliberately outside the dev/holdout split -- see that constant's docstring.
The `sme_waypoint_*` scenarios (Wave 2, §6) are also graded against the
imported DR spec, but -- unlike Wave 1 -- *are* folded into the dev/holdout
split, per the Phase 6 acceptance criteria; see `WAVE2_SME_SCENARIOS` below.
The `sme_waypoint_tech_*` scenarios (Wave 3, §7) follow the same pattern --
graded against the DR spec and folded into the dev/holdout split -- per the
Phase 7 acceptance criteria; see `WAVE3_SME_SCENARIOS` below.
The `informal_*` scenarios (Wave 4, §8) are graded against the DR spec but,
like Wave 1, are deliberately kept outside the dev/holdout split -- per the
Phase 8 acceptance criteria; see `WAVE4_INFORMAL_SCENARIOS` below.

`SCENARIO_DISPOSITION` records the explicit, one-time decision made for each
of the 18 legacy scenarios when the DR ontology import happened (#1109 Phase
3): re-labeled against the DR ontology, retired, or kept as a separate,
non-DR-ontology context. See `ScenarioDisposition` and
`tests/integration/fixtures/pipelines/individual_extraction/LEGACY_CORPUS_DISPOSITION.md`.
It is scoped to `LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS` only -- Wave 2
scenarios are new, DR-native ground truth authored directly against the
imported ontology, not legacy scenarios carrying a re-labeling/retirement/
separate-context decision, so they have no disposition to record.

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

The legacy corpus has two domains: 10 hand-labeled software-architecture-concept
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

Legacy total: 13 dev / 5 holdout (18 total), close to the original 70/30 ratio.

A third domain was added in Wave 2 (#1109 Phase 6): 4 SME-authored
`sme_waypoint_*` scenarios (`WAVE2_SME_SCENARIOS`), stratified into dev/
holdout the same way -- first 3 alphabetically -> dev, last 1 -> holdout.

A fourth domain was added in Wave 3 (#1109 Phase 7): 4 SME-authored,
lower-layer/technical `sme_waypoint_tech_*` scenarios
(`WAVE3_SME_SCENARIOS`), stratified into dev/holdout the same way -- first 3
alphabetically -> dev, last 1 -> holdout.

Grand total: 19 dev / 7 holdout (26 total).

Wave 4 (#1109 Phase 8, design doc §8) added 4 `informal_*` scenarios --
user-manual, sales-literature, marketing-copy, and support-article prose
that mentions the same kinds of DR entities only incidentally, never
written with an ontology in mind. Like Wave 1's bootstrap scenarios (and
unlike Waves 2/3), these are deliberately **excluded** from
`INDIVIDUAL_EXTRACTION_SCENARIOS` / the dev-holdout split -- the acceptance
criteria for Phase 8 explicitly forbid using Wave 4 results to gate any
Wave 0-3 accept/reject decision, and this is the same "distinct,
always-reported diagnostic group" mechanism already used for
`DR_BOOTSTRAP_SCENARIOS`. See `WAVE4_INFORMAL_SCENARIOS` below.
"""

from enum import Enum

LEGACY_INDIVIDUAL_EXTRACTION_DEV_SCENARIOS: list[str] = [
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

LEGACY_INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS: list[str] = [
    # Software-architecture-concept domain
    "reactive_programming",
    "service_oriented",
    "testing_strategies",
    # Arxiv domain
    "arxiv_llm_research_lab",
    "arxiv_researcher_profile",
]

# Canonical ordering: dev scenarios first, then holdout. The full 18-scenario
# legacy corpus used by the quality test suites before Wave 2 landed.
LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS: list[str] = (
    LEGACY_INDIVIDUAL_EXTRACTION_DEV_SCENARIOS + LEGACY_INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS
)

# Wave 2 SME-authored domain (documentation/karpathy_loop_dr_ontology_design.md
# §6, #1109 Phase 6): upper-layer (motivation/business/ux/navigation) product
# documentation prose, authored and adjudicated directly against the Wave 0
# DR spec import by the domain SME -- no LLM-drafted intermediate ground
# truth. Unlike the Wave 1 bootstrap scenarios, these ARE folded into the
# fixed dev/holdout split per the standard split rules (see module docstring).
WAVE2_SME_DEV_SCENARIOS: list[str] = [
    "sme_waypoint_business_operations",
    "sme_waypoint_navigation_flows",
    "sme_waypoint_product_vision",
]

WAVE2_SME_HOLDOUT_SCENARIOS: list[str] = [
    "sme_waypoint_technician_ux",
]

WAVE2_SME_SCENARIOS: list[str] = WAVE2_SME_DEV_SCENARIOS + WAVE2_SME_HOLDOUT_SCENARIOS

# Wave 3 SME-authored domain (documentation/karpathy_loop_dr_ontology_design.md
# §7, #1109 Phase 7): lower-layer/technical (technology/data-store/data-model/
# api/apm) engineering-note prose, authored and adjudicated directly against
# the Wave 0 DR spec import by the domain SME -- no LLM-drafted intermediate
# ground truth, same discipline as Wave 2. These ARE folded into the fixed
# dev/holdout split per the standard split rules (see module docstring).
WAVE3_SME_DEV_SCENARIOS: list[str] = [
    "sme_waypoint_tech_api_rate_limiting",
    "sme_waypoint_tech_database_selection",
    "sme_waypoint_tech_observability_alerting",
]

WAVE3_SME_HOLDOUT_SCENARIOS: list[str] = [
    "sme_waypoint_tech_schema_contracts",
]

WAVE3_SME_SCENARIOS: list[str] = WAVE3_SME_DEV_SCENARIOS + WAVE3_SME_HOLDOUT_SCENARIOS

# Full corpus: legacy domains (placeholder ontology) + Wave 2/3 SME domains
# (DR spec ontology). Both dev and holdout are still each populated from
# every domain currently in the corpus.
INDIVIDUAL_EXTRACTION_DEV_SCENARIOS: list[str] = (
    LEGACY_INDIVIDUAL_EXTRACTION_DEV_SCENARIOS + WAVE2_SME_DEV_SCENARIOS + WAVE3_SME_DEV_SCENARIOS
)

INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS: list[str] = (
    LEGACY_INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS
    + WAVE2_SME_HOLDOUT_SCENARIOS
    + WAVE3_SME_HOLDOUT_SCENARIOS
)

# Canonical ordering: dev scenarios first, then holdout. Equivalent to the
# full corpus used by the quality test suites.
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


# Every legacy scenario runs against the throwaway 3-class placeholder
# ontology. A scenario graded against the imported DR spec (see
# documentation/karpathy_loop_dr_ontology_design.md) is added below with
# OntologyContext.DR_SPEC.
SCENARIO_ONTOLOGY: dict[str, OntologyContext] = {
    scenario: OntologyContext.PLACEHOLDER for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS
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

# Wave 2 SME-authored scenarios (§6, #1109 Phase 6): graded against the Wave 0
# DR spec import, never the placeholder. Unlike DR_BOOTSTRAP_SCENARIOS, these
# ARE part of INDIVIDUAL_EXTRACTION_SCENARIOS / the dev-holdout split (see
# WAVE2_SME_SCENARIOS's docstring above).
SCENARIO_ONTOLOGY.update({scenario: OntologyContext.DR_SPEC for scenario in WAVE2_SME_SCENARIOS})

# Wave 3 SME-authored scenarios (§7, #1109 Phase 7): graded against the Wave 0
# DR spec import, never the placeholder. Unlike DR_BOOTSTRAP_SCENARIOS, these
# ARE part of INDIVIDUAL_EXTRACTION_SCENARIOS / the dev-holdout split (see
# WAVE3_SME_SCENARIOS's docstring above).
SCENARIO_ONTOLOGY.update({scenario: OntologyContext.DR_SPEC for scenario in WAVE3_SME_SCENARIOS})

# Wave 4 informal/incidental-prose scenarios (documentation/
# karpathy_loop_dr_ontology_design.md §8, #1109 Phase 8): user-manual,
# sales-literature, marketing-copy, and support-article prose about the same
# fictional "Waypoint" product used by Waves 2/3, written without an ontology
# or architecture model in mind. Graded against the Wave 0 DR spec import,
# never the placeholder. Like DR_BOOTSTRAP_SCENARIOS -- and unlike Waves 2/3
# -- these are a distinct, always-reported diagnostic group, deliberately
# NOT added to INDIVIDUAL_EXTRACTION_SCENARIOS / the dev-holdout split: the
# Phase 8 acceptance criteria require that Wave 4 results never gate a Wave
# 0-3 accept/reject decision, and several of these scenarios have
# single-digit (down to 2) ground-truth triples by design -- see each
# scenario's README.md "Findings" section -- which is too thin to
# holdout-split or optimize against, the same rationale as Wave 1 (§5).
WAVE4_INFORMAL_SCENARIOS: list[str] = [
    "informal_user_manual",
    "informal_sales_literature",
    "informal_marketing_copy",
    "informal_support_article",
]

SCENARIO_ONTOLOGY.update(
    {scenario: OntologyContext.DR_SPEC for scenario in WAVE4_INFORMAL_SCENARIOS}
)


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
    §9; #1109 Phase 3 / discussion #1111). Every scenario in
    `LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS` must have exactly one — none may
    be left silently carrying stale individual/property/entity-based ground
    truth after the placeholder ontology is retired. Wave 2+ scenarios are
    new, DR-native ground truth, not legacy scenarios subject to this
    decision, so they are never registered here (see `disposition_for`).
    """

    RELABELED = "relabeled"  # ground truth rewritten against the DR ontology
    RETIRED = "retired"  # dropped from the active corpus
    SEPARATE_CONTEXT = "separate_context"  # kept, permanently scoped to its own (non-DR) ontology


# Disposition recorded for every legacy scenario when the DR ontology import
# landed. All 18 pre-import scenarios keep their existing
# individual/property/entity ground truth and continue running against the
# placeholder ontology (OntologyContext.PLACEHOLDER) as a distinct,
# permanently-scoped evaluation context — none are retired (the corpus
# remains a working measurement of the extraction pipeline on its original
# domain) or relabeled (relabeling against the DR ontology's 186 classes is
# Wave 2-4 authoring work, not a mechanical Phase 3 change). Full rationale:
# tests/integration/fixtures/pipelines/individual_extraction/LEGACY_CORPUS_DISPOSITION.md
SCENARIO_DISPOSITION: dict[str, ScenarioDisposition] = {
    scenario: ScenarioDisposition.SEPARATE_CONTEXT
    for scenario in LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS
}


def disposition_for(scenario: str) -> ScenarioDisposition:
    """
    Return the recorded legacy-corpus disposition for `scenario`.

    Raises:
        ValueError: If the scenario has no recorded disposition — every
            scenario in `LEGACY_INDIVIDUAL_EXTRACTION_SCENARIOS` must have
            one (see `SCENARIO_DISPOSITION`'s module-level comment). Wave 2+
            scenarios are not legacy scenarios and always raise here.
    """
    if scenario not in SCENARIO_DISPOSITION:
        raise ValueError(f"Scenario '{scenario}' has no recorded legacy-corpus disposition")
    return SCENARIO_DISPOSITION[scenario]
