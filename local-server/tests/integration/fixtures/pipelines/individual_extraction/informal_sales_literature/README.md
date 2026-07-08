# Informal Fixture: Waypoint Sales One-Pager

**Source:** Originally authored sales-collateral prose for "Waypoint," the
same fictional field-service scheduling and dispatch platform used by the
Wave 2/3 SME corpus (fictional product, written in the register of a
prospect-facing sales one-pager -- confident, benefit-led, and never
written with an ontology in mind).
**Wave:** 4 -- informal/incidental prose scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §8, #1109 Phase 8).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** business (product, businessservice, contract), with an
incidental apm touch (dashboard) where the copy briefly leaks an
operational detail into an otherwise customer-facing pitch.

## Overview

Ground truth was hand-adjudicated directly against this scenario's own
text, per the prose-only sourcing rule (design doc §3). Every `is_a`
triple's object is a real DR node-schema id and every relationship triple's
`(subject_class, predicate, object_class)` combination was checked against
a real DR relationship schema (`business.product.aggregates.
business.businessservice`, `business.product.composes.business.contract`)
before being included.

## Distractors

`distractors.json` contains three plausible over-generations: the Service
Level Agreement "governing" Work Order Management (Wave 2's
`sme_waypoint_business_operations` scenario states that relationship for
the *same-named* contract, but this document never says which service its
SLA governs -- an extractor that carries the fact over from a different
document, rather than grounding only in this text, would over-generate
it); "bank-level encryption" reified as a `security.securitypolicy`
individual (marketing hyperbole with no clean class mapping -- see
Findings); and the Waypoint Operations Dashboard "monitoring" Scheduling &
Dispatch (plausible-sounding, but `business.businessservice` is not a valid
object type for any `apm.dashboard.monitors.*` relationship schema --
dashboards monitor spans, metrics, operations, alerts, and log records, not
business services directly).

## Findings

This is the design doc's predicted failure mode in miniature (§8: "marketing
hyperbole with no clean class mapping"):

- **"Bank-level encryption"** gestures at a real security control but has
  no DR node it can be honestly mapped to without inventing detail the text
  never provides (which product, which algorithm, which layer). Excluded
  from ground truth entirely -- not even as a low-confidence `is_a`. This is
  a stronger case than a genuinely ambiguous mention: it is a rhetorical
  flourish, and grounding it as an individual would mean the ground truth
  crediting the pipeline for text that was never meant to describe a system
  component in the first place.
- **"Live map" / real-time technician location** clearly echoes Wave 2's
  `sme_waypoint_business_operations` requirement ("Real-Time Technician
  Location Visibility"), but this document never uses that phrase or names
  a requirement -- it just describes the customer-visible effect. No triple
  was added for it, consistent with the prose-only-per-scenario rule: two
  documents describing the same underlying system are not the same ground
  truth.
- **The dashboard mention** is the one clean technical leak into otherwise
  non-technical copy -- "Waypoint Operations Dashboard" is a proper noun
  and grounds cleanly as `apm.dashboard`, but the text never says *what* it
  monitors, so no relationship triple was added for it (see the third
  distractor above).
