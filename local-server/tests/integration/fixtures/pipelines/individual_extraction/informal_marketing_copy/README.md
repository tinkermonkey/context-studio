# Informal Fixture: Waypoint Blog/Marketing Copy

**Source:** Originally authored blog-post-style marketing copy for
"Waypoint," the same fictional field-service scheduling and dispatch
platform used by the Wave 2/3 SME corpus (fictional product, written in the
register of a company blog post pitching a feature -- narrative,
benefit-led, never written with an ontology or architecture model in mind).
**Wave:** 4 -- informal/incidental prose scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §8, #1109 Phase 8).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** incidental data-store (database) and motivation (value)
touches -- a backend concept and a company value both leak into copy that
is otherwise pure narrative.

## Overview

Ground truth was hand-adjudicated directly against this scenario's own
text, per the prose-only sourcing rule (design doc §3). This is
deliberately the sparsest fixture in the corpus: only two individuals in
the entire piece are named clearly enough, and boundaried tightly enough,
to ground as DR individuals. See Findings below -- the sparseness itself is
the primary finding this scenario produces, not a defect in the
fixture.

## Distractors

`distractors.json` contains two invented triples an over-eager extractor
might produce: "Job Event Store satisfies Customer Trust" (no DR
relationship schema connects `data-store.database` to `motivation.value`
directly -- bridging a backend entity to a business value would require an
intermediate `requirement`, which this text never names, unlike Wave 2's
`sme_waypoint_product_vision` scenario, which explicitly chains
driver -> goal -> requirement -> value); and "missed appointments cut in
half" reified as its own `motivation.outcome` individual (see Findings --
this is a narrativized result, not a named entity).

## Findings

This scenario is the clearest illustration in the corpus of the design
doc's prediction (§8): "marketing hyperbole with no clean class mapping."

- **Extreme sparsity.** Two triples, both `is_a`, zero relationships. Job
  Event Store is a proper noun carried over from Wave 3's
  `sme_waypoint_tech_database_selection` engineering-note scenario, and it
  grounds just as cleanly here -- proper technical nouns survive register
  changes. Customer Trust is a proper noun carried over from Wave 2's
  `sme_waypoint_product_vision` scenario and grounds just as cleanly too.
  Nothing else in the piece clears the bar.
- **Paraphrased outcomes lack a nominal boundary.** "customers tell us
  they've cut missed appointments in half" describes the same result Wave
  2 names explicitly as the individual "Missed-Appointment Rate Cut in
  Half," but here it is dissolved into a sentence with no candidate proper
  noun -- is the individual "cutting missed appointments in half," "missed
  appointments," or the whole clause? None of those are defensible as a
  single bounded label, so this was excluded from ground truth rather than
  forced. This is a genuinely open question for the extraction pipeline,
  not just for hand-labeling: whether some claim/result mentions should be
  captured as a lower-confidence individual with a paraphrased label is a
  candidate for future extraction-mechanics work, not something this
  ground truth should paper over by inventing a canonical label the text
  doesn't supply.
- **Generic, unnamed references are not individuals.** "every login
  screen, every offline sync, every dashboard alert" reads like class-level
  gestures (there could be many login screens, many syncs, many alerts),
  not references to one specific individual the way "Sync Status Banner" or
  "Waypoint Operations Dashboard" are in the other Wave 4 scenarios. No
  triples were added for any of them.
- **No architecturally valid bridge exists for the piece's central causal
  claim.** The whole post's thesis -- that the Job Event Store's offline
  durability is *why* customers trust Waypoint -- is exactly the kind of
  connection a human reader draws instantly but the DR relationship schema
  set has no direct edge for (see Distractors). Grounding it correctly
  would require the text to state the missing intermediate
  (`motivation.requirement`), which marketing copy has no reason to name.
