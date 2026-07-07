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

## Scenarios pending review

- [ ] `arxiv_researcher_profile/` (promoted from `fixture_paper_1.json`)
- [ ] `arxiv_byzantine_fault_tolerance/` (promoted from `fixture_paper_2.json`)
- [ ] `arxiv_cloud_platform_landscape/` (promoted from `fixture_paper_3.json`)
- [ ] `arxiv_llm_research_lab/` (promoted from `fixture_paper_4.json`)
- [ ] `arxiv_consensus_protocol_collaboration/` (promoted from `fixture_paper_5.json`)
- [ ] `arxiv_cloud_provisioning/` (promoted from `fixture_cloud_provisioning_paper.json`)
- [ ] `arxiv_crdt_networks/` (promoted from `fixture_crdt_networks_paper.json`)
- [ ] `arxiv_kubernetes_energy_monitoring/` (promoted from `fixture_kubernetes_energy_monitoring.json`)

Each scenario's own `README.md` also carries this notice and points back
here. **Do not remove this file** until every box above is checked off by a
human who has actually skimmed the corresponding `expected.json`.
