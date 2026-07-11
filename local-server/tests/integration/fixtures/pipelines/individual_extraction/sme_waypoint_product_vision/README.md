# SME Fixture: Waypoint Product Vision

**Source:** Originally authored product-vision prose for "Waypoint," a
plausible field-service scheduling and dispatch platform (fictional product,
written in the register of a typical product vision document).
**Wave:** 2 -- upper-layer SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §6, #1109 Phase 6).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** motivation (all 10 motivation-layer node types are
represented at least once: assessment, constraint, driver, goal, meaning,
outcome, principle, requirement, stakeholder, value).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- there is no LLM-drafted
intermediate ground truth to review here. Every `is_a` triple's object is a
real DR node-schema id (e.g. `motivation.goal`) and every relationship
triple's `(subject_class, predicate, object_class)` combination was checked
against a real DR relationship schema (e.g.
`motivation.driver.influence.motivation.goal`) before being included; see
`documentation/karpathy_loop_dr_ontology_design.md` §6's SME-adjudication
requirement.

Every fact scored in `expected.json` is stated explicitly in `input.json`'s
text -- ground truth is not backfilled from anything outside the prose
itself, consistent with the prose-only sourcing rule carried forward from
Wave 1 (design doc §3).

## Distractors

`distractors.json` contains plausible-but-wrong triples an extractor might
over-generate: a stakeholder-to-goal association the text never states (only
a stakeholder-to-requirement association is stated), a stakeholder
misclassified as a driver, and an `outcome realizes goal` relationship with
the direction reversed from what the text actually says.
