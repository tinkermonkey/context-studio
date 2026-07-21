# SME Fixture (Wave 5, SCAFFOLD): sme_waypoint_apm_incident_response

> **STATUS: PROSE DRAFTED + `is_a` TRIPLES PREFILLED — RELATIONSHIP GT NOT YET
> AUTHORED.** `input.json` holds candidate prose (review/edit); `expected.json`
> has one `is_a` typing triple per named individual (review them) plus a TODO
> placeholder where you add the relationship triples + the `excluded`
> true-negative; `distractors.json` is still a TODO template. This scenario is
> **not** in the scored split yet (see graduation at the bottom).

**Intent:** Waypoint's incident-response observability: the monitored resources, metric instruments, alerts, traces, and dashboards used during a dispatch-volume incident.

**Source:** SME-authored prose for "Waypoint," the fictional field-service
scheduling/dispatch platform used by the Wave 2/3 corpus. Continue that product;
restate any entity introduced elsewhere (each scenario's GT must be
self-contained — prose-only sourcing rule, design doc §3).

**Wave:** 5 — SME-authored coverage-growth scenarios (holdout thickening +
`security`-layer coverage). Folded into the scored dev/holdout split on
graduation, like Wave 2/3 (NOT a diagnostic tier).

**Split:** `holdout` — gives the holdout veto power over the apm layer (currently dev-only).

**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`).

**Layer focus:** `apm`.

## DR class palette for this layer (is_a `object` targets)

Use these fully-qualified refs as the `object.label` on each individual's `is_a`
triple (full layer list: DR spec `schemas/nodes/apm/`):

- `apm.resource`
- `apm.metricinstrument`
- `apm.alert`
- `apm.dashboard`
- `apm.traceconfiguration`
- `apm.span`
- `apm.logrecord`
- `apm.exporterconfig`

## Valid relationship predicates

Spec-valid `(subject_class, predicate, object_class)` edges sourced from this
scenario's classes. Object refs are fully qualified — a `apm.` object stays
in this layer; anything else is a legitimate cross-layer edge you may use if the
prose supports it.

**Within this scenario's focused classes:**

- `apm.alert` --monitors--> `apm.logrecord`
- `apm.alert` --monitors--> `apm.metricinstrument`
- `apm.alert` --monitors--> `apm.span`
- `apm.dashboard` --monitors--> `apm.alert`
- `apm.dashboard` --monitors--> `apm.logrecord`
- `apm.dashboard` --monitors--> `apm.metricinstrument`
- `apm.dashboard` --monitors--> `apm.span`
- `apm.exporterconfig` --serves--> `apm.resource`
- `apm.logrecord` --depends-on--> `apm.resource`
- `apm.logrecord` --references--> `apm.span`
- `apm.metricinstrument` --depends-on--> `apm.resource`
- `apm.metricinstrument` --flows-to--> `apm.exporterconfig`
- `apm.metricinstrument` --flows-to--> `apm.span`
- `apm.metricinstrument` --references--> `apm.span`
- `apm.resource` --aggregates--> `apm.exporterconfig`
- `apm.resource` --aggregates--> `apm.metricinstrument`
- `apm.resource` --aggregates--> `apm.span`
- `apm.span` --composes--> `apm.metricinstrument`
- `apm.span` --composes--> `apm.traceconfiguration`
- `apm.span` --depends-on--> `apm.resource`
- `apm.span` --flows-to--> `apm.exporterconfig`
- `apm.span` --flows-to--> `apm.span`
- `apm.span` --references--> `apm.span`
- `apm.traceconfiguration` --aggregates--> `apm.exporterconfig`
- `apm.traceconfiguration` --aggregates--> `apm.metricinstrument`
- `apm.traceconfiguration` --aggregates--> `apm.span`

**To other apm-layer classes:**

- `apm.logrecord` --depends-on--> `apm.instrumentationscope`
- `apm.logrecord` --flows-to--> `apm.logprocessor`
- `apm.metricinstrument` --depends-on--> `apm.instrumentationscope`
- `apm.metricinstrument` --flows-to--> `apm.logprocessor`
- `apm.span` --aggregates--> `apm.spanlink`
- `apm.span` --composes--> `apm.spanevent`
- `apm.span` --depends-on--> `apm.instrumentationscope`
- `apm.span` --flows-to--> `apm.logprocessor`

**Cross-layer edges:**

- `apm.alert` --monitors--> `api.operation`
- `apm.alert` --monitors--> `api.ratelimit`
- `apm.dashboard` --monitors--> `api.operation`
- `apm.exporterconfig` --depends-on--> `technology.technologyservice`
- `apm.exporterconfig` --satisfies--> `motivation.requirement`
- `apm.exporterconfig` --satisfies--> `security.retentionpolicy`
- `apm.exporterconfig` --serves--> `data-store.database`
- `apm.logrecord` --monitors--> `application.applicationservice`
- `apm.logrecord` --references--> `data-model.objectschema`
- `apm.logrecord` --references--> `navigation.route`
- `apm.logrecord` --references--> `data-model.schemadefinition`
- `apm.logrecord` --references--> `ux.view`
- `apm.logrecord` --satisfies--> `security.accountabilityrequirement`
- `apm.metricinstrument` --maps-to--> `motivation.outcome`
- `apm.metricinstrument` --monitors--> `ux.actioncomponent`
- …(+47 more in `schemas/relationships/apm/`)

**Thin-tail predicates to deliberately exercise here:** (none specifically targeted) — the corpus
currently has <3 GT instances of these; using them stabilizes strict predicate
scoring.

## Authoring checklist

1. Write `input.json` `text`: a coherent apm-focused note/spec about Waypoint.
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
1. Record its `default` cassette: `pytest --refresh-cassettes -k "test_quality_scenario_with_metrics and sme_waypoint_apm_incident_response"` (needs live LLM).
2. In `_harness/dataset_split.py`, move `"sme_waypoint_apm_incident_response"` from `WAVE5_PENDING_SCENARIOS` into `WAVE5_SME_HOLDOUT_SCENARIOS` (uncomment the wiring) so it joins `INDIVIDUAL_EXTRACTION_HOLDOUT_SCENARIOS` + `SCENARIO_ONTOLOGY`.
3. `pytest tests/unit/test_harness_dataset_split.py` to confirm the split is valid.
