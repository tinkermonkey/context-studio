# NEEDS HUMAN REVIEW — auto-drafted ground truth

The 8 scenarios listed below were promoted from previously-unused arxiv-domain
fixtures by an automated agent, per `documentation/karpathy_loop_design.md`
§3.3 ("Corpus growth: promote the 8 unused arxiv `fixture_*.json` files into
full scenarios (LLM-drafted GT, one human skim)").

**This is exactly the kind of measurement-integrity risk the Karpathy loop
design is trying to guard against**: the same kind of automated agent that
proposes and implements pipeline changes also drafted the ground truth these
changes will be scored against. Until a human has reviewed it, this ground
truth **must not** be treated as an authoritative accept/reject signal —
treat it the same way the design treats an unreviewed holdout veto: advisory,
not authoritative (§3.3, §6).

## What a reviewer should check, per scenario

For each `expected.json` below, read `input.json`'s `text` alongside it and
confirm:

1. Every triple in `result.triples` is actually supported by the text (no
   hallucinated facts).
2. No GT triple is missing that a reasonable annotator would expect to see
   (recall of the ground truth itself, not just precision).
3. Subject/object labels are reasonable snake_case reductions of the source
   phrases (consistent with the style of the other 10 scenarios in this
   directory).
4. The `result.excluded` negative example is actually contradicted by the
   text (i.e. it's a true negative, not an ambiguous one).
5. `distractors.json` remains a plausible-but-wrong triple, not an
   accidentally-true one.

## Scenarios reviewed — dispositions

All 8 were human-reviewed. The common finding: every one uses free-form,
un-clamped predicates (`affiliated_with`, `develops`, `provides`,
`synchronizes_via`, …) against the placeholder ontology — the exact predicate
drift the DR-grounded pipeline exists to prevent — so their GT is anti-signal
for the scored corpus. Dispositions recorded in
`_harness/dataset_split.py` (`RETIRED_ARXIV_SCENARIOS` /
`RELABEL_PENDING_ARXIV_SCENARIOS`) and `LEGACY_CORPUS_DISPOSITION.md`.

**RETIRED** (removed from the scored split — contrived/synthetic toy factoids):
- [x] `arxiv_researcher_profile/` — RETIRED (synthetic "John Doe"; was holdout)
- [x] `arxiv_llm_research_lab/` — RETIRED (OpenAI/GPT‑4 trivia + shaky GT: "Elon Musk founded OpenAI"; was holdout)
- [x] `arxiv_byzantine_fault_tolerance/` — RETIRED (synthetic "John Doe")
- [x] `arxiv_consensus_protocol_collaboration/` — RETIRED (synthetic "John Doe")
- [x] `arxiv_cloud_platform_landscape/` — RETIRED (AWS/Azure trivia, not a paper)

**RELABEL** (real abstracts; GT to be re-authored against the DR ontology, then
folded back into the scored split as DR-native benchmarks):
- [x] `arxiv_cloud_provisioning/` — RELABEL pending
- [x] `arxiv_crdt_networks/` — RELABEL pending
- [x] `arxiv_kubernetes_energy_monitoring/` — RELABEL pending

Review is complete; no unreviewed agent-drafted GT remains in the scored split
(so `HOLDOUT_GT_REVIEW_PENDING` is now `false`). This file is retained as the
record of that review. The three RELABEL scenarios' new DR-grounded GT will
itself need a human review pass when authored.
