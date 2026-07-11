# SME Fixture: Waypoint Database Saturation Alerting

**Source:** Originally authored backend-engineering-note prose for "Waypoint,"
a plausible field-service scheduling and dispatch platform (fictional
product, written in the register of a typical internal engineering design
note), continuing the same fictional product used by the Wave 2 corpus and
the Job Event Store introduced in the `sme_waypoint_tech_database_selection`
scenario (restated here explicitly, since each scenario's ground truth must
be self-contained and stated in its own text -- see the prose-only sourcing
rule, design doc §3).
**Wave:** 3 -- lower-layer/technical SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §7, #1109 Phase 7).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** apm (resource, metricinstrument, alert, dashboard), with
incidental technology (node, systemsoftware) and data-store (database)
touches where the apm layer's own relationship schemas cross into those
layers (e.g. `apm.resource.monitors.technology.node`,
`apm.metricinstrument.monitors.data-store.database`).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- no LLM-drafted intermediate
ground truth, same discipline as Wave 2. Every relationship triple's
`(subject_class, predicate, object_class)` combination was checked against a
real DR relationship schema before being included.

The text also contains one explicit negation -- the Connection Pool
Saturation Alert monitors the gauge, **not** the Job Event Store directly --
captured as an `excluded` triple in `expected.json` so an extractor that
collapses the alert-to-gauge-to-database chain into a direct alert-to-database
edge is penalized rather than credited.

## Distractors

`distractors.json` contains one near-miss: the Database Health Dashboard
monitoring the Job Event Store Resource directly (the text states the
dashboard monitors the alert and the gauge, never the underlying resource
record itself).
