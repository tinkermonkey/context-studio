# SME Fixture (Wave 5, SCAFFOLD): sme_waypoint_app_service_decomposition

> **STATUS: PROSE DRAFTED (review it) — GT NOT YET AUTHORED.** `input.json`
> holds candidate agent-drafted prose for you to review/edit; `expected.json`
> and `distractors.json` are still TODO templates for you to author. This
> scenario is **not** in the scored split yet (see graduation at the bottom).

**Intent:** Waypoint's application-layer decomposition: the components, the services they expose, the functions/processes they realize, and the data objects they act on.

**Source:** SME-authored prose for "Waypoint," the fictional field-service
scheduling/dispatch platform used by the Wave 2/3 corpus. Continue that product;
restate any entity introduced elsewhere (each scenario's GT must be
self-contained — prose-only sourcing rule, design doc §3).

**Wave:** 5 — SME-authored coverage-growth scenarios (holdout thickening +
`security`-layer coverage). Folded into the scored dev/holdout split on
graduation, like Wave 2/3 (NOT a diagnostic tier).

**Split:** `holdout` — gives the holdout veto power over the application layer (currently dev-only).

**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`).

**Layer focus:** `application`.

## DR class palette for this layer (is_a `object` targets)

Use these fully-qualified refs as the `object.label` on each individual's `is_a`
triple (full layer list: DR spec `schemas/nodes/application/`):

- `application.applicationcomponent`
- `application.applicationservice`
- `application.applicationfunction`
- `application.applicationprocess`
- `application.applicationinterface`
- `application.dataobject`
- `application.applicationcollaboration`

## Valid relationship predicates

Spec-valid `(subject_class, predicate, object_class)` edges sourced from this
scenario's classes. Object refs are fully qualified — a `application.` object stays
in this layer; anything else is a legitimate cross-layer edge you may use if the
prose supports it.

**Within this scenario's focused classes:**

- `application.applicationcollaboration` --aggregates--> `application.applicationcomponent`
- `application.applicationcollaboration` --delivers-value--> `application.applicationservice`
- `application.applicationcollaboration` --depends-on--> `application.applicationcomponent`
- `application.applicationcollaboration` --depends-on--> `application.applicationinterface`
- `application.applicationcollaboration` --depends-on--> `application.dataobject`
- `application.applicationcollaboration` --provides--> `application.applicationinterface`
- `application.applicationcomponent` --accesses--> `application.dataobject`
- `application.applicationcomponent` --assigned-to--> `application.applicationfunction`
- `application.applicationcomponent` --assigned-to--> `application.applicationinterface`
- `application.applicationcomponent` --composes--> `application.applicationfunction`
- `application.applicationcomponent` --provides--> `application.applicationinterface`
- `application.applicationcomponent` --realizes--> `application.applicationservice`
- `application.applicationcomponent` --uses--> `application.applicationcomponent`
- `application.applicationfunction` --accesses--> `application.dataobject`
- `application.applicationfunction` --delivers-value--> `application.applicationprocess`
- `application.applicationfunction` --delivers-value--> `application.applicationservice`
- `application.applicationfunction` --depends-on--> `application.applicationfunction`
- `application.applicationfunction` --depends-on--> `application.dataobject`
- `application.applicationfunction` --flows-to--> `application.applicationfunction`
- `application.applicationfunction` --realizes--> `application.applicationservice`
- `application.applicationinterface` --delivers-value--> `application.applicationcollaboration`
- `application.applicationinterface` --depends-on--> `application.applicationcomponent`
- `application.applicationinterface` --depends-on--> `application.applicationfunction`
- `application.applicationinterface` --depends-on--> `application.applicationservice`
- `application.applicationinterface` --depends-on--> `application.dataobject`
- `application.applicationinterface` --serves--> `application.applicationservice`
- `application.applicationprocess` --delivers-value--> `application.applicationservice`
- `application.applicationprocess` --depends-on--> `application.applicationcollaboration`
- `application.applicationprocess` --depends-on--> `application.applicationfunction`
- `application.applicationprocess` --depends-on--> `application.applicationinterface`
- …(+8 more in `schemas/relationships/application/`)

**To other application-layer classes:**

- `application.applicationcollaboration` --delivers-value--> `application.applicationinteraction`
- `application.applicationcollaboration` --depends-on--> `application.applicationinteraction`
- `application.applicationfunction` --depends-on--> `application.applicationevent`
- `application.applicationprocess` --depends-on--> `application.applicationevent`
- `application.applicationprocess` --triggers--> `application.applicationevent`

**Cross-layer edges:**

- `application.applicationcomponent` --accesses--> `security.secureresource`
- `application.applicationcomponent` --constrained-by--> `security.securitypolicy`
- `application.applicationcomponent` --implements--> `security.countermeasure`
- `application.applicationcomponent` --mitigates--> `security.threat`
- `application.applicationcomponent` --realizes--> `business.businessservice`
- `application.applicationcomponent` --realizes--> `motivation.goal`
- `application.applicationcomponent` --realizes--> `motivation.principle`
- `application.applicationcomponent` --satisfies--> `motivation.requirement`
- `application.applicationcomponent` --serves--> `business.businessrole`
- `application.applicationfunction` --accesses--> `security.secureresource`
- `application.applicationfunction` --realizes--> `business.businessfunction`
- `application.applicationfunction` --satisfies--> `motivation.requirement`
- `application.applicationinterface` --exposes--> `security.secureresource`
- `application.applicationinterface` --serves--> `business.businessrole`
- `application.applicationprocess` --realizes--> `business.businessprocess`
- …(+11 more in `schemas/relationships/application/`)

**Thin-tail predicates to deliberately exercise here:** (none specifically targeted) — the corpus
currently has <3 GT instances of these; using them stabilizes strict predicate
scoring.

## Authoring checklist

1. Write `input.json` `text`: a coherent application-focused note/spec about Waypoint.
2. `expected.json` `result.triples`: one `is_a` triple per distinct individual
   (object = a class ref above), then relationship triples between individuals
   (predicates from the lists above). Every triple must be text-supported;
   `confidence: 1.0`. Delete the `_comment` template objects.
3. `expected.json` `result.excluded`: >=1 true-negative (a plausible edge the
   text contradicts) with a `note`.
4. `distractors.json`: one near-miss triple (confidence ~0.2).
5. Aim for ~15-25 triples (matches the Wave 2/3 scenarios).

## Graduation (moves it into the scored split)

Once GT is authored:
1. Record its `default` cassette: `pytest --refresh-cassettes -k "test_quality_scenario_with_metrics and sme_waypoint_app_service_decomposition"` (needs live LLM).
2. In `_harness/dataset_split.py`, move `"sme_waypoint_app_service_decomposition"` from `WAVE5_PENDING_SCENARIOS` into `WAVE5_SME_HOLDOUT_SCENARIOS` (uncomment the wiring) so it joins `INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS` + `SCENARIO_ONTOLOGY`.
3. `pytest tests/unit/test_harness_dataset_split.py` to confirm the split is valid.
