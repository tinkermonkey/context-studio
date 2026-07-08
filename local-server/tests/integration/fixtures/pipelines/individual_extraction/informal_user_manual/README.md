# Informal Fixture: Waypoint Quick Start Guide

**Source:** Originally authored end-user quick-start-guide prose for
"Waypoint," the same fictional field-service scheduling and dispatch
platform used by the Wave 2/3 SME corpus (fictional product, written in the
register of a typical mobile-app onboarding guide handed to a new
technician -- not a UX specification).
**Wave:** 4 -- informal/incidental prose scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §8, #1109 Phase 8).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** ux (uxapplication, view, actioncomponent, errorconfig),
with an incidental business touch (businessrole) where the ux layer's own
relationship schemas cross into it (`ux.view.serves.business.businessrole`).

## Overview

This document describes the exact same technician app UI as Wave 2's
`sme_waypoint_technician_ux` scenario (same product, same screens, same
buttons), but in a different register: a quick-start guide written for a
new hire, not a UX spec written for an engineering audience. Ground truth
was hand-adjudicated directly against this scenario's own text -- per the
prose-only sourcing rule (design doc §3), nothing was backfilled from Wave
2's more detailed spec prose about the same product, even where an entity
happens to share a name.

## Distractors

`distractors.json` contains three near-misses: the Complete Job button
navigating to Job Detail (the text says View Job does the navigating;
Complete Job is a same-screen action), the Sync Status Banner "governing"
Today's Jobs (the text states the reverse relationship, `requires`, not
`governs` -- and `errorconfig.governs.view` is not even a real DR
relationship schema), and the Waypoint App directly aggregating Today's
Jobs (no DR relationship schema connects `ux.uxapplication` to `ux.view`
directly -- Wave 2's more detailed spec routes this through an intermediate
`ux.uxspec`, which this guide's casual "you'll land on Today's Jobs"
phrasing never mentions).

## Findings

Of the four wave-4 scenarios' genres, this one -- a step-by-step guide --
came closest to the SME-authored register: instructions naturally name the
screens and buttons a user taps, in order, so `is_a` and `aggregates`/
`navigates-to` triples were extractable almost as cleanly as Wave 2's UX
spec. The gaps that did show up:

- The guide never names a requirement or business event the way Wave 2's
  spec prose does (e.g. no "One-Tap Job Completion" requirement, no "Job
  Marked Complete" business event) -- "hit the button, and you're done" is
  a plain-language paraphrase of both, with no proper noun to extract.
  Nothing in `expected.json` corresponds to those two Wave 2 triples,
  because this text never names them, not because the extractor should
  infer them from the other document.
- The app itself ("Waypoint App") only earns an `is_a` triple, not a
  containment relationship to its screens -- the DR relationship schema set
  requires routing through `ux.uxspec` for that, and casual "you'll land
  on..." phrasing never surfaces the spec-level intermediate.
