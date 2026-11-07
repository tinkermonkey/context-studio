# Context Studio as the Ontology Workbench

> Record copy of the proposal accepted on 2026-10-26, exported on 2026-10-29 from the live document at https://claude.ai/artifact/BqR3Ljk5byD7e9suaYjK97 (private). The live document may have moved on since; the two embedded diagrams (interaction model, phased plan) don't export and appear as placeholders.

Oct 26, 2026 · Austin Sand

The next phase should make Context Studio the place where the Documentation Robotics (DR) and House ontologies are designed and refined. Claude Code works with it through an MCP server, and the in-app chat uses the same tools. Agents propose, people decide inside Context Studio, and each project's repo stays the release channel. The first milestone is deliberately small (charter fields, a read-only MCP server, the House schema import), so we can compare against the manual workflow while it is still fresh.

## Why this direction

Two live projects are doing Context Studio's core job by hand, in Claude Code, right now. That gives us a manual baseline we remember in detail, which is the cheapest value test we will ever get.

**Documentation Robotics.** The spec (13 layers, 192 element types, 1,529 relationship schemas, 71 predicates) is refined by a pipeline of TypeScript scripts and JSONL files in `cli/scripts/spec-enrich/`. A design charter now anchors every judgment. Opus proposes definitions, Sonnet splits maintainer notes into 1,462 atomic claims, and Clef triages them. A reflection stage asks "if not this, then what?" for each relationship. The result is a per-triple change plan, applied in probability-gated tiers. Tier 1 removed 86 schemas and renamed 5, and an audit record now generates the instance migration for `dr upgrade`. It works, but all state lives in files, review happens in markdown reports, and none of it is reusable for another ontology.

**House.** The schema (7 node kinds, 16 edge rules, units, creation policies, guidance heuristics, \~31 starter activities) is written once as prose in `docs/ONTOLOGY.md`. It is then copied by hand into about seven code locations: `contract.ts`, `rules.ts`, the SQL `CHECK`, `guidance.ts`, `starter.ts`, zod descriptions and `SERVER_INSTRUCTIONS`. Drift is already visible between docs and code. Each slice ships through a \~235-line plan with a numbered decision table, then four PRs. Definition quality is policed by a word-count heuristic tuned one eval failure at a time. The live data also shows the cost of copies: every group gets its own seeded activity vocabulary, and the Household and Personal copies have already diverged.

**Context Studio** already has most of the substrate: taxonomies, concept schemes, classes with definitions and embeddings, property definitions with domain and range, a graph context with SPARQL, review-before-apply extraction runs with revert, and a chat agent with seven read-only tools. What it lacks is the connective tissue: a place to state intent, a way for agents to propose changes, an MCP surface, and a round trip to the project repos.

## What to adopt

Every idea below has already earned its place in DR or House, with numbers. The rightmost column is the form it takes in Context Studio.

| Idea | Proven in | Evidence | Context Studio form |
| --- | --- | --- | --- |
| Vision statement plus one-paragraph summary | DR `DESIGN_CHARTER.md` | Summary in triage: same accuracy, higher confidence in the right answer. Full charter made Opus gold labels consistent. Full charter in a per-item classifier dropped Clef layer accuracy from 81% to 34%. | `vision` and `summary` on every taxonomy, plus a context policy per pipeline stage: full, summary or none |
| Intent at every level | DR layer intent in triage state | Every layer definition originally read "Layer N: Name"; writing real ones was the first fix | Concept scheme scope note and class definition, assembled with the charter into state cards |
| Operational definitions | DR `propose-nodes.ts` | Type-given-layer accuracy 68.5% to 78.9% (82.3% with kind narrowing) | Class: definition, "use sibling X instead when" clauses, evidence signals. Predicate: meaning sentence, evidence sentence, direction |
| A rubric for judging change | DR charter, last section | Defect / works as designed / judgment call, and editorial / additive / breaking | Every proposal carries a validity and a scope; scope drives who must approve |
| Deterministic evidence packs | DR `triage.ts --evidence` | Clef 40% to 60–70% agreement with human gold at the same cost; an Opus debate reached 60% at about 60 times the cost | Packs built from graph queries: how siblings declare an attribute, which edges already join the named classes |
| A decision model with calibrated probabilities | DR Clef backend | About $0.001 per card. A 0.60 threshold gives 92–97% precision on 36–41% of cards | A `DecisionModel` port (choice, score, yes/no to probabilities); Clef adapter plus an LLM fallback; `none` always offered |
| Sorting questions | DR `triage-reflect.ts` | 1,160 reflections for about $1.52; changed 29% of validity decisions | A refinement pipeline: for each edge or class, the best source, target, predicate or parent among the catalog, siblings and `none` |
| Change plan with tiered apply | DR `reflect-plan.ts` | 184 of 526 rows clear p ≥ 0.6; tier 1 applied 87 actions; retargets and conflicts never automatic | A proposal bundle grouped by change kind, with a probability threshold in the review UI |
| Change records that drive migration | DR relationship migration (in progress) | 104 triple rules and 1 predicate rename, composed across records | Each accepted schema change emits a record; Context Studio migrates its own individuals and exports the record |
| Human gold for every stage | DR `bench-gold.jsonl` | One adjudicated claim became the reflection stage | Reviewer decisions saved as gold per taxonomy (absorbs #1316) |
| Creation policy per kind | House `ONTOLOGY.md` §6.2 | Activities created then mentioned; places confirmed first | An approval policy per class and scope: what an agent may apply directly vs only propose |
| Warnings that name the fix | House `guidance.ts`, `check_vocabulary` | Closet-in-den definitions went from 2/5 to 5/5 after one rule change | Definition-quality checks (rules plus an LLM judge), each warning carrying its suggested action |
| Schema written once, generated everywhere | House pain point | About seven hand-copied locations | A versioned export bundle per project; the project generates its code from it |
| The project's evals as the release gate | House evals (27 scenarios) | Every slice tuned until its bar to ship holds | Unchanged: an export lands as a branch, and the project's own evals decide |

## Interaction model

One ontology and one tool layer, reached four ways. Claude Code (and later claude.ai) comes in over MCP. A person uses the chat panel and the review UI. Bulk refinement runs as pipelines. Changes leave through an export to the project repo, where that project's own tests and evals decide.

_[Diagram: interaction model: 4 ways in, 1 tool layer, 2 project repos. See the live document.]_

Each participant does what it is best at:

- **Claude Code** keeps the code context: the AST, the evals, the commit history. It asks Context Studio about the ontology instead of grepping prose docs, drafts proposals, and turns an accepted export into code changes and a PR.
- **The chat panel** is the partner while you are looking at the ontology. It uses the same tools as MCP, with the taxonomy summary in its system prompt.
- **The review UI** is where people decide: a proposal queue, diffs, evidence, and a probability threshold for bulk accepts.
- **Pipelines** do the passes nobody wants to do by hand: definition enrichment, claim triage, reflection and definition audits. Their output is proposals, never direct writes.

Five principles hold it together:

1. **Agents propose, people decide.** Every agent write, from MCP, chat or a pipeline, lands as a proposal with its source, rationale, evidence and probability. A per-taxonomy approval policy can let some changes apply directly, the way House creates activities but confirms places first.
2. **One tool registry, every face.** Chat tools and MCP tools come from the same registry, so anything the chat can do, Claude Code can do too. The chat's existing `ToolSpec` is already MCP-shaped.
3. **The repo releases, Context Studio refines.** DR's spec and House's schema still ship by PR. Context Studio keeps what files handle badly: claims, decisions, gold, provenance and history.
4. **Intent travels with every call.** The taxonomy summary, scheme scope note and class definitions go into each agent's and pipeline's context, following DR's measured rule: full charter for judges, summary for triage and chat, nothing for per-item classifiers.
5. **Every decision is data.** Accepts, rejects and edits become gold for benchmarks and, later, for tuning a decision model.

## Walkthroughs

Three pieces of work that are next anyway, done the proposed way. Each one doubles as a value test.

**House slice 2c: makes, models and furniture.** Today this would mean a plan with a decision table, a docs PR, a graph PR and a tools PR, with the same facts typed into about seven files.

1. In the House repo, you ask Claude Code to design slice 2c. Over MCP it reads the House taxonomy summary and searches the resource classes, instead of re-reading `ONTOLOGY.md`.
2. Claude Code submits its design as one proposal bundle: whether Furniture is a resource subkind, how a make and model sit under a resource with `is_a`, and the rationale for each, marked additive.
3. Context Studio checks each new definition (too thin? distinguished from its siblings?) and runs the sorting questions ("if Furniture is not a resource, what is it?"). The results are attached to the proposal.
4. You review in Context Studio, ask the chat anything you need, and accept with edits. The accepted bundle is the decision log; there is no separate D-table.
5. Claude Code exports the House bundle onto a branch, runs House's generator to rewrite the constants, rules and starter vocabulary, runs the evals, and opens the PR.

**DR reflection, tier 2.** Tier 1 applied only the mechanical changes. What remains (164 retargets, 65 compound changes, 60 conflicts) needs a person to judge each one, which is exactly what markdown reports are worst at.

1. Re-import spec 0.10.0. Load DR's existing claims, decisions and reflections as the starting state, so nothing is paid for twice.
2. The review UI groups the plan by change kind. Each retarget shows the claim, the sorting-question answers with their probabilities, and an evidence pack built from the graph.
3. You decide row by row; mechanical leftovers go through a threshold slider. Every decision is saved as gold.
4. Accepted changes produce a change record in DR's `applied-*.json` shape. The export writes the schema files and the record; DR's own generator builds the `dr upgrade` migration, and Claude Code runs DR's tests.

**A fix that starts in chat.** You are looking at House's "Gutter cleaning", which sits under both Cleaning and Maintenance.

1. You ask the chat whether it should have two parents.
2. The chat reads the taxonomy summary and both parents' definitions, answers, and offers a proposal, for example keeping both parents and tightening the definition.
3. The proposal shows as a card in the chat with accept and reject, and links to the review queue. Once accepted, it rides along in the next export.

## Capabilities

Most of the substrate exists. The biggest gap is the proposal layer: today every write goes straight to the database. The second is the MCP surface.

| Area | Today | Needed |
| --- | --- | --- |
| Charter and intent | Taxonomy and scheme have a title and one free `description` | Taxonomy `vision` and `summary`, a scheme scope note, versioned with the taxonomy, shown on its page and served as an MCP resource |
| Operational definitions | Free `description`; title and definition embeddings; the definition competes with the title in matching | Class: definition, sibling distinctions, evidence signals. Predicate: meaning, evidence, direction. Matching led by the definition |
| Schema expressiveness | Property definitions carry domain, range and a canonical predicate; one parent per class; edges carry no attributes | Inverse, symmetric, transitive and cardinality on properties; attributes on edges (House `requires` has quantity, unit, optional); more than one parent. Only what the two exports need |
| Proposals | Writes are applied at once; changesets group events after the fact; extraction runs already hold candidates with apply and revert | A proposal holding pending operations with source, rationale, evidence, probability and scope, plus apply, reject and revert. Generalize the extraction-run pattern instead of building a second one |
| Approval policy | None | Per taxonomy: which scopes and classes an agent may apply directly |
| Tool layer and MCP | Seven read-only chat tools; no MCP server | One registry with reads, the taxonomy summary, `propose_*`, `run_refinement`, `get_proposal` and `export_project`; an MCP endpoint on the FastAPI app; the chat gets the propose tools too |
| Decision model | LLM providers only | A `DecisionModel` port, a Clef adapter configured in `config.json`, an LLM fallback, and question sets versioned with the taxonomy |
| Refinement pipelines | Schema extraction, grounding, definition and connection refinement | Definition enrichment, notes to claims, triage with evidence packs, sorting questions, change plan, definition audit; all of them emit proposals |
| Change records and migration | Change events with before and after state; entity snapshots | Records of renames, retypes and reversals; Context Studio migrates its own individuals, and the record ships in the export |
| Project bindings | DR import by script only; SKOS, OWL and GraphML via API, no UI | Import and export adapters per project (DR spec directory, House JSON bundle), a drift check on import, available from API, MCP and UI |
| Benchmarks | Extraction quality harness, cassettes, the Karpathy loop | Gold per taxonomy from reviewer decisions, a benchmark per stage, zero-shot classifiability as a quality score for definitions |
| Extraction | Two-pass LLM individual extraction (dev strict-F1 0.94), schema extraction, recognition | Charter-aware context, typing led by definitions, an explicit `none`, an auto-accept band from the decision model, and output as proposals |

Out of scope for now: real multi-workspace support (one database, one taxonomy per project is enough), remote access for claude.ai, reading House's live per-group data, and fine-tuning a decision model.

## Phased plan

Four phases, each small enough to finish and then judge against the manual baseline. Phase A is the first milestone: it makes Context Studio useful to Claude Code before any write path exists.

_[Diagram: phased plan: 4 phases, 4 value gates. See the live document.]_

- **A, plug in.** Add vision and summary fields and scheme scope notes, and write both charters. Serve the existing seven chat tools plus the taxonomy summary over MCP. Import House's schema and starter vocabulary, and re-import DR 0.10.0.
- **B, propose and ship.** Build the proposal layer by generalizing extraction-run apply and revert. Add the approval policy, the propose tools for MCP and chat, and the review queue. Build the House and DR export adapters (plus a small generator on the House side), and add only the property traits and edge attributes those exports need.
- **C, refine.** Add the decision-model port and Clef adapter. Bring DR's loop in as pipelines: enrichment, claims, triage with evidence packs, sorting questions, change plan and tiered apply. Add change records with individual migration, and save reviewer decisions as gold.
- **D, extract.** Point extraction at the same intent stack: charter-aware context, typing led by definitions, an explicit `none`, an auto-accept band and corrections as gold. House's manuals become the first new source, producing model, part and maintenance-activity proposals.

Phase A is planned as the milestone [Workbench A · Plug in](https://github.com/tinkermonkey/context-studio/milestone/8), tracked in [#1342](https://github.com/tinkermonkey/context-studio/issues/1342) with eight issues (#1334–#1341). One design refinement came out of planning: the taxonomy's existing `description` becomes the one-paragraph summary, so `vision` is the only new field.

Phases A and B are done, and both milestones are closed (2026-11-05). Phase A merged in #1343 and #1346–#1350. House's bundle and charter landed in tinkermonkey/house#32: `ontology/VISION.md` is informative only, and `docs/ONTOLOGY.md` stays House's specification. Gate B (#1370) replaced Gate A. Phase B, [Workbench B · Propose and ship](https://github.com/tinkermonkey/context-studio/milestone/9), closed with 21 issues, tracked in [#1351](https://github.com/tinkermonkey/context-studio/issues/1351). Phase C is under way in two milestones, [C1 · Clean up and decide](https://github.com/tinkermonkey/context-studio/milestone/10) and [C2 · Refine](https://github.com/tinkermonkey/context-studio/milestone/11), tracked in [#1421](https://github.com/tinkermonkey/context-studio/issues/1421).

Phase B design decisions:

- A proposal is a run, so the existing revert works.
- Scope is computed by the system, and breaking changes never auto-apply.
- Agents only propose, get and list.
- MCP requires a bearer token.
- Bundle import becomes a proposal.
- Relationship attributes become first-class for House kits.
- The review queue gets a design pass first.
- Gate B is measured on a DR layer walk (in place of DR's spreadsheet), a DR charter-driven change, and House kits.

## Disambiguation cues

A recorded idea for the extraction work ([#1333](https://github.com/tinkermonkey/context-studio/issues/1333)). It makes DR's sorting questions systematic and points them at extraction. Classes, predicates and individuals carry **disambiguation cues** that separate them from their nearest neighbours, or from another sense of the same word:

- **Questions** in a decision model's shape. For example, "is the text describing a running process or a stored record?" When a match is ambiguous, Clef answers the candidates' questions against the passage.
- **Contrastive examples**: a snippet marked match or no match, with a one-line reason.

The idea gives a reviewer a real outlet:

- Next to Accept and Reject, they can record *why*: what the match should have been and a one-line reason. That becomes a draft cue on the entities involved.
- A **Chat about it** button opens the chat scoped to that candidate, to sharpen the reason before it is captured.
- Refinement pipelines can populate cues in bulk from confusable pairs. A cue is kept only if a decision model answers it reliably.

It needs the proposal layer (Phase B) and the decision model (Phase C). It also answers the open design question in #1316.

## Judging value

Every ontology task done through Context Studio gets one row in a log, compared with the same kind of task done by hand in the last few weeks. Context Studio records proposal and review timings itself; the rest is a two-minute note at the end of the task.

| Measure | What we record | Manual baseline |
| --- | --- | --- |
| Hand edits per change | Places a person or Claude Code edited by hand to land one schema change | House: about seven locations per concept |
| Drift | Mismatches between the ontology and the project's code or docs found at review | House: three known drifts today |
| Time to decision | Wall-clock time from question raised to accepted change | House slices 2a and 2b; DR tier 1 |
| Review effort | Minutes per adjudicated proposal or claim | DR's review of `plan-clef.md` and the reflection summary |
| Decisions captured | Share of decisions saved with rationale and evidence | House D-tables; DR's 10-claim benchmark gold |
| Agent context spent | Claude Code turns and tokens spent re-reading ontology docs | Recent Claude Code session transcripts |
| Quality held | Project evals pass rate; DR classification accuracy | Current eval results and Phase 0 numbers |
| Cost | LLM and decision-model spend per task | DR: about $5 for all node proposals, $1.52 for all reflections |

Each phase ends at a gate: continue if Context Studio wins on hand edits and decisions captured without losing quality. If it does not, we fix the friction the log names before building the next phase.

### Value log

One row per task done through Context Studio (Gate A: [#1341](https://github.com/tinkermonkey/context-studio/issues/1341); Gate B: [#1370](https://github.com/tinkermonkey/context-studio/issues/1370); Gate C: [#1420](https://github.com/tinkermonkey/context-studio/issues/1420)).

| Date | Project | Task | Hand edits | Drift found | Time to decision | Agent context spent | What was missing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-04 | Documentation Robotics | Gate B #1: business-layer reflection walk in the review queue (proposal 0b6d60f8, 22 ops), in place of the spreadsheet. Landed in documentation_robotics#993 | 0 field edits in review; 22/22 accepted unchanged. To land it in #993: a hand-written maintainer pass (`applied-business-principles.json`) that fixed decisions that broke the layer's rules or contradicted each other, and one decision overridden (row 17's replacement). One code change mid-walk ([#1394](https://github.com/tinkermonkey/context-studio/pull/1394)) to resolve an in-use delete | 1: op 8 deleted a relationship type still used by 2 relationships. 0 defects caught at review; 1 missed (row 17's replacement linked a different pair, found while landing #993) | 21 ops in 2m07s; op 8 blocked 1h50m until #1394 shipped; 26h15m calendar. Baseline: the application-layer walk took 3h54m for 18 rows, including building the walk tooling; 0/18 accepted unchanged | n/a (a person walked it) | In-use blockers show only at apply time, and chat and MCP don't show them. Review didn't flag whether a delete's replacement links the same pair of element types; with the maintainer pass, `dr upgrade` migrates 10 of 26 retired types and drops 16. 21 ops in 2m07s suggests partly bulk acceptance. 11 layers not yet imported |
| 2026-11-05 | Documentation Robotics | Gate B #2: charter-driven change over MCP in the application layer (redefine component assigned-to interface; add collaboration aggregates collaboration), reviewed in the UI, applied to `spec/schemas/**` in documentation_robotics#995 | 0 field edits in review; 2/2 accepted unchanged. To land it: 3 files written by hand (2 schemas and the CHANGELOG) plus 4 regenerated | 1: 9 application-layer relationship types are in Context Studio (proposal 69642a4f, 2026-10-30) but not in the DR spec. 0 defects caught at review | About 4 min to propose; 15h19m elapsed to decision (overnight; active review time isn't recorded); about 11 min from decision to an open, locally validated PR (14:33 to 14:44 UTC) | About 50 tool calls. Charter read once (it is the taxonomy vision); Context Studio's DR importer source read twice to learn the identifier and reference conventions | Context Studio can't hold `x-dr-evidence`, cardinality or strength, so they rode in rationale text and couldn't be edited at review. `export_dr_decisions.py` handles only triple decisions, so the spec edit was by hand. MCP `get_entity` and `get_proposal` omit fields that REST returns. Decisions carry no `decided_at` |
| 2026-11-05 | House | Gate B #3: starter kits proposed over MCP (21 resources, 24 `requires` edges) under an approval policy, then a bundle round trip | 0 in House files. 0/45 kit ops kept (24 rejected, 21 auto-applied then reverted). In Context Studio: 2 policy updates, 24 rejects and 1 revert | 70 ops: House bundle 7b4858c had not been imported yet. Applied 70/70; the round trip then plans 0 ops in both directions | Kits proposed about 8.5 min after start; 21 auto-applied within 1 s; rejected on scope (time not recorded) and reverted 15h21m after proposal (23:17 to 14:39 UTC, overnight). Drift import applied 15h17m after it was proposed | About 50 tool calls. Read House's ONTOLOGY.md, the stage-2a decisions, VISION.md, House's exporter, and Context Studio's policy and bundle code | Kit contents (hammer, screws) are detail settled between claude.ai and the user, not ontology; the existing `requires` Activity/Task → Resource schema is enough. A `min_probability` above 0 blocks every bundle-import op, even editorial ones. Policy class rules don't cover subclasses. No proposal dry run. `propose_changes` has no field for an individual's data. Attribute-key renames count as breaking |
| 2026-11-06 | Documentation Robotics | #1405 drift cleanup: land the 11 Context-Studio-only types in DR, then delete what DR's main spec retired (proposal 85e85700, 79 deletes) | 1 for the DR side: the export was filtered to the 8 types that fit DR's rules and evidence was added by hand (documentation_robotics#1004). 0 field edits in review; 79/79 accepted as proposed, with 8 in-use deletes resolved in review (5 moved, 2 dropped; the 15 `extends` edges moved to `specializes` to follow DR, though many aren't subtypes) | Re-import from DR main found 79 stale entities, not the 20 expected: DR had since stated data-model and product rules and split `capability`; 3 of #1004's additions were reversed into `serves` before merge. A re-import after apply reports none | 73 ops decided in about 10 min; the 6 in-use deletes waited on one question to the agent; 17 min from first to last decision | About 60 tool calls to map 79 stale types to DR's `applied-*.json` rename chains (including the capability split followed by a product-rules rename) | Context Studio can't map stale types to their replacements itself; the agent rebuilt DR's rename chains by hand. In review, applied operations keep the amber and red pair flags while operations still needing a decision look the same, and the banner reads `pending: 0` while in-use deletes still need a choice |
| 2026-11-06 | Documentation Robotics | Gate C #1: DR's ux-layer rules pass pushed into Context Studio as a reflection plan (proposal e08cc84a, 108 ops: 27 renames, 81 deletes), adjudicated in the review queue, exported and landed in documentation_robotics#1029 | 1 on import: the plan's operation `kind` held the plan kind, so the importer refused every op until it was fixed in a copy (DR fixed its exporter for the api pass). 0 field edits in review; 108/108 accepted as proposed, with 3 in-use deletes resolved (1 moved, 2 dropped). Landed by DR's `cs-decisions-to-spec.ts` from the `cs-dr-spec-changes/1` export; `renders` retired into `composes` | 477: before the pass, Context Studio still held 477 types DR main had retired (seven layers' rules); a catch-up proposal (9be68661) deleted them first. A re-import after #1029 merged reports none | 41 min from first to last decision (20:12 to 20:53 UTC), including a bulk-apply hang that [#1441](https://github.com/tinkermonkey/context-studio/pull/1441) fixed mid-walk; 5h54m from proposal to DR merge, most of it waiting on the maintainer | n/a in review (a person walked it); DR-side context not recorded | The plan format had no check on DR's side, so a field mismatch blocked the whole import. "Accept 105 ready" hung for minutes with no spinner, because the vector index wrote on a second connection inside the apply (fixed in #1441). Context Studio only learns of DR's retirements when someone re-imports, so drift built up to 477 types |
| 2026-11-06 | Documentation Robotics | Gate C #2: DR's api-layer rules pass (proposal 177ff609, 113 ops: 25 renames, 88 deletes), same path, landed in the same PR as #1 | 0 on import. 0 field edits in review; 113/113 accepted as proposed, with 1 in-use delete resolved (dropped). Landed by the same script | 0 new: the catch-up from #1 covered it. A re-import after #1029 merged reports none | 2 min from first to last decision (20:56 to 20:58 UTC), after the #1441 fix; 5h14m from proposal to DR merge | n/a in review; DR-side context not recorded | 113 ops in 2 min is bulk acceptance; the review can't tell a skimmed accept from a considered one |

**Gate B reading (2026-11-05).** Context Studio wins on hand edits at review and on decisions captured:

- Tasks 1 and 2 accepted 24/24 ops unchanged, though 21 of task 1's 22 went through in 2m07s, so this is partly bulk acceptance. Task 3's 24 kit edges were rejected on scope, and its 21 auto-applied resources were reverted.
- Every decision is saved with its operation's rationale and evidence, plus the reviewer's reason or in-use resolution where there was one. A reverted proposal's decisions are no longer exported.
- House's round trip closed at zero ops, and revert worked.

Quality held: DR validation passes in CI on documentation_robotics#993, and locally on #995 (`npm run build:spec:validate`), which is not merged yet. House evals were not run.

Landing changes in the project still cost hand work, so three frictions were fixed before Phase C (#1397–#1399):

- Applying a DR decision still means hand-editing spec files. The export script handles only triple decisions, and Context Studio has no fields for evidence, cardinality or strength.
- Review doesn't flag when a delete's replacement links a different pair of element types. The rationale names the replacement, but nothing marks the change of pair. That is how task 1 missed row 17.
- Approval policies can't auto-apply bundle imports.

**Gate C reading (2026-11-07).** Context Studio wins on hand edits and decisions captured on the client-driven path, where DR proposes and Context Studio adjudicates:

- Tasks 1 and 2 accepted 221/221 ops with no field edits. Four in-use deletes were resolved in review, and both passes landed in DR from the export through `cs-decisions-to-spec.ts`, where Gate B's tasks needed hand-edited spec files.
- Every decision is saved as gold with `decided_at`, the reviewer and any in-use resolution.
- After documentation_robotics#1029 merged, a re-import created nothing and found nothing stale: the workspace and DR's spec agree at 975 relationship types.

Quality held: CI passed on documentation_robotics#1029. House evals were not run, and House has not pushed a proposal yet, so House's part of the gate is still open.

One direction changed during the gate. Context Studio ran its own reflections on DR's motivation layer (b8ca98d2, 09121a29) and House (76663213), and they collided with DR's own motivation pass (documentation_robotics#1007). The rule now is that the client codebases originate proposals and Context Studio only adjudicates. 09121a29 was reverted and 76663213 rejected; b8ca98d2 had already been applied, and the clean re-import shows the workspace matches what DR landed.

The frictions the log names:

- A bulk apply hung with no progress shown. Fixed in #1441.
- Context Studio learns of a client's retirements only on a manual re-import, so drift built up to 477 types before the pass.
- Review usability: inspector order, definition overlays and conflict selection (#1439); in-use covered edges and edited delete targets (#1438); predicate retirements round trip (#1440).
- Bulk acceptance can't be told from considered review in the record.

## Decisions to make

Nine choices set the shape of the work. Each has a recommendation; the alternative is the realistic other option.

| Question | Recommendation | Alternative |
| --- | --- | --- |
| Where is the source of truth? | The repo releases and Context Studio refines. Import is idempotent and reports drift when the repo was edited by hand | Context Studio as sole source, repo files fully generated (revisit once trusted) |
| How much can agents write? | Proposals only, with a per-taxonomy policy that may let editorial changes apply directly | Direct writes, with revert as the safety net |
| How does Claude Code connect? | An MCP endpoint on the running local server, added with `claude mcp add --transport http` | A stdio server that opens the SQLite files itself (a second writer) |
| Which decision model? | Clef on Workers AI, opt-in in `config.json`, with an LLM fallback | LLM only: simpler, about 10 times the cost, poorly calibrated |
| How much of House? | The schema and starter vocabulary first | Also audit each group's live vocabulary through House's MCP server |
| One workspace or many? | One database, one taxonomy per project | Build real multi-workspace support first |
| Where does refinement state live? | `operations.db` for runs; decisions and change records exported to the project repo for audit | JSONL files in git, as DR does today |
| What happens to DR's scripts? | Context Studio loads their data and runs the next tier; the scripts stay as the reference until Context Studio matches them | Port every script before using Context Studio |
| What happens to the open streams? | Fold stream 3 (#1314–#1317) into the proposal and refinement work, since #1316 becomes "decisions as gold". Hold stream 4 (#1318–#1321) except #1320 | Finish streams 3 and 4 first |

## Sources

Local checkouts as of this date; DR on branch `feature/extraction-eval-harness`, including uncommitted migration work.

- DR: `spec/DESIGN_CHARTER.md`, `docs/EXTRACTION_STRATEGY.md`, `cli/scripts/spec-enrich/README.md`, `cli/scripts/classify-eval/README.md`, `cli/scripts/classify-eval/backends/clef.ts`, `cli/scripts/spec-enrich/data/triage/reflect/clef/plan-clef.md`, `cli/src/core/relationship-migration.ts`
- House: `docs/ONTOLOGY.md`, `docs/ROADMAP.md`, `docs/LIBRARY.md`, `docs/plans/`, `services/graph/src/{contract,rules,schema,guidance,starter,resolve}.ts`, `apps/house/src/tools/index.ts`, `apps/house/evals/`, plus a read-only look at the live vocabulary through House's MCP tools
- Context Studio: `local-server/domain/ontology/entities.py`, `local-server/domain/chat/services.py`, `local-server/adapters/chat/tools.py`, `local-server/domain/versioning/`, `local-server/adapters/web/`, `documentation/karpathy_loop_design.md`, open milestones 3 and 4
