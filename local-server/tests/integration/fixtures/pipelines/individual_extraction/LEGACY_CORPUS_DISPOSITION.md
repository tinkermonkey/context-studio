# Legacy corpus disposition — DR ontology import (#1109 Phase 3)

`documentation/karpathy_loop_dr_ontology_design.md` replaces the throwaway
3-class placeholder ontology (`individual`/`property`/`entity`) with the
imported Documentation Robotics 12-layer ontology as the corpus's real,
structural grading target (see that doc §9 and discussion #1111). That
document treats the import as resetting the Karpathy loop's incumbent
baselines — see `local-server/experiments/ledger.py`'s `baseline_reset`
mechanism, appended automatically by `scripts/import_dr_ontology.py`.

Retiring the placeholder ontology raises one question per pre-existing
scenario: what happens to ground truth that was authored and labeled
against classes (`individual`, `property`, `entity`) that no longer exist as
the "current" ontology? This file records the explicit, one-time decision
made for each of the 18 scenarios that predate the import — see
`SCENARIO_DISPOSITION` in
`tests/integration/pipelines/_harness/dataset_split.py`, which is the
machine-readable record of the same decision (a test —
`tests/unit/test_harness_dataset_split.py::TestDispositionFor` — asserts
every scenario in the fixed split has an entry, so none can be added later
without a disposition being recorded too).

## Decision: all 18 scenarios → `SEPARATE_CONTEXT`

None of the three possible dispositions available (re-label against the DR
ontology, retire, or document as a separate context) applied uniformly
except the last:

- **Not re-labeled.** Re-authoring GT against the DR ontology's 186 classes
  and 1,566 relationship types for 10 hand-written software-architecture
  scenarios plus 8 arxiv abstracts is exactly the SME-authored corpus-growth
  work described as Waves 2-4 in
  `documentation/karpathy_loop_dr_ontology_design.md` §§6-8 — real authoring
  effort, not a mechanical Phase 3 change. Wave 1's own bootstrap scenarios
  (§5) are new, DR-native fixtures for this reason, not a relabeling of the
  existing 18.
- **Not retired.** The 18 scenarios remain a valid, working measurement of
  the individual-extraction pipeline's software-architecture-concept and
  arxiv-abstract domains. Discarding them would throw away real signal the
  Karpathy loop still uses (`documentation/karpathy_loop_design.md` §§3-4)
  with nothing yet built to replace it — Wave 1 is explicitly "a sanity
  gate, not a coverage benchmark" (design doc §5) and cannot stand in.
- **Kept as a separate, non-DR ontology context.** Each of the 18 scenarios
  is explicitly mapped to `OntologyContext.PLACEHOLDER` in
  `SCENARIO_ONTOLOGY` (`tests/integration/pipelines/_harness/dataset_split.py`)
  — a permanent, recorded scope, not a silent default. They continue to run
  and score against the placeholder ontology exactly as before. Any future
  scenario graded against the DR spec ontology is added with
  `OntologyContext.DR_SPEC` and its own `ScenarioDisposition.RELABELED` or
  a fresh Wave-N entry — the two ontology contexts run side by side, never
  merged, so no scenario carries stale ground truth silently: its
  disposition and ontology context are both explicit and tested for
  completeness.

## Scenarios covered by this decision

Software-architecture-concept domain (10): `async_patterns`, `clean_code`,
`design_patterns`, `distributed_systems`, `domain_driven_design`,
`microservices_architecture`, `object_oriented_design`,
`reactive_programming`, `service_oriented`, `testing_strategies`.

Arxiv domain (8): `arxiv_byzantine_fault_tolerance`,
`arxiv_cloud_platform_landscape`, `arxiv_cloud_provisioning`,
`arxiv_consensus_protocol_collaboration`, `arxiv_crdt_networks`,
`arxiv_kubernetes_energy_monitoring`, `arxiv_llm_research_lab`,
`arxiv_researcher_profile`.

(`basic/` is excluded from this decision, same as from the dev/holdout split
— it is a minimal input/expected contract fixture with no hand-labeled GT
triples to score, not one of the 18 quality-corpus scenarios.)

## Revisiting this decision

If Waves 2-4 land and a scenario here is deliberately re-authored against
the DR ontology, update both records together: flip its entry in
`SCENARIO_DISPOSITION` to `RELABELED` and its entry in `SCENARIO_ONTOLOGY` to
`OntologyContext.DR_SPEC` in the same change, and update this file's table.
Do not change one without the other — the completeness test only checks that
every scenario has a disposition and a context, not that they agree; use
`TestDispositionFor::test_disposition_and_ontology_context_agree_for_every_scenario`
to catch that class of mistake locally.
