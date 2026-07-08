# SME Fixture: Waypoint Job Payload Schema Contract

**Source:** Originally authored backend-engineering-note prose for "Waypoint,"
a plausible field-service scheduling and dispatch platform (fictional
product, written in the register of a typical internal engineering design
note), continuing the same fictional product used by the Wave 2 corpus.
**Wave:** 3 -- lower-layer/technical SME-authored scenarios
(`documentation/karpathy_loop_dr_ontology_design.md` §7, #1109 Phase 7).
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not the
placeholder.
**Layer focus:** data-model (jsonschema, objectschema, schemaproperty,
schemadefinition), with incidental api (schema), data-store (collection),
technology (systemsoftware), and motivation (requirement, goal) touches
where the data-model layer's own relationship schemas cross into those
layers (e.g. `data-model.jsonschema.realizes.api.schema`,
`data-model.schemadefinition.maps-to.data-store.collection`).

## Overview

`expected.json` was hand-adjudicated directly against the Wave 0 DR
ontology's classes and relationship types -- no LLM-drafted intermediate
ground truth, same discipline as Wave 2. Every relationship triple's
`(subject_class, predicate, object_class)` combination was checked against a
real DR relationship schema before being included.

This scenario is the densest of the Wave 3 batch in relationships-per-entity
terms -- a single small paragraph states four distinct `maps-to`/`realizes`
cross-layer links -- which is exactly the "tighter relationship graphs per
sentence" stress design doc §7 predicts for technical prose relative to
Wave 2.

This is the Wave 3 holdout scenario (see `WAVE3_SME_HOLDOUT_SCENARIOS` in
`tests/integration/pipelines/_harness/dataset_split.py`).

## Distractors

`distractors.json` contains two near-misses: the Job Priority Property
mapping directly to the Job API Schema (the text never states a mapping for
either schema property -- only the Address Sub-Schema is stated to map to
anything), and the Job Core Object Schema mapping to the Jobs Collection
(the text states that mapping for the Address Sub-Schema specifically, not
for the object schema that aggregates it).
