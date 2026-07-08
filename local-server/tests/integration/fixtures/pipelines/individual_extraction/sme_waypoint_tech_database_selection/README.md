# SME Fixture: Waypoint Job Event Data Store

**Source:** Originally authored backend-engineering-note prose for "Waypoint,"
a plausible field-service scheduling and dispatch platform (fictional
product, written in the register of a typical internal engineering design
note), continuing the same fictional product used by the Wave 2 corpus.
**Wave:** 3 -- lower-layer/technical SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §7, #1109 Phase 7).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** data-store (database, collection, field, accesspattern,
index, retentionpolicy), with incidental technology (node, systemsoftware,
technologyservice) and motivation (requirement) touches where the data-store
layer's own relationship schemas cross into those layers (e.g.
`data-store.database.depends-on.technology.systemsoftware`,
`data-store.retentionpolicy.uses.technology.technologyservice`).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- there is no LLM-drafted
intermediate ground truth to review here, same discipline as Wave 2. Every
`is_a` triple's object is a real DR node-schema id (e.g.
`data-store.accesspattern`) and every relationship triple's
`(subject_class, predicate, object_class)` combination was checked against a
real DR relationship schema (e.g.
`data-store.index.optimizes.data-store.accesspattern`) before being
included.

This scenario is denser and more jargon-heavy than the Wave 2 product-vision
prose (index/field/access-pattern indexing design nuances rather than
motivation/business narrative), which is intentional -- design doc §7 calls
this out as the expected stress difference between the two waves.

Every fact scored in `expected.json` is stated explicitly in `input.json`'s
text -- ground truth is not backfilled from anything outside the prose
itself, consistent with the prose-only sourcing rule (design doc §3).

## Distractors

`distractors.json` contains three near-misses an extractor might
over-generate: the access pattern "using" the compound index (the text says
the index optimizes the access pattern, the reverse direction), the database
itself "using" the archival service (the text states that relationship for
the retention policy, not the database directly), and the DocumentDB Engine
misclassified as a `technology.node` instead of the `technology.systemsoftware`
it actually is.
