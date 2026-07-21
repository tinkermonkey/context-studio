# SME Fixture (Wave 5, SCAFFOLD): sme_waypoint_navigation_dispatch_flow

> **STATUS: SCAFFOLD — GT NOT YET AUTHORED.** `input.json`, `expected.json`, and
> `distractors.json` contain TODO templates. This scenario is **not** in the
> scored split yet (see the graduation checklist at the bottom).

**Intent:** A dispatcher's navigation flow through Waypoint: the routes, the flow steps between them, and the guard conditions gating each transition.

**Source:** SME-authored prose for "Waypoint," the fictional field-service
scheduling/dispatch platform used by the Wave 2/3 corpus. Continue that product;
restate any entity introduced elsewhere (each scenario's GT must be
self-contained — prose-only sourcing rule, design doc §3).

**Wave:** 5 — SME-authored coverage-growth scenarios (holdout thickening +
`security`-layer coverage). Folded into the scored dev/holdout split on
graduation, like Wave 2/3 (NOT a diagnostic tier).

**Split:** `holdout` — gives the holdout veto power over the navigation layer (currently dev-only).

**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`).

**Layer focus:** `navigation`.

## DR class palette for this layer (is_a `object` targets)

Use these fully-qualified refs as the `object.label` on each individual's `is_a`
triple (full layer list: DR spec `schemas/nodes/navigation/`):

- `navigation.route`
- `navigation.navigationflow`
- `navigation.flowstep`
- `navigation.guardcondition`
- `navigation.navigationguard`
- `navigation.navigationtransition`
- `navigation.guardaction`
- `navigation.contextvariable`

## Valid relationship predicates

Spec-valid `(subject_class, predicate, object_class)` edges sourced from this
scenario's classes. Object refs are fully qualified — a `navigation.` object stays
in this layer; anything else is a legitimate cross-layer edge you may use if the
prose supports it.

**Within this scenario's focused classes:**

- `navigation.contextvariable` --consumes--> `navigation.route`
- `navigation.contextvariable` --flows-to--> `navigation.flowstep`
- `navigation.contextvariable` --triggers--> `navigation.navigationtransition`
- `navigation.flowstep` --consumes--> `navigation.contextvariable`
- `navigation.flowstep` --navigates-to--> `navigation.route`
- `navigation.flowstep` --realizes--> `navigation.route`
- `navigation.flowstep` --requires--> `navigation.navigationguard`
- `navigation.flowstep` --triggers--> `navigation.navigationtransition`
- `navigation.guardaction` --depends-on--> `navigation.guardcondition`
- `navigation.guardaction` --navigates-to--> `navigation.route`
- `navigation.guardaction` --uses--> `navigation.contextvariable`
- `navigation.guardcondition` --constrains--> `navigation.route`
- `navigation.guardcondition` --consumes--> `navigation.contextvariable`
- `navigation.guardcondition` --triggers--> `navigation.guardaction`
- `navigation.guardcondition` --uses--> `navigation.contextvariable`
- `navigation.navigationflow` --aggregates--> `navigation.contextvariable`
- `navigation.navigationflow` --aggregates--> `navigation.flowstep`
- `navigation.navigationflow` --composes--> `navigation.flowstep`
- `navigation.navigationflow` --flows-to--> `navigation.navigationtransition`
- `navigation.navigationflow` --requires--> `navigation.navigationguard`
- `navigation.navigationguard` --constrains--> `navigation.navigationtransition`
- `navigation.navigationguard` --consumes--> `navigation.contextvariable`
- `navigation.navigationguard` --evaluates--> `navigation.guardcondition`
- `navigation.navigationguard` --intercepts--> `navigation.navigationflow`
- `navigation.navigationguard` --protects--> `navigation.route`
- `navigation.navigationguard` --triggers--> `navigation.guardaction`
- `navigation.navigationguard` --uses--> `navigation.guardcondition`
- `navigation.navigationtransition` --flows-to--> `navigation.route`
- `navigation.navigationtransition` --navigates-to--> `navigation.route`
- `navigation.navigationtransition` --requires--> `navigation.navigationguard`
- …(+6 more in `schemas/relationships/navigation/`)

**To other navigation-layer classes:**

- `navigation.guardcondition` --references--> `navigation.routemeta`
- `navigation.route` --associated-with--> `navigation.routemeta`
- `navigation.route` --composes--> `navigation.routemeta`

**Cross-layer edges:**

- `navigation.contextvariable` --maps-to--> `api.parameter`
- `navigation.contextvariable` --maps-to--> `data-model.schemaproperty`
- `navigation.contextvariable` --references--> `application.dataobject`
- `navigation.contextvariable` --references--> `data-model.jsonschema`
- `navigation.flowstep` --accesses--> `application.applicationservice`
- `navigation.flowstep` --accesses--> `data-store.collection`
- `navigation.flowstep` --accesses--> `data-model.objectschema`
- `navigation.flowstep` --accesses--> `api.operation`
- `navigation.flowstep` --maps-to--> `ux.view`
- `navigation.flowstep` --realizes--> `business.businessfunction`
- `navigation.flowstep` --satisfies--> `motivation.requirement`
- `navigation.guardcondition` --references--> `data-model.objectschema`
- `navigation.guardcondition` --references--> `security.permission`
- `navigation.navigationflow` --accesses--> `data-store.collection`
- `navigation.navigationflow` --accesses--> `data-model.objectschema`
- …(+49 more in `schemas/relationships/navigation/`)

**Thin-tail predicates to deliberately exercise here:** `flows-to`, `references` — the corpus
currently has <3 GT instances of these; using them stabilizes strict predicate
scoring.

## Authoring checklist

1. Write `input.json` `text`: a coherent navigation-focused note/spec about Waypoint.
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
1. Record its `default` cassette: `pytest --refresh-cassettes -k "test_quality_scenario_with_metrics and sme_waypoint_navigation_dispatch_flow"` (needs live LLM).
2. In `_harness/dataset_split.py`, move `"sme_waypoint_navigation_dispatch_flow"` from `WAVE5_PENDING_SCENARIOS` into `WAVE5_SME_HOLDOUT_SCENARIOS` (uncomment the wiring) so it joins `INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS` + `SCENARIO_ONTOLOGY`.
3. `pytest tests/unit/test_harness_dataset_split.py` to confirm the split is valid.
