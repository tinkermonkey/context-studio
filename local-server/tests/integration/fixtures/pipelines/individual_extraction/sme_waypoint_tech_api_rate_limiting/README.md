# SME Fixture: Waypoint Assign Job Endpoint Rate Limiting

**Source:** Originally authored backend-engineering-note prose for "Waypoint,"
a plausible field-service scheduling and dispatch platform (fictional
product, written in the register of a typical internal engineering design
note), continuing the same fictional product used by the Wave 2 corpus.
**Wave:** 3 -- lower-layer/technical SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §7, #1109 Phase 7).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** api (operation, ratelimit, securityscheme) and apm
(traceconfiguration, metricinstrument, exporterconfig), with incidental
technology (systemsoftware, technologyservice) and motivation (constraint)
touches where the api/apm layers' own relationship schemas cross into those
layers (e.g. `api.ratelimit.uses.technology.systemsoftware`,
`apm.traceconfiguration.depends-on.technology.technologyservice`).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- no LLM-drafted intermediate
ground truth, same discipline as Wave 2. Every relationship triple's
`(subject_class, predicate, object_class)` combination was checked against a
real DR relationship schema before being included.

The text also contains one explicit negation -- the Dispatcher Burst Rate
Limit governs the Assign Job Operation only, **not** the Assignment Fan-Out
Service the operation separately uses -- captured as an `excluded` triple in
`expected.json` so an extractor that over-generates the wrong governance
scope is penalized rather than credited.

## Distractors

`distractors.json` contains two near-misses: the Assign Job Latency
Histogram depending directly on the Telemetry Pipeline Service (the text
states that dependency for the trace configuration, not the histogram), and
the Assign Job Operation referencing the histogram directly (the text says
the operation references the trace configuration, which in turn aggregates
the histogram -- the operation-to-histogram link is never stated).
