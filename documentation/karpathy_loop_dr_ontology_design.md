# DR Ontology Import & Waved Corpus Build-Out

**Status:** Proposed
**Date:** 2026-07-06
**Scope:** `local-server/` individual-extraction pipelines — replaces the ontology and corpus the Karpathy loop runs against; does not change the loop mechanics themselves
**Parent design:** `documentation/karpathy_loop_design.md`
**External dependency:** `../documentation_robotics/spec` (Documentation Robotics' 12-layer architecture ontology) and `../documentation_robotics_viewer` (a real, dogfooded DR model used as the Wave 1 corpus source)

## 1. Purpose

The parent design's individual-extraction corpus is graded against a throwaway 3-class ontology (`individual`/`property`/`entity` — see `test_quality_individual_extraction.py`). With nothing structural to match against, the grounding knobs the parent design widens in Loop A (`similarity_threshold`, `ground_to_schema`, `require_schema_match`) are nearly inert: there's no real class space for candidates to be matched into.

This document replaces that placeholder with Documentation Robotics' own 12-layer architecture ontology — a real, independently designed and pressure-tested model of the software-architecture domain — and lays out a waved plan for building prose ground truth against it. Two decisions drive the design:

1. **Import the whole ontology, not a subset.** The point of using a rich, external ontology is to remove ontology-quality as a confound while the extraction algorithm is being built and tuned — that only works if the ontology is genuinely comprehensive (186 classes / 1,566 relationship types), not a hand-picked slice sized to match today's corpus.
2. **The corpus must be prose only.** Documentation Robotics builds its own models by having Claude Code interpret source code via an AST-analysis MCP server — a fundamentally different mechanism from what Context Studio's individual-extraction pipeline does (NLP/LLM extraction from text). The target capability under test is "do for prose what DR does for code": given text about software — architecture docs, user manuals, sales literature — extract the entities and relationships it describes, resolved against the DR ontology. Any ground truth sourced from a code file, config file, or machine-generated spec is explicitly excluded, even where DR's own dogfooded models contain it, because scoring against facts that only exist in source code would fail the pipeline for reasons that have nothing to do with extraction quality.

## 2. What was verified before designing this

| Claim | Finding |
|---|---|
| DR spec scope | 186 node schemas + 1,566 relationship schemas + 13 base schemas across 12 layers (`documentation_robotics/spec/schemas/{nodes,relationships,base}/`) |
| `documentation_robotics`'s own dogfooded model | Scaffolded but never populated — every layer in `documentation-robotics/model/manifest.yaml` shows `elements: {}`. **Not usable; excluded entirely.** |
| `documentation_robotics_viewer`'s own dogfooded model | 285 total individuals, but produced almost entirely from source code / config (`.ts`, `.tsx`, `package.json`, `docs/api-spec.yaml`). Only **23 individuals** trace to a markdown/prose file. |
| Prose-sourced individuals (viewer) | 23 total, by file: `README.md` (16), `CLAUDE.md` (4), `documentation/ACCESSIBILITY.md` (2), `tests/README.md` (1). By layer: motivation (16), business (3), security (3), testing (1) — **4 of 12 layers touched.** By provenance: 11 `extracted`, 12 `inferred`. |
| Prose-sourced relationships (viewer) | 445 relationships total; 24 have both endpoints among the 23 prose-sourced individuals; 10 of those 24 have both endpoints `provenance: extracted`. |

Layer-by-layer DR spec breakdown (node schemas / relationship schemas):

| Layer | Node schemas | Relationship schemas |
|---|---|---|
| motivation | 10 | 80 |
| business | 13 | 73 |
| security | 29 | 183 |
| application | 9 | 79 |
| technology | 13 | 128 |
| api | 27 | 196 |
| data-model | 9 | 71 |
| data-store | 11 | 106 |
| ux | 22 | 188 |
| navigation | 11 | 122 |
| apm | 15 | 138 |
| testing | 17 | 202 |
| **Total** | **186** | **1,566** |

**Implication:** the DR spec is exactly the rich, real ontology this project needs. But the *existing dogfooded models* are a much smaller bootstrap resource than they first looked — one real system, concentrated in one file, touching a third of the layers. They're good for a first end-to-end sanity check, not for coverage.

## 3. Prose-only sourcing rule

Applies to every wave below, including Wave 1: a ground-truth individual or relationship is usable **only if** its source is human-authored prose (`.md` files — README, CHANGELOG, CONTRIBUTING, GOVERNANCE, `docs/*.md`, etc.). Source-code files, config files (`package.json`), and machine-generated specs (`docs/api-spec.yaml`) never contribute GT, directly or indirectly (e.g. no "this exists somewhere in the system" priors backfilled from code-derived individuals). This is a hard filter on `documentation_robotics_viewer`'s 285-individual model, reducing it to the 23 identified in §2 before any of it enters the corpus.

## 4. Wave 0 — Ontology import (prerequisite for everything else)

Translate `documentation_robotics/spec/schemas/{nodes,relationships,base}/**/*.json` into Context Studio's ontology tables:

- One **Taxonomy** for the DR spec as a whole (e.g. identifier `dr_spec`, tagged with the spec's own `spec_version`).
- One **ConceptScheme** per layer (12 total) — mirrors DR's own partitioning and gives Loop A/B a natural axis to slice diagnostics by later (e.g. "which layer are we failing to recover candidates for").
- One **Class** per node schema (186 total) — title/description from the JSON Schema's own fields; preserve the DR schema id (e.g. `motivation.goal`) as an external identifier so re-imports are idempotent and traceable back to the source schema.
- One **PropertyDefinition** per relationship schema (1,566 total) — domain/range from the relationship schema's declared source/target node types; predicate label from the schema id (e.g. `stakeholder.associated-with.requirement`).

Mechanics:

- New script: `local-server/scripts/import_dr_ontology.py`. Idempotent (safe to re-run on a spec version bump). Reads from a configured path to the sibling `documentation_robotics/spec` checkout — treated as an external, versioned dependency, **not vendored/copied** into this repo.
- **Scale caution:** this is ~1,750 new rows in `ontology_entities`/`property_definitions` for a single ontology, roughly three orders of magnitude past today's 3-class placeholder. Before assuming Loop A's knob sweep is still "seconds-per-eval," verify the existing `SchemaVectorIndex` (brute-force numpy cosine, per the current `open_v1` implementation) performs acceptably at this scale. If it doesn't, that's a Loop A infrastructure fix to schedule here — not a reason to shrink the ontology.
- Out of scope: a generic "any ontology" importer. This is a DR-spec-shaped importer; generalizing it is speculative until a second ontology source actually exists.

## 5. Wave 1 — Bootstrap corpus (`documentation_robotics_viewer`, prose-only)

Purpose: verify the whole pipeline — ontology import → grounding → candidate extraction → relation derivation → scoring — works end-to-end against a real ontology and real, independently-produced ground truth. **This is a sanity gate, not a coverage benchmark**, and must never by itself justify an accept/reject decision in Loop C (§9).

- Strict-GT tier: the 11 `provenance: extracted` individuals and the 10 relationships with both endpoints in that set, across all 4 qualifying source files. The 12 `inferred` individuals and their edges are left out of GT entirely for this wave (not used as GT, not used as distractors) — they weren't literally stated in the text, and penalizing or crediting the pipeline either way for them would be measuring DR's inference step, not Context Studio's extraction.
- **Up to 4 scenarios**, one per qualifying source file: `README.md`, `CLAUDE.md`, `documentation/ACCESSIBILITY.md`, `tests/README.md`. Each scenario's `input.json.text` is the real file content (copied at generation time, pinned — these files can change upstream independently of this project, since `documentation_robotics_viewer` is an external, unvendored checkout), and its ontology reference points at the Wave 0 import, not the placeholder. `expected.json` triples are that file's `extracted`-provenance individuals/relationships.
  - **Actually generated: 2 of 4** (`dr_bootstrap_readme`, `dr_bootstrap_claude` — 5 and 4 extracted individuals respectively, 0 same-file relationships). `documentation/ACCESSIBILITY.md` (2 extracted individuals) and `tests/README.md` (0 extracted individuals — its only reference is `provenance: inferred`) are discoverable from the model data but were not present on disk in the viewer checkout at generation time — upstream drift in an external, independently-maintained repo, not a bug in the generator. `scripts/generate_dr_bootstrap_corpus.py` skips a discovered-but-missing file with a warning rather than fabricating content for it (real, pinned text is required — see that script's docstring), so no fixture was written for either. Re-running the script will pick both back up automatically if/when they reappear upstream; `DR_BOOTSTRAP_SCENARIOS` in `dataset_split.py` lists only the 2 currently on disk.
- These scenarios join the corpus as a distinct, always-reported diagnostic group (e.g. `dr_bootstrap_*` naming), **not** folded into the Phase 1 dev/holdout 70/30 split — even at the full 4-scenario target this covers only 4 of 12 layers, several with single-digit GT triples, too thin to holdout-split meaningfully or to move soft-F1 in a way worth optimizing against. The current 2-scenario reality is thinner still and should be read as a first end-to-end sanity check, not as satisfying the 4-scenario target.

## 6. Wave 2 — Upper-layer SME-authored scenarios

New prose — written or curated by the user as domain SME — describing product functionality, use cases, user types, workflows, and business outcomes for a product (real or plausible), in the register of typical product documentation.

- Target layers: motivation, business, ux, navigation primarily; application/api to the extent product docs describe them functionally rather than technically.
- GT authored and adjudicated directly by the user against the Wave 0 ontology — no LLM-draft-then-skim step. This is a higher GT-confidence tier than even the parent design's arxiv corpus growth (Phase 5), because the user is the acknowledged domain authority for this content.
- Suggested starting size: 3-5 documents, to validate the authoring workflow (how GT triples get written against a 186-class ontology in practice) before committing to a larger batch.

## 7. Wave 3 — Lower-layer / technical SME-authored scenarios

New prose covering deep technical rationale — e.g. why one database technology suits a task better than an alternative, down to index-caching design nuances.

- Target layers: technology, data-store, data-model, api, apm primarily.
- Same SME-authored/adjudicated GT discipline as Wave 2.
- Expect this wave to stress the pipeline differently than Wave 2 — denser technical vocabulary, tighter relationship graphs per sentence, more domain-specific jargon that a general-purpose dependency parser or embedding model may handle worse. Watch the parent design's error-report diagnostics (§3.2) closely here; a quality drop relative to Wave 2 would be a genuine finding about the pipeline's technical-prose ceiling, not noise.

**Phase 7 authoring (#1109):** 4 scenarios landed under `sme_waypoint_tech_*` — `database_selection` (data-store/technology: index/access-pattern/retention-policy/caching design), `api_rate_limiting` (api/apm: rate limits, security schemes, trace/metric instrumentation), `schema_contracts` (data-model/api/data-store: contract-first JSON Schema design), `observability_alerting` (apm/technology/data-store: resource monitoring, alerting, dashboards). Same Waypoint fictional product as Wave 2, continued as an internal engineering-note series rather than product documentation. 3 dev / 1 holdout (`schema_contracts`), stratified alphabetically per the standard rule (§3.3 of the parent design) — see `WAVE3_SME_SCENARIOS` in `tests/integration/pipelines/_harness/dataset_split.py`.

Error-report diagnostics were reviewed via the deterministic, non-LLM `open_v1` rule-mode baseline (`test_quality_individual_extraction_open.py`, the only harness path that runs offline without recorded LLM cassettes for these new scenarios). At that baseline, both waves already score near zero on strict metrics — rule mode's snake_case/fused-phrase exact-tuple matching doesn't line up with hand-labeled prose ground truth on *any* SME scenario, Wave 2 included (see the module's own docstring: rule mode does not meet production floors by design). Within that near-floor regime, Wave 3's soft-F1 (mean 0.037) and candidate_recall (mean 0.284) were not lower than Wave 2's (0.032 and 0.207 respectively); predicate_recall was somewhat lower (0.060 vs 0.080), a small-sample signal consistent with — but not strong evidence for — the denser relationship graphs called out above. Because both waves are already saturated at the rule-mode floor, a real technical-prose-ceiling comparison needs the LLM-mode path (recorded cassettes or a live provider), not this offline baseline; that comparison is future work once cassettes are recorded for the Wave 2/3 corpus. Adding these 4 scenarios pulled the pinned `RULE_MODE_MEAN_RECALL_FLOOR` baseline down from 0.05 to 0.045 (actual measured mean ~0.049) — expected collateral of growing the SME-authored (zero-recall-under-rule-mode) share of the corpus, not a regression in the rule-mode implementation itself.

## 8. Wave 4 — The "ultimate test": informal, non-technical software prose

New prose that mentions the same kinds of underlying entities only incidentally — user manuals, sales literature, marketing copy, support articles — text never written with an ontology or architecture model in mind.

- Purpose: test generalization beyond writing that's already organized the way the ontology expects. Waves 2-3 are still "about" architecture/products in a structured way; Wave 4 checks whether the algorithm only works on already-half-structured input, or genuinely projects the ontology onto arbitrary text.
- Sequence this last. Expect it to surface gaps that motivate new pipeline mechanics (handling implicit references, marketing hyperbole with no clean class mapping) rather than a wave that simply "passes."

**Phase 8 authoring (#1109):** 4 scenarios landed under `informal_*` — `informal_user_manual` (ux: a quick-start guide describing the same technician-app UI as Wave 2's `sme_waypoint_technician_ux`, in onboarding-guide register), `informal_sales_literature` (business/apm: a prospect-facing sales one-pager), `informal_marketing_copy` (data-store/motivation: a company blog post pitching offline durability), `informal_support_article` (data-store: a help-center FAQ explaining record retention). All four continue the same fictional "Waypoint" product used by Waves 2-3, deliberately, so that entity continuity (or its absence) across registers is itself observable. Ground truth was hand-adjudicated per-scenario directly against each scenario's own text (the prose-only-per-scenario rule applies here just as strictly as in Waves 2/3 — no fact was backfilled from a same-product Wave 2/3 document, even where an individual shares a name). These are graded against the Wave 0 DR spec (`ontology_id: "dr_spec"`) but, per this wave's design intent, are kept out of `INDIVIDUAL_EXTRACTION_SCENARIOS`/the dev-holdout split entirely — the same "distinct, always-reported diagnostic group" mechanism Wave 1 established (`WAVE4_INFORMAL_SCENARIOS` in `tests/integration/pipelines/_harness/dataset_split.py`, `_build_wave4_reports` in `scripts/quality_tournament.py`) — so Wave 4 structurally cannot gate a Wave 0-3 accept/reject decision, satisfying the Phase 8 acceptance criteria without relying on discipline alone.

The predicted generalization failure showed up immediately during authoring, before any pipeline was even run against these fixtures: ground-truth density collapses as register moves away from architecture-aware writing, even while the same named entities keep recurring across documents. The four scenarios' triple counts are 12, 8, 2, and 2 respectively (user manual → sales literature → marketing copy → support article) — proper nouns for technical entities (e.g. "Job Event Store") ground identically well in a blog post as in an engineering note, but paraphrased results ("cut missed appointments in half" vs. Wave 2's formally named "Missed-Appointment Rate Cut in Half"), generic/lowercase role and infrastructure references ("regional operations manager," "cold storage" vs. Wave 2/3's capitalized proper nouns for the same concepts), marketing hyperbole with no clean class mapping ("bank-level encryption"), and DR relationship schemas that require an unstated intermediate layer to bridge two incidentally-mentioned entities (no direct `data-store.database`→`motivation.value` edge exists; a `motivation.requirement` intermediate is required, and informal prose has no reason to name one) all produced legitimate, class-supported extraction gaps rather than pipeline bugs. Each scenario's README.md documents its specific findings rather than a pass/fail verdict, per the Phase 8 acceptance criteria. A rule-mode/LLM-mode pipeline run against this wave, and any resulting diagnostics, is future work once cassettes exist for it (same limitation noted for Wave 3 in §7) — the findings recorded here are from ground-truth authoring itself, which already surfaced the wave's central lesson before any extractor was involved.

## 9. Sequencing and relationship to the existing build plan

- Waves 1-4 all reuse the parent design's Phase 1 measurement-layer infrastructure (soft-F1, diagnostics, dev/holdout split, error reports) as-is — nothing here duplicates it.
- Order: Wave 0 (ontology import) → Wave 1 (bootstrap sanity check) → Waves 2 and 3 (independent authoring efforts, can proceed in parallel once Wave 0 lands) → Wave 4 (last, hardest, most speculative).
- **Non-goal:** this document does not change Loop A/B/C mechanics (already built per the parent design's Phases 1-6) — only what ontology and corpus they run against. One expected exception: Loop A's `_INDIVIDUAL_SPACE` knob *values* (e.g. `similarity_threshold` defaults tuned against the placeholder ontology) will likely need re-tuning once a real 186-class ontology is in place. The knob *mechanics* shouldn't need to change, just their ranges.
- Per the parent design's own rule (§6, "metric-gaming defense"), swapping the ontology and corpus resets the incumbent baselines — Loop C's ledger starts fresh once Wave 0/1 land; pre-DR-ontology ledger entries and scores are not comparable and shouldn't be used to judge post-import experiments. **This is a mechanism, not just a documented convention** (#1109 Phase 3): `scripts/import_dr_ontology.py` appends a `decision: "baseline_reset"` entry to `experiments/ledger.jsonl` (via `experiments/ledger.py`'s `append_baseline_reset`) recording the imported `spec_version`, idempotently — a re-run against an unchanged spec version does not append a duplicate. Every ledger read that feeds a Loop C decision (`rejected_hypotheses`, via `entries_since_last_baseline_reset`) is scoped to entries recorded since the most recent checkpoint, so pre-reset entries are excluded automatically rather than by discipline.
- The same Phase 3 change made an explicit, recorded disposition for each of the 18 pre-import scenarios (re-label / retire / document as a separate context) — see `tests/integration/fixtures/pipelines/individual_extraction/LEGACY_CORPUS_DISPOSITION.md` and `SCENARIO_DISPOSITION` in `tests/integration/pipelines/_harness/dataset_split.py`. The pre-import scenarios were kept as a separate, non-DR ontology context (`ScenarioDisposition.SEPARATE_CONTEXT`, paired with their existing `OntologyContext.PLACEHOLDER` mapping) rather than retired or relabeled — full rationale in that file.
- **The scored split is now DR-grounded only.** A later refinement removed the 10 legacy software-architecture-concept placeholder scenarios from the scored split entirely: they ran against the throwaway 3-class placeholder ontology, tested free-form concept extraction rather than grounded identification, scored ~0 strict-F1, and were the sole source of the casing/pluralization "failures." They retain their `SEPARATE_CONTEXT` disposition but are no longer scored, and their fixtures were pruned. The scored split is DR-grounded only (dev 9 / holdout 2 — Wave 2/3 SME + relabeled arxiv); grounded baseline is dev strict-F1 ≈ 0.66 / soft-F1 ≈ 0.69. Full account in `individual_extraction_refinement_learnings.md`.
- **Recognition episodes are a new diagnostic group.** The semantic entity-recognition (dedup) capability (issues #1137/#1142) is measured on a multi-document episode corpus (`tests/integration/fixtures/pipelines/individual_recognition/`) reporting dedup precision/recall/F1 via `RECOGNITION_EPISODES` in `dataset_split.py`. Like the Wave 1/4 groups, it is always reported but kept out of the scored dev/holdout split (precision-floored), so it structurally cannot gate a Loop C accept/reject decision.

## 10. Open questions / risks

- **Vector-index performance** at ~1,750-row ontology scale (flagged in §4) needs verifying before Loop A's sweep cost assumptions carry over.
- **Relationship cardinality** — some DR relationship schemas may express 1:1 vs 1:N constraints beyond simple domain/range. KISS default: drop this at import, revisit only if loop errors show it mattered.
- **Spec versioning** — DR's spec evolves (its `CHANGELOG.md` is substantial). The imported ontology is pinned to the `spec_version` read from `{spec-dir}/dist/manifest.json` at import time, recorded in `experiments/ledger.jsonl`'s baseline-reset checkpoint for reproducibility of loop baselines (§9 above). **Any future spec-version upgrade is therefore always a deliberate, baseline-resetting re-import — never an in-place, silent update**: re-running `scripts/import_dr_ontology.py` against a bumped `spec_version` upserts the ontology data in place (by design, for idempotency of the entity rows themselves) but also appends a *new* `baseline_reset` ledger checkpoint, so Loop C's target selection and any human review of prior experiments can see exactly when and to what version the ground truth it's being judged against changed.
- **Wave 1 thinness is a hard limit, not a temporary one** until Waves 2-4 land: 4 scenarios, 4 of 12 layers, one real system. It cannot support an accept/reject decision in Loop C on its own.
